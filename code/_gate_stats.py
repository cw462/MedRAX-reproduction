import json, re
ranking = json.load(open("rag_eval/rank_bm25_dedup_full.json", encoding="utf-8"))
rows = json.load(open("rag_eval/data/questions_848.json", encoding="utf-8"))
qm = {r["question_id"]: r for r in rows}
STOP = set("""a an the of in on at to for with and or is are was were be been being this that these those
what which who whom how why when where does do did can could should would may might will patient patients
image images picture show shows seen evidence present observed any there normal abnormal chest x-ray""".split())
def gate(docs, q):
    toks = {w for w in re.findall(r"[a-z]{3,}", q.lower()) if w not in STOP}
    return [d for d in docs if any(t in d["title"].lower() for t in toks)][:3]
yn = [r for r in rows if r["dataset"]=="chexbench" and r.get("options") and set(str(v).lower() for v in r["options"].values()) <= {"yes","no"}]
empty = 0; kept = 0
for r in yn:
    q = r["question"] + " " + " ".join(str(v) for v in r["options"].values())
    docs = ranking.get(r["question_id"], [])
    g = gate(docs, q)
    if g: kept += 1
    else: empty += 1
print(f"CheXBench yes/no n={len(yn)}: gate 保留证据 {kept}, 全部过滤 {empty} ({100*empty/len(yn):.1f}%)")
# 看几个被过滤的问题
cnt=0
for r in yn:
    q = r["question"] + " " + " ".join(str(v) for v in r["options"].values())
    g = gate(ranking.get(r["question_id"], []), q)
    if not g and cnt<5:
        print("  FILTERED:", r["question"][:70], "| top1 title:", (ranking.get(r["question_id"]) or [{}])[0].get("title","")[:60])
        cnt+=1
