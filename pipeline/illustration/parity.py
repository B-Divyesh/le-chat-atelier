"""Greedy-decode the same prompt with HF (CPU, reference) and llama-server; compare tokens."""
import json, sys, time, urllib.request, torch
sys.path.insert(0, "/workspace/atelier")
from svg_model import get_tokenizer, prompt_tokens
from transformers import Mistral3ForConditionalGeneration
tok = get_tokenizer(); N = 80
cap = json.loads(open("/workspace/atelier/data/eval.jsonl").readlines()[1])["description"]
ids = prompt_tokens(tok, cap)
r = json.load(urllib.request.urlopen(urllib.request.Request("http://127.0.0.1:8094/completion", json.dumps(dict(
    prompt=ids, n_predict=N, temperature=0, cache_prompt=False, return_tokens=True)).encode(), {"Content-Type": "application/json"}), timeout=120))
cpp = r.get("tokens") or tok.encode(r["content"], add_special_tokens=False).ids
torch.set_num_threads(48); t = time.time()
model = Mistral3ForConditionalGeneration.from_pretrained("/dev/shm/atelier-merged-0625", dtype=torch.float32, device_map={"": "cpu"})
with torch.inference_mode():
    out = model.generate(input_ids=torch.tensor([ids]), attention_mask=torch.ones(1, len(ids), dtype=torch.long), max_new_tokens=N, do_sample=False)[0, len(ids):].tolist()
match = next((i for i, (a, b) in enumerate(zip(out, cpp)) if a != b), min(len(out), len(cpp)))
print("HF time", round(time.time() - t), "s | identical prefix:", match, "of", min(len(out), len(cpp)), "tokens")
print("HF :", tok.decode(out)[:400]); print("CPP:", tok.decode(cpp)[:400])
