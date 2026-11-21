"""Contact sheet + stats from an eval output dir (works on partial runs)."""
import json, sys, textwrap
from pathlib import Path
from PIL import Image, ImageDraw
from tokenizers import Tokenizer
tok = Tokenizer.from_file("/dev/shm/atelier-merged-0625/tokenizer.json")
d, prompts, out = Path(sys.argv[1]), sys.argv[2], sys.argv[3]
rows = [json.loads(l) for l in open(prompts)]
done = sorted(d.glob("*.svg.txt"))
sheet = Image.new("RGB", (1000, 265 * ((len(done) + 4) // 5)), "white"); dr = ImageDraw.Draw(sheet)
stats = []
for k, f in enumerate(done):
    i = int(f.name[:2]); txt = f.read_text(); n = len(tok.encode(txt).ids); png = d / f"{i:02d}.png"
    x, y = (k % 5) * 200, (k // 5) * 265
    if png.exists():
        sheet.paste(Image.open(png).convert("RGB"), (x, y))
    else:
        dr.text((x + 10, y + 90), "INVALID / UNCLOSED", fill="red")
    ok = "ok" if png.exists() else "FAIL"
    stats.append((n, png.exists(), txt.rstrip().endswith("</svg>")))
    label = f"{i:02d} {n}t {ok} | " + rows[i]["description"]
    dr.multiline_text((x + 3, y + 202), "\n".join(textwrap.wrap(label, 33)[:4]), fill="black")
sheet.save(out)
print("done", len(stats), "valid", sum(s[1] for s in stats), "closed", sum(s[2] for s in stats),
      "mean tokens", round(sum(s[0] for s in stats) / max(1, len(stats))), "tokens", [s[0] for s in stats])
print("reference mean tokens for these prompts:", round(sum(r["tokens"] for r in rows) / len(rows)))
