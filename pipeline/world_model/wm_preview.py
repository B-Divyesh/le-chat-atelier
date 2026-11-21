"""Render a real training trajectory (action + SVG frame -> next SVG frame) with AI sprites, as the game shows it."""
import io, json, re, urllib.request
import cairosvg
from PIL import Image, ImageDraw
PICO = ["#000000","#1D2B53","#7E2553","#008751","#AB5236","#5F574F","#C2C3C7","#FFF1E8","#FF004D","#FFA300","#FFEC27","#00E436","#29ADFF","#83769C","#FF77A8","#FFCCAA"]
HEX = "0123456789abcdef"
spec = json.load(open("/dev/shm/work/arena-test.json"))
plan = {"hero": spec["hero"], "e1": spec["enemies"][0]["name"], "e2": spec["enemies"][1]["name"], "e3": spec["enemies"][2]["name"],
        "o1": spec["obstacles"][0], "o2": spec["obstacles"][1], "gem": spec["gem"]}
sprites = {}
for k, name in plan.items():
    r = json.load(urllib.request.urlopen(urllib.request.Request("http://127.0.0.1:8090/sprite", json.dumps({"name": name, "temperature": 0.75}).encode(),
                  {"Content-Type": "application/json"}), timeout=60))
    sprites[k] = "".join(f'<rect x="{x/8:.3f}" y="{y/8:.3f}" width="0.13" height="0.13" fill="{PICO[HEX.index(c)]}"/>'
                         for y, row in enumerate(r["rows"]) for x, c in enumerate(row) if c != ".")
def compose(frame):
    body = []
    for m in re.finditer(r'<text x="0" y="1">([^<]*)</text>|<use href="#(\w+)" x="(\d+)" y="(\d+)"/>', frame):
        if m.group(1) is not None:
            body.append(f'<text x="0.2" y="0.75" font-family="monospace" font-size="0.62" fill="#FFF1E8" stroke="#000" stroke-width="0.1" paint-order="stroke">{m.group(1)}</text>')
        else:
            body.append(f'<g transform="translate({m.group(3)} {m.group(4)})">{sprites[m.group(2)]}</g>')
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 12" width="480" height="360" shape-rendering="crispEdges">'
            f'<rect width="16" height="12" fill="#008751"/>' + "".join(body) + "</svg>")
rows = [json.loads(l) for l in open("/dev/shm/work/data-wm2/all.jsonl")]
start = next(r for r in rows if r["description"].startswith("start"))
best = None
for i in range(len(rows) - 8):
    chain = rows[i:i + 7]
    if all(chain[j]["svg"] == chain[j + 1]["description"].split("\n", 1)[1] for j in range(6)) and chain[0]["description"].count("#e") >= 3 \
            and any(a in chain[j]["description"] for j in range(6) for a in ("left", "right", "up")):
        best = chain; break
frames = [("start (empty SVG in)", start["svg"])] + [(c["description"].split("\n")[0], c["svg"]) for c in best]
sheet = Image.new("RGB", (4 * 490, 2 * 400), (13, 12, 20)); d = ImageDraw.Draw(sheet)
for i, (label, fr) in enumerate(frames[:8]):
    png = cairosvg.svg2png(bytestring=compose(fr).encode())
    x, y = (i % 4) * 490 + 5, (i // 4) * 400 + 30
    sheet.paste(Image.open(io.BytesIO(png)).convert("RGB"), (x, y))
    d.text((x, y - 22), f"frame {i}  ·  action → {label}", fill=(255, 163, 0))
sheet.save("/dev/shm/work/wm-preview.png")
print("names:", plan)
print("EXAMPLE TRANSITION\nINPUT:", best[1]["description"].replace("\n", "  |  "), "\nOUTPUT:", best[1]["svg"])
