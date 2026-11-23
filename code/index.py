#!/usr/bin/env python3
"""BM25 index (pure numpy, no Java/GPU)."""
import json, os, pickle, re, sys, time
import numpy as np

ROOT = r"H:/RAG_KB"
CORPUS = os.environ.get("RAG_CORPUS", os.path.join(ROOT, "corpus.jsonl"))
INDEX = os.environ.get("RAG_INDEX", os.path.join(ROOT, "bm25_index.pkl"))
TOKEN = re.compile(r"[a-z0-9]+")
STOP = set("""a an the of in on at to for with and or is are was were be been being this that these those
as by from its it their his her they we you i not no but if then than so such can could may might must
show shows shown seen imaging image images patient patients case cases finding findings present presented
what which who whom how why when where does do did has have had also use used using into more most other
about after before between during within without there here all any each both some very well
""".split())

def stem(w):
    if w.endswith("ies") and len(w) > 4: return w[:-3] + "y"
    if w.endswith(("ses", "xes", "ches", "shes")): return w[:-2]
    if w.endswith("s") and not w.endswith("ss") and len(w) > 3: return w[:-1]
    if w.endswith("ing") and len(w) > 5: return w[:-3]
    if w.endswith("ed") and len(w) > 4: return w[:-2]
    return w

def toks(text):
    return [stem(t) for t in TOKEN.findall(text.lower()) if t not in STOP and len(t) > 1]

JUNK = re.compile(r"(access free multiple choice questions|review questions|click here)", re.I)

def doc_text(d):
    c = d["contents"]
    if d.get("source") == "StatPearls" and d.get("title"):
        return (d["title"] + " ") * 2 + c
    return c

def usable(d, tk):
    if len(tk) < 8: return False
    if d.get("source") == "StatPearls" and JUNK.search(d["contents"]) and len(d["contents"]) < 320:
        return False
    return True

def build():
    t0 = time.time()
    ids, sources, titles, contents, dls = [], [], [], [], []
    df = {}
    rows = 0
    with open(CORPUS, encoding="utf-8") as f:
        for line in f:
            rows += 1
            d = json.loads(line)
            tk = toks(doc_text(d))
            if not usable(d, tk):
                continue
            ids.append(d["id"]); sources.append(d["source"]); titles.append(d.get("title", ""))
            contents.append(d["contents"]); dls.append(len(tk))
            for w in set(tk):
                df[w] = df.get(w, 0) + 1
            if rows % 100000 == 0:
                print("read", rows, len(ids), round(time.time() - t0, 1), flush=True)
    N = len(ids)
    vocab = {w: i for i, w in enumerate(df)}
    print("kept docs", N, "vocab", len(vocab))
    inv_ids = [[] for _ in range(len(vocab))]
    inv_tfs = [[] for _ in range(len(vocab))]
    keep = 0
    with open(CORPUS, encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            tk = toks(doc_text(d))
            if not usable(d, tk):
                continue
            tf = {}
            for w in tk:
                tf[w] = tf.get(w, 0) + 1
            for w, c in tf.items():
                tid = vocab[w]
                inv_ids[tid].append(keep); inv_tfs[tid].append(c)
            keep += 1
            if keep % 200000 == 0:
                print("index", keep, flush=True)
    assert keep == N, (keep, N)
    idf = np.zeros(len(vocab), dtype=np.float32)
    for w, i in vocab.items():
        n = df[w]
        idf[i] = np.log(1 + (N - n + 0.5) / (n + 0.5))
    data = {"ids": ids, "sources": sources, "titles": titles, "contents": contents,
            "dl": np.asarray(dls, dtype=np.int32), "avgdl": float(np.mean(dls)),
            "vocab": vocab, "idf": idf,
            "inv_ids": [np.asarray(x, dtype=np.int32) for x in inv_ids],
            "inv_tfs": [np.asarray(x, dtype=np.float32) for x in inv_tfs]}
    with open(INDEX, "wb") as f:
        pickle.dump(data, f, protocol=4)
    print("built in", round(time.time() - t0, 1), "s ->", INDEX, flush=True)

def load():
    with open(INDEX, "rb") as f:
        return pickle.load(f)

def search(idx, query, k=5, k1=1.5, b=0.75):
    q = toks(query)
    if not q: return []
    scores = np.zeros(len(idx["ids"]), dtype=np.float32)
    avgdl, dl = idx["avgdl"], idx["dl"]
    for w in q:
        rid = idx["vocab"].get(w)
        if rid is None: continue
        dids = idx["inv_ids"][rid]; tfs = idx["inv_tfs"][rid]
        denom = tfs + k1 * (1 - b + b * dl[dids] / avgdl)
        scores[dids] += idx["idf"][rid] * tfs * (k1 + 1) / denom
    kk = min(k, len(scores) - 1)
    top = np.argpartition(-scores, kk)[:k]
    top = top[np.argsort(-scores[top])]
    return [{"doc": int(i), "score": float(scores[i]), "id": idx["ids"][i], "source": idx["sources"][i],
             "title": idx["titles"][i], "contents": idx["contents"][i]} for i in top if scores[i] > 0]

if __name__ == "__main__":
    if sys.argv[1] == "build":
        if len(sys.argv) > 2: CORPUS = sys.argv[2]
        if len(sys.argv) > 3: INDEX = sys.argv[3]
        build()
    else:
        idx = load()
        print("docs", len(idx["ids"]))
        for r in search(idx, "aortic aneurysm", 3):
            print(round(r["score"], 2), r["source"], "|", r["title"][:90])
