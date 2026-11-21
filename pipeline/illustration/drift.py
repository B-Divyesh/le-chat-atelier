import re, sys
from pathlib import Path
from tokenizers import Tokenizer
tok = Tokenizer.from_file("/dev/shm/atelier-merged-0625/tokenizer.json")
for f in sorted(Path(sys.argv[1]).glob("*.svg.txt")):
    t = f.read_text(); first = None
    for m in re.finditer(r'd="([^"]*)', t):
        bad = next((n for n in re.finditer(r"-?\d+(?:\.\d+)?", m.group(1)) if abs(float(n.group())) > 260), None)
        if bad: first = len(tok.encode(t[:m.start(1) + bad.start()]).ids); break
    print(f.name[:2], "first out-of-canvas coordinate at token", first, "of", len(tok.encode(t).ids))
