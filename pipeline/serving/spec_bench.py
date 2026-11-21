"""Compare per-frame latency and outputs: plain vs n-gram speculative llama-server (greedy, grammar-constrained)."""
import json, re, sys, urllib.request
from tokenizers import Tokenizer
tok = Tokenizer.from_file("/dev/shm/atelier-merged-0625/tokenizer.json")
src = open("/workspace/atelier/fast_server.py").read()
G = re.search(r"WM_GRAMMAR = r'''(.*?)'''", src, re.S).group(1)
rows = [json.loads(l) for l in open("/dev/shm/work/data-wm/heldout.jsonl")][:30]
def run(port, action, svg):
    ids = tok.encode(f"<s>[INST]{action}\n{svg}[/INST]", add_special_tokens=False).ids
    r = json.load(urllib.request.urlopen(urllib.request.Request(f"http://127.0.0.1:{port}/completion", json.dumps(dict(
        prompt=ids, n_predict=420, temperature=0, cache_prompt=False, grammar=G)).encode(), {"Content-Type": "application/json"}), timeout=60))
    return r["content"], r["timings"]["predicted_ms"], r["tokens_predicted"]
res = {p: [] for p in sys.argv[1:]}; same = 0
for r in rows:
    a, svg = r["description"].split("\n", 1)
    outs = {p: run(p, a, svg) for p in sys.argv[1:]}
    for p, (o, ms, n) in outs.items(): res[p].append((ms, n))
    same += len({o for o, _, _ in outs.values()}) == 1
for p, v in res.items():
    ms = sum(m for m, _ in v) / len(v); n = sum(k for _, k in v) / len(v)
    print(f"port {p}: {ms:.0f} ms/frame, {n:.0f} tokens, {1000 * n / ms:.0f} tok/s")
print("identical outputs:", same, "/", len(rows))
