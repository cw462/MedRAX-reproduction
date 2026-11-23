#!/usr/bin/env python3
"""Aggregate all evaluation results into one table."""
import glob, json, os

def summarize(path):
    d = json.load(open(path, encoding="utf-8"))
    out = {}
    for arm in ("base", "rag"):
        vals = [x[arm]["correct"] for x in d if arm in x and isinstance(x.get(arm), dict) and x[arm].get("correct") is not None]
        out[arm] = (sum(vals), len(vals))
    b, r = out["base"], out["rag"]
    fix = sum(1 for x in d if isinstance(x.get("base"), dict) and isinstance(x.get("rag"), dict)
              and not x["base"].get("correct") and x["rag"].get("correct"))
    brk = sum(1 for x in d if isinstance(x.get("base"), dict) and isinstance(x.get("rag"), dict)
              and x["base"].get("correct") and not x["rag"].get("correct"))
    return b, r, fix, brk

print(f"{'result file':38s} {'base':>12s} {'rag':>12s} {'delta':>8s} {'fix':>4s} {'break':>6s}")
for p in sorted(glob.glob("rag_eval/res_*.json")):
    if "smoke" in p: continue
    try:
        b, r, fix, brk = summarize(p)
    except Exception as e:
        print(p, "ERR", e); continue
    bs = f"{b[0]}/{b[1]}={100*b[0]/max(1,b[1]):.2f}%" if b[1] else "-"
    rs = f"{r[0]}/{r[1]}={100*r[0]/max(1,r[1]):.2f}%" if r[1] else "-"
    delta = f"{100*(r[0]/max(1,r[1]) - b[0]/max(1,b[1])):+.2f}" if b[1] and r[1] else "-"
    print(f"{os.path.basename(p):38s} {bs:>12s} {rs:>12s} {delta:>8s} {fix:4d} {brk:6d}")
