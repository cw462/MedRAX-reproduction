import json, re
from collections import Counter
D = r"H:/RAG_KB/qwen8_m5"
rows=[]
for ds in ["slake","vqarad","chexbench"]:
    for line in open(f"{D}/flash_m5_{ds}.jsonl", encoding="utf-8"):
        r=json.loads(line); r["dataset"]=ds; rows.append(r)
def opts_of(r):
    o=r.get("options")
    if isinstance(o,str):
        try:o=json.loads(o)
        except:o={}
    return o or {}
LAT={"right","left","bilateral","both","upper","lower","mid","apex","base","lateral","medial","basal","hilar","peripheral","central","anterior","posterior","superior","inferior"}
SEVW={"mild","severe","moderate","small","large","minimal","marked","slight"}
FINE=r"(pneumothorax|pleural|lymphadenopath|hilar|free air|mass|nodule|catheter|fracture|contour|border|outline|narrowing|obscured|apex|fossa|calcif|thickening|opacity|infiltrat|consolidat|atelecta|hernia|granuloma|cyst|lesion|device|tube|wire|clip|stent)"
def cls(r):
    o=opts_of(r); vals=[str(v).lower() for v in o.values()]
    if o and len(vals)>=2:
        toks=[set(re.findall(r"[a-z]+", v)) for v in vals]
        diff=set()
        for i in range(len(toks)):
            for j in range(i+1,len(toks)): diff |= (toks[i]-toks[j])|(toks[j]-toks[i])
        # remove common filler
        diff -= {"the","a","of","in","with","and"}
        if diff and diff <= LAT: return "localization (left/right/site)"
        if diff and diff <= SEVW: return "severity (mild/severe)"
        if set(vals) <= {"yes","no"}: return "presence (yes/no)"
        return "finding identification"
    if str(r["reference"]).strip().lower() in ("yes","no"):
        s=r["question"].lower()
        if re.search(FINE,s): return "fine-detail presence"
        return "global presence"
    return "open/short"
wrong=[r for r in rows if not r["correct"]]
c=Counter(cls(r) for r in wrong)
print("Qwen3.6-Flash M5（8工具）848 题，错 190，分类：")
for k,v in c.most_common(): print(f"  {k:28s} {v:4d}  {100*v/len(wrong):5.1f}%")
print("\n各数据集:")
for ds in ["slake","vqarad","chexbench"]:
    sub=[r for r in rows if r["dataset"]==ds]; w=sum(1 for r in sub if not r["correct"])
    ok=len(sub)-w
    cc=Counter(cls(r) for r in sub if not r["correct"])
    print(f"  {ds:10s} {ok}/{len(sub)} = {100*ok/len(sub):5.2f}%  错 {w}  {dict(cc)}")
