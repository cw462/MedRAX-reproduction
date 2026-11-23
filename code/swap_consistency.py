import json
a = {r["qid"]: r for r in json.load(open("rag_eval/paired_crop_judged.json", encoding="utf-8")) if r["ok"] is not None}
b = {r["qid"]: r for r in json.load(open("rag_eval/paired_crop_judged_swap.json", encoding="utf-8")) if r["ok"] is not None}
both = [q for q in a if q in b]
agree = sum(1 for q in both if a[q]["pred"] == b[q]["pred"])
print(f"配对 {len(both)} 题，两次一致 {agree} ({100*agree/len(both):.1f}%)")
consistent = [q for q in both if a[q]["pred"] == b[q]["pred"]]
if consistent:
    ok = sum(1 for q in consistent if a[q]["ok"])
    print(f"一致题准确率: {ok}/{len(consistent)} = {100*ok/len(consistent):.1f}%")
amb = [q for q in both if a[q]["pred"] != b[q]["pred"]]
print(f"不一致（弃权）{len(amb)} 题")
