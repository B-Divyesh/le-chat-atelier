import json, urllib.request
def post(path, body):
    return json.load(urllib.request.urlopen(urllib.request.Request("http://127.0.0.1:8090" + path, json.dumps(body).encode(), {"Content-Type": "application/json"}), timeout=120))
def start(genre):
    req = urllib.request.Request("http://127.0.0.1:8090/step_stream", json.dumps({"svg": '<svg viewBox="0 0 16 12"></svg>', "action": f"{genre}: start"}).encode(), {"Content-Type": "application/json"})
    return "".join(json.loads(l).get("text", "") for l in urllib.request.urlopen(req, timeout=120))
acts = {"survivors": ["up", "down", "left", "right", "stay"], "snake": ["up", "down", "left", "right", "stay"], "shooter": ["left", "right", "stay"],
        "dodge": ["left", "right", "stay"], "platformer": ["left", "right", "up", "stay"]}
for g, A in acts.items():
    f = start(g); print(f"== {g} start: {f[46:210]}")
    for a in [A[0], A[-1], A[1]]:
        r = post("/step_all", {"svg": f, "genre": g, "actions": A}); f = r["branches"][a]["svg"]
        ms = r["ms"]
        print(f"   {a:5} ({len(A)} branches in {ms} ms): {f[46:210]}")
