"""CLIP-score each valid render against its prompt; add 'clip' to the manifest."""
import json, sys, torch
from PIL import Image
from transformers import CLIPModel, CLIPProcessor
MAN, PNG, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
name = "/dev/shm/work/clip"
model = CLIPModel.from_pretrained(name, dtype=torch.float16).cuda().eval(); proc = CLIPProcessor.from_pretrained(name)
rows = [json.loads(l) for l in open(MAN)]
valid = [r for r in rows if r["valid"]]
prompts = sorted({r["prompt"] for r in valid}); tidx = {p: i for i, p in enumerate(prompts)}
with torch.no_grad():
    te = []
    for s in range(0, len(prompts), 512):
        t = proc(text=[f"an illustration of {p}" for p in prompts[s:s + 512]], return_tensors="pt", padding=True, truncation=True).to("cuda")
        te.append(torch.nn.functional.normalize(model.text_projection(model.text_model(input_ids=t['input_ids'], attention_mask=t['attention_mask']).pooler_output).float(), dim=-1))
    te = torch.cat(te)
    for s in range(0, len(valid), 256):
        chunk = valid[s:s + 256]
        ims = [Image.open(f"{PNG}/{r['i']}_{r['k']}.png").convert("RGB") for r in chunk]
        pv = proc(images=ims, return_tensors="pt")['pixel_values'].to('cuda', torch.float16)
        ie = torch.nn.functional.normalize(model.visual_projection(model.vision_model(pixel_values=pv).pooler_output).float(), dim=-1)
        sims = (ie * te[[tidx[r["prompt"]] for r in chunk]]).sum(-1) * 100
        for r, v in zip(chunk, sims.tolist()): r["clip"] = round(v, 2)
with open(OUT, "w") as f:
    for r in rows: f.write(json.dumps(r, ensure_ascii=False) + "\n")
print("scored", len(valid))
