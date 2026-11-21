#!/usr/bin/env bash
# Wait for the sprite model, export to Q8 GGUF, serve on GPU 1 :8101, then run the gallery test.
set -u
cd /dev/shm/work
until ls -d /dev/shm/work/pix8-model/step-* >/dev/null 2>&1; do sleep 5; done
sleep 3
D=$(ls -d /dev/shm/work/pix8-model/step-* | tail -1); echo "model dir $D $(date -u +%T)"
bash /dev/shm/work/export.sh "$D" pix8 full 2>&1 | tail -1
cd /workspace/atelier
CUDA_VISIBLE_DEVICES=1 nohup runtime/llama.cpp/build/bin/llama-server --model /dev/shm/work/pix8-q8_0.gguf --host 127.0.0.1 --port 8101 --no-webui \
  --n-gpu-layers 99 --flash-attn on --ctx-size 16384 --parallel 16 --threads 8 < /dev/null > /dev/shm/work/pix8-server.log 2>&1 &
for i in $(seq 1 90); do curl -fsS --max-time 2 http://127.0.0.1:8101/health >/dev/null 2>&1 && break; sleep 2; done
echo "pix8 server: $(curl -s http://127.0.0.1:8101/health) $(date -u +%T)"
/root/renderenv/bin/python /dev/shm/work/pix_eval.py /dev/shm/work/pix8-gallery.png
echo "done $(date -u +%T)"
