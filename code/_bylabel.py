import json, re
from collections import defaultdict
d = json.load(open("rag_eval/res_vqarad_wiki.json", encoding="utf-8"))
qmap = {r["question_id"]: r for r in json.load(open("rag_eval/data/questions_848.json", encoding="utf-8"))}
FIND = [("apical pneumothorax","pneumothorax"),("pleural line/visceral pleura","visceral pleura"),
        ("hilar lymphadenopathy","lymphadenopath"),("free air","free air"),("mass","mass"),
        ("nodule","nodule"),("cardiomegaly/size","cardiomegal|heart.{0,20}(size|large)|enlarg"),
        ("consolidation/opacity","consolidat|opacit|infiltrat"),("fracture","fracture"),
        ("catheter/device","catheter|tube|pacemaker"),("rib count","rib"),("aortic","aort")]
rows=[]
for x in d:
    if "base" not in x or x["base"].get("correct") is None: continue
    q=qmap.get(x["qid"],{}).get("question","").lower()
    lab=next((n for n,p in FIND if re.search(p,q)), "other")
    rows.append((lab, x["base"]["correct"]))
by=defaultdict(lambda:[0,0])
for l,c in rows: by[l][0]+=1; by[l][1]+= 1 if c else 0
print("VQA-RAD 纯视觉基线：按所见征象")
for l,v in sorted(by.items(), key=lambda kv:-(kv[1][0]-kv[1][1])):
    print(f"  {l:28s} n={v[0]:3d}  acc={100*v[1]/v[0]:5.1f}%  错={v[0]-v[1]}")
