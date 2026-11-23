import json, re
meas = json.load(open("rag_eval/gradcam_measure.json", encoding="utf-8"))
tasks = {t["qid"]: t for t in json.load(open("rag_eval/measure_tasks.json", encoding="utf-8"))}
def sev(txt):
    t=str(txt).lower()
    if re.search(r"\b(severe|large|marked)\b", t): return 1
    if re.search(r"\b(mild|small|minimal|moderate)\b", t): return 0
    return None
rows=[]
for qid,m in meas.items():
    t=tasks.get(qid); mm=m.get("measure")
    if not t or not mm: continue
    o=t["options"]; ref=t["reference"]
    g=sev(o.get(ref) or o.get(ref.upper()) or "")
    if g is None: continue
    rows.append({"qid":qid,"region":t["region"],"label":m.get("label"),"g":g,
                 "area":mm["area_ratio"],"w":mm["bbox_w_ratio"],"h":mm["bbox_h_ratio"],"cx":mm["centroid_x"]})
print("evaluable:", len(rows))
def auc(pairs):
    pos=[x for x,g in pairs if g==1]; neg=[x for x,g in pairs if g==0]
    if not pos or not neg: return None
    w=sum(1 for a in pos for b in neg if a>b)+0.5*sum(1 for a in pos for b in neg if a==b)
    return w/(len(pos)*len(neg))
for metric in ["area","w","h"]:
    a=auc([(r[metric],r["g"]) for r in rows])
    print(f"metric {metric:5s} AUC={a:.3f}" if a else f"metric {metric} insufficient")
for reg in ["heart","both_lungs","spine"]:
    sub=[r for r in rows if r["region"]==reg]
    a=auc([(r["area"],r["g"]) for r in sub])
    print(f"  {reg:12s} n={len(sub):2d} AUC(area)={a:.3f}" if a else f"  {reg} insufficient")
