#!/usr/bin/env python3
"""Retrieval methods over the local corpus."""
import argparse, json, math, os, sys, time, urllib.request
from collections import Counter
sys.path.insert(0, "rag_eval")
import index as bidx
from concepts import find_concepts, _VOCAB

EMB_BASE = "https://dashscope.aliyuncs.com/compatible-mode/v1"
EMB_MODEL = "text-embedding-v4"
GRAPH = {"adj": {}}

def qwen_key():
    return open("medrax_work/.secrets/qwen_api.key").read().strip()

def embed(texts, retries=3):
    body = json.dumps({"model": EMB_MODEL, "input": texts, "dimensions": 1024, "encoding_format": "float"}).encode()
    for attempt in range(retries):
        try:
            req = urllib.request.Request(EMB_BASE + "/embeddings", data=body, method="POST")
            req.add_header("Authorization", "Bearer " + qwen_key())
            req.add_header("Content-Type", "application/json")
            with urllib.request.urlopen(req, timeout=60) as r:
                d = json.loads(r.read())
            return [x["embedding"] for x in d["data"]]
        except Exception:
            if attempt == retries - 1:
                raise
            time.sleep(1.5)

def cos(a, b):
    na = math.sqrt(sum(x * x for x in a)); nb = math.sqrt(sum(x * x for x in b))
    if not na or not nb: return 0.0
    return sum(x * y for x, y in zip(a, b)) / (na * nb)

def dedup(docs):
    seen, out = set(), []
    for d in docs:
        key = d["title"].split(" -- ")[0].strip().lower() if d["source"] == "StatPearls" else d["id"]
        if key in seen: continue
        seen.add(key); out.append(d)
    return out

def rrf(lists, k=60):
    scores, store = {}, {}
    for lst in lists:
        for rank, d in enumerate(lst):
            key = d["id"]
            scores[key] = scores.get(key, 0) + 1.0 / (k + rank + 1)
            store[key] = d
    return [store[i] for i in sorted(scores, key=lambda x: -scores[x])]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--method", required=True,
                    choices=["bm25", "bm25_dedup", "rewrite", "hybrid", "prf", "graph", "concept"])
    ap.add_argument("--rewrites", default="rag_eval/data/queries_848.json")
    ap.add_argument("--graph", default="")
    ap.add_argument("--cand", type=int, default=20)
    ap.add_argument("--k", type=int, default=5)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    idx = bidx.load()
    global GRAPH
    if a.graph and os.path.exists(a.graph):
        GRAPH = json.load(open(a.graph, encoding="utf-8"))
    rows = json.load(open("rag_eval/data/questions_848.json", encoding="utf-8"))
    rewrites = json.load(open(a.rewrites, encoding="utf-8")) if os.path.exists(a.rewrites) else {}
    res = {}
    t0 = time.time()
    for n, r in enumerate(rows, 1):
        qid = r["question_id"]
        q = r["question"] + (" " + " ".join(str(v) for v in r["options"].values()) if r.get("options") else "")
        rw = rewrites.get(qid, {})
        qs = [x for x in (rw.get("queries") or []) if x][:3]
        concept = rw.get("concept") or ""
        if a.method == "bm25":
            docs = bidx.search(idx, q, a.k)
        elif a.method == "bm25_dedup":
            docs = dedup(bidx.search(idx, q, a.cand))[:a.k]
        elif a.method == "prf":
            first = bidx.search(idx, q, 10)
            terms = Counter()
            for d in first:
                for w in bidx.toks(d["title"] + " " + d["contents"][:600]):
                    terms[w] += 1
            expansion = [w for w, _ in terms.most_common(40) if w not in bidx.toks(q)][:8]
            docs = bidx.search(idx, q + " " + " ".join(expansion), a.k)
        elif a.method == "graph":
            hits = find_concepts(q, _VOCAB)
            expand = []
            for term, kind in hits[:3]:
                for nb in list((GRAPH.get("adj", {}).get(term, {}) or {}))[:4]:
                    if len(nb) > 3:
                        expand.append(nb)
            q2 = q + " " + " ".join(dict.fromkeys(expand))
            docs = dedup(bidx.search(idx, q2, a.cand))[:a.k]
        elif a.method == "concept":
            extra = " ".join([concept] + qs[:2])
            docs = bidx.search(idx, q + " " + extra, a.k)
        elif a.method == "rewrite":
            lists = [bidx.search(idx, x, a.cand) for x in qs] or [bidx.search(idx, q, a.cand)]
            docs = dedup(rrf(lists))[:a.k]
        else:
            base_q = " ".join(qs) if qs else q
            cands = dedup(bidx.search(idx, base_q, a.cand))[:a.cand]
            texts = [(c["title"] if c["source"] == "StatPearls" else "") + " " + c["contents"][:500] for c in cands]
            try:
                qv = embed([base_q + " " + concept])[0]
                cv = []
                for i in range(0, len(texts), 10):
                    cv.extend(embed(texts[i:i + 10]))
                docs = [c for c, _ in sorted(zip(cands, cv), key=lambda x: -cos(qv, x[1]))[:a.k]]
            except Exception as e:
                print("embed fail", qid, e); docs = cands[:a.k]
        res[qid] = [{"id": d["id"], "source": d["source"], "title": d["title"], "contents": d["contents"]} for d in docs]
        if n % 200 == 0:
            print(a.method, n, round(time.time() - t0, 1), flush=True)
    json.dump(res, open(a.out, "w", encoding="utf-8"), ensure_ascii=False)
    print("saved", a.out, len(res), round(time.time() - t0, 1), "s")

if __name__ == "__main__":
    main()