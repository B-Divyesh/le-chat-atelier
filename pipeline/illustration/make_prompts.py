import json, random, re
import pyarrow.parquet as pq
rng = random.Random(11)
E2E = {"a red apple with a green leaf", "a cute orange cat sitting", "a rocket ship flying to the moon", "a cup of hot coffee",
       "a small house with a tree next to it", "a smiling yellow sun", "a blue bicycle", "a pizza slice with pepperoni"}
def ok(p):
    w = p.split(); return 2 <= len(w) <= 12 and p.lower() not in E2E and not re.search(r"[<>{}\[\]]|http|svg", p, re.I)
vin = list({r["description"].strip() for r in pq.read_table("/dev/shm/work/vinoku/train-0.parquet", columns=["description"]).to_pylist()})
vin = [p for p in vin if ok(p)]; rng.shuffle(vin)
mm = [json.loads(l)["description"] for l in open("/dev/shm/work/data-short2/train.jsonl")]
mm = list({p for p in mm if ok(p) and len(p.split()) <= 8}); rng.shuffle(mm)
prompts = vin[:2400] + mm[:600]; rng.shuffle(prompts)
with open("/dev/shm/work/distill_prompts.jsonl", "w") as f:
    for p in prompts: f.write(json.dumps({"prompt": p}) + "\n")
print("vinoku", len(vin), "mmsvg-short", len(mm), "-> prompts", len(prompts)); print(prompts[:12])
