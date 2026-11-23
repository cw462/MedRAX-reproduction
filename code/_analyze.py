import json
for ds in ["slake", "vqarad"]:
    d = json.load(open(f"rag_eval/res_{ds}_tb.json", encoding="utf-8"))
    base = [x for x in d if x.get("base") and x["base"].get("correct")]
    rag = [x for x in d if x.get("rag") and x["rag"].get("correct")]
    broke = [x for x in d if x.get("base") and x.get("rag") and x["base"]["correct"] and not x["rag"]["correct"]]
    fixed = [x for x in d if x.get("base") and x.get("rag") and not x["base"]["correct"] and x["rag"]["correct"]]
    print(f"== {ds}: base {len(base)}/{len(d)}  rag {len(rag)}/{len(d)}  broke {len(broke)} fixed {len(fixed)}")
    for x in broke[:5]:
        print("  BROKE", x["qid"], "| ref:", x["reference"])
        print("    base:", (x["base"]["raw"] or "")[:100])
        print("    rag :", (x["rag"]["raw"] or "")[:100])
