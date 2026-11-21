"""Convert pixel-art atlas sprites to 8x8 PICO-8 grids ('.'=transparent, 0-f=palette) + preview + JSONL."""
import io, json, random, sys, glob
from collections import Counter
import pyarrow.parquet as pq
from PIL import Image, ImageDraw
PICO = ["#000000","#1D2B53","#7E2553","#008751","#AB5236","#5F574F","#C2C3C7","#FFF1E8","#FF004D","#FFA300","#FFEC27","#00E436","#29ADFF","#83769C","#FF77A8","#FFCCAA"]
PAL = [tuple(int(h[i:i+2], 16) for i in (1, 3, 5)) for h in PICO]
HEX = "0123456789abcdef"
N = int(sys.argv[2]) if len(sys.argv) > 2 else 8
def lab(c):
    def f(u):
        u /= 255; return ((u + 0.055) / 1.055) ** 2.4 if u > 0.04045 else u / 12.92
    r, g, b = (f(float(v)) for v in c[:3])
    x, y, z = (r * .4124 + g * .3576 + b * .1805) / .95047, r * .2126 + g * .7152 + b * .0722, (r * .0193 + g * .1192 + b * .9505) / 1.08883
    h = lambda t: t ** (1 / 3) if t > 0.008856 else 7.787 * t + 16 / 116
    return (116 * h(y) - 16, 500 * (h(x) - h(y)), 200 * (h(y) - h(z)))
PAL_LAB = [lab(p) for p in PAL]
_cache = {}
def nearest(c):
    key = c[:3]
    if key not in _cache:
        L = lab(key); _cache[key] = min(range(16), key=lambda i: sum((PAL_LAB[i][k] - L[k]) ** 2 for k in range(3)))
    return _cache[key]
def to_grid(png):
    im = Image.open(io.BytesIO(png)).convert("RGBA")
    W, H = im.size
    bbox = im.getchannel("A").point(lambda a: 255 if a > 100 else 0).getbbox()
    if not bbox: return None, im.size
    im = im.crop(bbox); w, h = im.size; s = max(w, h)
    sq = Image.new("RGBA", (s, s), (0, 0, 0, 0)); sq.paste(im, ((s - w) // 2, (s - h) // 2))
    px = sq.load(); rows = []
    for gy in range(N):
        row = ""
        for gx in range(N):
            x0, x1 = gx * s // N, max(gx * s // N + 1, (gx + 1) * s // N); y0, y1 = gy * s // N, max(gy * s // N + 1, (gy + 1) * s // N)
            cells = [px[x, y] for y in range(y0, y1) for x in range(x0, x1)]
            opaque = [c for c in cells if c[3] > 100]
            if len(opaque) * 2 < len(cells): row += "."; continue
            row += HEX[Counter(nearest(c) for c in opaque).most_common(1)[0][0]]
        rows.append(row)
    return rows, (W, H)
rows = []
for f in sorted(glob.glob(sys.argv[1])):
    rows += pq.read_table(f, columns=["image", "caption", "subject"]).to_pylist()
random.Random(1).shuffle(rows)
PART, PARTS = (int(sys.argv[3]), int(sys.argv[4])) if len(sys.argv) > 4 else (0, 1)
rows = rows[PART::PARTS]
sizes = Counter(); out = []
for r in rows:
    g, size = to_grid(r["image"]["bytes"]); sizes[size] += 1
    if not g: continue
    filled = sum(ch != "." for line in g for ch in line)
    if filled < N * N * 0.2 or len(set("".join(g)) - {"."}) < 2: continue
    out.append(dict(caption=r["caption"].strip(), subject=r["subject"], grid="\n".join(g)))
print("rows", len(rows), "kept", len(out), "image sizes", sizes.most_common(4))
with open(f"/dev/shm/work/pixlab{N}_part{PART}.jsonl", "w") as f:
    for o in out: f.write(json.dumps(o) + "\n")
S = 12; cell = S * N + 4; cols = 12
sheet = Image.new("RGB", (cols * cell, 3 * (cell + 26)), (40, 110, 60)); d = ImageDraw.Draw(sheet)
for i, o in enumerate(out[:cols * 3]):
    x0, y0 = (i % cols) * cell, (i // cols) * (cell + 26)
    for y, line in enumerate(o["grid"].split("\n")):
        for x, ch in enumerate(line):
            if ch != ".": d.rectangle([x0 + 2 + x * S, y0 + 2 + y * S, x0 + 1 + (x + 1) * S, y0 + 1 + (y + 1) * S], fill=PICO[HEX.index(ch)])
    d.text((x0 + 2, y0 + cell), o["caption"][:18], fill="white")
sheet.save(f"/dev/shm/work/pixlab{N}-preview{PART}.png")
