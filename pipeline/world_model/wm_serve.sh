#!/usr/bin/env bash
# wm_serve.sh OUTDIR NAME PORT GPU SIM HELDOUT : wait for the model, export Q8 GGUF, serve it, evaluate it
set -u
OUT=$1; NAME=$2; PORT=$3; GPU=$4; SIM=$5; HELD=$6
cd /dev/shm/work
until ls -d $OUT/step-* >/dev/null 2>&1; do sleep 5; done; sleep 3
D=$(ls -d $OUT/step-* | tail -1); echo "$NAME model $D $(date -u +%T)"
bash export.sh "$D" $NAME full 2>&1 | tail -1
cd /workspace/atelier
CUDA_VISIBLE_DEVICES=$GPU nohup runtime/llama.cpp/build/bin/llama-server --model /dev/shm/work/$NAME-q8_0.gguf --host 127.0.0.1 --port $PORT --no-webui \
  --n-gpu-layers 99 --flash-attn on --ctx-size 8192 --parallel 2 --threads 8 < /dev/null > /dev/shm/work/$NAME-server.log 2>&1 &
for i in $(seq 1 90); do curl -fsS --max-time 2 http://127.0.0.1:$PORT/health >/dev/null 2>&1 && break; sleep 2; done
echo "$NAME server: $(curl -s http://127.0.0.1:$PORT/health) $(date -u +%T)"
cd /dev/shm/work && /root/renderenv/bin/python wm_eval.py $PORT $SIM $HELD 200 150
echo "done $(date -u +%T)"
