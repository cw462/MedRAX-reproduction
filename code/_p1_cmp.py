import json
base = {x["qid"]: x for x in json.load(open("rag_eval/p1_chexbench_yn.json", encoding="utf-8"))}
rag  = {x["qid"]: x for x in json.load(open("rag_eval/p1b_chexbench_rag.json", encoding="utf-8"))}
fix = brk = same = 0
for qid, r in rag.items():
    b = base.get(qid, {}).get("base", {})
    if b.get("correct") is None or r.get("rag", {}).get("correct") is None: continue
    if not b["correct"] and r["rag"]["correct"]: fix += 1
    elif b["correct"] and not r["rag"]["correct"]: brk += 1
    if b.get("raw") == r["rag"].get("raw"): same += 1
print(f"P1(new gate): fixed {fix}, broke {brk}, identical answers {same}/{len(rag)}")
print(f"base acc {sum(1 for x in base.values() if x.get('base',{}).get('correct'))}/{len(base)}")
print(f"rag  acc {sum(1 for x in rag.values() if x.get('rag',{}).get('correct'))}/{len(rag)}")
