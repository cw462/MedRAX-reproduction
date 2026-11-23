import json
res = json.load(open("rag_eval/paired_crop_judged.json", encoding="utf-8"))
M5 = {}
for line in open("H:/RAG_KB/qwen8_m5/flash_m5_chexbench.jsonl", encoding="utf-8"):
    r = json.loads(line); M5[r["question_id"]] = r
valid = [r for r in res if r["ok"] is not None]
ok = sum(1 for r in valid if r["ok"])
m5ok = sum(1 for r in valid if M5.get(r["qid"], {}).get("correct"))
print(f"paired-crop: {ok}/{len(valid)} = {100*ok/len(valid):.1f}%")
print(f"M5 baseline（同 {len(valid)} 题）: {m5ok}/{len(valid)} = {100*m5ok/len(valid):.1f}%")
from collections import Counter
print("裁判选择分布:", Counter(r["pick"] for r in valid))
print("改对/改错:", sum(1 for r in valid if r["ok"] and not M5.get(r['qid'],{}).get('correct')),
      "/", sum(1 for r in valid if not r["ok"] and M5.get(r['qid'],{}).get('correct')))
