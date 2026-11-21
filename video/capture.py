"""Record real model output from the running demo (through the SSH tunnel) for the Remotion video."""
import json, time, urllib.request
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
BASE = "http://127.0.0.1:8090"
H = {"Content-Type": "application/json", "X-Atelier": "3"}
def post(path, body, timeout=180):
    return json.load(urllib.request.urlopen(urllib.request.Request(BASE + path, json.dumps(body).encode(), H), timeout=timeout))
def step(svg, action):
    t = time.time()
    req = urllib.request.Request(BASE + "/step_stream", json.dumps({"svg": svg, "action": action, "temperature": 0.3}).encode(), H)
    out = "".join(json.loads(l).get("text", "") for l in urllib.request.urlopen(req, timeout=120))
    return out, round((time.time() - t) * 1000)
RUNS = [
    ("survivors", "Le Chat survives a haunted cheese dungeon full of ghost rats", ["right"] * 4 + ["up"] * 4 + ["left"] * 5 + ["down"] * 4 + ["stay"] * 3 + ["right"] * 4),
    ("snake", "Le Chat grows longer eating sardines in a neon maze", ["up"] * 3 + ["left"] * 4 + ["down"] * 4 + ["right"] * 5 + ["up"] * 3 + ["left"] * 5),
    ("shooter", "Le Chat defends the moon from alien laser mice in a tiny rocket", ["left"] * 4 + ["right"] * 7 + ["stay"] * 3 + ["left"] * 6 + ["right"] * 4),
    ("dodge", "Le Chat dodges falling croissants on a Paris highway", ["left", "left", "right", "stay", "right", "right", "left", "stay"] * 3),
    ("platformer", "Le Chat leaps across rooftop platforms collecting golden fish", ["right", "right", "up", "right", "right", "stay", "up", "right"] * 3),
]
data = {"runs": []}
for genre, prompt, keys in RUNS:
    t0 = time.time(); spec = post("/arena", {"prompt": prompt}); design_ms = round((time.time() - t0) * 1000)
    names = {"hero": "orange cat", "e1": spec["enemies"][0]["name"], "e2": spec["enemies"][1]["name"], "e3": spec["enemies"][2]["name"],
             "o1": spec["obstacles"][0], "o2": spec["obstacles"][1] + (" block" if genre == "platformer" else ""), "gem": spec["gem"],
             "b": spec.get("projectile") or "yellow energy bolt"}
    with ThreadPoolExecutor(8) as ex:
        sprites = dict(zip(names, ex.map(lambda n: post("/sprite", {"name": n, "temperature": 0.75}), names.values())))
    start = post("/start", {"genre": genre, "layout": spec.get("layout", "")})
    frames = [{"action": f"{genre}: start", "svg": start["svg"], "ms": start["ms"], "source": start["source"]}]
    f = start["svg"]
    for k in keys:
        f, ms = step(f, f"{genre}: {k}"); frames.append({"action": f"{genre}: {k}", "svg": f, "ms": ms})
    story = post("/narrate", {"title": spec["title"], "event": f"Le Chat, a brave orange cat, begins a {genre} adventure. Dream up the next part of the story."})
    data["runs"].append({"genre": genre, "prompt": prompt, "title": spec["title"], "intro": spec["intro"], "design_ms": design_ms,
                         "director_genre": spec.get("genre"), "names": names, "sprites": {k: v["rows"] for k, v in sprites.items()},
                         "sprite_ms": {k: v["ms"] for k, v in sprites.items()}, "frames": frames, "story": story.get("text", "")})
    print(genre, "| title:", spec["title"], "| director picked:", spec.get("genre"), "| frames:", len(frames), "| start:", start["source"],
          "| mean step ms:", round(sum(x["ms"] for x in frames[1:]) / (len(frames) - 1)), flush=True)
surv = data["runs"][0]
fut = post("/step_all", {"svg": surv["frames"][6]["svg"], "genre": "survivors", "actions": ["up", "down", "left", "right", "stay"]})
data["futures"] = {"from": surv["frames"][6]["svg"], "ms": fut["ms"], "branches": {k: v["svg"] for k, v in fut["branches"].items()}}
json.dump(data, open(Path(__file__).parent / "src" / "data.json", "w"))
print("saved data.json; futures in", fut["ms"], "ms")
