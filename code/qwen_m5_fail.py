import json, re
from collections import Counter, defaultdict
D = r"H:/RAG_KB/qwen8_m5"
LAT = {"right","left","bilateral","both","upper","lower","mid","apex","base","lateral","medial","basal","hilar","peripheral","central","anterior","posterior","superior","inferior"}
MEAS = r"(ratio|half the|wider than|>12|12 ribs|size limit|less than|inspirator|tilting|plane|\bAP\b|\bPA\b|modality|pregnan|diameter|shift|deviation|adequat|rotation|penetration|number of)"
FINE = r"(pneumothorax|pleural|lymphadenopath|hilar|free air|mass|nodule|catheter|fracture|contour|border|outline|narrowing|obscured|apex|fossa|calcif|thickening|opacity|infiltrat|consolidat|atelecta|hernia|granuloma|cyst|lesion|device|tube|wire|clip|stent)"

rows=[]
for ds in ["slake","vqarad","chexbench"]:
    for line in open(f"{D}/flash_m5_{ds}.jsonl", encoding="utf-8"):
        r=json.loads(line); r["dataset"]=ds; rows.append(r)
print("total:", len(rows), "correct:", sum(1 for r in rows if r["correct"]))
wrong=[r for r in rows if not r["correct"]]
print("wrong:", len(wrong))

def opts_of(r):
    o=r.get("options")
    if isinstance(o,str):
        try: o=json.loads(o)
        except Exception: o={}
    return o or {}

def cls(r):
    o=opts_of(r); vals=[str(v).lower() for v in o.values()]
    if o and set(vals) <= {"yes","no"}: t="presence"
    elif o:
        toks=[set(v.split()) for v in vals]; diff=set()
        for i in range(len(toks)):
            for j in range(i+1,len(toks)): diff |= (toks[i]-toks[j])|(toks[j]-toks[i])
        t="localization" if diff and diff <= LAT else "finding-choice"
    else:
        t="presence" if str(r["reference"]).strip().lower() in ("yes","no") else "open"
    s=r["question"].lower()
    if re.search(MEAS,s): return "measurement"
    if t=="localization": return "localization"
    if t=="finding-choice":
        vals=" ".join(vals)
        if re.search(r"\b(mild|severe|moderate|small|large|minimal|marked)\b", vals): return "severity grading"
        return "finding-choice"
    if re.search(FINE,s): return "fine-detail"
    if t=="open": return "open/short"
    return "global normal/abnormal"

by=Counter(cls(r) for r in wrong)
print("\n=== 190 条失败的分类 ===")
for k,v in by.most_common(): print(f"  {k:24s} {v:4d}  {100*v/len(wrong):5.1f}%")

print("\n=== 按数据集 ===")
for ds in ["slake","vqarad","chexbench"]:
    sub=[r for r in rows if r["dataset"]==ds]; w=[r for r in sub if not r["correct"]]
    print(f"  {ds:10s} {len(sub)-len(w):3d}/{len(sub):3d} = {100*(len(sub)-len(w))/len(sub):.1f}%  (错 {len(w)})")

print("\n=== 失败题的工具调用 ===")
tc=Counter()
for r in wrong:
    for t in (r.get("tool_observations") or []):
        name = t.get("tool") if isinstance(t,dict) else str(t)
        tc[name]+=1
print("  ", dict(tc.most_common(8)))
print("  平均工具调用:", round(sum(r["tool_calls"] for r in wrong)/len(wrong),2),
      " 对比全部题:", round(sum(r["tool_calls"] for r in rows)/len(rows),2))
