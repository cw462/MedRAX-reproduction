import json
meas = json.load(open("rag_eval/measure_all.json", encoding="utf-8"))
tasks = {t["qid"]: t for t in json.load(open("rag_eval/measure_tasks.json", encoding="utf-8"))}
import re
def sev(txt):
    t=str(txt).lower()
    if re.search(r"\b(severe|large|marked)\b", t): return 1
    if re.search(r"\b(mild|small|minimal|moderate)\b", t): return 0
    return None
def auc(pairs):
    pos=[m for m,s in pairs if s==1]; neg=[m for m,s in pairs if s==0]
    if not pos or not neg: return None,0
    w=sum(1 for a in pos for b in neg if a>b)+0.5*sum(1 for a in pos for b in neg if a==b)
    return w/(len(pos)*len(neg)), len(pairs)

# CTR-like: heart width / lung field width
pairs=[]
for qid,m in meas.items():
    t=tasks.get(qid)
    if not t or t["region"]!="heart": continue
    o=t["options"]; ref=t["reference"]
    g=sev(o.get(ref) or o.get(ref.upper()) or "")
    h=m.get("heart") or {}; l=m.get("both_lungs") or {}
    if g is None or not h or not l: continue
    ctr = h["bbox_w_ratio"]/max(1e-6, l["bbox_w_ratio"])
    pairs.append((ctr,g))
a,n = auc(pairs)
print(f"heart: CTR-like ratio, n={n}, AUC={a:.3f}" if a else "no data")
# also area ratio heart/lung
pairs2=[]
for qid,m in meas.items():
    t=tasks.get(qid)
    if not t or t["region"]!="heart": continue
    o=t["options"]; ref=t["reference"]
    g=sev(o.get(ref) or o.get(ref.upper()) or "")
    h=m.get("heart") or {}; l=m.get("both_lungs") or {}
    if g is None or not h or not l: continue
    pairs2.append((h["area_ratio"]/max(1e-6,l["area_ratio"]), g))
a2,n2=auc(pairs2)
print(f"heart: area ratio heart/lung, n={n2}, AUC={a2:.3f}" if a2 else "no data")
