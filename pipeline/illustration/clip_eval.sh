#!/usr/bin/env bash
# clip_eval.sh PORT NAME : one sample per held-out prompt -> render -> CLIP -> summary
set -euo pipefail
cd /dev/shm/work; PORT=$1; NAME=$2
/root/renderenv/bin/python gen_base.py heldout_prompts.jsonl ev-$NAME-raw.jsonl 1 $PORT 16 > /dev/null
rm -rf ev-$NAME-png; /root/renderenv/bin/python render_gen.py ev-$NAME-raw.jsonl ev-$NAME-man.jsonl /dev/shm/work/ev-$NAME-png > /dev/null
CUDA_VISIBLE_DEVICES=${CLIPGPU:-1} /venv/main/bin/python clip_score.py ev-$NAME-man.jsonl /dev/shm/work/ev-$NAME-png ev-$NAME-scored.jsonl > /dev/null 2>&1
python3 - "$NAME" <<'PY'
import json, statistics as st, sys
n = sys.argv[1]; rows = [json.loads(l) for l in open(f"ev-{n}-scored.jsonl")]
v = [r for r in rows if r.get("clip") is not None]
raw = {json.loads(l)["i"]: json.loads(l) for l in open(f"ev-{n}-raw.jsonl")}
print(json.dumps(dict(model=n, prompts=len(rows), valid=len(v), mean_clip_valid=round(st.mean(r["clip"] for r in v), 2),
      mean_clip_all=round(sum(r.get("clip") or 0 for r in rows) / len(rows), 2),
      mean_gen_tokens=round(st.mean(r["tokens"] or 0 for r in raw.values())), mean_svg_tokens=round(st.mean(r["svg_tokens"] for r in v)))))
PY
