import json, re, sys, urllib.request
from tokenizers import Tokenizer
tok = Tokenizer.from_file("/dev/shm/atelier-merged-0625/tokenizer.json")
G = re.search(r"WM_GRAMMAR = r'''(.*?)'''", open("/workspace/atelier/fast_server.py").read(), re.S).group(1)
rows = [json.loads(l) for l in open("/dev/shm/work/data-multi/heldout.jsonl")]
rows = [r for r in rows if "start" not in r["description"].split("\n")[0]][:25]
for port in sys.argv[1:]:
    ms = toks = 0
    for r in rows:
        a, svg = r["description"].split("\n", 1)
        ids = tok.encode(f"<s>[INST]{a}\n{svg}[/INST]", add_special_tokens=False).ids
        o = json.load(urllib.request.urlopen(urllib.request.Request(f"http://127.0.0.1:{port}/completion", json.dumps(dict(prompt=ids, n_predict=600, temperature=0, grammar=G)).encode(), {"Content-Type": "application/json"}), timeout=90))
        ms += o["timings"]["predicted_ms"]; toks += o["tokens_predicted"]
    print(f"port {port}: {ms/len(rows):.0f} ms/frame, {1000*toks/ms:.0f} tok/s")
