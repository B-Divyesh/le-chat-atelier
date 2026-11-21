"""Full fine-tune of the merged step-625 model (decoder layers, fp32 master weights) on short integer SVGs."""
import argparse, json, math, random, time
from pathlib import Path
import torch
import shutil
from transformers import Mistral3ForConditionalGeneration
from svg_model import get_tokenizer
import os
GRID = int(os.environ.get("GRID", "8"))
PIX_SYSTEM = (f"Draw the requested game sprite as {GRID}x{GRID} pixel art in the PICO-8 palette. "
              f"Reply with {GRID} lines of {GRID} characters: . is transparent, 0-f are palette colors.")
def prompt_tokens(tok, caption):
    return tok.encode(f"<s>[SYSTEM_PROMPT]{PIX_SYSTEM}[/SYSTEM_PROMPT][INST]{caption}[/INST]", add_special_tokens=False).ids

def read_split(path, tok):
    out = []
    for line in open(path, encoding="utf-8"):
        row = json.loads(line)
        p = prompt_tokens(tok, row["description"])
        c = tok.encode(row["svg"] + "\n</s>", add_special_tokens=False).ids
        out.append((p + c, len(p)))
    return out

def micro_batches(items, budget):
    """Group similar lengths so padding stays small; each group holds <= budget padded tokens."""
    items = sorted(items, key=lambda x: len(x[0]))
    groups, cur = [], []
    for it in items:
        if cur and len(it[0]) * (len(cur) + 1) > budget:
            groups.append(cur); cur = []
        cur.append(it)
    if cur: groups.append(cur)
    return groups

def batch_loss(model, group):
    L = max(len(ids) for ids, _ in group)
    ids = torch.zeros((len(group), L), dtype=torch.long); mask = torch.zeros_like(ids); labels = torch.full_like(ids, -100)
    for i, (seq, pre) in enumerate(group):
        t = torch.tensor(seq); ids[i, :len(seq)] = t; mask[i, :len(seq)] = 1; labels[i, pre:len(seq)] = t[pre:]
    ids, mask, labels = ids.cuda(), mask.cuda(), labels.cuda()
    n = int((labels[:, 1:] != -100).sum())
    return model(input_ids=ids, attention_mask=mask, labels=labels, use_cache=False).loss, n

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", type=Path, required=True); ap.add_argument("--init-model", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True); ap.add_argument("--lr", type=float, default=1e-4)
    ap.add_argument("--mb-tokens", type=int, default=8192); ap.add_argument("--update-tokens", type=int, default=32768)
    ap.add_argument("--ckpt", action="store_true"); ap.add_argument("--minutes", type=float, default=40)
    ap.add_argument("--epochs", type=float, default=1.0)
    a = ap.parse_args(); torch.manual_seed(42)
    tok = get_tokenizer()
    model = Mistral3ForConditionalGeneration.from_pretrained(a.init_model, dtype=torch.float32, attn_implementation="sdpa", device_map={"": 0})
    for name, prm in model.named_parameters():
        prm.requires_grad = ".language_model.layers." in name
    print("trainable", sum(p.numel() for p in model.parameters() if p.requires_grad), flush=True)
    if a.ckpt: model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})
    model.enable_input_require_grads() if a.ckpt else None
    model.train()
    train = read_split(a.data / "train.jsonl", tok); valid = read_split(a.data / "valid.jsonl", tok)
    groups = micro_batches(train, a.mb_tokens); rng = random.Random(42)
    sched = []
    for ep in range(math.ceil(a.epochs)):
        g = groups[:]; rng.shuffle(g); sched += g
    sched = sched[: int(len(groups) * a.epochs)]
    updates, cur, cur_tok = [], [], 0
    for g in sched:
        cur.append(g); cur_tok += sum(len(s) - p for s, p in g)
        if cur_tok >= a.update_tokens: updates.append(cur); cur, cur_tok = [], 0
    if cur: updates.append(cur)
    steps = len(updates); warm = max(1, round(steps * 0.03))
    print(json.dumps(dict(train=len(train), micro_batches=len(sched), updates=steps)), flush=True)
    opt = torch.optim.AdamW((p for p in model.parameters() if p.requires_grad), lr=a.lr, weight_decay=0.0, fused=True)
    a.out.mkdir(parents=True, exist_ok=True); start = time.monotonic(); seen = 0
    for step, upd in enumerate(updates, 1):
        f = min(step / warm, 1) * (1 + math.cos(math.pi * max(0, step - warm) / max(1, steps - warm))) / 2
        opt.param_groups[0]["lr"] = a.lr * f; opt.zero_grad(set_to_none=True)
        total = sum(sum(len(s) - p - 1 for s, p in g) for g in upd); acc = 0.0
        for g in upd:
            with torch.autocast("cuda", dtype=torch.bfloat16):
                loss, n = batch_loss(model, g)
            (loss * n / total).backward(); acc += loss.item() * n / total; seen += sum(len(s) for s, _ in g)
        gn = torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0); opt.step()
        sec = time.monotonic() - start
        print(json.dumps(dict(step=step, of=steps, loss=round(acc, 4), grad_norm=round(gn.item(), 3), tok_s=round(seen / sec),
                              peak_gib=round(torch.cuda.max_memory_allocated() / 2**30, 1), min=round(sec / 60, 1))), flush=True)
        done = step == steps or sec >= a.minutes * 60
        if done:
            tmp = a.out / f".writing-{step}"
            model.save_pretrained(tmp, state_dict={k: v.to(torch.bfloat16) for k, v in model.state_dict().items()})
            for f in a.init_model.iterdir():
                if f.suffix != ".safetensors" and not f.name.endswith(".index.json") and f.name != "config.json" and f.is_file():
                    shutil.copy(f, tmp / f.name)
            tmp.rename(a.out / f"step-{step:04d}")
        if step % 100 == 0 or done:
            model.eval()
            with torch.no_grad(), torch.autocast("cuda", dtype=torch.bfloat16):
                vs = [batch_loss(model, g) for g in micro_batches(valid, a.mb_tokens)]
            print(json.dumps(dict(step=step, validation_loss=round(sum(l.item() * n for l, n in vs) / sum(n for _, n in vs), 4))), flush=True)
            model.train()
        if done: break

if __name__ == "__main__":
    main()
