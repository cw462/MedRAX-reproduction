#!/usr/bin/env python3
"""Proxy for the human ceiling: how does an independent reader (MAIRA-2's own
grounded report) do specifically on the cases M5 got WRONG?

If a second, independent reader can recover most of M5's misses, the errors are
perceptual and worth attacking. If it also fails, the misses look like label
ambiguity. This is not a substitute for the human packet, but it is free and it
tells us whether asking a human is even worth the time.
"""
import json
import pathlib
from collections import Counter, defaultdict

HERE = pathlib.Path(__file__).resolve().parent.parent
R = HERE / "results"


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    r = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5)
    return ((c - r) / d, (c + r) / d)


def main():
    tasks = {t["qid"]: t for t in json.load(open(R / "maira2_20261123" / "lat_tasks_maira.json", encoding="utf-8"))}
    rep = {r["qid"]: r for r in json.load(open(R / "maira2_20261123" / "maira_report_scored.json", encoding="utf-8"))}
    p0 = {r["qid"]: r for r in json.load(open(R / "p0_side_result.json", encoding="utf-8"))}

    rows = []
    for q, t in tasks.items():
        if t["kind"] != "side" or q not in p0:
            continue
        r = rep.get(q) or {}
        rows.append({
            "qid": q,
            "stratum": "m5_right" if p0[q]["okA"] else "m5_wrong",
            "gold_attr": t["gold_attr"],
            "pred": r.get("pred"),
            "phrase": t["phrase"],
        })

    print(f"side tasks with M5 result: {len(rows)}")
    e = sum(1 for r in rows if r["stratum"] == "m5_wrong") / len(rows)
    print(f"M5 error rate: {100*e:.1f}%\n")

    print(f"{'stratum':10s} {'n':>4s} {'MAIRA answered':>15s} {'acc@answered':>13s} {'95% CI':>16s}")
    stats = {}
    for s in ("m5_wrong", "m5_right"):
        sel = [r for r in rows if r["stratum"] == s]
        ans = [r for r in sel if r["pred"]]
        ok = sum(1 for r in ans if r["pred"] == r["gold_attr"])
        lo, hi = wilson(ok, len(ans))
        stats[s] = (ok, len(ans), len(sel))
        print(f"{s:10s} {len(sel):4d} {len(ans):6d} ({100*len(ans)/len(sel):4.0f}%) "
              f"{100*ok/max(1,len(ans)):12.1f}% {100*lo:7.1f}–{100*hi:5.1f}%")

    print()
    print("=== interpretation ===")
    okw, nw, tw = stats["m5_wrong"]
    okr, nr, tr = stats["m5_right"]
    hw = okw / max(1, nw)
    hr = okr / max(1, nr)
    print(f"independent reader recovers {100*hw:.1f}% of M5's misses "
          f"({okw}/{nw} answered) and {100*hr:.1f}% of M5's hits ({okr}/{nr}).")
    print(f"weighted ceiling implied by this reader = "
          f"{100*(e*hw + (1-e)*hr):.1f}%")
    print()
    if hw > hr + 0.15:
        print("-> the reader is BETTER on M5's misses than on M5's hits.")
        print("   That is the signature of a real, recoverable perception gap.")
    elif hw > 0.60:
        print("-> substantial recoverable mass: M5's misses are largely answerable.")
    else:
        print("-> the reader also fails on M5's misses; consistent with label")
        print("   ambiguity rather than a perception gap.")

    # per-finding, on the wrong stratum
    print()
    print("per-finding on M5's misses (answered cases):")
    g = defaultdict(lambda: [0, 0])
    for r in rows:
        if r["stratum"] != "m5_wrong" or not r["pred"]:
            continue
        g[r["phrase"]][1] += 1
        g[r["phrase"]][0] += r["pred"] == r["gold_attr"]
    for k, (ok, n) in sorted(g.items(), key=lambda kv: -kv[1][1]):
        if n >= 2:
            print(f"  {k:34s} n={n:2d} recovered={100*ok/n:5.1f}%")


if __name__ == "__main__":
    main()
