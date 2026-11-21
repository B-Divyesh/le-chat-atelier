"""Extract, minify, safety-check and render each generated SVG; write manifest + 224px PNGs."""
import io, json, os, re, sys
from multiprocessing import get_context
from xml.etree import ElementTree as ET
BAD = {"image", "script", "foreignObject", "style", "use", "iframe", "filter", "pattern", "mask", "feGaussianBlur", "clipPath"}
import signal
class Slow(Exception): pass
def _alarm(*_): raise Slow()
signal.signal(signal.SIGALRM, _alarm)

def work(args):
    line, png_dir = args
    import cairosvg
    from PIL import Image, ImageChops
    row = json.loads(line); row["valid"] = False; text = row.pop("text", "")
    m = re.search(r"<svg\b.*?</svg>", text, re.S)
    if not m: return row
    svg = re.sub(r"<!--.*?-->", "", m.group(), flags=re.S)
    svg = re.sub(r">\s+<", "><", svg).strip(); svg = re.sub(r"\s{2,}", " ", svg)
    try:
        root = ET.fromstring(svg)
        for el in root.iter():
            if el.tag.split("}")[-1] in BAD: return row
            for a, v in el.attrib.items():
                if a.endswith("href") or re.search(r"url\(\s*[^#]", v, re.I): return row
        signal.alarm(2)
        try:
            png = cairosvg.svg2png(bytestring=svg.encode(), output_width=224, output_height=224)
        finally:
            signal.alarm(0)
        img = Image.open(io.BytesIO(png)).convert("RGBA"); white = Image.new("RGBA", img.size, "white")
        vis = Image.alpha_composite(white, img).convert("RGB")
        if not ImageChops.difference(vis, Image.new("RGB", vis.size, "white")).getbbox(): return row
        vis.save(f"{png_dir}/{row['i']}_{row['k']}.png")
    except (Exception, Slow):
        return row
    row.update(valid=True, svg=svg)
    return row

if __name__ == "__main__":
    SRC, MAN, PNG = sys.argv[1], sys.argv[2], sys.argv[3]
    os.makedirs(PNG, exist_ok=True)
    lines = open(SRC).readlines()
    rows = [work((l, PNG)) for l in lines]
    from tokenizers import Tokenizer
    tok = Tokenizer.from_file("/dev/shm/atelier-merged-0625/tokenizer.json")
    valid = [r for r in rows if r["valid"]]
    for r, enc in zip(valid, tok.encode_batch([r["svg"] + "</s>" for r in valid], add_special_tokens=False)):
        r["svg_tokens"] = len(enc.ids)
    with open(MAN, "w") as out:
        for r in rows: out.write(json.dumps(r, ensure_ascii=False) + "\n")
    print("rows", len(rows), "valid", len(valid), flush=True)
