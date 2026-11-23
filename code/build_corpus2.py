#!/usr/bin/env python3
"""Build the full retrieval corpus: StatPearls (NCBI) + MedRAG textbooks."""
import glob, json, os, sys
sys.path.insert(0, "rag_eval")
import build_corpus as bc

OUT = "H:/RAG_KB/corpus_full.jsonl"
n_tb = n_sp = 0
with open(OUT, "w", encoding="utf-8") as w:
    for p in sorted(glob.glob("H:/RAG_KB/textbooks/*.jsonl")):
        book = os.path.basename(p)[:-6]
        with open(p, encoding="utf-8") as f:
            for line in f:
                if not line.strip(): continue
                d = json.loads(line)
                w.write(json.dumps({"id": f"tb:{book}:{d.get('id')}", "source": "Textbooks",
                                    "title": d.get("title", ""), "contents": d.get("contents") or d.get("content", "")},
                                   ensure_ascii=False) + "\n")
                n_tb += 1
    print("textbooks", n_tb, flush=True)
    files = glob.glob("H:/RAG_KB/sp_full/**/*.nxml", recursive=True)
    print("statpearls files", len(files), flush=True)
    for i, p in enumerate(files):
        for d in bc.extract_nxml(p):
            w.write(json.dumps({"id": f"sp:{d['id']}", "source": "StatPearls",
                                "title": d.get("title", ""), "contents": d["contents"]}, ensure_ascii=False) + "\n")
            n_sp += 1
        if i % 1000 == 0: print("sp", i, n_sp, flush=True)
print("DONE", n_tb, n_sp, flush=True)
