"""Pick the best CLIP-scored candidate per prompt; write train/valid in the training format."""
import json, random, re, statistics as st, sys
from tokenizers import Tokenizer
SCORED, OUT, MIN_CLIP, MAX_TOK = sys.argv[1], sys.argv[2], float(sys.argv[3]), int(sys.argv[4])
SYSTEM = "Draw the requested illustration. Return only a complete SVG on a 200 by 200 viewBox."
PREFIX = "Generate an SVG illustration: "
tok = Tokenizer.from_file("/dev/shm/atelier-merged-0625/tokenizer.json")
TEXTY = re.compile(r"label|text|word|letter|sign|logo|'|\"|written|says", re.I)
rows = [json.loads(l) for l in open(SCORED)]
groups = {}
for r in rows: groups.setdefault(r["i"], []).append(r)
complete = {i: g for i, g in groups.items() if len(g) == 4}
keep, k0, best = [], [], []
for i, g in sorted(complete.items()):
    v = [r for r in g if r.get("clip") is not None and r["svg_tokens"] <= MAX_TOK and ("<text" not in r["svg"] or TEXTY.search(r["prompt"]))]
    z = [r for r in g if r["k"] == 0 and r.get("clip") is not None]
    if z: k0.append(z[0]["clip"])
    if not v: continue
    b = max(v, key=lambda r: r["clip"]); best.append(b["clip"])
    if b["clip"] >= MIN_CLIP: keep.append(b)
random.Random(5).shuffle(keep)
valid, train = keep[:60], keep[60:]
import os; os.makedirs(OUT, exist_ok=True)
for name, part in [("valid", valid), ("train", train)]:
    with open(f"{OUT}/{name}.jsonl", "w") as f:
        for r in part:
            prompt = "<s>[SYSTEM_PROMPT]" + SYSTEM + "[/SYSTEM_PROMPT][INST]" + PREFIX + r["prompt"] + "[/INST]"
            n = len(tok.encode(prompt, add_special_tokens=False).ids) + r["svg_tokens"]
            f.write(json.dumps(dict(id=f"d{r['i']}", description=r["prompt"], svg=r["svg"], tokens=n, clip=r["clip"]), ensure_ascii=False) + "\n")
print(json.dumps(dict(complete_prompts=len(complete), single_sample_clip=round(st.mean(k0), 2), best_of_4_clip=round(st.mean(best), 2),
                      kept=len(keep), train=len(train), valid=len(valid), train_tokens=sum(r["svg_tokens"] for r in train),
                      mean_svg_tokens=round(st.mean(r["svg_tokens"] for r in keep)), mean_kept_clip=round(st.mean(r["clip"] for r in keep), 2))))
