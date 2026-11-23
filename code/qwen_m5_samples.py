import json, re
D = r"H:/RAG_KB/qwen8_m5"
rows=[]
for ds in ["slake","vqarad","chexbench"]:
    for line in open(f"{D}/flash_m5_{ds}.jsonl", encoding="utf-8"):
        r=json.loads(line); r["dataset"]=ds; rows.append(r)
def opts_of(r):
    o=r.get("options")
    if isinstance(o,str):
        try:o=json.loads(o)
        except:o={}
    return o or {}
SEV = re.compile(r"\b(mild|severe|moderate|small|large|minimal|marked)\b", re.I)
wrong=[r for r in rows if not r["correct"]]
sev=[r for r in wrong if SEV.search(" ".join(str(v) for v in opts_of(r).values()))]
print("=== 严重度分级失败样例 (%d) ===" % len(sev))
for r in sev[:8]:
    print("  ", r["dataset"], "|", opts_of(r), "| ref:", r["reference"], "| ans:", str(r.get("answer"))[:25])
glob=[r for r in wrong if not opts_of(r) and str(r["reference"]).strip().lower() in ("yes","no")]
print("\n=== 整体判定失败样例 (%d) ===" % len(glob))
for r in glob[:8]:
    print("  ", r["dataset"], "|", r["question"][:70], "| ref:", r["reference"], "| ans:", str(r.get("answer"))[:25])
