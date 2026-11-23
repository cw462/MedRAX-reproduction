import json, re
D = r"H:/RAG_KB/qwen8_m5"
rows = [json.loads(l) for l in open(f"{D}/flash_m5_chexbench.jsonl", encoding="utf-8")]
LAT = {"left","right"}
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
wrong=[r for r in rows if is_lat(r) and not r["correct"]]
# look at raw observations for the 2 tools
for r in wrong[:4]:
    print("="*70)
    print("Q:", r["question"][:60], "| opts:", opts_of(r), "| ref:", r["reference"])
    for o in (r.get("tool_observations") or []):
        s = json.dumps(o, ensure_ascii=False)
        if "maira2_grounded_report" in s or "report" in s.lower():
            print("  REPORT-ish:", s[:900])
