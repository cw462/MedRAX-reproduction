#!/usr/bin/env python3
"""Unified question-type analysis v2: all three benchmarks, same taxonomy."""
import json, re, sys
from collections import defaultdict

LAT = {"right","left","bilateral","both","upper","lower","mid","apex","base","lateral","medial",
       "basal","hilar","peripheral","central","anterior","posterior","superior","inferior"}
FINDING_RE = (r"(pneumothorax|effusion|atelectas|consolidat|cardiomegal|nodule|mass|fracture|catheter|"
              r"opacit|infiltrat|edema|lymphadenopath|hernia|calcif|emphysem|fibros|scolio|kypho|"
              r"device|tube|pacemaker|stent|prosthe|free air|pneumoperitone|lesion|abscess|cyst|"
              r"cavity|granuloma|thickening|bronchiecta|hyperinflat|dislocat|osteophy|spondyl|"
              r"transplant|drain|clip|wire|hardware|implant|normal)")
MEASURE_RE = (r"(ratio|half the|wider than|>12|12 ribs|size limit|less than|inspirator|position|"
              r"tilting|plane|AP image|PA image|modality|pregnan|diameter|shift|deviation|"
              r"adequat|rotation|penetration)")
FINE_RE = (r"(pneumothorax|pleural|lymphadenopath|hilar|free air|mass|nodule|catheter|fracture|"
           r"contour|border|outline|narrowing|obscured|apex|fossa|calcif|thickening|opacity|"
           r"infiltrate|consolidat|atelecta|hernia|granuloma|cyst|lesion)")

def norm(t): return re.sub(r"[^a-z0-9 ]", " ", str(t).lower())

def demand(q):
    s = q.lower()
    if re.search(MEASURE_RE, s): return "measurement/projection"
    if re.search(FINE_RE, s): return "fine-detail presence"
    return "global judgement"

def qtype(q, options, ref):
    if options:
        vals = [norm(v) for v in options.values()]
        if set(vals) <= {"yes", "no"}:
            return "presence (yes/no)"
        toks = [set(v.split()) for v in vals]
        diff = set()
        for i in range(len(toks)):
            for j in range(i+1, len(toks)):
                diff |= (toks[i]-toks[j]) | (toks[j]-toks[i])
        if diff and diff <= LAT: return "localization (side/site)"
        if re.search(FINDING_RE, " ".join(vals)): return "finding identification"
        if diff and len(diff) <= 3: return "localization (side/site)"
        return "other MCQ"
    if norm(ref).strip() in ("yes", "no"):
        return "presence (yes/no)"
    return "open/short"

def load(path):
    d = json.load(open(path, encoding="utf-8"))
    qm = {r["question_id"]: r for r in json.load(open("rag_eval/data/questions_848.json", encoding="utf-8"))}
    out = []
    for x in d:
        if not isinstance(x.get("base"), dict) or x["base"].get("correct") is None: continue
        q = qm.get(x["qid"], {})
        out.append({"qid": x["qid"], "q": q.get("question",""), "opts": q.get("options") or {},
                    "ref": str(q.get("reference","")), "base": x["base"]["correct"],
                    "rag": (x.get("rag") or {}).get("correct")})
    return out

def table(rows, key):
    by = defaultdict(lambda: [0,0,0,0])
    for r in rows:
        t = key(r)
        by[t][0] += 1; by[t][1] += 1 if r["base"] else 0
        if r["rag"] is not None:
            by[t][2] += 1; by[t][3] += 1 if r["rag"] else 0
    out = []
    for t,v in sorted(by.items(), key=lambda kv:-kv[1][0]):
        b = 100*v[1]/v[0]; rg = 100*v[3]/max(1,v[2])
        out.append((t, v[0], b, rg, rg-b))
    return out

def show(name, path):
    rows = load(path)
    print("="*74); print(f"{name}   n={len(rows)}")
    print(f"{'type':30s} {'n':>4s} {'base':>8s} {'rag':>8s} {'delta':>7s}")
    for t,n,b,rg,d in table(rows, lambda r: qtype(r["q"], r["opts"], r["ref"])):
        print(f"{t:30s} {n:4d} {b:7.1f}% {rg:7.1f}% {d:+7.1f}")
    pres = [r for r in rows if qtype(r["q"], r["opts"], r["ref"]) == "presence (yes/no)"]
    if pres:
        print(f"-- presence 题按视觉能力细分 ({len(pres)}) --")
        print(f"{'demand':30s} {'n':>4s} {'base':>8s} {'rag':>8s} {'delta':>7s}")
        for t,n,b,rg,d in table(pres, lambda r: demand(r["q"])):
            print(f"{t:30s} {n:4d} {b:7.1f}% {rg:7.1f}% {d:+7.1f}")

if __name__ == "__main__":
    show("SLAKE", "rag_eval/res_slake_sp_full.json")
    show("VQA-RAD", "rag_eval/res_vqarad_sp_full.json")
    show("CheXBench", "rag_eval/res_chexbench_sp_full.json")