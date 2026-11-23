import json
d = json.load(open("rag_eval/res_vqarad_wiki.json", encoding="utf-8"))
qmap = {r["question_id"]: r for r in json.load(open("rag_eval/data/questions_848.json", encoding="utf-8"))}
rows = []
for x in d:
    if "base" not in x or x["base"].get("correct") is None: continue
    q = qmap.get(x["qid"], {})
    ref = str(q.get("reference", "")).strip().lower()
    ans = (x["base"]["raw"] or "").strip().lower()
    pred = "yes" if "yes" in ans.split()[:2] or ans.startswith("yes") else ("no" if "no" in ans.split()[:2] or ans.startswith("no") else "other")
    rows.append((x["qid"], q.get("question", ""), ref, pred, x["base"]["correct"]))
fp = [r for r in rows if r[2] == "no" and r[3] == "yes"]
fn = [r for r in rows if r[2] == "yes" and r[3] == "no"]
print("VQA-RAD yes/no: n=%d  false-positive(说yes但答案no)=%d  false-negative(说no但答案yes)=%d" % (len(rows), len(fp), len(fn)))
print("\n-- 漏诊(false negative) --")
for r in fn[:12]: print("  ", r[0], "|", r[1][:80])
print("\n-- 误报(false positive) --")
for r in fp[:12]: print("  ", r[0], "|", r[1][:80])
print("\n-- other 类问题样本 --")
import re
for r in rows:
    if not re.search(r"(enlarg|effusion|consolidat|pneumothor|nodule|mass|catheter|fracture|lymph|opacit)", r[1].lower()):
        print("  ", r[0], "|", r[1][:80], "| ref:", r[2], "| pred:", r[3])
