"""Evaluate a llama-server endpoint on the fixed eval prompts; save SVG, PNG, JSON and a contact sheet."""
import argparse, io, json, re, textwrap, time, urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import cairosvg
from PIL import Image, ImageChops, ImageDraw

SYSTEM = "Draw the requested illustration. Return only a complete SVG on a 200 by 200 viewBox."
PREFIX = "Generate an SVG illustration: "

def render(svg):
    data = cairosvg.svg2png(bytestring=svg.encode(), output_width=200, output_height=200)
    white = Image.new("RGB", (200, 200), "white"); img = white.copy()
    rgba = Image.open(io.BytesIO(data)).convert("RGBA"); img.paste(rgba, mask=rgba.getchannel("A"))
    if not ImageChops.difference(white, img).getbbox():
        raise ValueError("blank")
    return img

def run(args, i, row):
    prompt = f"[SYSTEM_PROMPT]{SYSTEM}[/SYSTEM_PROMPT][INST]{PREFIX}{row['description']}[/INST]"
    body = dict(prompt=prompt, n_predict=args.max_tokens, temperature=args.temperature, top_p=0.95,
                stop=["</svg>"], cache_prompt=False, seed=1000 + i)
    t = time.time()
    r = json.load(urllib.request.urlopen(urllib.request.Request(args.endpoint, json.dumps(body).encode(),
                  {"Content-Type": "application/json"}), timeout=900))
    text = r["content"] + ("</svg>" if r.get("stopping_word") == "</svg>" else "")
    res = dict(i=i, description=row["description"], tokens=r.get("tokens_predicted"), seconds=round(time.time() - t, 2),
               tok_s=round(r.get("timings", {}).get("predicted_per_second", 0), 1), closed=text.rstrip().endswith("</svg>"),
               chars=len(text), paths=text.count("<path"), valid=False)
    (args.out / f"{i:02d}.svg.txt").write_text(text)
    m = re.search(r"<svg\b.*?</svg>", text, re.S)
    img = None
    if m:
        try:
            img = render(m.group()); res["valid"] = True; img.save(args.out / f"{i:02d}.png")
        except Exception as e:
            res["error"] = str(e)[:120]
    return res, img

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--prompts", default="/workspace/atelier/data/eval.jsonl")
    p.add_argument("--endpoint", default="http://127.0.0.1:8091/completion")
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--max-tokens", type=int, default=8192)
    p.add_argument("--temperature", type=float, default=0.7)
    p.add_argument("--workers", type=int, default=2)
    p.add_argument("--limit", type=int, default=20)
    a = p.parse_args(); a.out.mkdir(parents=True, exist_ok=True)
    rows = [json.loads(l) for l in open(a.prompts)][:a.limit]
    with ThreadPoolExecutor(a.workers) as ex:
        results = list(ex.map(lambda x: run(a, *x), enumerate(rows)))
    sheet = Image.new("RGB", (1000, 265 * ((len(rows) + 4) // 5)), "white"); d = ImageDraw.Draw(sheet)
    for res, img in results:
        x, y = (res["i"] % 5) * 200, (res["i"] // 5) * 265
        if img: sheet.paste(img, (x, y))
        else: d.text((x + 10, y + 90), "INVALID / UNCLOSED", fill="red")
        d.multiline_text((x + 3, y + 202), "\n".join(textwrap.wrap(f"{res['i']:02d} {res['tokens']}t {res['seconds']}s | " + res["description"], 33)[:4]), fill="black")
    sheet.save(a.out / "contact-sheet.png")
    rs = [r for r, _ in results]
    summary = dict(n=len(rs), valid=sum(r["valid"] for r in rs), closed=sum(r["closed"] for r in rs),
                   mean_tokens=round(sum(r["tokens"] for r in rs) / len(rs)), max_tokens=max(r["tokens"] for r in rs),
                   mean_seconds=round(sum(r["seconds"] for r in rs) / len(rs), 1), mean_tok_s=round(sum(r["tok_s"] for r in rs) / len(rs), 1))
    (a.out / "results.json").write_text(json.dumps(dict(summary=summary, rows=rs), indent=1))
    print(json.dumps(summary)); [print(json.dumps(r)) for r in rs]

if __name__ == "__main__":
    main()
