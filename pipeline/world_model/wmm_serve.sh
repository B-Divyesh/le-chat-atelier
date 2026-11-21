#!/usr/bin/env bash
# Deploy the multi-genre world model: export, two replicas (one per GPU) with n-gram speculation, evaluate.
set -u
cd /dev/shm/work
until ls -d /dev/shm/work/wmm-model/step-* >/dev/null 2>&1; do sleep 5; done; sleep 3
D=$(ls -d /dev/shm/work/wmm-model/step-* | tail -1); echo "multi model $D $(date -u +%T)"; grep validation train-multi.log | tail -1
bash export.sh "$D" wmm full 2>&1 | tail -1
cd /workspace/atelier
for spec in "0 8108" "1 8109"; do set -- $spec
  CUDA_VISIBLE_DEVICES=$1 nohup runtime/llama.cpp/build/bin/llama-server --model /dev/shm/work/wmm-q8_0.gguf --host 127.0.0.1 --port $2 --no-webui \
    --n-gpu-layers 99 --flash-attn on --ctx-size 24576 --parallel 6 --threads 8 --spec-type ngram-simple --spec-draft-n-max 16 \
    < /dev/null > /dev/shm/work/wmm-$2.log 2>&1 &
done
for p in 8108 8109; do for i in $(seq 1 90); do curl -fsS --max-time 2 http://127.0.0.1:$p/health >/dev/null 2>&1 && break; sleep 2; done; echo "replica $p: $(curl -s http://127.0.0.1:$p/health)"; done
cd /dev/shm/work && /root/renderenv/bin/python wm_eval_multi.py 8108 /dev/shm/work/data-multi/heldout.jsonl
echo "done $(date -u +%T)"
