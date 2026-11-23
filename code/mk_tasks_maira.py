#!/usr/bin/env python3
"""Build MAIRA-2 phrase-grounding tasks for CheXBench localization questions.

Reads the frozen inputs.jsonl, splits each 2-option question into
(options, common phrase, differing token), and classifies the question type
so we can later answer geometrically from a grounding box.
"""
import json
import os
import re
import sys

INP = "/dev/shm/frozen/data/chexbench/inputs.jsonl"
ROOT = "/dev/shm/frozen/data/chexbench"
OUT = "/dev/shm/lat_tasks_maira.json"
GOLD = "/root/chexbench_gold.json"

SIDE_PAIRS = {"left": "right", "right": "left"}
VERT_PAIRS = {"upper": "lower", "lower": "upper", "base": "apex", "apex": "base",
              "upperlobe": "lowerlobe"}


def split_opts(a, b):
    """Return (common_tokens, diff_a, diff_b) tokenised on whitespace."""
    ta, tb = a.split(), b.split()
    if len(ta) != len(tb):
        return None
    diffs = [(i, x, y) for i, (x, y) in enumerate(zip(ta, tb)) if x != y]
    if len(diffs) != 1:
        return None
    i, da, db = diffs[0]
    common = ta[:i] + ta[i + 1:]
    return common, da, db, i


def classify(da, db):
    if SIDE_PAIRS.get(da) == db:
        return "side"
    if VERT_PAIRS.get(da) == db:
        return "vertical"
    if {da, db} <= {"severe", "mild", "moderate", "small", "large"}:
        return "severity"
    return "other"


def main():
    rows = [json.loads(l) for l in open(INP, encoding="utf-8")]
    gold = json.load(open(GOLD, encoding="utf-8"))
    tasks, skipped = [], []
    for r in rows:
        o = r.get("options") or {}
        if not ({"A", "B"} <= set(o)):
            continue
        a, b = str(o["A"]).strip().lower(), str(o["B"]).strip().lower()
        sp = split_opts(a, b)
        if sp is None:
            skipped.append((r["question_id"], a, b, "not_single_token_diff"))
            continue
        common, da, db, idx = sp
        kind = classify(da, db)
        if kind == "other":
            skipped.append((r["question_id"], a, b, f"diff={da}/{db}"))
            continue
        phrase = " ".join(common).strip()
        if not phrase:
            skipped.append((r["question_id"], a, b, "empty_common"))
            continue
        img = os.path.join(ROOT, r["images"][0])
        g = gold.get(r["question_id"])
        if g not in ("A", "B"):
            skipped.append((r["question_id"], a, b, f"no_gold({g})"))
            continue
        tasks.append({
            "qid": r["question_id"],
            "image": img,
            "options": {"A": a, "B": b},
            "phrase": phrase,
            "kind": kind,
            "diff_a": da,
            "diff_b": db,
            "diff_index": idx,
            "subset": r["source"]["subset"],
            "gold": g,
            "gold_attr": da if g == "A" else db,
        })
    json.dump(tasks, open(OUT, "w"), indent=0)
    from collections import Counter
    print("tasks", len(tasks), Counter(t["kind"] for t in tasks))
    print("gold balance:", Counter(t["gold"] for t in tasks))
    print("skipped", len(skipped))
    for s in skipped[:8]:
        print("  skip:", s)
    missing = [t["image"] for t in tasks if not os.path.exists(t["image"])]
    print("missing images:", len(missing))
    for m in missing[:5]:
        print("   ", m)
    print("saved", OUT)


if __name__ == "__main__":
    main()
