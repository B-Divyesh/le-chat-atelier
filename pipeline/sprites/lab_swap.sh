#!/usr/bin/env bash
# Wait for the Lab-color sprite model, export, serve on GPU1 :8103, check it, then point the game server's sprite route at it.
set -u
cd /dev/shm/work
until ls -d /dev/shm/work/pixlab-model/step-* >/dev/null 2>&1; do sleep 5; done; sleep 3
D=$(ls -d /dev/shm/work/pixlab-model/step-* | tail -1); echo "lab model $D $(date -u +%T)"; grep validation train-pixlab.log | tail -1
bash export.sh "$D" pixlab full 2>&1 | tail -1
cd /workspace/atelier
CUDA_VISIBLE_DEVICES=1 nohup runtime/llama.cpp/build/bin/llama-server --model /dev/shm/work/pixlab-q8_0.gguf --host 127.0.0.1 --port 8103 --no-webui \
  --n-gpu-layers 99 --flash-attn on --ctx-size 16384 --parallel 16 --threads 8 < /dev/null > /dev/shm/work/pixlab-server.log 2>&1 &
for i in $(seq 1 90); do curl -fsS --max-time 2 http://127.0.0.1:8103/health >/dev/null 2>&1 && break; sleep 2; done
echo "pixlab server: $(curl -s http://127.0.0.1:8103/health)"
pkill -f "^/venv/main/bin/python -u fast_server.py --port 8091"; sleep 1
HF_HOME=/dev/shm/atelier-hf HF_HUB_OFFLINE=1 nohup /venv/main/bin/python -u fast_server.py --port 8091 --upstream pix8=http://127.0.0.1:8103#pix8 < /dev/null > /dev/shm/work/fast-8091.log 2>&1 &
sleep 5; cd /dev/shm/work && /root/renderenv/bin/python pix_eval_8091.py pixlab-gallery.png
echo "ready $(date -u +%T)"
