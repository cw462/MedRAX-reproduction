#!/usr/bin/env python3
"""Score the stratified human packet and decide on the self-trained detector.

The 50 cases are 25 that M5 got wrong + 25 it got right, with laterality
balanced inside each stratum. That lets us estimate the human ceiling on the
population with proper weights, and — more usefully — how much of M5's error
mass is humanly recoverable.

Usage:
  python score_human.py "1A 2B 3- ..."     # "-"/"?" = cannot tell
  python score_human.py --selftest
"""
import json
import pathlib
import random
import sys
from collections import Counter, defaultdict

HERE = pathlib.Path(__file__).resolve().parent
MAN = HERE.parent / "results" / "human_lat_manifest_50.json"

M5_ACC = 0.650
PRIOR = 0.540
DS_BASE = 0.526


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    r = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5)
    return ((c - r) / d, (c + r) / d)


def parse(sheet):
    out = {}
    for tok in sheet.replace(",", " ").split():
        tok = tok.strip().upper()
        if not tok:
            continue
        num = "".join(ch for ch in tok if ch.isdigit())
        if not num:
            continue
        letter = "".join(ch for ch in tok if ch.isalpha() or ch in "-?")
        out[int(num)] = (letter[:1] or "-")
    return out


def load():
    d = json.load(open(MAN, encoding="utf-8"))
    return d["meta"], d["cases"]


def report(ans, meta, cases):
    per = defaultdict(lambda: [0, 0, 0])   # stratum -> [ok, answered, cannot_tell]
    per_group = defaultdict(lambda: [0, 0])
    for c in cases:
        s = per[c["stratum"]]
        a = ans.get(c["case"], "-")
        if a in ("-", "?", ""):
            s[2] += 1
            continue
        s[1] += 1
        ok = a == c["gold"]
        s[0] += ok
        per_group[c["phrase"]][1] += 1
        per_group[c["phrase"]][0] += ok

    n_ans = sum(v[1] for v in per.values())
    n_tot = sum(v[1] + v[2] for v in per.values())
    print(f"answered {n_ans}/{n_tot}, cannot-tell {sum(v[2] for v in per.values())}")
    print()
    print(f"{'stratum':10s} {'n':>3s} {'answered':>9s} {'human acc':>10s} {'95% CI':>16s}")
    stats = {}
    for name in ("m5_wrong", "m5_right"):
        ok, n, skip = per[name]
        lo, hi = wilson(ok, n)
        stats[name] = ok / n if n else None
        print(f"{name:10s} {n+skip:3d} {n:9d} {100*ok/max(1,n):9.1f}% "
              f"{100*lo:7.1f}–{100*hi:5.1f}%")
    print()
    if stats["m5_wrong"] is None or stats["m5_right"] is None:
        print("need answers in both strata to estimate the ceiling")
        return
    e = meta["err_rate"]
    ceiling = e * stats["m5_wrong"] + (1 - e) * stats["m5_right"]
    recoverable = e * stats["m5_wrong"]
    print(f"population weighting: {100*e:.1f}% of the 291 tasks are M5 errors")
    print(f"estimated human ceiling on the population = {100*ceiling:.1f}%")
    print(f"  M5 {100*M5_ACC:.1f}%   prior {100*PRIOR:.1f}%   DeepSeek {100*DS_BASE:.1f}%")
    print(f"  error mass a perfect system could recover = {100*recoverable:.1f} points "
          f"(if every human-solvable miss were fixed)")
    print()
    print("per-finding (answered cases):")
    for k, (ok, n) in sorted(per_group.items(), key=lambda kv: -kv[1][1]):
        if n >= 2:
            print(f"  {k:34s} n={n:2d} acc={100*ok/n:5.1f}%")
    print()
    print("=== detector decision ===")
    hw = stats["m5_wrong"]
    if hw >= 0.80:
        print(f"VERDICT: humans solve {100*hw:.0f}% of the cases M5 misses — the errors are")
        print("         perceptual, not label noise. A CXR detector has real upside.")
    elif hw >= 0.60:
        print(f"VERDICT: humans solve {100*hw:.0f}% of M5's misses. Headroom is real but")
        print("         modest; a detector must be strong to beat a 65% baseline.")
    else:
        print(f"VERDICT: humans only solve {100*hw:.0f}% of the cases M5 misses. Most of")
        print("         the error mass is label ambiguity, not perception. Do NOT")
        print("         fund a detector for this subset.")


def selftest():
    meta, cases = load()
    rng = random.Random(11)
    for name, hw, hr in [("oracle", 1.0, 1.0), ("realistic", 0.75, 0.95), ("weak", 0.45, 0.85)]:
        a = {}
        for c in cases:
            p = hw if c["stratum"] == "m5_wrong" else hr
            good = rng.random() < p
            a[c["case"]] = c["gold"] if good else ("B" if c["gold"] == "A" else "A")
        print(f"--- synthetic {name} (h_wrong={hw:.2f}, h_right={hr:.2f}) ---")
        report(a, meta, cases)
        print()
    print("--- parser ---", parse("1A 2b,3- 4? 5 A"))
    print("--- empty sheet ---")
    report({}, meta, cases)


def main():
    meta, cases = load()
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    if sys.argv[1] == "--selftest":
        selftest()
        return 0
    report(parse(sys.argv[1]), meta, cases)
    return 0


if __name__ == "__main__":
    sys.exit(main())
