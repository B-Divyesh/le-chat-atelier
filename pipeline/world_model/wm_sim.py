"""SVG world-model data: a tiny survivors-style rule engine whose state IS an SVG frame.
Writes (action + current SVG -> next SVG) transitions for training the model to be the game engine."""
import json, random, sys
W, H = 16, 12
ACTIONS = {"up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0), "stay": (0, 0)}
def sgn(v): return (v > 0) - (v < 0)
def to_svg(s):
    out = [f'<svg viewBox="0 0 16 12"><text x="0" y="1">HP {s["hp"]} XP {s["xp"]} T {s["t"]}</text>',
           f'<use href="#hero" x="{s["hx"]}" y="{s["hy"]}"/>']
    out += [f'<use href="#e{k}" x="{x}" y="{y}"/>' for k, x, y in sorted(s["en"], key=lambda e: (e[2], e[1], e[0]))]
    out += [f'<use href="#gem" x="{x}" y="{y}"/>' for x, y in sorted(s["gems"], key=lambda g: (g[1], g[0]))]
    return "".join(out) + "</svg>"
def reset(): return dict(hx=8, hy=6, hp=5, xp=0, t=0, en=[], gems=[])
def step(s, action, rng):
    if s["hp"] <= 0: return reset()
    s = dict(s, en=[list(e) for e in s["en"]], gems=[list(g) for g in s["gems"]])
    dx, dy = ACTIONS[action]
    s["hx"], s["hy"] = min(W - 1, max(0, s["hx"] + dx)), min(H - 1, max(0, s["hy"] + dy))
    if [s["hx"], s["hy"]] in s["gems"]:
        s["gems"].remove([s["hx"], s["hy"]]); s["xp"] = min(99, s["xp"] + 1)
    for e in s["en"]:
        k, x, y = e; ddx, ddy = s["hx"] - x, s["hy"] - y
        if k == 1 or (k == 2 and s["t"] % 2 == 0):
            if abs(ddx) >= abs(ddy): x += sgn(ddx)
            else: y += sgn(ddy)
        elif k == 3: x += sgn(ddx); y += sgn(ddy)
        e[1], e[2] = x, y
    hit = [e for e in s["en"] if e[1] == s["hx"] and e[2] == s["hy"]]
    s["hp"] = max(0, s["hp"] - len(hit)); s["en"] = [e for e in s["en"] if not (e[1] == s["hx"] and e[2] == s["hy"])]
    if s["t"] % 2 == 0:
        near = [e for e in s["en"] if max(abs(e[1] - s["hx"]), abs(e[2] - s["hy"])) <= 1]
        for e in near:
            if [e[1], e[2]] not in s["gems"] and len(s["gems"]) < 6: s["gems"].append([e[1], e[2]])
        s["en"] = [e for e in s["en"] if max(abs(e[1] - s["hx"]), abs(e[2] - s["hy"])) > 1]
    if s["t"] % 3 == 0 and len(s["en"]) < 8:
        side, k = rng.randrange(4), rng.choice([1, 1, 2, 3])
        pos = [(rng.randrange(W), 0), (rng.randrange(W), H - 1), (0, rng.randrange(H)), (W - 1, rng.randrange(H))][side]
        s["en"].append([k, *pos])
    s["t"] = (s["t"] + 1) % 100
    return s
def rand_state(rng):
    hx, hy = rng.randrange(W), rng.randrange(H)
    en = [[rng.choice([1, 1, 2, 3]), rng.randrange(W), rng.randrange(H)] for _ in range(rng.randrange(0, 8))]
    en = [e for e in en if (e[1], e[2]) != (hx, hy)]
    gems = [list(g) for g in {(rng.randrange(W), rng.randrange(H)) for _ in range(rng.randrange(0, 5))}]
    return dict(hx=hx, hy=hy, hp=rng.randint(1, 5), xp=rng.randrange(0, 40), t=rng.randrange(100), en=en, gems=gems)
if __name__ == "__main__":
    n, out = int(sys.argv[1]), sys.argv[2]
    rng = random.Random(int(sys.argv[3]) if len(sys.argv) > 3 else 0)
    rows = []
    while len(rows) < n:
        s = reset() if rng.random() < 0.3 else rand_state(rng); a = "stay"
        for _ in range(30):
            if rng.random() > 0.6: a = rng.choice(["up", "down", "left", "right", "stay"])
            nxt = step(s, a, rng)
            rows.append(dict(description=f"{a}\n{to_svg(s)}", svg=to_svg(nxt), action=a, state=s, next=nxt))
            s = nxt
    with open(out, "w") as f:
        for r in rows[:n]: f.write(json.dumps(r) + "\n")
    print("wrote", n)
