#!/usr/bin/env bash
# Serve Ministral 3 3B with vLLM's OpenAI server for fast_server.py.
#
# Flag names change between vLLM releases. Check every flag below with
# `vllm serve --help` on the box before relying on this script.
#
# Mode A, LoRA (no extra disk): base BF16 plus adapters. One server answers
# model "base" and each adapter name, e.g. "step-0625".
#   MODE=lora GPU=1 PORT=8001 ./serve_vllm.sh
#   ADAPTERS="step-0625=$PWD/checkpoints/step-0625 step-0300=$PWD/checkpoints/step-0300" MODE=lora ./serve_vllm.sh
#
# Mode B, merged checkpoint from merge_adapter.py, optionally FP8 (H100 native):
#   MODE=merged MODEL=merged/step-0625 SERVED=step-0625 FP8=1 GPU=1 PORT=8002 ./serve_vllm.sh
#
# Mode C, n-gram speculative decoding on top of either mode:
#   NGRAM=1 MODE=merged MODEL=merged/step-0625 ./serve_vllm.sh
#
# Env vars: MODE (lora|merged), GPU, PORT, MODEL, SERVED, MEMFRAC, ADAPTERS,
# FP8, NGRAM, TOKENIZER_MODE (unset = vLLM default; try hf or mistral), EXTRA.
# MEMFRAC is the fraction of the GPU's TOTAL memory this server may take, and it
# must fit in what is free right now (the old demo.py holds ~10 GiB on GPU 1).
set -euo pipefail
cd "$(dirname "$0")"

MODE=${MODE:-lora}
GPU=${GPU:-1}
PORT=${PORT:-8001}
MEMFRAC=${MEMFRAC:-0.35}
BASE_REPO=mistralai/Ministral-3-3B-Instruct-2512-BF16

args=(--host 127.0.0.1 --port "$PORT" --max-model-len 8192 --gpu-memory-utilization "$MEMFRAC"
      --enable-prefix-caching --limit-mm-per-prompt '{"image":0}')

case "$MODE" in
  lora)
    if [[ -z "${MODEL:-}" ]]; then
      # Serve from the local HF cache snapshot so vLLM does not download the
      # Mistral-native consolidated weights next to the HF shards (16 GB disk).
      MODEL=$(python3 - "$BASE_REPO" <<'EOF'
import sys
from huggingface_hub import snapshot_download
print(snapshot_download(sys.argv[1], allow_patterns=["*.json", "*.jinja", "model*.safetensors"],
                        ignore_patterns=["params.json", "tekken.json", "consolidated*"]))
EOF
)
    fi
    ADAPTERS=${ADAPTERS:-step-0625=$PWD/checkpoints/step-0625}
    # shellcheck disable=SC2206  # ADAPTERS is a space-separated list on purpose
    args+=(--served-model-name "${SERVED:-base}" --enable-lora --max-lora-rank 32 --max-loras 2
           --lora-modules $ADAPTERS)
    ;;
  merged)
    MODEL=${MODEL:?Set MODEL to the merged directory, e.g. merged/step-0625}
    args+=(--served-model-name "${SERVED:-$(basename "$MODEL")}")
    if [[ "${FP8:-0}" == 1 ]]; then args+=(--quantization fp8); fi
    ;;
  *) echo "MODE must be lora or merged" >&2; exit 2 ;;
esac

if [[ -n "${TOKENIZER_MODE:-}" ]]; then args+=(--tokenizer-mode "$TOKENIZER_MODE"); fi
if [[ "${NGRAM:-0}" == 1 ]]; then
  args+=(--speculative-config '{"method":"ngram","num_speculative_tokens":4,"prompt_lookup_max":4,"prompt_lookup_min":2}')
fi

echo "CUDA_VISIBLE_DEVICES=$GPU vllm serve $MODEL ${args[*]} ${EXTRA:-}" >&2
# shellcheck disable=SC2086  # EXTRA is split into flags on purpose
CUDA_VISIBLE_DEVICES=$GPU exec vllm serve "$MODEL" "${args[@]}" ${EXTRA:-}
