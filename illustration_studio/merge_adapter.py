"""Merge a LoRA checkpoint into the BF16 base and save an HF-format directory vLLM can serve.

    python merge_adapter.py checkpoints/step-0625 --out merged/step-0625

Runs on CPU by default so it never touches a GPU that is training or serving.
The vision tower is kept so the architecture matches vLLM's Mistral3 loader.
"""
import argparse
import shutil
from pathlib import Path

from svg_model import MODEL

# Written by save_pretrained, or Mistral-native files that would make vLLM pick the mistral format.
SKIP = {"config.json", "generation_config.json", "model.safetensors.index.json", "params.json", "tekken.json"}
NEED = 9 * 10**9


def free_bytes(path):
    path = path.resolve()
    while not path.exists():
        path = path.parent
    return shutil.disk_usage(path).free


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("adapter", type=Path, help="PEFT checkpoint directory, e.g. checkpoints/step-0625")
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--device", default="cpu", help="cpu (default) or e.g. cuda:0")
    p.add_argument("--force", action="store_true", help="Skip the free-disk check")
    args = p.parse_args()
    if not (args.adapter / "adapter_config.json").exists():
        p.error(f"{args.adapter} has no adapter_config.json")
    if args.out.exists() and any(args.out.iterdir()):
        p.error(f"{args.out} already exists and is not empty")
    free = free_bytes(args.out.parent)
    if free < NEED and not args.force:
        raise SystemExit(f"Only {free / 1e9:.1f} GB free under {args.out.parent.resolve()}; the merged model needs "
                         f"about 8 GB. Free space or pass --force.")

    import torch
    from huggingface_hub import snapshot_download
    from peft import PeftModel
    from transformers import Mistral3ForConditionalGeneration

    base = Mistral3ForConditionalGeneration.from_pretrained(MODEL, dtype=torch.bfloat16, device_map={"": args.device})
    merged = PeftModel.from_pretrained(base, args.adapter).merge_and_unload()
    merged.save_pretrained(args.out, safe_serialization=True)

    snapshot = Path(snapshot_download(MODEL, allow_patterns=["*.json", "*.jinja", "*.txt"],
                                      ignore_patterns=["params.json", "tekken.json", "consolidated*"]))
    copied = []
    for item in sorted(snapshot.iterdir()):
        target = args.out / item.name
        if item.is_file() and item.name not in SKIP and not item.name.startswith("consolidated") and not target.exists():
            shutil.copy2(item, target)  # snapshot files are symlinks; copy2 copies their contents
            copied.append(item.name)
    size = sum(f.stat().st_size for f in args.out.iterdir() if f.is_file())
    print(f"Saved {args.out} ({size / 1e9:.2f} GB). Copied from base: {', '.join(copied) or 'nothing'}", flush=True)


if __name__ == "__main__":
    main()
