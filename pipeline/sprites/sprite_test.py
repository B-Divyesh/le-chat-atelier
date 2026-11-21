"""Generate sprites from the model, rasterize to 16x16, remove background, snap to PICO-8 palette, outline; save a preview grid."""
import io, json, re, sys, urllib.request
from concurrent.futures import ThreadPoolExecutor
import cairosvg
from PIL import Image, ImageDraw
SYSTEM = "Draw the requested illustration. Return only a complete SVG on a 200 by 200 viewBox."
PICO = ["#000000","#1D2B53","#7E2553","#008751","#AB5236","#5F574F","#C2C3C7","#FFF1E8","#FF004D","#FFA300","#FFEC27","#00E436","#29ADFF","#83769C","#FF77A8","#FFCCAA"]
PAL = [tuple(int(h[i:i+2], 16) for i in (1, 3, 5)) for h in PICO]
NAMES = ["a green oak tree", "a grey rock", "a red health potion", "a gold coin", "a green slime monster", "a red mushroom",
         "a knight hero", "a cactus", "a purple bat", "a wooden treasure chest", "a pine tree with snow", "a blue crystal"]
def gen(port, name):
    p = f"[SYSTEM_PROMPT]{SYSTEM}[/SYSTEM_PROMPT][INST]Generate an SVG illustration: {name}, simple game sprite icon[/INST]"
    r = json.load(urllib.request.urlopen(urllib.request.Request(f"http://127.0.0.1:{port}/completion", json.dumps(dict(
        prompt=p, n_predict=450, temperature=0.7, top_p=0.95, stop=["</svg>"], cache_prompt=True)).encode(), {"Content-Type": "application/json"}), timeout=120))
    return r["content"] + "</svg>", r["tokens_predicted"], r["timings"]["predicted_ms"]
def close(t):
    m = re.search(r"<svg\b.*", t, re.S)
    if not m: return None
    s = m.group(); s = s[: s.find("</svg>") + 6] if "</svg>" in s else s
    s = s[: s.rfind(">") + 1]; stack = []
    for mm in re.finditer(r"<(/?)([a-zA-Z][\w:-]*)\b[^>]*?(/?)>", s):
        if mm.group(1): stack and stack.pop()
        elif not mm.group(3): stack.append(mm.group(2))
    s += "".join(f"</{x}>" for x in reversed(stack))
    return s if "xmlns" in s[:200] else s.replace("<svg", '<svg xmlns="http://www.w3.org/2000/svg"', 1)
def pixelate(svg, n=16):
    im = Image.open(io.BytesIO(cairosvg.svg2png(bytestring=svg.encode(), output_width=n, output_height=n))).convert("RGBA")
    px = im.load(); W = n
    corners = [px[0, 0], px[W-1, 0], px[0, W-1], px[W-1, W-1]]
    bg = max(set(corners), key=corners.count)
    if bg[3] > 128:  # opaque background: flood-fill it away from the border
        near = lambda c: c[3] > 128 and sum(abs(c[i] - bg[i]) for i in range(3)) < 60
        stack = [(x, y) for x in range(W) for y in (0, W-1)] + [(x, y) for y in range(W) for x in (0, W-1)]; seen = set()
        while stack:
            x, y = stack.pop()
            if (x, y) in seen or not (0 <= x < W and 0 <= y < W) or not near(px[x, y]): continue
            seen.add((x, y)); px[x, y] = (0, 0, 0, 0); stack += [(x+1, y), (x-1, y), (x, y+1), (x, y-1)]
    out = Image.new("RGBA", (W, W), (0, 0, 0, 0)); o = out.load()
    for y in range(W):
        for x in range(W):
            c = px[x, y]
            if c[3] > 110: o[x, y] = min(PAL, key=lambda p: sum((p[i] - c[i]) ** 2 for i in range(3))) + (255,)
    for y in range(W):  # 1px dark outline around the sprite
        for x in range(W):
            if o[x, y][3] == 0 and any(0 <= x+dx < W and 0 <= y+dy < W and out.getpixel((x+dx, y+dy))[3] == 255 and out.getpixel((x+dx, y+dy))[:3] != (0, 0, 0) for dx, dy in ((1,0),(-1,0),(0,1),(0,-1))):
                o[x, y] = (0, 0, 0, 200)
    return out
for port, label in ((8100, "distilled"), (8099, "base")):
    with ThreadPoolExecutor(12) as ex: res = list(ex.map(lambda n: gen(port, n), NAMES))
    sheet = Image.new("RGB", (len(NAMES) * 100, 130), (40, 120, 60)); d = ImageDraw.Draw(sheet)
    for i, (txt, tok, ms) in enumerate(res):
        s = close(txt)
        try: sheet.paste(pixelate(s).resize((96, 96), Image.NEAREST), (i * 100 + 2, 2), pixelate(s).resize((96, 96), Image.NEAREST))
        except Exception as e: d.text((i * 100 + 5, 40), "fail", fill="red")
        d.text((i * 100 + 2, 100), f"{NAMES[i][2:16]}\n{tok}t {ms/1000:.1f}s", fill="white")
    sheet.save(f"/dev/shm/work/sprites-{label}.png")
    print(label, "tokens", [t for _, t, _ in res], "mean s", round(sum(m for *_, m in res) / len(res) / 1000, 2))
