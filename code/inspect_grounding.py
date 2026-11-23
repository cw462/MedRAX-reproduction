import json, re
D = r"H:/RAG_KB/qwen8_m5"
rows = [json.loads(l) for l in open(f"{D}/flash_m5_chexbench.jsonl", encoding="utf-8")]
def opts_of(r):
    o = r.get("options")
    if isinstance(o, str):
        try: o = json.loads(o)
        except Exception: o = {}
    return o or {}
LAT = {"left","right"}
def is_lat(r):
    o = opts_of(r); vals = [str(v).lower() for v in o.values()]
    if len(vals) < 2: return False
    toks = [set(re.findall(r"[a-z]+", v)) for v in vals]
    diff = set()
    for i in range(len(toks)):
        for j in range(i+1, len(toks)):
            diff |= (toks[i]-toks[j]) | (toks[j]-toks[i])
    return bool(diff) and diff <= LAT
cands = [r for r in rows if is_lat(r) and not r["correct"]]
print("wrong laterality questions:", len(cands))
show = 0
for r in cands:
    obs = r.get("tool_observations") or []
    texts = json.dumps(obs, ensure_ascii=False)
    if "xray_phrase_grounding" not in texts: continue
    print("="*70)
    print("Q:", r["question"][:70], "| opts:", opts_of(r), "| ref:", r["reference"], "| ans:", str(r.get("answer"))[:30])
    for o in obs:
        if isinstance(o, dict) and o.get("tool") == "xray_phrase_grounding":
            print("  grounding obs:", json.dumps(o.get("observation"), ensure_ascii=False)[:600])
    show += 1
    if show >= 3: break
if show == 0:
    print("no grounding obs found in wrong laterality cases; sample obs keys:")
    for r in cands[:2]:
        print(json.dumps(r.get("tool_observations"), ensure_ascii=False)[:500])
