"""End-to-end test through the studio's server (/generate NDJSON), one request at a time like a user."""
import io, json, re, sys, textwrap, time, urllib.request
import cairosvg
from PIL import Image, ImageChops, ImageDraw
URL, MODEL, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
TEMPLATE = sys.argv[4] if len(sys.argv) > 4 else "{}"
PROMPTS = ["A red apple with a green leaf", "A cute orange cat sitting", "A rocket ship flying to the moon",
           "A cup of hot coffee", "A small house with a tree next to it", "A smiling yellow sun",
           "A blue bicycle", "A pizza slice with pepperoni"]
cells, rows = [], []
for p in PROMPTS:
    req = urllib.request.Request(URL, json.dumps(dict(prompt=TEMPLATE.format(p[0].lower() + p[1:]) if TEMPLATE != "{}" else p, model=MODEL)).encode(), {"Content-Type": "application/json"})
    t0 = time.monotonic(); first_text = first_path = None; text = ""; done = {}
    with urllib.request.urlopen(req, timeout=300) as r:
        for line in r:
            o = json.loads(line)
            if "error" in o: done = {"error": o["error"]}; break
            if "text" in o:
                text += o["text"]; now = time.monotonic() - t0
                first_text = first_text or now
                if first_path is None and re.search(r"<path\b[^>]*/>", text): first_path = now
            if o.get("done"): done = o
    total = time.monotonic() - t0
    ok, img = False, Image.new("RGB", (200, 200), "white")
    m = re.search(r"<svg\b.*?</svg>", text, re.S)
    if m:
        try:
            rgba = Image.open(io.BytesIO(cairosvg.svg2png(bytestring=m.group().encode(), output_width=200, output_height=200))).convert("RGBA")
            img.paste(rgba, mask=rgba.getchannel("A")); ok = bool(ImageChops.difference(img, Image.new("RGB", (200, 200), "white")).getbbox())
        except Exception: pass
    row = dict(prompt=p, ok=ok, tokens=done.get("tokens"), total_s=round(total, 1), first_path_s=first_path and round(first_path, 2),
               tok_s=round((done.get("tokens") or 0) / total, 1), stopped=done.get("stopped"), repaired=done.get("repaired"))
    rows.append(row); cells.append((img, row)); print(json.dumps(row), flush=True)
sheet = Image.new("RGB", (800, 265 * 2), "white"); d = ImageDraw.Draw(sheet)
for i, (img, r) in enumerate(cells):
    x, y = (i % 4) * 200, (i // 4) * 265; sheet.paste(img, (x, y))
    d.multiline_text((x + 3, y + 202), "\n".join(textwrap.wrap(f"{r['tokens']}t {r['total_s']}s {'' if r['ok'] else 'FAIL '}| {r['prompt']}", 33)[:4]), fill="black")
sheet.save(OUT)
print(json.dumps(dict(model=MODEL, valid=sum(r["ok"] for r in rows), n=len(rows), mean_total_s=round(sum(r["total_s"] for r in rows) / len(rows), 1),
                      mean_tok_s=round(sum(r["tok_s"] for r in rows) / len(rows), 1))))
