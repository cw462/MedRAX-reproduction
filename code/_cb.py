import json, re
from collections import Counter
rows = json.load(open("rag_eval/data/questions_848.json", encoding="utf-8"))
cb = [r for r in rows if r["dataset"] == "chexbench"]
yn = sum(1 for r in cb if set(v.lower() for v in (r.get("options") or {}).values()) == {"yes","no"})
lat = sum(1 for r in cb if re.search(r"(right|left|bilateral|upper|lower)", " ".join((r.get("options") or {}).values()), re.I))
print("CheXBench 618:", "yes/no 二选一 =", yn, "| 选项含左右/部位 =", lat, "| 其他 =", len(cb)-yn-lat)
print("样例:")
for r in cb[:3]:
    print("  ", r["question"][:60], r.get("options"))
