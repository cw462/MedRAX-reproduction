import csv, json, re
from collections import Counter, defaultdict
CSV = r"C:/Users/cheng/r55_requested_8tools_20261121/publication_bundle/reports/r55_8tools_20261121/per_question.csv"
rows = [r for r in csv.DictReader(open(CSV, encoding="utf-8-sig")) if r["model"] == "Qwen3.6-Flash"]

LAT = {"right","left","bilateral","both","upper","lower","mid","apex","base","lateral","medial","basal","hilar","peripheral","central","anterior","posterior","superior","inferior"}
MEAS = r"(ratio|half the|wider than|>12|12 ribs|size limit|less than|inspirator|tilting|plane|\bAP\b|\bPA\b|modality|pregnan|diameter|shift|deviation|adequat|rotation|penetration|number of)"
FINE = r"(pneumothorax|pleural|lymphadenopath|hilar|free air|mass|nodule|catheter|fracture|contour|border|outline|narrowing|obscured|apex|fossa|calcif|thickening|opacity|infiltrate|consolidat|atelecta|hernia|granuloma|cyst|lesion|device|tube|wire|clip|stent)"

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
    need = ("measurement" if re.search(MEAS,s) else
            "localization" if t=="localization" else
            "fine-detail" if re.search(FINE,s) else "knowledge")
    return need

def tools_of(r):
    try: return [t for t in json.loads(r["observed_tools_json"] or "[]")]
    except Exception: return []

wrong = [r for r in rows if r["correct"]=="0"]
print("Qwen3.6-Flash wrong:", len(wrong))
by = defaultdict(list)
for r in wrong: by[cls(r["question"], r["options_json"], r["reference_answer"])].append(r)
for k, lst in sorted(by.items(), key=lambda kv:-len(kv[1])):
    used = Counter()
    n_tool = 0
    for r in lst:
        ts = tools_of(r)
        if ts: n_tool += 1
        for t in ts: used[t]+=1
    print(f"\n[{k}] n={len(lst)}  用了工具的 {n_tool} ({100*n_tool/len(lst):.0f}%)")
    print("   tools:", dict(used.most_common(6)))
print("\n=== 全部 Qwen3.6 题的工具栏使用率 ===")
allu = Counter()
for r in rows:
    for t in tools_of(r): allu[t]+=1
print(dict(allu.most_common()))
