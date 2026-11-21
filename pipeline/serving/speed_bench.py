import json, time, urllib.request
def post(path, body):
    return json.load(urllib.request.urlopen(urllib.request.Request("http://127.0.0.1:8090" + path, json.dumps(body).encode(), {"Content-Type": "application/json"}), timeout=120))
def stream(svg, action):
    req = urllib.request.Request("http://127.0.0.1:8090/step_stream", json.dumps({"svg": svg, "action": action}).encode(), {"Content-Type": "application/json"})
    t = time.time(); out = ""; first = None
    for line in urllib.request.urlopen(req, timeout=120):
        o = json.loads(line)
        if o.get("text"): out += o["text"]; first = first or time.time() - t
    return out, time.time() - t, first
acts = {"survivors": ["up", "left", "stay", "right", "down"], "snake": ["up", "left", "down", "right", "stay"], "shooter": ["left", "right", "stay"],
        "dodge": ["left", "right", "stay"], "platformer": ["right", "up", "right", "stay"]}
for g, A in acts.items():
    f = post("/start", {"genre": g})["svg"]; single = []
    for i in range(10):
        f, dt, first = stream(f, f"{g}: {A[i % len(A)]}"); single.append(dt)
    allb = [post("/step_all", {"svg": f, "genre": g, "actions": sorted(set(A))})["ms"] for _ in range(3)]
    print(f"{g:10} single step: {1000*sum(single)/len(single):4.0f} ms avg ({1/(sum(single)/len(single)):.1f} fps) | all {len(set(A))} futures: {sum(allb)/len(allb):4.0f} ms avg")
