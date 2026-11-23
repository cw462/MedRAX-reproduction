import json
d = json.load(open("rag_eval/res_vqarad_wiki.json", encoding="utf-8"))
broke = [x for x in d if x.get("base") and x.get("rag") and x["base"]["correct"] and not x["rag"]["correct"]]
fixed = [x for x in d if x.get("base") and x.get("rag") and not x["base"]["correct"] and x["rag"]["correct"]]
print("BROKE", len(broke))
for x in broke[:8]:
    print(" -", x["qid"], "| ref:", x["reference"], "| base:", (x["base"]["raw"] or "")[:60].replace("\n"," "), "| rag:", (x["rag"]["raw"] or "")[:60].replace("\n"," "))
print("FIXED", len(fixed))
for x in fixed[:6]:
    print(" -", x["qid"], "| ref:", x["reference"], "| rag:", (x["rag"]["raw"] or "")[:60].replace("\n"," "))
