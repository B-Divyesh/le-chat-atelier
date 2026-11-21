"""Pass 1: clean every MMSVG row with integer coordinates and count exact training tokens.
Pass 2 (--select): filter by tokens/colors, render-check, dedupe, write train/valid/eval-short JSONL."""
import argparse, glob, hashlib, io, json, random, re
from collections import Counter
from multiprocessing import Pool
from xml.etree import ElementTree as ET

SYSTEM = "Draw the requested illustration. Return only a complete SVG on a 200 by 200 viewBox."
PREFIX = "Generate an SVG illustration: "
NS = "{http://www.w3.org/2000/svg}"
NUM = re.compile(r"[-+]?(?:\d+\.\d*|\.\d+|\d+)(?:[eE][-+]?\d+)?")
HEX6 = re.compile(r"^#([0-9a-f])\1([0-9a-f])\2([0-9a-f])\3$")
PATH_ATTR = {"d", "fill", "fill-opacity", "fill-rule", "stroke", "stroke-width", "stroke-opacity",
             "stroke-linecap", "stroke-linejoin", "opacity", "filling"}
ET.register_namespace("", NS[1:-1])
TOK = None

def short_hex(v):
    v = v.lower(); m = HEX6.match(v)
    return "#" + m.group(1) + m.group(2) + m.group(3) if m else v

def clean(source):
    root = ET.fromstring(source)
    if root.tag != NS + "svg" or root.attrib.keys() - {"viewBox", "height", "width"}:
        return None, 0
    if list(map(float, root.attrib["viewBox"].split())) != [0, 0, 200, 200]:
        return None, 0
    root.attrib.clear(); root.set("viewBox", "0 0 200 200")
    colors = set()
    for path in root:
        if path.tag != NS + "path" or len(path) or path.attrib.keys() - PATH_ATTR:
            return None, 0
        if any("url" in v.lower() for v in path.attrib.values()):
            return None, 0
        path.attrib.pop("filling", None)
        if path.get("fill-opacity") in {"1", "1.0"}: del path.attrib["fill-opacity"]
        if path.get("fill-rule") == "nonzero": del path.attrib["fill-rule"]
        for k in ("fill", "stroke"):
            if k in path.attrib: path.set(k, short_hex(path.get(k)))
        colors.add(path.get("fill", "black"))
        d = path.attrib["d"]
        if re.search(r"[\d.][-+.]\d", re.sub(r"\d+\.\d+", "1", d)):
            return None, 0
        d = NUM.sub(lambda m: str(round(float(m.group()))), d)
        d = re.sub(r"(L-?\d+ -?\d+)(?: \1)+", r"\1", d)  # drop zero-length repeats from rounding
        path.set("d", d)
    return ET.tostring(root, encoding="unicode", short_empty_elements=True), len(colors)

def init(tok_path):
    global TOK
    from tokenizers import Tokenizer
    TOK = Tokenizer.from_file(tok_path)

def work(item):
    try:
        svg, ncol = clean(item["svg"])
    except Exception:
        return None
    if not svg or not item["description"].strip():
        return None
    cap = item["description"].strip()
    prompt = "<s>[SYSTEM_PROMPT]" + SYSTEM + "[/SYSTEM_PROMPT][INST]" + PREFIX + cap + "[/INST]"
    n = len(TOK.encode(prompt, add_special_tokens=False).ids) + len(TOK.encode(svg + "</s>", add_special_tokens=False).ids)
    return dict(id=item["id"], description=cap, svg=svg, tokens=n, colors=ncol, paths=svg.count("<path"))

def nonblank(row):
    import cairosvg
    from PIL import Image, ImageChops
    try:
        png = cairosvg.svg2png(bytestring=row["svg"].encode(), output_width=200, output_height=200)
        img = Image.open(io.BytesIO(png)).convert("RGBA"); white = Image.new("RGBA", img.size, "white")
        vis = Image.alpha_composite(white, img).convert("RGB")
        return bool(ImageChops.difference(vis, white.convert("RGB")).getbbox())
    except Exception:
        return False

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--shards", default="/dev/shm/work/shards/*.parquet")
    p.add_argument("--tokenizer", default="/dev/shm/atelier-merged-0625/tokenizer.json")
    p.add_argument("--cache", default="/dev/shm/work/candidates.jsonl")
    p.add_argument("--select", action="store_true")
    p.add_argument("--max-tokens", type=int, default=1600)
    p.add_argument("--min-colors", type=int, default=3)
    p.add_argument("--train-size", type=int, default=12000)
    p.add_argument("--out", default="/dev/shm/work/data-short")
    a = p.parse_args()
    if not a.select:
        import pyarrow.parquet as pq
        rows = []
        for f in sorted(glob.glob(a.shards)):
            rows += pq.read_table(f, columns=["id", "description", "svg"]).to_pylist()
        with Pool(48, initializer=init, initargs=(a.tokenizer,)) as pool:
            out = [r for r in pool.imap(work, rows, chunksize=64) if r]
        with open(a.cache, "w") as s:
            for r in out: s.write(json.dumps(r, ensure_ascii=False) + "\n")
        print("rows", len(rows), "clean", len(out))
        for lim in (1000, 1200, 1600, 2000, 3000):
            for mc in (1, 2, 3, 4):
                print(f"tokens<={lim} colors>={mc}: {sum(r['tokens'] <= lim and r['colors'] >= mc for r in out)}")
        return
    held = set()
    for f in ("/workspace/atelier/data/eval.jsonl", "/workspace/atelier/data/valid.jsonl"):
        for l in open(f): held.add(json.loads(l)["id"])
    cands = [json.loads(l) for l in open(a.cache)]
    cands = [r for r in cands if r["tokens"] <= a.max_tokens and r["colors"] >= a.min_colors and r["id"] not in held]
    random.Random(42).shuffle(cands)
    seen, uniq = set(), []
    for r in cands:
        h = hashlib.sha256(r["svg"].encode()).digest()
        if h not in seen: seen.add(h); uniq.append(r)
    uniq = uniq[: a.train_size + 70]
    with Pool(48) as pool:
        ok = pool.map(nonblank, uniq, chunksize=32)
    rows = [r for r, k in zip(uniq, ok) if k]
    import os; os.makedirs(a.out, exist_ok=True)
    for name, part in [("eval_short", rows[:20]), ("valid", rows[20:70]), ("train", rows[70:])]:
        with open(f"{a.out}/{name}.jsonl", "w") as s:
            for r in part: s.write(json.dumps(dict(id=r["id"], description=r["description"], svg=r["svg"], tokens=r["tokens"]), ensure_ascii=False) + "\n")
        print(name, len(part), "tokens", sum(r["tokens"] for r in part), "mean", round(sum(r["tokens"] for r in part) / max(1, len(part))))
    print("candidates", len(cands), "unique", len(uniq), "nonblank", len(rows))

if __name__ == "__main__":
    main()
