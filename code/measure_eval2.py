import json
rows = json.load(open("rag_eval/measure_eval.json", encoding="utf-8"))
def auc(sub):
    pos=[r["measure"] for r in sub if r["gold_sev"]==1]; neg=[r["measure"] for r in sub if r["gold_sev"]==0]
    if not pos or not neg: return None
    w=sum(1 for a in pos for b in neg if a>b)+0.5*sum(1 for a in pos for b in neg if a==b)
    return w/(len(pos)*len(neg))
for reg in ["heart","both_lungs","spine"]:
    sub=[r for r in rows if r["region"]==reg]
    a=auc(sub)
    print(f"{reg:12s} n={len(sub):2d} (sev {sum(1 for r in sub if r['gold_sev']==1)}, mild {sum(1 for r in sub if r['gold_sev']==0)})  AUC={a:.3f}" if a else f"{reg} insufficient")
m5 = [r for r in rows if r["m5_correct"] in (True, "True", 1)]
print(f"\nM5 在这 44 题上的正确数: {len(m5)}/{len(rows)} = {100*len(m5)/len(rows):.1f}%")
