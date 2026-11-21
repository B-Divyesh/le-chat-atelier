"""Prepare a reproducible, captioned OmniSVG pilot from local Parquet shards."""
import argparse
import hashlib
import io
import json
import random
import re
from collections import Counter
from pathlib import Path
from xml.etree import ElementTree as ET

import cairosvg
import pyarrow.parquet as pq
from PIL import Image, ImageChops
from tokenizers import Tokenizer

SYSTEM = "Draw the requested illustration. Return only a complete SVG on a 200 by 200 viewBox."
PREFIX = "Generate an SVG illustration: "
NS = "{http://www.w3.org/2000/svg}"
NUM = re.compile(r"[-+]?(?:\d+\.\d*|\.\d+|\d+)(?:[eE][-+]?\d+)?")
PATH_ATTR = {"d", "fill", "fill-opacity", "fill-rule", "stroke", "stroke-width",
             "stroke-opacity", "stroke-linecap", "stroke-linejoin", "opacity", "filling"}
ET.register_namespace("", NS[1:-1])


def rounded(m, decimals=1):
    value = round(float(m.group()), decimals)
    return str(int(value)) if value.is_integer() else str(value)


def clean(source, decimals=1):
    root = ET.fromstring(source)
    if root.tag != NS + "svg" or root.attrib.keys() - {"viewBox", "height", "width"}:
        return None
    if list(map(float, root.attrib["viewBox"].split())) != [0, 0, 200, 200]:
        return None
    root.attrib.clear()
    root.set("viewBox", "0 0 200 200")
    colors = set()
    for path in root:
        if path.tag != NS + "path" or len(path) or path.attrib.keys() - PATH_ATTR:
            return None
        if any("url" in v.lower() for v in path.attrib.values()):
            return None
        colors.add(path.get("fill", "black").lower())
        path.attrib.pop("filling", None)
        if path.get("fill-opacity") in {"1", "1.0"}:
            del path.attrib["fill-opacity"]
        # Keep explicit separators between numbers when rounding. Some SVG path
        # encodings omit separators before a minus sign; the dataset uses spaces.
        d = path.attrib["d"]
        if re.search(r"[\d.][-+.]\d", re.sub(r"\d+\.\d+", "1", d)):
            return None
        path.set("d", NUM.sub(lambda m: rounded(m, decimals), d))
    if len(colors) < 2:
        return None
    return ET.tostring(root, encoding="unicode", short_empty_elements=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("shards", nargs="+")
    parser.add_argument("--tokenizer", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--train-size", type=int, default=5000)
    parser.add_argument("--decimals", type=int, default=1, help="Decimal places kept in path data (0 = integers)")
    parser.add_argument("--max-tokens", type=int, default=8192, help="Drop examples longer than this (prompt + SVG)")
    args = parser.parse_args()
    tok = Tokenizer.from_file(args.tokenizer)
    candidates = []
    for shard in args.shards:
        candidates.extend(pq.read_table(shard, columns=["id", "description", "svg"]).to_pylist())
    random.Random(42).shuffle(candidates)
    counts = Counter()
    seen = set()
    rows = []
    for item in candidates:
        counts["examined"] += 1
        caption = item["description"].strip()
        if not caption:
            continue
        try:
            svg = clean(item["svg"], args.decimals)
            if not svg:
                continue
            digest = hashlib.sha256(svg.encode()).digest()
            if digest in seen:
                continue
            # Explicit system instruction matches this model's text-only template.
            prompt = "<s>[SYSTEM_PROMPT]" + SYSTEM + "[/SYSTEM_PROMPT][INST]" + PREFIX + caption + "[/INST]"
            n = len(tok.encode(prompt + svg + "</s>", add_special_tokens=False).ids)
            if n > args.max_tokens:
                continue
            png = cairosvg.svg2png(bytestring=svg.encode(), output_width=200, output_height=200)
            image = Image.open(io.BytesIO(png)).convert("RGBA")
            white = Image.new("RGBA", image.size, "white")
            visible = Image.alpha_composite(white, image).convert("RGB")
            if not ImageChops.difference(visible, white.convert("RGB")).getbbox():
                continue
        except (ValueError, KeyError, ET.ParseError):
            counts["malformed"] += 1
            continue
        seen.add(digest)
        rows.append(dict(id=item["id"], description=caption, svg=svg, tokens=n))
        if len(rows) >= args.train_size + 70:
            break
    args.output.mkdir(exist_ok=True, parents=True)
    for name, part in [("eval", rows[:20]), ("valid", rows[20:70]), ("train", rows[70:])]:
        if not part:
            raise RuntimeError(f"No {name} examples")
        with (args.output / (name + ".jsonl")).open("w") as stream:
            for item in part:
                print(json.dumps(item, ensure_ascii=False), file=stream)
        print(name, len(part), sum(row["tokens"] for row in part), "tokens", flush=True)
    print(dict(counts), flush=True)


if __name__ == "__main__":
    main()
