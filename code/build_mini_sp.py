import glob, json, sys
sys.path.insert(0, "rag_eval")
import build_corpus as bc

files = glob.glob("H:/RAG_KB/sp_try/**/*.nxml", recursive=True)
print("nxml files:", len(files), flush=True)
out = "H:/RAG_KB/corpus_sp_mini.jsonl"
n = 0
with open(out, "w", encoding="utf-8") as w:
    for p in files:
        for d in bc.extract_nxml(p):
            w.write(json.dumps({"id": "sp:" + d["id"], "source": "StatPearls",
                                "title": d.get("title", ""), "contents": d["contents"]}, ensure_ascii=False) + "\n")
            n += 1
print("snippets:", n, "->", out)
