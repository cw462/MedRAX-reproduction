#!/usr/bin/env python3
"""Compute retrieval reachability from a ranking file."""
import json, sys
sys.path.insert(0, "rag_eval")
from concepts import concept_for

def norm(t):
    return " " + " ".join(str(t).lower().split()) + " "

def covered(concept, docs, field="both"):
    if not concept or not docs: return False
    c = norm(concept)
    for d in docs:
        text = norm(d["title"] + " " + d["contents"][:800]) if field == "both" else norm(d["title"])
        if c in text:
            return True
    return False

def main():
    ranking_path = sys.argv[1]
    ranking = json.load(open(ranking_path, encoding="utf-8"))
    rows = json.load(open("rag_eval/data/questions_848.json", encoding="utf-8"))
    out = []
    for r in rows:
        qid = r["question_id"]
        docs = ranking.get(qid, [])
        concept, kind = concept_for(r["question"], r.get("options") or {})
        out.append({"dataset": r["dataset"], "qid": qid, "concept": concept, "kind": kind,
                    "hit1": covered(concept, docs[:1]), "hit5": covered(concept, docs[:5])})
    print("%-10s %5s %8s %9s %9s %9s" % ("dataset", "n", "finding%", "hit@1", "hit@5", "hit@5(find)"))
    for ds in ["slake", "vqarad", "chexbench", "ALL"]:
        sub = [o for o in out if ds == "ALL" or o["dataset"] == ds]
        find = [o for o in sub if o["kind"] == "finding"]
        f = lambda xs, k: 100 * sum(1 for x in xs if x[k]) / max(1, len(xs))
        print("%-10s %5d %8.1f%% %8.1f%% %8.1f%% %8.1f%%" % (
            ds, len(sub), 100 * len(find) / max(1, len(sub)),
            f(find, "hit1"), f(find, "hit5"), f(find, "hit5")))
    json.dump(out, open(ranking_path.replace(".json", "_metrics.json"), "w"), ensure_ascii=False, indent=1)

if __name__ == "__main__":
    main()
