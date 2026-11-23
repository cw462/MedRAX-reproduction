import json, re
from collections import defaultdict
d = json.load(open("rag_eval/res_chexbench_sp_full.json", encoding="utf-8"))
qm = {r["question_id"]: r for r in json.load(open("rag_eval/data/questions_848.json", encoding="utf-8"))}
rows = []
for x in d:
    if not isinstance(x.get("base"), dict) or x["base"].get("correct") is None: continue
    q = qm.get(x["qid"], {})
    opts = q.get("options") or {}
    vals = {k.lower(): str(v).lower() for k, v in opts.items()}
    if set(vals.values()) != {"yes", "no"}: continue
    ref = str(q.get("reference", "")).strip().lower()
    gold = vals.get(ref, "")
    rows.append({"gold": gold, "base": x["base"]["correct"], "rag": (x.get("rag") or {}).get("correct")})
pos = [r for r in rows if r["gold"] == "yes"]; neg = [r for r in rows if r["gold"] == "no"]
acc = lambda xs,k: 100*sum(1 for x in xs if x[k])/max(1,len(xs))
print(f"CheXBench yes/no n={len(rows)}  (gold yes={len(pos)}, no={len(neg)})")
print(f"  gold=yes: base {acc(pos,'base'):.1f}%  rag {acc(pos,'rag'):.1f}%")
print(f"  gold=no : base {acc(neg,'base'):.1f}%  rag {acc(neg,'rag'):.1f}%")
