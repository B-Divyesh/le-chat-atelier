"""Render random samples from a parquet file into a labeled grid, with Ministral token counts."""
import argparse, io, random, re, textwrap
import cairosvg, pyarrow.parquet as pq
from PIL import Image, ImageDraw
from tokenizers import Tokenizer

p = argparse.ArgumentParser()
p.add_argument("parquet", nargs="+"); p.add_argument("--svg", required=True); p.add_argument("--desc", required=True)
p.add_argument("--out", required=True); p.add_argument("--n", type=int, default=20); p.add_argument("--max-tokens", type=int, default=0)
p.add_argument("--int", action="store_true", help="round numbers to integers before counting")
a = p.parse_args()
tok = Tokenizer.from_file("/dev/shm/atelier-merged-0625/tokenizer.json")
rows = []
for f in a.parquet:
    rows += pq.read_table(f, columns=[a.svg, a.desc]).to_pylist()
random.Random(7).shuffle(rows)
NUM = re.compile(r"-?\d+\.\d+")
picked = []
for r in rows:
    s = r[a.svg]
    if a.int: s = NUM.sub(lambda m: str(round(float(m.group()))), s)
    n = len(tok.encode(s).ids)
    if a.max_tokens and n > a.max_tokens: continue
    picked.append((s, r[a.desc], n))
    if len(picked) >= a.n: break
sheet = Image.new("RGB", (1000, 265 * ((len(picked) + 4) // 5)), "white"); d = ImageDraw.Draw(sheet)
for i, (s, desc, n) in enumerate(picked):
    x, y = (i % 5) * 200, (i // 5) * 265
    try:
        img = Image.open(io.BytesIO(cairosvg.svg2png(bytestring=s.encode(), output_width=200, output_height=200))).convert("RGBA")
        bg = Image.new("RGBA", img.size, "white"); sheet.paste(Image.alpha_composite(bg, img).convert("RGB"), (x, y))
    except Exception as e:
        d.text((x + 5, y + 90), "render error", fill="red")
    d.multiline_text((x + 3, y + 202), "\n".join(textwrap.wrap(f"{n}t | {desc}", 33)[:4]), fill="black")
sheet.save(a.out)
print("candidates", len(rows), "picked", len(picked), "mean tokens", round(sum(n for *_, n in picked) / max(1, len(picked))))
