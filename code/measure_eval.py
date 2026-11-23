import json, re
meas = json.load(open("rag_eval/measure_all.json", encoding="utf-8"))
tasks = {t["qid"]: t for t in json.load(open("rag_eval/measure_tasks.json", encoding="utf-8"))}
M5 = {}
for line in open("H:/RAG_KB/qwen8_m5/flash_m5_chexbench.jsonl", encoding="utf-8"):
    r = json.loads(line); M5[r["question_id"]] = r

def sev_of_opt(txt):
    t = str(txt).lower()
    if re.search(r"\b(severe|large|marked)\b", t): return 1
    if re.search(r"\b(mild|small|minimal|moderate)\b", t): return 0
    return None

rows = []
for qid, m in meas.items():
    t = tasks.get(qid)
    if not t: continue
    region = t["region"]
    mvals = m.get(region) or m.get("both_lungs") or {}
    if not mvals: continue
    ref = t["reference"]
    opts = t["options"]
    gold_opt = opts.get(ref) or opts.get(ref.upper()) or ""
    gold_sev = sev_of_opt(gold_opt)
    if gold_sev is None: continue
    metric = mvals.get("bbox_w_ratio") if region == "heart" else mvals.get("area_ratio")
    rows.append({"qid": qid, "region": region, "gold_sev": gold_sev, "measure": metric,
                 "gold": gold_opt, "m5_correct": M5.get(qid, {}).get("correct")})
print("evaluable:", len(rows), "| severe:", sum(1 for r in rows if r["gold_sev"]==1), "| mild:", sum(1 for r in rows if r["gold_sev"]==0))

# AUC: P(measure(severe) > measure(mild))
pos = [r["measure"] for r in rows if r["gold_sev"] == 1]
neg = [r["measure"] for r in rows if r["gold_sev"] == 0]
if pos and neg:
    wins = sum(1 for a in pos for b in neg if a > b) + 0.5*sum(1 for a in pos for b in neg if a == b)
    auc = wins / (len(pos)*len(neg))
    print(f"AUC(measure -> severe) = {auc:.3f}")
    import statistics
    print(f"median severe {statistics.median(pos):.4f} vs mild {statistics.median(neg):.4f}")
    # accuracy with median split
    thr = (statistics.median(pos) + statistics.median(neg)) / 2
    acc = sum(1 for r in rows if (r["measure"] >= thr) == (r["gold_sev"] == 1)) / len(rows)
    print(f"median-threshold accuracy = {acc*100:.1f}%  (threshold={thr:.4f})")
from collections import Counter
print("by region:", Counter(r["region"] for r in rows))
json.dump(rows, open("rag_eval/measure_eval.json", "w"), ensure_ascii=False, indent=1)
