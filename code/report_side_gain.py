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
def report_text(r):
    out=[]
    for o in (r.get("tool_observations") or []):
        s=json.dumps(o,ensure_ascii=False)
        if "maira2_grounded_report" in s:
            try:
                obs=o.get("observation") or {}
                if isinstance(obs,str): obs=json.loads(obs)
                if obs.get("report"): out.append(obs["report"])
                for f in obs.get("findings") or []:
                    if isinstance(f,dict) and f.get("finding"): out.append(str(f["finding"]))
            except Exception: pass
    return " ".join(out).lower()
def side_of(txt):
    t=str(txt).lower()
    return "left" if "left" in t else ("right" if "right" in t else None)
def key_terms(txt):
    stop={"left","right","the","a","of","in","with","and","larg","small","mild","severe","base","lobe","upper","lower"}
    return [w for w in re.findall(r"[a-z]{4,}",str(txt).lower()) if w not in stop]

fixed=broke=same=abstain=0
fire=0
for r in rows:
    if not is_lat(r): continue
    rep=report_text(r); o=opts_of(r); ref=str(r["reference"]).strip().lower()
    gold_side=side_of(o.get(ref) or o.get(ref.upper()) or "")
    if gold_side is None: continue
    votes={"left":0,"right":0}
    for k,v in o.items():
        vs=side_of(v); terms=key_terms(v)
        if not vs or not terms: continue
        for term in terms:
            for m in re.finditer(term,rep):
                win=rep[max(0,m.start()-60):m.start()+60]
                if vs in win: votes[vs]+=1
    pred = None if votes["left"]==votes["right"] else ("left" if votes["left"]>votes["right"] else "right")
    if pred is None:
        abstain+=1; continue
    fire+=1
    model_correct = bool(r["correct"])
    rule_correct = (pred==gold_side)
    if rule_correct and not model_correct: fixed+=1
    elif (not rule_correct) and model_correct: broke+=1
    else: same+=1
print(f"规则触发 {fire} 次 | 弃权 {abstain}")
print(f"改对 {fixed} | 改错 {broke} | 不变 {same}")
print(f"净变化: {fixed-broke:+d} 题")
