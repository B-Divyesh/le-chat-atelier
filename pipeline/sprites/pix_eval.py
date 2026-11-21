"""Ask the sprite model (via the game server's /sprite) for every game object; render a labeled gallery."""
import json, sys, time, urllib.request
from concurrent.futures import ThreadPoolExecutor
from PIL import Image, ImageDraw
PICO = ["#000000","#1D2B53","#7E2553","#008751","#AB5236","#5F574F","#C2C3C7","#FFF1E8","#FF004D","#FFA300","#FFEC27","#00E436","#29ADFF","#83769C","#FF77A8","#FFCCAA"]
HEX = "0123456789abcdef"
NAMES = ["silver knight", "green oak tree", "green round bush", "grey boulder", "brown tree stump", "red apple", "red health potion", "gold coin",
         "red mushroom", "green slime", "yellow bee", "brown wild boar", "dark green pine tree", "green mossy rock", "brown fallen log", "blue berries",
         "grey wolf", "purple bat", "green goblin", "green cactus", "orange sandstone rock", "white skull", "blue water flask", "red ruby gem",
         "orange scorpion", "yellow sand snake", "white mummy", "snowy pine tree", "blue ice block", "white snowman", "hot soup bowl", "blue crystal"]
def one(n):
    t = time.time()
    r = json.load(urllib.request.urlopen(urllib.request.Request("http://127.0.0.1:8090/sprite", json.dumps({"name": n, "temperature": 0.75}).encode(),
                  {"Content-Type": "application/json"}), timeout=60))
    return n, r, time.time() - t
t0 = time.time()
with ThreadPoolExecutor(16) as ex: res = list(ex.map(one, NAMES))
wall = time.time() - t0
S, cols = 10, 8; cell = 8 * S + 10
sheet = Image.new("RGB", (cols * cell, (len(NAMES) + cols - 1) // cols * (cell + 24)), (40, 110, 60)); d = ImageDraw.Draw(sheet)
for i, (n, r, s) in enumerate(res):
    x0, y0 = (i % cols) * cell, (i // cols) * (cell + 24)
    if "rows" not in r: d.text((x0 + 5, y0 + 30), "ERR", fill="red"); continue
    for y, row in enumerate(r["rows"]):
        for x, ch in enumerate(row):
            if ch != ".": d.rectangle([x0 + 5 + x * S, y0 + 5 + y * S, x0 + 4 + (x + 1) * S, y0 + 4 + (y + 1) * S], fill=PICO[HEX.index(ch)])
    d.text((x0 + 3, y0 + cell - 2), f"{n[:15]}\n{r['ms']}ms {r['tokens']}t", fill="white")
sheet.save(sys.argv[1])
ok = [r for _, r, _ in res if "rows" in r]
print(json.dumps(dict(sprites=len(NAMES), ok=len(ok), wall_s=round(wall, 2), mean_ms=round(sum(r["ms"] for r in ok) / max(1, len(ok))),
                      mean_tokens=round(sum(r["tokens"] for r in ok) / max(1, len(ok)), 1))))
