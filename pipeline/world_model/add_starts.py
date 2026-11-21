"""Append start-only examples (empty SVG -> generated environment) for every genre, then shuffle the training set."""
import json, random, sys
sys.path.insert(0, "/dev/shm/work")
import wm_multi as M
rng = random.Random(123); rows = [json.loads(l) for l in open(sys.argv[1])]
per = int(sys.argv[2])
for g, (new, step, svg, rand, acts) in M.GENRES.items():
    for _ in range(per):
        if g == "survivors":
            lay = rng.choice(M.surv.LAYOUTS + [None])
            rows.append(dict(description=f"{g}: start {lay}\n{M.EMPTY}" if lay else f"{g}: start\n{M.EMPTY}", svg=svg(M.surv.new_env(rng, lay)), genre=g))
        else:
            rows.append(dict(description=f"{g}: start\n{M.EMPTY}", svg=svg(new(rng)), genre=g))
rng.shuffle(rows)
with open(sys.argv[1], "w") as f:
    for r in rows: f.write(json.dumps(r) + "\n")
print("rows", len(rows), "start examples", sum("start" in r["description"].split("\n")[0] for r in rows))
