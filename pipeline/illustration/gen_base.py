"""Sample K candidates per prompt from llama-servers (round-robin), save raw outputs as JSONL."""
import json, sys, time, threading, urllib.request
from concurrent.futures import ThreadPoolExecutor
SYSTEM = "Draw the requested illustration. Return only a complete SVG on a 200 by 200 viewBox."
PREFIX = "Generate an SVG illustration: "
prompts_file, out_file, K, ports = sys.argv[1], sys.argv[2], int(sys.argv[3]), sys.argv[4].split(",")
prompts = [json.loads(l)["prompt"] for l in open(prompts_file)]
jobs = [(i, p, k) for i, p in enumerate(prompts) for k in range(K)]
lock = threading.Lock(); out = open(out_file, "w"); done = [0]; t0 = time.time(); toks = [0]
def run(job):
    i, p, k = job; port = ports[(i * K + k) % len(ports)]
    body = dict(prompt=f"[SYSTEM_PROMPT]{SYSTEM}[/SYSTEM_PROMPT][INST]{PREFIX}{p}[/INST]", n_predict=1500, temperature=0.8, top_p=0.95,
                stop=["</svg>"], cache_prompt=True, seed=i * 31 + k)
    try:
        r = json.load(urllib.request.urlopen(urllib.request.Request(f"http://127.0.0.1:{port}/completion", json.dumps(body).encode(),
                      {"Content-Type": "application/json"}), timeout=600))
        text = r["content"] + ("</svg>" if r.get("stopping_word") == "</svg>" else "")
        row = dict(i=i, prompt=p, k=k, text=text, tokens=r.get("tokens_predicted"), closed=r.get("stopping_word") == "</svg>")
    except Exception as e:
        row = dict(i=i, prompt=p, k=k, text="", tokens=0, closed=False, error=str(e)[:100])
    with lock:
        out.write(json.dumps(row, ensure_ascii=False) + "\n"); done[0] += 1; toks[0] += row["tokens"] or 0
        if done[0] % 500 == 0:
            out.flush(); el = time.time() - t0
            print(f"{done[0]}/{len(jobs)} gens, {round(toks[0] / el)} tok/s aggregate, {round(el)}s", flush=True)
with ThreadPoolExecutor(int(sys.argv[5]) if len(sys.argv) > 5 else 64) as ex:
    list(ex.map(run, jobs))
out.close(); print("done", done[0], "tokens", toks[0], "seconds", round(time.time() - t0), flush=True)
