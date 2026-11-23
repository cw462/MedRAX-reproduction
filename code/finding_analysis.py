#!/usr/bin/env python3
"""Per-finding + answer-bias analysis for all three benchmarks (yes/no subset)."""
import json, re, sys
from collections import defaultdict

FIND = [("pneumothorax/air leak", r"pneumothorax|pneumomediastinum|free air|subcutaneous"),
        ("effusion", r"effusion"),
        ("consolidation/opacity", r"consolidat|opacit|infiltrat"),
        ("atelectasis", r"atelecta|collapse"),
        ("cardiomegaly/size", r"cardiomegal|enlarg|heart.{0,20}(size|large)|silhouette"),
        ("nodule/mass", r"nodule|mass|lesion"),
        ("lymphadenopathy/hilar", r"lymphadenopath|hilar|hilum"),
        ("catheter/tube/device", r"catheter|tube|pacemaker|stent|hardware|clip|wire|prosthe"),
        ("fracture/bone", r"fracture|rib|clavicle|vertebra|scolio|kypho|osteo"),
        ("edema/congestion", r"edema|congest"),
        ("normal/abnormal overall", r"\bnormal\b|abnormal|anything wrong|disease"),
        ("anatomy/organ presence", r"\b(heart|lung|liver|kidney|spleen|bladder|bowel|stomach|trachea|"
                                   r"mediastinum|diaphragm|spine|ribs|neck|abdomen|chest)\b")]

def label(q):
    s = q.lower()
    for n, p in FIND:
        if re.search(p, s): return n
    return "other"

def load(path):
    d = json.load(open(path, encoding="utf-8"))
    qm = {r["question_id"]: r for r in json.load(open("rag_eval/data/questions_848.json", encoding="utf-8"))}
    out = []
    for x in d:
        if not isinstance(x.get("base"), dict) or x["base"].get("correct") is None: continue
        q = qm.get(x["qid"], {})
        out.append({"q": q.get("question",""), "opts": q.get("options") or {},
                    "ref": str(q.get("reference","")).strip().lower(),
                    "base_raw": (x["base"].get("raw") or "").lower(),
                    "rag_raw": ((x.get("rag") or {}).get("raw") or "").lower(),
                    "base": x["base"]["correct"], "rag": (x.get("rag") or {}).get("correct")})
    return out

def show(name, path):
    rows = load(path)
    pres = [r for r in rows if (not r["opts"] and r["ref"] in ("yes","no")) or
            (r["opts"] and set(v.lower() for v in r["opts"].values()) == {"yes","no"})]
    print("="*72); print(f"{name}  yes/no 题 n={len(pres)}")
    pos = [r for r in pres if r["ref"] == "yes"]; neg = [r for r in pres if r["ref"] == "no"]
    acc = lambda xs, k: 100*sum(1 for x in xs if x[k])/max(1,len(xs))
    print(f"  参考答案 yes 的题: n={len(pos):3d}  base {acc(pos,'base'):5.1f}%  rag {acc(pos,'rag'):5.1f}%")
    print(f"  参考答案 no  的题: n={len(neg):3d}  base {acc(neg,'base'):5.1f}%  rag {acc(neg,'rag'):5.1f}%")
    by = defaultdict(lambda: [0,0,0,0])
    for r in pres:
        l = label(r["q"]); by[l][0]+=1; by[l][1]+= 1 if r["base"] else 0
        if r["rag"] is not None: by[l][2]+=1; by[l][3]+= 1 if r["rag"] else 0
    print(f"  {'finding':28s} {'n':>4s} {'base':>8s} {'rag':>8s}")
    for l,v in sorted(by.items(), key=lambda kv:-(kv[1][0]-kv[1][1])):
        print(f"  {l:28s} {v[0]:4d} {100*v[1]/v[0]:7.1f}% {100*v[3]/max(1,v[2]):7.1f}%")

if __name__ == "__main__":
    show("SLAKE", "rag_eval/res_slake_sp_full.json")
    show("VQA-RAD", "rag_eval/res_vqarad_sp_full.json")
    show("CheXBench", "rag_eval/res_chexbench_sp_full.json")
