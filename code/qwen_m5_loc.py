import json, re
from collections import Counter
D = r"H:/RAG_KB/qwen8_m5"
rows=[]
for ds in ["chexbench"]:
    for line in open(f"{D}/flash_m5_{ds}.jsonl", encoding="utf-8"):
        r=json.loads(line); r["dataset"]=ds; rows.append(r)
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
print("CheXBench 定位题:", len(loc), " 正确:", sum(1 for r in loc if r["correct"]))
wrong=[r for r in loc if not r["correct"]]
print("定位题错误:", len(wrong))
# 选项顺序与答案偏置
cnt=Counter()
for r in wrong:
    o=opts_of(r); ref=str(r["reference"]).strip().upper()
    ans=str(r.get("choice") or r.get("answer") or "")[:30]
    cnt[(ref, ans[:1].upper())]+=1
print("错误题的 (正确选项, 模型选项):", dict(cnt.most_common(6)))
# 看 grounding 调用是否返回了框
g_used=sum(1 for r in wrong if any(isinstance(t,dict) and t.get("tool")=="xray_phrase_grounding" for t in (r.get("tool_observations") or [])))
print("错误题中用了 grounding 的:", g_used)
print("\n样例:")
for r in wrong[:6]:
    o=opts_of(r)
    print("  Q:", r["question"][:60])
    print("     opts:", o, "| ref:", r["reference"], "| ans:", str(r.get("answer"))[:40], "| choice:", r.get("choice"))
