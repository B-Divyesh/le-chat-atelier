"""Simulate N players stepping the world model through the game server while sampling GPU utilisation."""
import json, subprocess, sys, threading, time, urllib.request
H = {"Content-Type": "application/json", "X-Atelier": "3"}
def post(path, body): return json.load(urllib.request.urlopen(urllib.request.Request("http://127.0.0.1:8090" + path, json.dumps(body).encode(), H), timeout=180))
def step(svg, action):
    req = urllib.request.Request("http://127.0.0.1:8090/step_stream", json.dumps({"svg": svg, "action": action, "temperature": 0.3}).encode(), H)
    return "".join(json.loads(l).get("text", "") for l in urllib.request.urlopen(req, timeout=180))
def player(genre, n, out):
    f = post("/start", {"genre": genre})["svg"]; t = time.time()
    for i in range(n): f = step(f, f"{genre}: " + ["right", "up", "left", "down"][i % 4])
    out.append((n, time.time() - t))
def sample(stop, rows):
    while not stop.is_set():
        r = subprocess.run(["nvidia-smi", "--query-gpu=index,utilization.gpu,memory.used,power.draw", "--format=csv,noheader,nounits"], capture_output=True, text=True).stdout
        rows.append([[float(x) for x in line.split(",")] for line in r.strip().splitlines()]); time.sleep(0.5)
for players in (1, 4):
    genres = ["survivors", "snake", "shooter", "platformer"][:players]
    out, rows, stop = [], [], threading.Event()
    s = threading.Thread(target=sample, args=(stop, rows)); s.start()
    th = [threading.Thread(target=player, args=(g, 15, out)) for g in genres]; [t.start() for t in th]; [t.join() for t in th]
    stop.set(); s.join()
    for gpu in (0, 1):
        u = [r[gpu][1] for r in rows if len(r) > gpu]; m = [r[gpu][2] for r in rows if len(r) > gpu]; p = [r[gpu][3] for r in rows if len(r) > gpu]
        print(f"{players} player(s) | GPU{gpu}: util avg {sum(u)/len(u):5.1f}% peak {max(u):5.1f}% | mem peak {max(m)/1024:4.1f} GB | power avg {sum(p)/len(p):5.0f} W")
    fps = [n / t for n, t in out]
    print(f"{players} player(s) | per-player {sum(fps)/len(fps):.2f} frames/s | total {sum(fps):.2f} frames/s")
