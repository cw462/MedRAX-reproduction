import json, os, re

D = r"H:/RAG_KB/qwen8_m5"
rows = [json.loads(l) for l in open(f"{D}/flash_m5_chexbench.jsonl", encoding="utf-8")]
inp = {json.loads(l)["question_id"]: json.loads(l) for l in open("rag_eval/data/chexbench_inputs.jsonl", encoding="utf-8")}
SEV = re.compile(r"\b(mild|severe|moderate|small|large|minimal|marked)\b", re.I)
def opts_of(r):
    o = r.get("options")
    if isinstance(o, str):
        try: o = json.loads(o)
        except Exception: o = {}
    return o or {}
def region_of(text):
    t = text.lower()
    if re.search(r"cardiomegal|heart|cardiovascular|cardiac", t): return "heart"
    if re.search(r"spine|vertebra|scolio|kypho|degenerat", t): return "spine"
    return "both_lungs"

tasks = []
for r in rows:
    qid = r["question_id"]
    if qid not in inp: continue
    o = opts_of(r); vals = [str(v) for v in o.values()]
    if len(vals) < 2: continue
    toks = [set(re.findall(r"[a-z]+", v.lower())) for v in vals]
    diff = set()
    for i in range(len(toks)):
        for j in range(i+1, len(toks)):
            diff |= (toks[i]-toks[j]) | (toks[j]-toks[i])
    diff -= {"the","a","of","in","with","and","left","right"}
    if not diff or not (diff <= {"mild","severe","moderate","small","large","minimal","marked"}):
        continue
    tasks.append({"qid": qid, "dataset": "chexbench",
                  "image": "chexbench/" + os.path.basename(inp[qid]["images"][0]),
                  "question": r["question"], "options": o, "reference": str(r["reference"]).strip().lower(),
                  "region": region_of(" ".join(vals)), "severity_diff": sorted(diff)})
print("severity tasks:", len(tasks))
json.dump(tasks, open("rag_eval/measure_tasks.json", "w"), ensure_ascii=False, indent=1)
