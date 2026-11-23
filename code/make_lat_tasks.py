import json, os, re

qm = {r["question_id"]: r for r in json.load(open("rag_eval/data/questions_848.json", encoding="utf-8"))}
inp = {json.loads(l)["question_id"]: json.loads(l) for l in open("rag_eval/data/chexbench_inputs.jsonl", encoding="utf-8")}
LAT = {"left", "right"}
LAB = [("cardiomegal", "Cardiomegaly"), ("heart", "Cardiomegaly"), ("atelectas", "Atelectasis"),
       ("effusion", "Effusion"), ("consolidat", "Consolidation"), ("pneumothorax", "Pneumothorax"),
       ("opacit", "Lung Opacity"), ("nodule", "Nodule"), ("mass", "Mass"), ("catheter", "Lung Opacity"),
       ("tube", "Lung Opacity"), ("fracture", "Fracture"), ("edema", "Edema"), ("hernia", "Hernia")]

def label_of(text):
    t = text.lower()
    for k, v in LAB:
        if k in t: return v
    return "Lung Opacity"

tasks = []
for qid, q in qm.items():
    if q["dataset"] != "chexbench" or qid not in inp: continue
    o = q.get("options") or {}
    if len(o) < 2: continue
    vals = [str(v) for v in o.values()]
    toks = [set(re.findall(r"[a-z]+", v.lower())) for v in vals]
    diff = set()
    for i in range(len(toks)):
        for j in range(i + 1, len(toks)):
            diff |= (toks[i] - toks[j]) | (toks[j] - toks[i])
    if not diff or not (diff <= LAT): continue
    ref = str(q["reference"]).strip().lower()
    gold = None
    for k, v in o.items():
        if k.lower() == ref:
            vv = str(v).lower()
            gold = "left" if "left" in vv else ("right" if "right" in vv else None)
    if not gold: continue
    tasks.append({"qid": qid, "image": "chexbench/" + os.path.basename(inp[qid]["images"][0]),
                  "finding": " ".join(sorted((set().union(*toks)) - LAT)), "label": label_of(vals[0]),
                  "gold_side": gold, "options": o})
print("laterality tasks:", len(tasks))
json.dump(tasks, open("rag_eval/lat_tasks.json", "w"), ensure_ascii=False, indent=1)
