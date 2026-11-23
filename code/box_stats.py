import json, re
D = r"H:/RAG_KB/qwen8_m5"
rows = [json.loads(l) for l in open(f"{D}/flash_m5_chexbench.jsonl", encoding="utf-8")]
LAT={"left","right"}
def opts_of(r):
    o=r.get("options")
    if isinstance(o,str):
        try:o=json.loads(o)
        except:o={}
    return o or {}
def is_lat(r):
    o=opts_of(r); vals=[str(v).lower() for v in o.values()]
    if len(vals)<2: return False
    toks=[set(re.findall(r"[a-z]+",v)) for v in vals]; diff=set()
    for i in range(len(toks)):
        for j in range(i+1,len(toks)): diff|=(toks[i]-toks[j])|(toks[j]-toks[i])
    return bool(diff) and diff<=LAT
def count_boxes(r):
    n=0; phrases=[]
    for o in (r.get("tool_observations") or []):
        s=json.dumps(o,ensure_ascii=False)
        if "xray_phrase_grounding" in s:
            try:
                obs=o.get("observation")
                if isinstance(obs,str): obs=json.loads(obs)
                for item in (obs if isinstance(obs,list) else [obs]):
                    for p in (item.get("predictions") or []):
                        if p.get("bounding_boxes"): n+=1; phrases.append(str(p.get("phrase"))[:40])
            except Exception: pass
    return n, phrases
with_grounding=0; multi=0; total=0
for r in rows:
    if not is_lat(r): continue
    total+=1
    n,ph=count_boxes(r)
    if n>0: with_grounding+=1
    if n>=2: multi+=1
print(f"laterality 题 {total} | 调过 grounding 的 {with_grounding} | 拿到 >=2 个框的 {multi}")
print(f"→ 在拿到多框的题里，{100*multi/max(1,with_grounding):.0f}% 是两个选项各给了一个框（强制出框）")
