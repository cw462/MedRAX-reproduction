import json
for ds in ["slake", "vqarad"]:
    d = json.load(open(f"rag_eval/res_{ds}_wiki.json", encoding="utf-8"))
    base = [x for x in d if x.get("base") and x["base"].get("correct") is not None]
    rag = [x for x in d if x.get("rag") and x["rag"].get("correct") is not None]
    b = sum(1 for x in base if x["base"]["correct"]); r = sum(1 for x in rag if x["rag"]["correct"])
    broke = [x for x in d if x.get("base") and x.get("rag") and x["base"]["correct"] and not x["rag"]["correct"]]
    fixed = [x for x in d if x.get("base") and x.get("rag") and not x["base"]["correct"] and x["rag"]["correct"]]
    print(f"{ds}: n={len(d)} base {b}/{len(base)}={100*b/len(base):.2f}%  rag {r}/{len(rag)}={100*r/len(rag):.2f}%  fixed {len(fixed)} broke {len(broke)}")
