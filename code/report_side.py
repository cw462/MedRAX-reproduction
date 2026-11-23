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
    out = []
    for o in (r.get("tool_observations") or []):
        s = json.dumps(o, ensure_ascii=False)
        if "maira2_grounded_report" in s:
            try:
                obs = o.get("observation") or {}
                if isinstance(obs, str): obs = json.loads(obs)
                rep = obs.get("report") or ""
                if rep: out.append(rep)
                for f in obs.get("findings") or []:
                    if isinstance(f, dict) and f.get("finding"): out.append(str(f["finding"]))
            except Exception:
                pass
    return " ".join(out).lower()

def side_of_option(txt):
    t = str(txt).lower()
    return "left" if "left" in t else ("right" if "right" in t else None)

# key nouns per question
def key_terms(txt):
    stop = {"left","right","the","a","of","in","with","and","larg","small","mild","severe","base","lobe","upper","lower"}
    return [w for w in re.findall(r"[a-z]{4,}", str(txt).lower()) if w not in stop]

stats = {"n":0,"hit":0,"abstain":0,"wrong":0}
examples=[]
for r in rows:
    if not is_lat(r): continue
    rep = report_text(r)
    if not rep: stats["abstain"] += 1; continue
    o = opts_of(r)
    ref = str(r["reference"]).strip().lower()
    gold_side = side_of_option(o.get(ref) or o.get(ref.upper()) or "")
    if gold_side is None: continue
    # which option's key terms appear in report, and with which side
    votes = {"left":0, "right":0}
    for k,v in o.items():
        vs = side_of_option(v)
        terms = key_terms(v)
        if not vs or not terms: continue
        for term in terms:
            for m in re.finditer(term, rep):
                window = rep[max(0,m.start()-60):m.start()+60]
                if vs in window: votes[vs] += 1
    stats["n"] += 1
    if votes["left"] == votes["right"]:
        stats["abstain"] += 1; continue
    pred = "left" if votes["left"] > votes["right"] else "right"
    if pred == gold_side: stats["hit"] += 1
    else:
        stats["wrong"] += 1
        if len(examples) < 6: examples.append((r["question"][:50], o, ref, pred, rep[:200]))
print(stats)
tot = stats["hit"] + stats["wrong"]
if tot: print(f"非弃权题的准确率: {stats['hit']}/{tot} = {100*stats['hit']/tot:.1f}%")
for e in examples: print(e[0], e[1], "ref", e[2], "pred", e[3])
