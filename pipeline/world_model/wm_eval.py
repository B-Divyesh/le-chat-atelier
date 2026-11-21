"""Evaluate a served SVG world model against the rule simulator.
1) one-step accuracy on held-out transitions; 2) closed-loop rollout where every model frame is re-checked by the rules."""
import json, random, re, sys, time, urllib.request
sys.path.insert(0, "/dev/shm/work")
PORT, SIM, HELDOUT = sys.argv[1], sys.argv[2], sys.argv[3]
sim = __import__(SIM)
src = open("/workspace/atelier/fast_server.py").read()
GRAMMAR = re.search(r"WM_GRAMMAR = r'''(.*?)'''", src, re.S).group(1)
from tokenizers import Tokenizer
tok = Tokenizer.from_file("/dev/shm/atelier-merged-0625/tokenizer.json")
def model(action, svg):
    ids = tok.encode(f"<s>[INST]{action}\n{svg}[/INST]", add_special_tokens=False).ids
    r = json.load(urllib.request.urlopen(urllib.request.Request(f"http://127.0.0.1:{PORT}/completion", json.dumps(dict(
        prompt=ids, n_predict=420, temperature=0, cache_prompt=True, grammar=GRAMMAR)).encode(), {"Content-Type": "application/json"}), timeout=60))
    return r["content"], r["timings"]["predicted_ms"], r["tokens_predicted"]
def parse(svg):
    m = re.search(r"HP (\d+) XP (\d+) T (\d+)", svg)
    uses = re.findall(r'href="#(\w+)" x="(\d+)" y="(\d+)"', svg)
    s = dict(hp=int(m.group(1)), xp=int(m.group(2)), t=int(m.group(3)), en=[], gems=[], ob=[])
    for k, x, y in uses:
        x, y = int(x), int(y)
        if k == "hero": s["hx"], s["hy"] = x, y
        elif k.startswith("e"): s["en"].append([int(k[1]), x, y])
        elif k.startswith("o"): s["ob"].append([int(k[1]), x, y])
        else: s["gems"].append([x, y])
    return s
def compare(pred, want, spawn_tick):
    p, w = parse(pred), parse(want)
    hud = (p["hp"], p["xp"], p["t"]) == (w["hp"], w["xp"], w["t"])
    hero = (p.get("hx"), p.get("hy")) == (w.get("hx"), w.get("hy"))
    pe, we = sorted(map(tuple, p["en"])), sorted(map(tuple, w["en"]))
    if spawn_tick:  # one enemy may legitimately differ (random spawn): drop edge enemies not shared before comparing
        edge = lambda e: e[1] in (0, 15) or e[2] in (0, 1, 11)
        pe = [e for e in pe if not (edge(e) and e not in we)]; we = [e for e in we if not (edge(e) and e not in pe)]
    return dict(exact=pred == want, hud=hud, hero=hero, enemies=pe == we, gems=sorted(map(tuple, p["gems"])) == sorted(map(tuple, w["gems"])),
                obstacles=sorted(map(tuple, p["ob"])) == sorted(map(tuple, w["ob"])))
rows = [json.loads(l) for l in open(HELDOUT)][:int(sys.argv[4]) if len(sys.argv) > 4 else 200]
agg, ms, toks = {}, [], []
for r in rows:
    action, svg = r["description"].split("\n", 1)
    if action == "start": continue
    pred, t_ms, n = model(action, svg); ms.append(t_ms); toks.append(n)
    spawn = parse(svg)["t"] % 3 == 0
    c = compare(pred, r["svg"], spawn)
    if not spawn: c["exact_nonspawn"] = c["exact"]
    for k, v in c.items(): agg.setdefault(k, []).append(v)
one = {k: round(100 * sum(v) / len(v), 1) for k, v in agg.items()}
print("ONE-STEP accuracy % (held-out):", json.dumps(one), "| n", len(agg["exact"]), "| mean ms", round(sum(ms) / len(ms)), "| mean tokens", round(sum(toks) / len(toks)))
# closed loop: the model consumes its own frames; each step is re-simulated by the rules from the model's input frame
rng = random.Random(5); state_svg = sim.to_svg(sim.new_env(rng) if hasattr(sim, "new_env") else sim.reset())
ok = {}; a = "stay"; t0 = time.time()
for i in range(int(sys.argv[5]) if len(sys.argv) > 5 else 200):
    if rng.random() > 0.6: a = rng.choice(["up", "down", "left", "right", "stay"])
    pred, _, _ = model(a, state_svg)
    s = parse(state_svg)
    if s["hp"] <= 0: state_svg = pred; continue
    if not hasattr(sim, "new_env"): s.pop("ob", None)
    want = sim.to_svg(sim.step(s, a, random.Random(i)))
    c = compare(pred, want, s["t"] % 3 == 0)
    for k, v in c.items():
        if k != "exact": ok.setdefault(k, []).append(v)
    state_svg = pred
print("CLOSED-LOOP rule consistency % over", len(ok.get("hud", [])), "steps:", json.dumps({k: round(100 * sum(v) / len(v), 1) for k, v in ok.items()}),
      "| wall", round(time.time() - t0, 1), "s")
