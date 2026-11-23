import csv, json, re
from collections import Counter, defaultdict
CSV = r"C:/Users/cheng/r55_requested_8tools_20261121/publication_bundle/reports/r55_8tools_20261121/per_question.csv"
rows = [r for r in csv.DictReader(open(CSV, encoding="utf-8-sig")) if r["model"] == "Qwen3.6-Flash"]
LAT = {"right","left","bilateral","both","upper","lower","mid","apex","base","lateral","medial","basal","hilar","peripheral","central","anterior","posterior","superior","inferior"}
MEAS = r"(ratio|half the|wider than|>12|12 ribs|size limit|less than|inspirator|tilting|plane|\bAP\b|\bPA\b|modality|pregnan|diameter|shift|deviation|adequat|rotation|penetration|number of)"
FINE = r"(pneumothorax|pleural|lymphadenopath|hilar|free air|mass|nodule|catheter|fracture|contour|border|outline|narrowing|obscured|apex|fossa|calcif|thickening|opacity|infiltrat|consolidat|atelecta|hernia|granuloma|cyst|lesion|device|tube|wire|clip|stent)"
ANAT = r"\b(heart|lung|liver|kidney|spleen|bladder|bowel|stomach|trachea|mediastinum|diaphragm|spine|ribs|neck|abdomen|chest|skeletal|cardiovascular|nervous|endocrine|urinary|reproductive|digestive)\b"

def cls(q, opts_json, ref):
    try: opts = json.loads(opts_json) if opts_json else {}
    except Exception: opts = {}
    vals = [str(v).lower() for v in opts.values()]
    if opts and set(vals) <= {"yes","no"}: t="presence"
    elif opts:
        toks=[set(v.split()) for v in vals]; diff=set()
        for i in range(len(toks)):
            for j in range(i+1,len(toks)): diff |= (toks[i]-toks[j])|(toks[j]-toks[i])
        t = "localization" if diff and diff <= LAT else "finding-choice"
    else: t = "presence" if str(ref).strip().lower() in ("yes","no") else "open"
    s=q.lower()
    if re.search(MEAS,s): return "measurement"
    if t=="localization": return "localization"
    if re.search(FINE,s): return "fine-detail"
    if t=="finding-choice": return "finding-choice"
    if t=="open": return "open/short"
    return "global-normal/abnormal"

wrong=[r for r in rows if r["correct"]=="0"]
c=Counter(cls(r["question"], r["options_json"], r["reference_answer"]) for r in wrong)
print("Qwen3.6-Flash 8工具 失败分解 (n=%d, 3 arms x 848)" % len(wrong))
for k,v in c.most_common():
    print(f"  {k:24s} {v:4d}  {100*v/len(wrong):5.1f}%")
print()
# among finding-choice, sample
fc=[r for r in wrong if cls(r["question"], r["options_json"], r["reference_answer"])=="finding-choice"]
print("finding-choice 失败样例:")
for r in fc[:8]:
    print("  ", r["dataset"], "|", r["question"][:70], "| opts:", r["options_json"][:80], "| pred:", r["model_answer"][:30], "| ref:", r["reference_answer"])
