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
loc=[r for r in rows if is_loc(r)]
print("loc n:", len(loc))
print("refs:", Counter(str(r["reference"]).strip().upper() for r in loc))
print("preds:", Counter(str(r.get("choice") or "?").strip().upper()[:1] for r in loc))
print("correct:", sum(1 for r in loc if r["correct"]))
# accuracy when ref=A vs ref=B
for k in ["A","B"]:
    sub=[r for r in loc if str(r["reference"]).strip().upper()==k]
    print(f"  ref={k}: n={len(sub)} acc={100*sum(1 for r in sub if r['correct'])/len(sub):.1f}%")
# 左右选项与患者侧
def side(opts, key):
    v=str(opts.get(key,"")).lower()
    if "left" in v: return "L"
    if "right" in v: return "R"
    return "?"
print("\n样例（选项顺序 vs 答案）:")
for r in loc[:6]:
    o=opts_of(r)
    print("  ", {k:side(o,k) for k in o}, "| ref:", str(r["reference"]).upper(), "| pred:", str(r.get("choice")).upper()[:1], "| correct:", r["correct"])
