"""Per-genre evaluation of the multi-genre SVG world model: one-step accuracy on held-out transitions and
closed-loop stability (frames stay well-formed, the tick advances by exactly 1, the hero never disappears)."""
import json, random, re, sys, time, urllib.request
from collections import defaultdict
sys.path.insert(0, "/dev/shm/work")
import wm_multi as M
PORT, HELD = sys.argv[1], sys.argv[2]
src = open("/workspace/atelier/fast_server.py").read()
G = re.search(r"WM_GRAMMAR = r'''(.*?)'''", src, re.S).group(1)
from tokenizers import Tokenizer
tok = Tokenizer.from_file("/dev/shm/atelier-merged-0625/tokenizer.json")
def model(prompt_action, svg):
    ids = tok.encode(f"<s>[INST]{prompt_action}\n{svg}[/INST]", add_special_tokens=False).ids
    r = json.load(urllib.request.urlopen(urllib.request.Request(f"http://127.0.0.1:{PORT}/completion", json.dumps(dict(
        prompt=ids, n_predict=600, temperature=0, cache_prompt=True, grammar=G)).encode(), {"Content-Type": "application/json"}), timeout=90))
    return r["content"], r["timings"]["predicted_ms"], r["tokens_predicted"]
hud = lambda s: (re.search(r"<text[^>]*>([^<]*)</text>", s) or [None, None])[1]
hero = lambda s: re.search(r'href="#hero" x="(\d+)" y="(\d+)"', s)
stats = defaultdict(lambda: defaultdict(list))
rows = [json.loads(l) for l in open(HELD)]
per = defaultdict(int)
for r in rows:
    g = r["genre"]
    if per[g] >= 30 or "start" in r["description"].split("\n")[0]: continue
    per[g] += 1
    a, svg = r["description"].split("\n", 1)
    out, ms, n = model(a, svg)
    st = stats[g]; st["exact"].append(out == r["svg"]); st["hud"].append(hud(out) == hud(r["svg"]))
    h1, h2 = hero(out), hero(r["svg"]); st["hero"].append(bool(h1 and h2 and h1.groups() == h2.groups())); st["ms"].append(ms); st["tok"].append(n)
print("ONE-STEP accuracy % per genre (held-out):")
for g, st in stats.items():
    print(f"  {g:10} exact {100*sum(st['exact'])/len(st['exact']):5.1f} | HUD {100*sum(st['hud'])/len(st['hud']):5.1f} | hero {100*sum(st['hero'])/len(st['hero']):5.1f}"
          f" | {sum(st['ms'])/len(st['ms']):.0f} ms, {sum(st['tok'])/len(st['tok']):.0f} tokens")
print("CLOSED-LOOP stability (60 self-fed steps per genre):")
rng = random.Random(9)
for g, (new, step, svg_fn, rand, acts) in M.GENRES.items():
    frame, _, _ = model(f"{g}: start", M.EMPTY); ok_t = ok_hero = n = 0; resets = 0
    for i in range(60):
        a = rng.choice(acts); nxt, _, _ = model(f"{g}: {a}", frame)
        t0, t1 = re.search(r" T (\d+)", frame), re.search(r" T (\d+)", nxt)
        if t1 and t1.group(1) == "0": resets += 1
        elif t0 and t1 and int(t1.group(1)) == (int(t0.group(1)) + 1) % 100: ok_t += 1
        ok_hero += bool(hero(nxt)); n += 1; frame = nxt
    print(f"  {g:10} tick consistency {100*ok_t/max(1,n-resets):5.1f}% | hero present {100*ok_hero/n:5.1f}% | resets {resets}")
