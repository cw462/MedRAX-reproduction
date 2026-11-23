import csv, json, re
from collections import Counter
CSV = r"C:/Users/cheng/r55_requested_8tools_20261121/publication_bundle/reports/r55_8tools_20261121/per_question.csv"
rows = [r for r in csv.DictReader(open(CSV, encoding="utf-8-sig")) if r["model"] == "Qwen3.6-Flash"]
LAT = {"right","left","bilateral","both","upper","lower","mid","apex","base","lateral","medial","basal","hilar","peripheral","central","anterior","posterior","superior","inferior"}
def kind(r):
    try: opts = json.loads(r["options_json"]) if r["options_json"] else {}
    except Exception: opts = {}
    vals = [str(v).lower() for v in opts.values()]
    if opts and set(vals) <= {"yes","no"}: return "presence"
    if opts:
        toks=[set(v.split()) for v in vals]; diff=set()
        for i in range(len(toks)):
            for j in range(i+1,len(toks)): diff |= (toks[i]-toks[j])|(toks[j]-toks[i])
        return "localization" if diff and diff <= LAT else "choice"
    return "presence" if str(r["reference_answer"]).strip().lower() in ("yes","no") else "open"
wrong=[r for r in rows if r["correct"]=="0"]
sev = [r for r in wrong if kind(r)=="choice" and re.search(r"\b(mild|severe|moderate|small|large|minimal|marked)\b", r["options_json"], re.I)]
print("choice 失败:", sum(1 for r in wrong if kind(r)=="choice"), " 其中严重度分级(mild/severe...):", len(sev))
c=Counter()
for r in sev:
    m=re.findall(r'"(mild|severe|moderate|small|large|minimal|marked)', r["options_json"], re.I)
    c[tuple(sorted(set(x.lower() for x in m)))]+=1
print("  ", dict(c.most_common(5)))
print()
# localization: how many had grounding vs roi
loc=[r for r in wrong if kind(r)=="localization"]
def tools(r):
    try: return json.loads(r["observed_tools_json"] or "[]")
    except Exception: return []
g=sum(1 for r in loc if "xray_phrase_grounding" in tools(r))
roi=sum(1 for r in loc if "roi_crop" in tools(r))
print(f"localization 失败 {len(loc)}: 用了 grounding {g} ({100*g/len(loc):.0f}%), 用了 roi_crop {roi} ({100*roi/len(loc):.0f}%)")
print()
# per-dataset failure counts
for ds in ["SLAKE","VQA-RAD","CheXBench"]:
    sub=[r for r in rows if r["dataset"]==ds]
    w=[r for r in sub if r["correct"]=="0"]
    print(f"{ds}: {len(w)}/{len(sub)} 错 ({100*len(w)/len(sub):.1f}%)")
