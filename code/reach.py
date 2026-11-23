#!/usr/bin/env python3
"""Offline retrieval-reachability probe for the 848 frozen questions.

For each question we build an *inference-time* query (question + options, never
the gold answer), retrieve top-5 from the local BM25 corpus, and check whether
the retrieved evidence covers the medical concept the question is about.

Metrics
-------
concept_cov      : share of questions where a medical concept could be extracted
topic_hit@1/@5   : P(concept appears in the rank-1 / top-5 evidence)
image_bound      : question whose options differ only by laterality/location ->
                   retrieval cannot answer it; reported separately
"""
import json, re, sys, collections
sys.path.insert(0, "rag_eval")
import index as bidx

BOILER = [
    "in this picture", "in this image", "in the image", "on this image", "in this chest x-ray",
    "in this cxr", "in this radiograph", "of this image", "in this study", "on this film",
    "in the picture", "in this photo", "shown here", "in the figure",
]
LATERAL = {"right", "left", "bilateral", "both", "upper", "lower", "base", "mid", "apex",
           "lateral", "medial", "basal", "side", "sides", "lobe", "zone", "abdominal",
           "peripheral", "central", "right-", "left-"}
NONMED = {"is", "are", "was", "were", "the", "a", "an", "there", "this", "that", "these", "those",
          "image", "picture", "show", "shows", "seen", "evidence", "present", "observed",
          "can", "could", "do", "does", "did", "which", "what", "where", "how", "why", "who",
          "any", "anything", "normal", "abnormal", "abnormally", "look", "looks", "appear",
          "appearing", "find", "finding", "findings", "study", "x-ray", "xray", "film",
          "radiograph", "chest", "yes", "no", "true", "false", "not", "or", "and", "of", "in",
          "on", "at", "to", "for", "with", "by", "from", "as", "it", "its", "be", "been"}

def norm(t):
    return re.sub(r"[^a-z0-9 ]", " ", t.lower())

def strip_boiler(q):
    s = " " + norm(q) + " "
    for b in BOILER:
        s = s.replace(" " + norm(b) + " ", " ")
    return re.sub(r"\s+", " ", s).strip()

def concept_of(question, options):
    """Medical concept, derived only from inference-time inputs."""
    cands = []
    if options:
        texts = [re.sub(r"^[a-d][\.\)]\s*", "", str(v)) for v in options.values()]
        # tokens shared by >=2 options are the common concept; for 2-option yes/no
        # questions the concept must come from the question itself
        toks = [set(w for w in norm(t).split() if w not in NONMED and w not in LATERAL) for t in texts]
        shared = set.intersection(*toks) if toks else set()
        if len(toks) >= 2 and shared:
            cands.append(" ".join(sorted(shared)))
        for t in texts:
            cands.append(t)
    q = strip_boiler(question)
    cands.append(q)
    for c in cands:
        words = [w for w in norm(c).split() if w not in NONMED and w not in LATERAL]
        if len(" ".join(words)) >= 4 and len(words) >= 1:
            return " ".join(words)
    return None

def is_image_bound(question, options):
    if not options:
        return False
    texts = [norm(str(v)) for v in options.values()]
    if len(texts) < 2:
        return False
    a, b = texts[0].split(), texts[1].split()
    if set(a) - set(b) and set(b) - set(a):
        da, db = set(a) - set(b), set(b) - set(a)
        if da | db <= LATERAL:
            return True
    return False

def hit(concept, docs):
    """Does any retrieved evidence cover the concept?"""
    words = [w for w in concept.split() if w not in NONMED and w not in LATERAL]
    if not words:
        return False, False
    phrase = " ".join(words)
    r1 = phrase in norm(docs[0]["title"] + " " + docs[0]["contents"][:400]) if docs else False
    anyhit = any(phrase in norm(d["title"] + " " + d["contents"][:600]) for d in docs)
    return r1, anyhit

def main():
    rows = json.load(open("rag_eval/data/questions_848.json", encoding="utf-8"))
    idx = bidx.load()
    print("index docs:", len(idx["ids"]))
    out = []
    for r in rows:
        q = r["question"]
        opts = r.get("options") or {}
        concept = concept_of(q, opts)
        query = strip_boiler(q)
        if opts:
            query += " " + " ".join(str(v) for v in opts.values())
        docs = bidx.search(idx, query, 5) if query.strip() else []
        ib = is_image_bound(q, opts)
        if concept:
            r1, anyh = hit(concept, docs)
        else:
            r1, anyh = False, False
        out.append({"dataset": r["dataset"], "qid": r["question_id"], "concept": concept,
                    "image_bound": ib, "r1": r1, "hit5": anyh,
                    "top1": docs[0]["title"][:120] if docs else None})
    json.dump(out, open("rag_eval/data/reachability.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    print("\n%-10s %5s %6s %8s %8s %8s %8s" % ("dataset", "n", "concept", "hit@1", "hit@5", "imgbound", "hit5(know)"))
    for ds in ["slake", "vqarad", "chexbench", "ALL"]:
        sub = [o for o in out if ds == "ALL" or o["dataset"] == ds]
        withc = [o for o in sub if o["concept"]]
        know = [o for o in withc if not o["image_bound"]]
        f = lambda xs, k: (sum(1 for x in xs if x[k]) / len(xs) * 100) if xs else 0.0
        print("%-10s %5d %5.1f%% %7.1f%% %7.1f%% %7.1f%% %7.1f%%" % (
            ds, len(sub), len(withc) / len(sub) * 100, f(withc, "r1"), f(withc, "hit5"),
            sum(1 for o in sub if o["image_bound"]) / len(sub) * 100, f(know, "hit5")))
    print("\nexamples with no hit:")
    for o in [o for o in out if o["concept"] and not o["hit5"]][:8]:
        print(" ", o["dataset"], "|", o["concept"], "|", o["top1"])

if __name__ == "__main__":
    main()
