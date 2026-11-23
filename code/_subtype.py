import json, re
from collections import defaultdict
d = json.load(open("rag_eval/res_vqarad_wiki.json", encoding="utf-8"))
qmap = {r["question_id"]: r for r in json.load(open("rag_eval/data/questions_848.json", encoding="utf-8"))}

MEASURE = r"(ratio|half the|wider than|>12|12 ribs|size limit|less than|inspirator|position|tilting|plane|AP image|PA image|modality|pregnan|diameter)"
FINE = r"(pneumothorax|pleural|lymphadenopath|hilar|free air|mass|nodule|catheter|fracture|contour|border|outline|narrowing|obscured|apex|fossa|calcif)"
def subtype(q):
    s = q.lower()
    if re.search(MEASURE, s): return "measurement/projection"
    if re.search(FINE, s): return "fine-detail presence"
    return "global judgement"

rows = []
for x in d:
    if "base" not in x or x["base"].get("correct") is None: continue
    q = qmap.get(x["qid"], {}).get("question", "")
    rows.append((subtype(q), x["base"]["correct"], (x.get("rag") or {}).get("correct")))
by = defaultdict(lambda: [0,0,0,0])
for s,b,r in rows:
    by[s][0]+=1; by[s][1]+= 1 if b else 0
    if r is not None: by[s][2]+=1; by[s][3]+= 1 if r else 0
print("VQA-RAD yes/no 按所需视觉能力分层:")
print(f"{'subtype':24s} {'n':>4s} {'base':>8s} {'rag':>8s}")
for s,v in sorted(by.items(), key=lambda kv:-kv[1][0]):
    print(f"{s:24s} {v[0]:4d} {100*v[1]/v[0]:7.1f}% {100*v[3]/max(1,v[2]):7.1f}%")
