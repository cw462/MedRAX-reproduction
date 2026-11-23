import json, re
from collections import Counter
d = json.load(open("rag_eval/lat_experiment.json", encoding="utf-8"))
def letter(p):
    m = re.search(r"\b([a-d])\b", p or "")
    return m.group(1) if m else "?"
print("n =", len(d))
print("full  predictions:", Counter(letter(x["full"]) for x in d))
print("crop  predictions:", Counter(letter(x["crop"]) for x in d))
print("refs             :", Counter(str(x["ref"]).strip().lower() for x in d))
# where options map to left/right
def side(opts, L):
    v = str(opts.get(L, "")).lower()
    if "left" in v: return "left"
    if "right" in v: return "right"
    return "?"
print("\n样例（选项与预测）:")
for x in d[:10]:
    print("  opts:", x["opts"], "| ref:", x["ref"], "| full:", (x["full"] or "")[:25], "| crop:", (x["crop"] or "")[:25])
