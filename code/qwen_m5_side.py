import json, re
from collections import Counter
D = r"H:/RAG_KB/qwen8_m5"
rows=[json.loads(l) for l in open(f"{D}/flash_m5_chexbench.jsonl", encoding="utf-8")]
def opts_of(r):
    o=r.get("options")
    if isinstance(o,str):
        try:o=json.loads(o)
        except:o={}
    return o or {}
LAT={"right","left","bilateral","both","upper","lower","mid","apex","base","lateral","medial","basal","hilar","peripheral","central","anterior","posterior","superior","inferior"}
def is_loc(r):
    o=opts_of(r); vals=[str(v).lower() for v in o.values()]
    if not o or set(vals)<={"yes","no"}: return False
    toks=[set(v.split()) for v in vals]; diff=set()
    for i in range(len(toks)):
        for j in range(i+1,len(toks)): diff|=(toks[i]-toks[j])|(toks[j]-toks[i])
    return bool(diff) and diff<=LAT
def side(txt):
    t=str(txt).lower()
    if "left" in t: return "L"
    if "right" in t: return "R"
    return "?"
loc=[r for r in rows if is_loc(r)]
# gold side
def gold_side(r):
    o=opts_of(r); ref=str(r["reference"]).strip().upper()
    return side(o.get(ref, o.get(ref.lower(), "")))
def pred_side(r):
    o=opts_of(r)
    ch=str(r.get("choice") or "").strip().upper()[:1]
    if ch in o: return side(o[ch])
    return side(r.get("answer",""))
gs=[gold_side(r) for r in loc]; ps=[pred_side(r) for r in loc]
print("gold side:", Counter(gs))
print("pred side:", Counter(ps))
pair=Counter((g,p) for g,p in zip(gs,ps))
print("confusion:", dict(pair))
for s in ["L","R"]:
    sub=[(g,p) for g,p in zip(gs,ps) if g==s]
    acc=sum(1 for g,p in sub if g==p)/len(sub)
    print(f"  gold={s}: n={len(sub)} acc={100*acc:.1f}%")
