#!/usr/bin/env python3
"""Build a concept co-occurrence graph over the retrieval corpus (GraphRAG-lite)."""
import json, re, sys
from collections import Counter, defaultdict
sys.path.insert(0, "rag_eval")
from concepts import FINDINGS, ANATOMY

NODES = list(dict.fromkeys([t.lower() for t in FINDINGS + ANATOMY]))
PATTERNS = [(n, re.compile(r"\b" + re.escape(n) + r"\b", re.I)) for n in NODES]

def main(corpus):
    edge = Counter()
    node_df = Counter()
    n = 0
    with open(corpus, encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            text = d["contents"][:1200]
            found = [node for node, pat in PATTERNS if pat.search(text)]
            if not found:
                continue
            n += 1
            for x in found:
                node_df[x] += 1
            for i in range(len(found)):
                for j in range(i + 1, len(found)):
                    a, b = sorted((found[i], found[j]))
                    edge[(a, b)] += 1
    adj = defaultdict(dict)
    for (a, b), c in edge.items():
        if c < 3:
            continue
        adj[a][b] = c
        adj[b][a] = c
    out = {"nodes": dict(node_df), "adj": {k: dict(sorted(v.items(), key=lambda x: -x[1])[:12]) for k, v in adj.items()}}
    dst = corpus.replace(".jsonl", "_graph.json")
    json.dump(out, open(dst, "w", encoding="utf-8"), ensure_ascii=False)
    print("docs with concepts:", n, "nodes:", len(node_df), "edges:", sum(len(v) for v in adj.values()) // 2, "->", dst)
    for k in list(adj)[:5]:
        print(" ", k, "->", list(adj[k])[:5])

if __name__ == "__main__":
    main(sys.argv[1])
