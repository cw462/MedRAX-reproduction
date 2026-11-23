#!/usr/bin/env python3
"""Build a compact 'diagnostic criteria' knowledge base from the Wikipedia corpus."""
import json, re
from collections import defaultdict
SRC = "H:/RAG_KB/corpus_wiki.jsonl"
DST = "H:/RAG_KB/corpus_wiki_crit.jsonl"
CRIT = re.compile(r"(radiograph|x-?ray|\bct\b|computed tomograph|\bmri\b|magnetic resonance|ultrasound|"
                  r"diagnos|criteria|ratio|sign\b|findings|appear|imaging|opacity|shadow)", re.I)
STRONG = re.compile(r"(radiograph|x-?ray|\bct\b|\bmri\b|ultrasound|imaging|appearance|findings|ratio)", re.I)
by = defaultdict(list)
with open(SRC, encoding="utf-8") as f:
    for line in f:
        d = json.loads(line)
        by[d["title"]].append(d)
out = []
for title, paras in by.items():
    scored = []
    for p in paras:
        t = p["contents"]
        if not CRIT.search(t): continue
        s = 2 * bool(STRONG.search(t)) + bool(re.search(r"diagnos|criteria|ratio", t, re.I))
        scored.append((s, len(t), p))
    scored.sort(key=lambda x: (-x[0], -x[1]))
    for s, l, p in scored[:3]:
        out.append(p)
with open(DST, "w", encoding="utf-8") as w:
    for p in out:
        w.write(json.dumps(p, ensure_ascii=False) + "\n")
print("articles", len(by), "criteria snippets", len(out), "->", DST)
