import json
titles = set()
for line in open("H:/RAG_KB/corpus_sp_mini.jsonl", encoding="utf-8"):
    d = json.loads(line)
    titles.add(d["title"].split(" -- ")[0].strip())
print("articles:", len(titles))
import re
keys = ["Pleural Effusion", "Cardiomegaly", "Atelectasis", "Pneumothorax", "Chest Radiograph", "Chest X-ray",
        "Pulmonary Edema", "Consolidation", "Aortic Aneurysm", "Lymphadenopathy", "Nodule", "Bronchiectasis"]
for k in keys:
    hits = [t for t in titles if k.lower() in t.lower()]
    print(f"{k:20s} {len(hits):3d} {hits[:3]}")
