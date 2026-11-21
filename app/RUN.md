# Running the SVG world model demo

Three llama.cpp servers and one small Python server. Each model is a Ministral 3 3B; an H100 runs all of them comfortably.

```sh
# 1. director + narrator: the base instruct model (convert mistralai/Ministral-3-3B-Instruct-2512-BF16 to Q8_0 GGUF first)
llama-server --model base-q8_0.gguf --port 8099 --n-gpu-layers 99 --flash-attn on --ctx-size 32768 --parallel 8
# 2. sprite model: B-Divyesh/atelier-pixel-sprites-8x8
llama-server --model pixlab-q8_0.gguf --port 8103 --n-gpu-layers 99 --flash-attn on --ctx-size 16384 --parallel 16
# 3. world model: this repo (one replica per GPU; n-gram speculation gives identical outputs, much faster)
CUDA_VISIBLE_DEVICES=0 llama-server --model wmm2-q8_0.gguf --port 8110 --n-gpu-layers 99 --flash-attn on --ctx-size 24576 --parallel 6 --spec-type ngram-simple --spec-draft-n-max 32
CUDA_VISIBLE_DEVICES=1 llama-server --model wmm2-q8_0.gguf --port 8111 --n-gpu-layers 99 --flash-attn on --ctx-size 24576 --parallel 6 --spec-type ngram-simple --spec-draft-n-max 32
# 4. game server (needs tokenizers + huggingface_hub; run from this app/ folder)
python fast_server.py --port 8090 --page app.html \
  --upstream base=http://127.0.0.1:8099#base --upstream pix8=http://127.0.0.1:8103#pix8 \
  --upstream wm=http://127.0.0.1:8110#wm --upstream wm_b=http://127.0.0.1:8111#wm --default base --temperature 0.3
```

Open `http://127.0.0.1:8090/game?prompt=Le%20Chat%20survives%20a%20haunted%20cheese%20dungeon%20full%20of%20ghost%20rats`.
Arrow keys move Le Chat. "Smoothing" toggles the in-browser gliding between model frames, "Imagine futures" shows the
model's next frame for every key, and the side panel shows the exact SVG going in and coming out on each step.
