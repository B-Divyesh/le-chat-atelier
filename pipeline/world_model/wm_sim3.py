"""SVG world model v3 (layout-conditioned environments: start arena|forest|maze|islands|cave). Based on v2: the model also generates the environment. Frames contain obstacles (#o1/#o2) that block
movement; the 'start' action on an empty SVG (or death) produces a freshly generated environment frame."""
import json, random, sys
W, H = 16, 12
ACTIONS = {"up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0), "stay": (0, 0)}
EMPTY = '<svg viewBox="0 0 16 12"></svg>'
def sgn(v): return (v > 0) - (v < 0)
def to_svg(s):
    out = [f'<svg viewBox="0 0 16 12"><text x="0" y="1">HP {s["hp"]} XP {s["xp"]} T {s["t"]}</text>',
           f'<use href="#hero" x="{s["hx"]}" y="{s["hy"]}"/>']
    out += [f'<use href="#o{k}" x="{x}" y="{y}"/>' for k, x, y in sorted(s["ob"], key=lambda e: (e[2], e[1], e[0]))]
    out += [f'<use href="#e{k}" x="{x}" y="{y}"/>' for k, x, y in sorted(s["en"], key=lambda e: (e[2], e[1], e[0]))]
    out += [f'<use href="#gem" x="{x}" y="{y}"/>' for x, y in sorted(s["gems"], key=lambda g: (g[1], g[0]))]
    return "".join(out) + "</svg>"
LAYOUTS = ["arena", "forest", "maze", "islands", "cave"]
def new_env(rng, layout=None):
    layout = layout or rng.choice(LAYOUTS)
    ob, seen = [], set()
    def add(k, x, y):
        if 0 <= x < W and 1 <= y < H and abs(x - 8) + abs(y - 6) > 2 and (x, y) not in seen:
            seen.add((x, y)); ob.append([k, x, y])
    if layout == "arena":
        for _ in range(rng.randint(2, 4)): add(1, rng.randrange(W), rng.randrange(1, H))
    elif layout == "forest":
        for _ in range(rng.randint(10, 14)): add(1, rng.randrange(W), rng.randrange(1, H))
    elif layout == "maze":
        for _ in range(rng.randint(3, 4)):
            x, y, horiz, n = rng.randrange(1, W - 1), rng.randrange(2, H - 1), rng.random() < 0.5, rng.randint(3, 5)
            for i in range(n): add(2, x + i if horiz else x, y if horiz else y + i)
    elif layout == "islands":
        for _ in range(rng.randint(3, 4)):
            k, cx, cy = rng.choice([1, 2]), rng.randrange(1, W - 1), rng.randrange(2, H - 1)
            for _ in range(rng.randint(2, 4)): add(k, cx + rng.randint(-1, 1), cy + rng.randint(-1, 1))
    else:  # cave: L-shaped rock walls in the corners
        for cx, cy, sx, sy in ((0, 1, 1, 1), (15, 1, -1, 1), (0, 11, 1, -1), (15, 11, -1, -1)):
            for i in range(rng.randint(2, 3)): add(2, cx + sx * i, cy); add(2, cx, cy + sy * i)
    return dict(hx=8, hy=6, hp=5, xp=0, t=0, ob=ob, en=[], gems=[])
def blocked(s, x, y): return any(o[1] == x and o[2] == y for o in s["ob"])
def step(s, action, rng):
    if action == "start" or s["hp"] <= 0: return new_env(rng)
    s = dict(s, en=[list(e) for e in s["en"]], gems=[list(g) for g in s["gems"]])
    dx, dy = ACTIONS[action]
    nx, ny = min(W - 1, max(0, s["hx"] + dx)), min(H - 1, max(0, s["hy"] + dy))
    if not blocked(s, nx, ny): s["hx"], s["hy"] = nx, ny
    if [s["hx"], s["hy"]] in s["gems"]:
        s["gems"].remove([s["hx"], s["hy"]]); s["xp"] = min(99, s["xp"] + 1)
    for e in s["en"]:
        k, x, y = e; ddx, ddy = s["hx"] - x, s["hy"] - y
        moves = []
        if k == 1 or (k == 2 and s["t"] % 2 == 0):
            first = (sgn(ddx), 0) if abs(ddx) >= abs(ddy) else (0, sgn(ddy))
            second = (0, sgn(ddy)) if first[0] else (sgn(ddx), 0)
            moves = [first, second]
        elif k == 3: moves = [(sgn(ddx), sgn(ddy)), (sgn(ddx), 0), (0, sgn(ddy))]
        for mx, my in moves:
            if (mx or my) and not blocked(s, x + mx, y + my): x, y = x + mx, y + my; break
        e[1], e[2] = x, y
    s["hp"] = max(0, s["hp"] - sum(1 for e in s["en"] if e[1] == s["hx"] and e[2] == s["hy"]))
    s["en"] = [e for e in s["en"] if not (e[1] == s["hx"] and e[2] == s["hy"])]
    if s["t"] % 2 == 0:
        for e in s["en"]:
            if max(abs(e[1] - s["hx"]), abs(e[2] - s["hy"])) <= 1 and [e[1], e[2]] not in s["gems"] and len(s["gems"]) < 6:
                s["gems"].append([e[1], e[2]])
        s["en"] = [e for e in s["en"] if max(abs(e[1] - s["hx"]), abs(e[2] - s["hy"])) > 1]
    if s["t"] % 3 == 0 and len(s["en"]) < 7:
        side, k = rng.randrange(4), rng.choice([1, 1, 2, 3])
        pos = [(rng.randrange(W), 1), (rng.randrange(W), H - 1), (0, rng.randrange(1, H)), (W - 1, rng.randrange(1, H))][side]
        if not blocked(s, *pos): s["en"].append([k, *pos])
    s["t"] = (s["t"] + 1) % 100
    return s
def rand_state(rng):
    s = new_env(rng)
    s.update(hx=rng.randrange(W), hy=rng.randrange(1, H), hp=rng.randint(1, 5), xp=rng.randrange(0, 40), t=rng.randrange(100))
    s["ob"] = [o for o in s["ob"] if (o[1], o[2]) != (s["hx"], s["hy"])]
    s["en"] = [[rng.choice([1, 1, 2, 3]), rng.randrange(W), rng.randrange(1, H)] for _ in range(rng.randrange(0, 7))]
    s["en"] = [e for e in s["en"] if (e[1], e[2]) != (s["hx"], s["hy"]) and not blocked(s, e[1], e[2])]
    s["gems"] = [list(g) for g in {(rng.randrange(W), rng.randrange(1, H)) for _ in range(rng.randrange(0, 4))} if not blocked(s, *g)]
    return s
if __name__ == "__main__":
    n, out = int(sys.argv[1]), sys.argv[2]
    rng = random.Random(int(sys.argv[3]) if len(sys.argv) > 3 else 0)
    rows = []
    while len(rows) < n:
        if rng.random() < 0.15:  # layout-conditioned environment generation from an empty frame
            lay = rng.choice(LAYOUTS + [None])
            rows.append(dict(description=f"start {lay}\n{EMPTY}" if lay else f"start\n{EMPTY}", svg=to_svg(new_env(rng, lay)))); continue
        s = new_env(rng) if rng.random() < 0.3 else rand_state(rng); a = "stay"
        for _ in range(30):
            if rng.random() > 0.6: a = rng.choice(["up", "down", "left", "right", "stay"])
            nxt = step(s, a, rng)
            rows.append(dict(description=f"{a}\n{to_svg(s)}", svg=to_svg(nxt))); s = nxt
    with open(out, "w") as f:
        for r in rows[:n]: f.write(json.dumps(r) + "\n")
    print("wrote", n)
