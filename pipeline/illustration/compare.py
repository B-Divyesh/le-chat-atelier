import json, sys, textwrap
from PIL import Image, ImageDraw
models = sys.argv[1].split(","); idx = [int(x) for x in sys.argv[2].split(",")]; out = sys.argv[3]
W = 150; sheet = Image.new("RGB", (120 + W * len(idx), 40 + (W + 10) * len(models)), "white"); d = ImageDraw.Draw(sheet)
prompts = [json.loads(l)["prompt"] for l in open("/dev/shm/work/heldout_prompts.jsonl")]
for c, i in enumerate(idx):
    d.multiline_text((120 + c * W + 2, 2), "\n".join(textwrap.wrap(prompts[i], 24)[:3]), fill="black")
for r, m in enumerate(models):
    sc = {json.loads(l)["i"]: json.loads(l) for l in open(f"/dev/shm/work/ev-{m}-scored.jsonl")}
    d.text((4, 40 + r * (W + 10) + W // 2), m, fill="black")
    for c, i in enumerate(idx):
        x, y = 120 + c * W, 40 + r * (W + 10)
        try:
            sheet.paste(Image.open(f"/dev/shm/work/ev-{m}-png/{i}_0.png").convert("RGB").resize((W - 6, W - 6)), (x, y))
            d.text((x + 2, y + W - 4), f"clip {sc[i].get('clip')}", fill="blue")
        except FileNotFoundError:
            d.text((x + 10, y + 60), "INVALID", fill="red")
sheet.save(out)
