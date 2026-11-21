"""Single-H100 completion-only LoRA pilot. Run with CUDA_VISIBLE_DEVICES=0."""
import argparse
import json
import math
import random
import time
from pathlib import Path

import torch
from peft import LoraConfig, PeftModel, get_peft_model
from svg_model import get_tokenizer, load_base, prompt_tokens


def read_split(path, tokenizer):
    records = []
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            row = json.loads(line)
            prompt = prompt_tokens(tokenizer, row["description"])
            completion = tokenizer.encode(row["svg"] + "</s>", add_special_tokens=False).ids
            assert len(prompt) + len(completion) == row["tokens"] <= 8192
            records.append((prompt + completion, len(prompt)))
    return records


def loss(model, item):
    ids, prefix = item
    inputs = torch.tensor([ids], device="cuda")
    labels = inputs.clone()
    labels[:, :prefix] = -100
    return model(input_ids=inputs, labels=labels, use_cache=False).loss


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, default=Path("data"))
    parser.add_argument("--out", type=Path, default=Path("checkpoints"))
    parser.add_argument("--minutes", type=int, default=180)
    parser.add_argument("--init-adapter", type=Path, help="Continue training this PEFT checkpoint instead of a fresh LoRA")
    parser.add_argument("--lr", type=float, default=1e-4)
    parser.add_argument("--accum", type=int, default=8, help="Examples per optimizer update")
    parser.add_argument("--no-grad-ckpt", action="store_true", help="Faster if activations fit in memory")
    args = parser.parse_args()
    if args.init_adapter and any(args.out.glob("step-*")):
        parser.error(f"{args.out} already has step-* checkpoints; pass a fresh --out such as checkpoints-v2")
    torch.manual_seed(42)
    tokenizer = get_tokenizer()
    base = load_base()
    if args.init_adapter:
        model = PeftModel.from_pretrained(base, args.init_adapter, is_trainable=True)
    else:
        pattern = r".*language_model\.layers\.\d+\.(self_attn\.(q_proj|k_proj|v_proj|o_proj)|mlp\.(gate_proj|up_proj|down_proj))"
        adapter = LoraConfig(r=32, lora_alpha=64, target_modules=pattern, task_type="CAUSAL_LM")
        model = get_peft_model(base, adapter)
    model.print_trainable_parameters()
    if not args.no_grad_ckpt:
        model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})
    model.train()
    train = read_split(args.data / "train.jsonl", tokenizer)
    valid = read_split(args.data / "valid.jsonl", tokenizer)
    random.Random(42).shuffle(train)
    args.out.mkdir(parents=True, exist_ok=True)
    optimizer = torch.optim.AdamW((p for p in model.parameters() if p.requires_grad),
                                  lr=args.lr, weight_decay=0.01, fused=True)
    steps = math.ceil(len(train) / args.accum)
    warmup = max(1, round(steps * 0.03))
    start = time.monotonic()
    total = 0
    for step, offset in enumerate(range(0, len(train), args.accum), 1):
        batch = train[offset:offset + args.accum]
        batch_tokens = sum(len(ids) - prefix for ids, prefix in batch)
        factor = min(step / warmup, 1) * (1 + math.cos(math.pi * max(0, step - warmup) / max(1, steps - warmup))) / 2
        optimizer.param_groups[0]["lr"] = args.lr * factor
        optimizer.zero_grad(set_to_none=True)
        accumulated = torch.zeros((), device="cuda")
        for item in batch:
            with torch.autocast("cuda", dtype=torch.bfloat16):
                value = loss(model, item) * ((len(item[0]) - item[1]) / batch_tokens)
            value.backward()
            accumulated += value.detach()
        grad_norm = torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0, error_if_nonfinite=True)
        optimizer.step()
        total += sum(len(ids) for ids, _ in batch)
        seconds = time.monotonic() - start
        print(json.dumps(dict(step=step, loss=accumulated.item(), grad_norm=grad_norm.item(),
                              tokens=total, tokens_per_second=round(total / seconds),
                              peak_vram_gib=round(torch.cuda.max_memory_allocated() / 2**30, 2))), flush=True)
        finished = seconds >= args.minutes * 60 or step == steps
        if step in {1, 5, 10} or step % 50 == 0 or finished:
            temporary = args.out / f".writing-{step}"
            model.save_pretrained(temporary)
            temporary.rename(args.out / f"step-{step:04d}")
        if step % 100 == 0 or finished:
            model.eval()
            with torch.no_grad(), torch.autocast("cuda", dtype=torch.bfloat16):
                n = sum(len(ids) - prefix for ids, prefix in valid)
                val = sum(loss(model, item).item() * (len(item[0]) - item[1]) for item in valid) / n
            print(json.dumps(dict(step=step, validation_loss=val)), flush=True)
            model.train()
        if finished:
            break


if __name__ == "__main__":
    main()
