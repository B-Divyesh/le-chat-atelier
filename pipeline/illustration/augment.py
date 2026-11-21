"""Rewrite ~45% of captions to short natural prompts (subject phrase only) so the model learns short user prompts."""
import json, random, re, sys
src, dst = sys.argv[1], sys.argv[2]
rng = random.Random(3)
LEAD = re.compile(r"^(the image (features|shows|depicts|displays|contains|consists of|presents)|this (image|illustration|icon) (features|shows|depicts))\s+", re.I)
CUT = re.compile(r"\s(with|featuring|against|set against|on a|in a|that|which|where|consisting|containing|depicted|displayed|positioned|placed|surrounded|arranged)\b|[,.;:(]", re.I)
NOCOMMA = re.compile(r"\s(with|featuring|against|set against|on a|in a|that|which|where|consisting|containing|depicted|displayed|positioned|placed|surrounded|arranged)\b|[.;:(]", re.I)
def short(desc):
    s = LEAD.sub("", desc.strip())
    m = CUT.search(s, 6)
    t = (s[:m.start()] if m else s).strip().rstrip(".")
    if len(t.split()) < 3:
        m = NOCOMMA.search(s, 6)
        t = (s[:m.start()] if m else s).strip().rstrip(".,")
    s = t
    if len(s.split()) < 2: return None
    return s[0].upper() + s[1:]
n = k = 0
with open(dst, "w") as out:
    for line in open(src):
        row = json.loads(line); n += 1
        if rng.random() < 0.45:
            s = short(row["description"])
            if s: row["description"] = s; k += 1
        out.write(json.dumps(row, ensure_ascii=False) + "\n")
print("rows", n, "shortened", k)
