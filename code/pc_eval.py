import json
pc = json.load(open("rag_eval/paired_crop.json", encoding="utf-8"))
tasks = {t["qid"]: t for t in json.load(open("rag_eval/lat_tasks.json", encoding="utf-8"))}
M5 = {}
for line in open("H:/RAG_KB/qwen8_m5/flash_m5_chexbench.jsonl", encoding="utf-8"):
    r = json.loads(line); M5[r["question_id"]] = r
ok = n = 0
m5ok = 0
rows = []
for qid, v in pc.items():
    t = tasks.get(qid)
    if not t or not v.get("pred_key"): continue
    opts = t["options"]
    gold_key = None
    for k, val in opts.items():
        if t["gold_side"] in str(val).lower(): gold_key = k
    if gold_key is None: continue
    n += 1
    hit = (v["pred_key"] == gold_key)
    ok += 1 if hit else 0
    m5ok += 1 if M5.get(qid, {}).get("correct") else 0
    rows.append((qid, hit, M5.get(qid, {}).get("correct")))
print(f"paired-crop: {ok}/{n} = {100*ok/n:.1f}%")
print(f"M5 baseline（同 40 题）: {m5ok}/{n} = {100*m5ok/n:.1f}%")
fix = sum(1 for q,h,m in rows if h and not m)
brk = sum(1 for q,h,m in rows if (not h) and m)
print(f"相对 M5：改对 {fix} / 改错 {brk}")
