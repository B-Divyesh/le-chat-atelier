"""Same frame, different keys -> what does the world model write? (live server, real requests)"""
import json, re, urllib.request
H = {"Content-Type": "application/json", "X-Atelier": "3"}
def post(path, body): return json.load(urllib.request.urlopen(urllib.request.Request("http://127.0.0.1:8090" + path, json.dumps(body).encode(), H), timeout=120))
def step(svg, action):
    req = urllib.request.Request("http://127.0.0.1:8090/step_stream", json.dumps({"svg": svg, "action": action, "temperature": 0}).encode(), H)
    return "".join(json.loads(l).get("text", "") for l in urllib.request.urlopen(req, timeout=120))
hero = lambda s: tuple(map(int, re.search(r'#hero" x="(\d+)" y="(\d+)"', s).groups()))
hud = lambda s: re.search(r">([^<]*)</text>", s).group(1)
for genre, keys in [("survivors", ["up", "down", "left", "right", "stay"]), ("platformer", ["left", "right", "up", "stay"]), ("snake", ["up", "down", "left", "right"])]:
    f = post("/start", {"genre": genre})["svg"]
    print(f"== {genre}: current frame hero at {hero(f)}  HUD '{hud(f)}'")
    for k in keys:
        n = step(f, f"{genre}: {k}")
        enemies = re.findall(r'#(e\d)" x="(\d+)" y="(\d+)"', n)[:2]
        print(f"   key {k:5} -> hero {hero(n)}  HUD '{hud(n)}'  first enemies {enemies}")
