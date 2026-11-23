import json
rows = [json.loads(l) for l in open("H:/RAG_KB/corpus_wiki.jsonl", encoding="utf-8")]
for title in ["Cardiomegaly", "Pleural effusion", "Pneumothorax"]:
    print("=" * 10, title)
    for r in rows:
        if r["title"] == title:
            print("  -", r["contents"][:220].replace("\n", " "))
