"""Multi-genre SVG world model data. One frame format for every genre:
<svg viewBox="0 0 16 12"><text x="0" y="1">HUD</text><use href="#kind" x y/>...</svg>
Prompt: "<genre>: <action>\n<current svg>" -> next svg. All state needed for the next frame is visible in the frame."""
import json, random, sys
import wm_sim3 as surv
W, H = 16, 12
EMPTY = '<svg viewBox="0 0 16 12"></svg>'
DIRS = {"up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0)}
def sgn(v): return (v > 0) - (v < 0)
def frame(hud, items):
    return (f'<svg viewBox="0 0 16 12"><text x="0" y="1">{hud}</text>'
            + "".join(f'<use href="#{k}" x="{x}" y="{y}"/>' for k, x, y in items) + "</svg>")
def srt(items): return sorted(items, key=lambda e: (e[2], e[1], e[0]))

# ---------------- snake: head + ordered body; direction = head - neck ----------------
def snake_new(rng):
    body = [(8, 6), (7, 6), (6, 6)]
    return dict(body=body, food=snake_food(rng, body), score=0, t=0)
def snake_food(rng, body):
    while True:
        p = (rng.randrange(W), rng.randrange(1, H))
        if p not in body: return p
def snake_svg(s):
    hx, hy = s["body"][0]
    items = [("hero", hx, hy)] + [("b", x, y) for x, y in s["body"][1:]] + [("gem", *s["food"])]
    return frame(f'LEN {len(s["body"])} SCORE {s["score"]} T {s["t"]}', items)
def snake_step(s, a, rng):
    if a == "start": return snake_new(rng)
    (hx, hy), (nx_, ny_) = s["body"][0], s["body"][1]
    d = (hx - nx_, hy - ny_)
    if a in DIRS and DIRS[a] != (-d[0], -d[1]): d = DIRS[a]
    head = (hx + d[0], hy + d[1])
    grow = head == s["food"]
    body = s["body"] if grow else s["body"][:-1]
    if not (0 <= head[0] < W and 1 <= head[1] < H) or head in body: return snake_new(rng)
    body = [head] + body
    if len(body) > 12: body = body[:12]
    food = snake_food(rng, body) if grow else s["food"]
    return dict(body=body, food=food, score=s["score"] + grow, t=(s["t"] + 1) % 100)
def snake_rand(rng):
    s = snake_new(rng)
    for _ in range(rng.randrange(0, 40)): s = snake_step(s, rng.choice(["up", "down", "left", "right", "stay", "stay"]), rng)
    return s

# ---------------- shooter: ship at the bottom auto-fires; enemies descend ----------------
def shoot_new(rng):
    return dict(hx=8, hp=3, score=0, t=0, en=[[1, rng.randrange(W), 1], [1, rng.randrange(W), 2]], bul=[])
def shoot_svg(s):
    items = [("hero", s["hx"], 11)] + [(f"e{k}", x, y) for k, x, y in srt(s["en"])] + [("b", x, y) for _, x, y in srt([[0, *b] for b in s["bul"]])]
    return frame(f'HP {s["hp"]} SCORE {s["score"]} T {s["t"]}', items)
def shoot_step(s, a, rng):
    if a == "start" or s["hp"] <= 0: return shoot_new(rng)
    s = dict(s, en=[list(e) for e in s["en"]], bul=[list(b) for b in s["bul"]])
    if a in ("left", "right"): s["hx"] = min(W - 1, max(0, s["hx"] + DIRS[a][0]))
    s["bul"] = [[x, y - 1] for x, y in s["bul"] if y - 1 >= 1]
    def hits():
        hit_b, hit_e = set(), set()
        for i, (x, y) in enumerate(s["bul"]):
            for j, e in enumerate(s["en"]):
                if j not in hit_e and e[1] == x and e[2] == y: hit_b.add(i); hit_e.add(j); break
        s["score"] = min(99, s["score"] + len(hit_e))
        s["bul"] = [b for i, b in enumerate(s["bul"]) if i not in hit_b]; s["en"] = [e for j, e in enumerate(s["en"]) if j not in hit_e]
    hits()
    if s["t"] % 3 == 0:
        for e in s["en"]: e[2] += 1
        landed = [e for e in s["en"] if e[2] >= 11]
        s["hp"] = max(0, s["hp"] - len(landed)); s["en"] = [e for e in s["en"] if e[2] < 11]
        hits()
    if s["t"] % 2 == 0 and [s["hx"], 10] not in s["bul"]: s["bul"].append([s["hx"], 10])
    if s["t"] % 4 == 0 and len(s["en"]) < 8: s["en"].append([rng.choice([1, 1, 2]), rng.randrange(W), 1])
    s["t"] = (s["t"] + 1) % 100
    return s
def shoot_rand(rng):
    s = shoot_new(rng)
    for _ in range(rng.randrange(0, 40)): s = shoot_step(s, rng.choice(["left", "right", "stay"]), rng)
    return s

# ---------------- dodge: vertical scroller; obstacles and coins fall ----------------
def dodge_new(rng): return dict(hx=8, hp=3, score=0, t=0, ob=[], coins=[])
def dodge_svg(s):
    items = [("hero", s["hx"], 10)] + [(f"o{k}", x, y) for k, x, y in srt(s["ob"])] + [("gem", x, y) for _, x, y in srt([[0, *c] for c in s["coins"]])]
    return frame(f'HP {s["hp"]} SCORE {s["score"]} T {s["t"]}', items)
def dodge_step(s, a, rng):
    if a == "start" or s["hp"] <= 0: return dodge_new(rng)
    s = dict(s, ob=[list(o) for o in s["ob"]], coins=[list(c) for c in s["coins"]])
    if a in ("left", "right"): s["hx"] = min(W - 1, max(0, s["hx"] + DIRS[a][0]))
    s["ob"] = [[k, x, y + 1] for k, x, y in s["ob"] if y + 1 <= 11]
    s["coins"] = [[x, y + 1] for x, y in s["coins"] if y + 1 <= 11]
    hit = [o for o in s["ob"] if o[1] == s["hx"] and o[2] == 10]
    s["hp"] = max(0, s["hp"] - len(hit)); s["ob"] = [o for o in s["ob"] if o not in hit]
    got = [c for c in s["coins"] if c == [s["hx"], 10]]
    s["score"] = min(99, s["score"] + 1 + 5 * len(got)); s["coins"] = [c for c in s["coins"] if c not in got]
    if s["t"] % 2 == 0:
        for _ in range(rng.randint(1, 2)):
            x = rng.randrange(W)
            if not any(o[1] == x and o[2] == 1 for o in s["ob"]): s["ob"].append([rng.choice([1, 2]), x, 1])
    if s["t"] % 5 == 0:
        x = rng.randrange(W)
        if not any(o[1] == x and o[2] == 1 for o in s["ob"]) and [x, 1] not in s["coins"]: s["coins"].append([x, 1])
    s["t"] = (s["t"] + 1) % 100
    return s
def dodge_rand(rng):
    s = dodge_new(rng)
    for _ in range(rng.randrange(0, 30)): s = dodge_step(s, rng.choice(["left", "right", "stay"]), rng)
    return s

# ---------------- platformer: side view, gravity, jump; e1 walks left, e2 walks right ----------------
def plat_new(rng):
    plats, seen = [], set()
    def add(x, y):
        if 0 <= x < W and 1 <= y < H and (x, y) not in seen: seen.add((x, y)); plats.append([2, x, y])
    for x in range(0, 6): add(x, 11)                       # start ground
    x = 6
    while x < W:                                            # ground segments with gaps
        n = rng.randint(2, 4)
        if rng.random() < 0.8:
            for i in range(n): add(x + i, 11)
        x += n + rng.randint(0, 1)
    for _ in range(rng.randint(2, 3)):                      # floating platforms
        px, py, n = rng.randrange(1, W - 3), rng.randrange(6, 9), rng.randint(2, 4)
        for i in range(n): add(px + i, py)
    coins = []
    for _ in range(3):
        x, y = rng.randrange(W), rng.randrange(4, 10)
        if (x, y) not in seen: coins.append([x, y])
    en = []
    tops = [p for p in plats if (p[1], p[2] - 1) not in seen and p[1] > 4]
    for p in rng.sample(tops, min(2, len(tops))): en.append([rng.choice([1, 2]), p[1], p[2] - 1])
    return dict(hx=2, hy=10, vy=0, hp=3, score=0, t=0, plats=plats, coins=coins, en=en)
def plat_svg(s):
    items = [("hero", s["hx"], s["hy"])] + [(f"o{k}", x, y) for k, x, y in srt(s["plats"])] \
          + [(f"e{k}", x, y) for k, x, y in srt(s["en"])] + [("gem", x, y) for _, x, y in srt([[0, *c] for c in s["coins"]])]
    return frame(f'HP {s["hp"]} SCORE {s["score"]} VY {s["vy"]} T {s["t"]}', items)
def plat_step(s, a, rng):
    if a == "start" or s["hp"] <= 0: return plat_new(rng)
    s = dict(s, en=[list(e) for e in s["en"]], coins=[list(c) for c in s["coins"]])
    solid = {(p[1], p[2]) for p in s["plats"]}
    on_ground = (s["hx"], s["hy"] + 1) in solid
    if a in ("left", "right"):
        nx = s["hx"] + DIRS[a][0]
        if 0 <= nx < W and (nx, s["hy"]) not in solid: s["hx"] = nx
    vy = s["vy"]
    if a == "up" and on_ground: vy = -2
    if vy < 0:
        ny = s["hy"] - 1
        if ny >= 1 and (s["hx"], ny) not in solid: s["hy"] = ny; vy += 1
        else: vy = 0
    elif (s["hx"], s["hy"] + 1) not in solid:
        s["hy"] += 1; vy = 0
    s["vy"] = vy
    if s["hy"] > 11:  # fell off the world: lose HP, back to the start
        s.update(hx=2, hy=10, vy=0, hp=s["hp"] - 1)
    for e in s["en"]:
        d = -1 if e[0] == 1 else 1; nx = e[1] + d
        if not (0 <= nx < W) or (nx, e[2]) in solid or (nx, e[2] + 1) not in solid: e[0] = 3 - e[0]
        else: e[1] = nx
    hit = [e for e in s["en"] if e[1] == s["hx"] and e[2] == s["hy"]]
    s["hp"] = max(0, s["hp"] - len(hit)); s["en"] = [e for e in s["en"] if e not in hit]
    got = [c for c in s["coins"] if c == [s["hx"], s["hy"]]]
    s["score"] = min(99, s["score"] + len(got)); s["coins"] = [c for c in s["coins"] if c not in got]
    s["t"] = (s["t"] + 1) % 100
    return s
def plat_rand(rng):
    s = plat_new(rng)
    for _ in range(rng.randrange(0, 30)): s = plat_step(s, rng.choice(["left", "right", "right", "up", "stay"]), rng)
    return s

def surv_new(rng): return surv.new_env(rng)
GENRES = {
    "survivors": (surv_new, surv.step, surv.to_svg, surv.rand_state, ["up", "down", "left", "right", "stay"]),
    "snake": (snake_new, snake_step, snake_svg, snake_rand, ["up", "down", "left", "right", "stay"]),
    "shooter": (shoot_new, shoot_step, shoot_svg, shoot_rand, ["left", "right", "stay"]),
    "dodge": (dodge_new, dodge_step, dodge_svg, dodge_rand, ["left", "right", "stay"]),
    "platformer": (plat_new, plat_step, plat_svg, plat_rand, ["left", "right", "up", "stay", "right"]),
}
if __name__ == "__main__":
    per, out = int(sys.argv[1]), sys.argv[2]
    rng = random.Random(int(sys.argv[3]) if len(sys.argv) > 3 else 0)
    rows = []
    for g, (new, step, svg, rand, acts) in GENRES.items():
        made = []
        while len(made) < per:
            if rng.random() < 0.08:
                if g == "survivors":
                    lay = rng.choice(surv.LAYOUTS + [None]); a = f"start {lay}" if lay else "start"
                    made.append(dict(description=f"{g}: {a}\n{EMPTY}", svg=svg(surv.new_env(rng, lay)), genre=g))
                else:
                    made.append(dict(description=f"{g}: start\n{EMPTY}", svg=svg(new(rng)), genre=g))
                continue
            s = new(rng) if rng.random() < 0.3 else rand(rng); a = "stay"
            for _ in range(25):
                if rng.random() > 0.55: a = rng.choice(acts)
                nxt = step(s, a, rng)
                made.append(dict(description=f"{g}: {a}\n{svg(s)}", svg=svg(nxt), genre=g)); s = nxt
        rows += made[:per]
    rng.shuffle(rows)
    with open(out, "w") as f:
        for r in rows: f.write(json.dumps(r) + "\n")
    print("wrote", len(rows))
