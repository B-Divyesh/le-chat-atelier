"""Compare served checkpoints on the fixed holdout and save renders and raw outputs."""
import argparse
import io
import json
import re
import textwrap
import time
from pathlib import Path
from urllib.request import Request, urlopen
from xml.etree import ElementTree as ET

import cairosvg
from PIL import Image, ImageChops, ImageDraw


def render(svg):
    root = ET.fromstring(svg)
    if root.tag != "{http://www.w3.org/2000/svg}svg":
        raise ValueError("Expected an SVG root")
    for element in root.iter():
        if element.tag.split("}")[-1] in {"image", "script", "foreignObject", "style", "use"}:
            raise ValueError("External or active content")
        for attr, value in element.attrib.items():
            if attr.endswith("href") or re.search(r"url\(\s*[^#]", value, re.I):
                raise ValueError("External reference")
    data = cairosvg.svg2png(bytestring=svg.encode(), output_width=200, output_height=200)
    white = Image.new("RGB", (200, 200), "white")
    image = white.copy()
    rgba = Image.open(io.BytesIO(data)).convert("RGBA")
    image.paste(rgba, mask=rgba.getchannel("A"))
    if not ImageChops.difference(white, image).getbbox():
        raise ValueError("Blank SVG")
    return image


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--prompts", type=Path, required=True)
    p.add_argument("--model", required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--endpoint", default="http://127.0.0.1:8090/generate")
    p.add_argument("--limit", default=20, type=int)
    p.add_argument("--temperature", type=float, help="fast_server only; 0 = greedy like demo.py")
    args = p.parse_args()
    if args.model == "latest":
        p.error("Choose a numbered checkpoint so every prompt uses the same adapter")
    with args.prompts.open(encoding="utf-8") as stream:
        rows = [json.loads(line) for line in stream][:args.limit]
    args.out.mkdir(exist_ok=True, parents=True)
    sheet = Image.new("RGB", (800, 265*((len(rows)+3)//4)), "white")
    draw = ImageDraw.Draw(sheet)
    for i, row in enumerate(rows):
        name = f"{i:02d}"
        # repair=False keeps raw model output so the closure metric stays honest on fast_server.
        body = dict(prompt=row["description"], model=args.model, repair=False)
        if args.temperature is not None:
            body["temperature"] = args.temperature
        request = Request(args.endpoint, data=json.dumps(body).encode(),
                          headers={"Content-Type": "application/json"})
        result = {"id": row["id"], "description": row["description"], "model": args.model}
        pieces = []
        start = time.monotonic()
        with urlopen(request, timeout=600) as stream:
            for line in stream:
                obj = json.loads(line)
                if "error" in obj:
                    raise RuntimeError(obj["error"])
                if "text" in obj:
                    pieces.append(obj["text"])
                    if "first_path_s" not in result and re.search(r"<path\b[^>]*>", "".join(pieces)):
                        result["first_path_s"] = round(time.monotonic() - start, 2)
                if obj.get("done"):
                    result.update(tokens=obj["tokens"], seconds=obj["seconds"])
        raw = "".join(pieces)
        (args.out / (name + ".txt")).write_text(raw)
        match = re.search(r"<svg\b.*?</svg>", raw, re.S)
        result.update(closed="</svg>" in raw, valid=False)
        x, y = (i%4)*200, (i//4)*265
        if match:
            try:
                image = render(match.group())
                result["valid"] = True
                image.save(args.out / (name + ".png"))
                sheet.paste(image, (x, y))
            except (ValueError, ET.ParseError, OSError) as e:
                result["render_error"] = str(e)
        if not result["valid"]:
            draw.text((x+10, y+85), "Incomplete or invalid SVG", fill="black")
        label = "\n".join(textwrap.wrap(row["description"], 31)[:4])
        draw.multiline_text((x+3, y+200), label, fill="black")
        (args.out / (name + ".json")).write_text(json.dumps(result, indent=2))
        sheet.save(args.out / "contact-sheet.png")
        print(json.dumps(result), flush=True)


if __name__ == "__main__":
    main()
