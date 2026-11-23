#!/usr/bin/env python3
"""Score MAIRA-2 grounded-report laterality against CheXBench gold."""
import json
import re
from collections import Counter, defaultdict

TASKS = "/dev/shm/lat_tasks_maira.json"
REPORTS = "/dev/shm/maira_reports.json"
SCORED = "/dev/shm/maira_scored.json"

SIDE_WORDS = {"left": "left", "right": "right"}
VERT_WORDS = {"upper": "upper", "lower": "lower", "basilar": "lower", "base": "lower"}


def side_in(text, kind):
    w = re.findall(r"[a-z]+", text.lower())
    table = SIDE_WORDS if kind == "side" else VERT_WORDS
    hits = [table[x] for x in w if x in table]
    if not hits:
        return None, False
    c = Counter(hits)
    if len(c) > 1:
        return c.most_common(1)[0][0], True  # both mentioned -> ambiguous
    return hits[0], False


def main():
    tasks = json.load(open(TASKS, encoding="utf-8"))
    reports = json.load(open(REPORTS, encoding="utf-8"))
    scored = {r["qid"]: r for r in json.load(open(SCORED, encoding="utf-8"))}

    rows = []
    for t in tasks:
        rep = reports.get(t["image"]) or {}
        sents = rep.get("sentences") or []
        kw = t["phrase"].split()[-1].lower().rstrip(".,")
        cands = [s for s in sents if kw in s["text"].lower()]
        pred = amb = None
        used = None
        for s in cands:
            p, a = side_in(s["text"], t["kind"])
            if p:
                pred, amb, used = p, a, s["text"][:120]
                break
        # fall back: whole report
        if pred is None:
            p, a = side_in(rep.get("raw", ""), t["kind"])
            pred, amb, used = p, a, "FULL_REPORT" if p else None
        rows.append({"qid": t["qid"], "kind": t["kind"], "phrase": t["phrase"],
                     "gold_attr": t["gold_attr"], "gold": t["gold"],
                     "pred": pred, "ambiguous": amb, "evidence": used,
                     "n_sents": len(sents)})

    def acc(sel, use_prior=False):
        ok = n = 0
        for r in sel:
            p = r["pred"]
            if p is None:
                if not use_prior:
                    continue
                p = None
            n += 1
            ok += p == r["gold_attr"]
        return ok, n

    print(f"=== report-based answers (n={len(rows)}) ===")
    for kind in ("side", "vertical"):
        sel = [r for r in rows if r["kind"] == kind]
        ok, n = acc(sel)
        cov = len([r for r in sel if r["pred"]])
        print(f"  {kind:9s} n={len(sel):3d} answered={cov:3d} ({100*cov/len(sel):5.1f}%) "
              f"acc@answered={100*ok/max(1,n):5.1f}%")
        # by subset
        for sub in {r.get("kind") for r in sel}:
            pass

    print("\n=== per-group ===")
    g = defaultdict(list)
    for r in rows:
        if r["kind"] == "side":
            g[r["phrase"]].append(r)
    for k, rs in sorted(g.items(), key=lambda kv: -len(kv[1]))[:12]:
        ans = [r for r in rs if r["pred"]]
        ok = sum(1 for r in ans if r["pred"] == r["gold_attr"])
        print(f"  {k:34s} n={len(rs):3d} ans={len(ans):3d} acc={100*ok/max(1,len(ans)):5.1f}%")

    print("\n=== sample evidence ===")
    for r in rows[:14]:
        if r["pred"]:
            print(f"  {r['qid'][-4:]} gold={r['gold_attr']:5s} pred={r['pred']:5s} "
                  f"amb={r['ambiguous']} | {r['evidence']}")
    json.dump(rows, open("/dev/shm/maira_report_scored.json", "w"), indent=0)


if __name__ == "__main__":
    main()
