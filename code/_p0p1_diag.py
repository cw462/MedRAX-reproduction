import json, re
from collections import Counter
# P0 diagnostics
d = json.load(open("rag_eval/p0_side_result.json", encoding="utf-8"))
none_b = sum(1 for r in d if r["predB"] is None)
diff = sum(1 for r in d if r["predA"] != r["predB"])
print("P0: n", len(d), "| predB=None(映射失败)", none_b, "| A/B 答案不同", diff)
print("  common 短语样例:", [r.get("common") for r in d[:6]])
# side 准确率（仅 side 类）
lat = [r for r in d if r["kind"]=="side"]
print("  side 类 n:", len(lat), "| A:", sum(1 for r in lat if r["okA"]), "| B:", sum(1 for r in lat if r["okB"]))
for r in lat[:8]:
    print(f"   ref={r['ref']} A={r['predA']} B={r['predB']} | {r['common']} | ansB={r['ansB'][:40]}")
# P1 diagnostics
p = json.load(open("rag_eval/p1_chexbench_yn.json", encoding="utf-8"))
same = sum(1 for x in p if (x.get("base") or {}).get("raw") == (x.get("rag") or {}).get("raw"))
print("\nP1: n", len(p), "| base/rag 答案完全相同:", same)
print("  base acc:", sum(1 for x in p if x["base"].get("correct")), "| rag acc:", sum(1 for x in p if x["rag"].get("correct")))
ex = [x for x in p if (x.get("base") or {}).get("raw") != (x.get("rag") or {}).get("raw")][:5]
for x in ex:
    print("   diff:", x["qid"], "| base:", (x["base"]["raw"] or "")[:40], "| rag:", (x["rag"]["raw"] or "")[:40])
