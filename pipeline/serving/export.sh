#!/usr/bin/env bash
# export.sh SRC NAME [adapter|full] -> /dev/shm/work/NAME-q8_0.gguf
set -euo pipefail
SRC=$1; NAME=$2; KIND=${3:-adapter}
cd /workspace/atelier
export HF_HOME=/dev/shm/atelier-hf HF_HUB_OFFLINE=1 CUDA_VISIBLE_DEVICES=""
HFDIR=$SRC
if [ "$KIND" = adapter ]; then
  HFDIR=/dev/shm/work/merged-$NAME; rm -rf "$HFDIR"
  SRC="$SRC" OUT="$HFDIR" /venv/main/bin/python - <<'PY'
import os, shutil, torch
from pathlib import Path
from peft import PeftModel
from transformers import Mistral3ForConditionalGeneration
base = Mistral3ForConditionalGeneration.from_pretrained("mistralai/Ministral-3-3B-Instruct-2512-BF16", dtype=torch.bfloat16, device_map={"": "cpu"})
PeftModel.from_pretrained(base, os.environ["SRC"]).merge_and_unload().save_pretrained(os.environ["OUT"], safe_serialization=True)
PY
fi
for f in /dev/shm/atelier-merged-0625/*; do
  b=$(basename "$f"); case "$b" in *.safetensors|*.index.json|config.json) ;; *) [ -e "$HFDIR/$b" ] || cp "$f" "$HFDIR/$b";; esac
done
runtime/convert-env/bin/python runtime/llama.cpp/convert_hf_to_gguf.py "$HFDIR" --outtype q8_0 --outfile /dev/shm/work/$NAME-q8_0.gguf 2>&1 | tail -1
[ "$KIND" = adapter ] && rm -rf "$HFDIR"
ls -la /dev/shm/work/$NAME-q8_0.gguf
