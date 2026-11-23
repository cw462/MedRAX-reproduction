import csv, json, re
from collections import Counter, defaultdict
CSV = r"C:/Users/cheng/r55_requested_8tools_20261121/publication_bundle/reports/r55_8tools_20261121/per_question.csv"
rows = [r for r in csv.DictReader(open(CSV, encoding="utf-8-sig")) if r["model"] == "Qwen3.6-Flash"]
LAT = {"right","left","bilateral","both","upper","lower","mid","apex","base","lateral","medial","basal","hilar","peripheral","central","anterior","posterior","superior","inferior"}
def tools(r):
    try: return set(json.loads(r["observed_tools_json"] or "[]"))
    except Exception: return set()
def is_loc(r):
    try: opts = json.loads(r["options_json"]) if r["options_json"] else {}
    except Exception: opts = {}
    vals=[str(v).lower() for v in opts.values()]
    if not opts or set(vals) <= {"yes","no"}: return False
    toks=[set(v.split()) for v in vals]; diff=set()
    for i in range(len(toks)):
        for j in range(i+1,len(toks)): diff |= (toks[i]-toks[j])|(toks[j]-toks[i])
    return bool(diff) and diff <= LAT
loc=[r for r in rows if is_loc(r)]
print("localization 题总数:", len(loc))
for grp_name, grp in [
    ("用了 roi_crop", [r for r in loc if "roi_crop" in tools(r)]),
    ("用了 grounding", [r for r in loc if "xray_phrase_grounding" in tools(r)]),
    ("grounding+roi 都用了", [r for r in loc if {"roi_crop","xray_phrase_grounding"} <= tools(r)]),
    ("两个都没用", [r for r in loc if not ({"roi_crop","xray_phrase_grounding"} & tools(r))]),
]:
    if not grp: continue
    c=sum(1 for r in grp if r["correct"]=="1")
    print(f"  {grp_name:22s} n={len(grp):3d}  acc={100*c/len(grp):5.1f}%")
print()
# 同样看 fine-detail
FINE = r"(pneumothorax|pleural|lymphadenopath|hilar|free air|mass|nodule|catheter|fracture|contour|border|outline|narrowing|obscured|apex|fossa|calcif)"
fine=[r for r in rows if re.search(FINE, r["question"], re.I) and not is_loc(r)]
print("fine-detail 题:", len(fine))
for grp_name, grp in [("用了 roi_crop", [r for r in fine if "roi_crop" in tools(r)]),
                      ("没用 roi_crop", [r for r in fine if "roi_crop" not in tools(r)])]:
    if not grp: continue
    c=sum(1 for r in grp if r["correct"]=="1")
    print(f"  {grp_name:22s} n={len(grp):3d}  acc={100*c/len(grp):5.1f}%")
