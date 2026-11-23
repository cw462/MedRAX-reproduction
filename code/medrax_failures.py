import csv, json, re, sys
from collections import Counter, defaultdict

CSV = r"C:/Users/cheng/r55_requested_8tools_20261121/publication_bundle/reports/r55_8tools_20261121/per_question.csv"
rows = list(csv.DictReader(open(CSV, encoding="utf-8-sig")))
print("total rows:", len(rows), "| models:", Counter(r["model"] for r in rows))

LAT = {"right","left","bilateral","both","upper","lower","mid","apex","base","lateral","medial","basal","hilar","peripheral","central","anterior","posterior","superior","inferior"}
MEAS = r"(ratio|half the|wider than|>12|12 ribs|size limit|less than|inspirator|tilting|plane|\bAP\b|\bPA\b|modality|pregnan|diameter|shift|deviation|adequat|rotation|penetration|number of)"
FINE = r"(pneumothorax|pleural|lymphadenopath|hilar|free air|mass|nodule|catheter|fracture|contour|border|outline|narrowing|obscured|apex|fossa|calcif|thickening|opacity|infiltrate|consolidat|atelecta|hernia|granuloma|cyst|lesion|device|tube|wire|clip|stent)"

def classify(q, opts_json, ref):
    try: opts = json.loads(opts_json) if opts_json else {}
    except Exception: opts = {}
    vals = [str(v).lower() for v in opts.values()]
    if opts and set(vals) <= {"yes","no"}:
        t = "presence"
    elif opts:
        toks = [set(v.split()) for v in vals]
        diff = set()
        for i in range(len(toks)):
            for j in range(i+1,len(toks)):
                diff |= (toks[i]-toks[j]) | (toks[j]-toks[i])
        t = "localization" if diff and diff <= LAT else "finding-choice"
    else:
        t = "presence" if str(ref).strip().lower() in ("yes","no") else "open"
    s = q.lower()
    if re.search(MEAS, s): need = "measurement → segmentation"
    elif t == "localization": need = "localization → detection/grounding"
    elif re.search(FINE, s): need = "fine-detail → detection/ROI"
    else: need = "knowledge/reasoning"
    return t, need

for model in ["Qwen3.6-Flash", "Qwen3.7-Plus"]:
    sub = [r for r in rows if r["model"] == model]
    print("\n" + "="*70)
    print(model, "rows", len(sub), "methods", Counter(r["method"] for r in sub))
    wrong = [r for r in sub if r["correct"] == "0"]
    print("wrong:", len(wrong), "/", len(sub))
    by = Counter()
    for r in wrong:
        t, need = classify(r["question"], r["options_json"], r["reference_answer"])
        by[need] += 1
    for k, v in by.most_common():
        print(f"   {k:36s} {v:4d}  ({100*v/len(wrong):.1f}%)")
    # per method accuracy
    acc = defaultdict(lambda: [0,0])
    for r in sub:
        acc[(r["method"], r["dataset"])][0] += 1
        acc[(r["method"], r["dataset"])][1] += 1 if r["correct"] == "1" else 0
    for (m, d), v in sorted(acc.items()):
        print(f"   {m:10s} {d:10s} {v[1]}/{v[0]} = {100*v[1]/v[0]:.1f}%")
