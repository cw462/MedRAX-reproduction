#!/usr/bin/env python3
"""Score laterality answers against the packet's answer key.

Usage
-----
    python score_llm_answers.py answers.txt
    python score_llm_answers.py answers.jsonl --json scores.json
    python score_llm_answers.py model.txt --human human.txt

Accepted answer formats (auto-detected)
---------------------------------------
  * the same string the HTML sheet produces:  "1A 2B 3? 4B ..."
  * one case per line:                        "1 A" / "1. A" / "1A"
  * JSONL:                                    {"case": 1, "answer": "A"}
  * JSON object:                              {"1": "A", "2": "B"}
  * "?" or "X" both mean "cannot tell"

Metrics: overall accuracy (with a Wilson 95% interval), accuracy over answered
items only, indeterminate rate, per-stratum and per-finding breakdowns, and
left/right plus A/B response bias (a model that always answers "A" must not be
mistaken for a working laterality model).
"""
import argparse
import json
import math
import os
import re
import sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
KEY = os.path.join(HERE, "answer_key.json")


def norm(x):
    if x is None:
        return None
    s = str(x).strip().upper()
    if s in ("", "NONE", "NULL", "-", "NA", "N/A"):
        return None
    if s in ("A", "B"):
        return s
    if s in ("?", "X", "U", "UNKNOWN", "UNSURE"):
        return "?"
    return None


def parse_answers(path):
    """Return {case:int: 'A'|'B'|'?'|None}."""
    raw = open(path, encoding="utf-8").read().strip()
    out = {}

    if path.lower().endswith(".jsonl") or (raw.startswith("{") and "\n{" in raw):
        for line in raw.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            case = obj.get("case", obj.get("id"))
            ans = obj.get("answer", obj.get("pred", obj.get("choice")))
            if case is None:
                continue
            out[int(case)] = norm(ans)
        return out

    if raw.startswith("{"):
        obj = json.loads(raw)
        for k, v in obj.items():
            try:
                out[int(k)] = norm(v)
            except ValueError:
                continue
        return out

    # free text / one-line answer string
    for case, letter in re.findall(r"(?<!\d)(\d{1,3})\s*[:.\)\-]?\s*([ABabXx?])", raw):
        out[int(case)] = norm(letter)
    return out


def wilson(k, n, z=1.96):
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    m = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((c - m) / d, (c + m) / d)


def summarize(rows):
    n = len(rows)
    answered = [r for r in rows if r["answer"] in ("A", "B")]
    unable = [r for r in rows if r["answer"] == "?"]
    missing = [r for r in rows if r["answer"] is None]
    correct = sum(r["answer"] == r["gold"] for r in answered)
    lo, hi = wilson(correct, n)
    return {
        "n": n,
        "answered": len(answered),
        "unable": len(unable),
        "missing": len(missing),
        "correct": correct,
        "acc_all": round(correct / n, 4) if n else None,
        "acc_all_ci95": [round(lo, 4), round(hi, 4)],
        "acc_answered_only": round(correct / len(answered), 4) if answered else None,
        "unable_rate": round(len(unable) / n, 4) if n else None,
        "left_rate": round(sum(r["chose_left"] for r in answered) / len(answered), 4)
        if answered else None,
        "a_rate": round(sum(r["answer"] == "A" for r in answered) / len(answered), 4)
        if answered else None,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("answers")
    ap.add_argument("--key", default=KEY)
    ap.add_argument("--human", help="optional human answer file, for a side-by-side")
    ap.add_argument("--json", help="write the full report here")
    a = ap.parse_args()

    key = json.load(open(a.key, encoding="utf-8"))
    key = key["cases"] if isinstance(key, dict) else key
    by_case = {int(k["case"]): k for k in key}
    ans = parse_answers(a.answers)

    unknown = sorted(set(ans) - set(by_case))
    if unknown:
        print("warning: %d answer case numbers not in the key: %r" % (len(unknown), unknown[:10]))

    rows = []
    for c in sorted(by_case):
        k = by_case[c]
        answer = ans.get(c)
        # the two options differ only by the laterality word, so the chosen side
        # is the gold side when correct and the opposite side when wrong
        chose_left = None
        if answer in ("A", "B"):
            chose_left = (k["gold_attr"] == "left") if answer == k["gold"] else (k["gold_attr"] != "left")
        rows.append({
            "case": c,
            "qid": k["qid"],
            "finding": k["finding"],
            "stratum": k.get("stratum"),
            "gold": k["gold"],
            "answer": answer,
            "correct": answer == k["gold"] if answer in ("A", "B") else None,
            "chose_left": chose_left if answer in ("A", "B") else None,
        })

    report = {"overall": summarize(rows)}

    if any(r["stratum"] for r in rows):
        for s in sorted({r["stratum"] for r in rows if r["stratum"]}):
            report.setdefault("by_stratum", {})[s] = summarize([r for r in rows if r["stratum"] == s])

    groups = defaultdict(list)
    for r in rows:
        groups[r["finding"]].append(r)
    report["by_finding"] = {
        g: summarize(v) for g, v in sorted(groups.items(), key=lambda kv: -len(kv[1]))
    }

    if a.human:
        hum = parse_answers(a.human)
        agree = sum(1 for c, v in hum.items() if c in ans and v in ("A", "B") and ans[c] == v)
        both = sum(1 for c, v in hum.items() if c in ans and v in ("A", "B") and ans[c] in ("A", "B"))
        hrows = [dict(r, answer=hum.get(r["case"])) for r in rows]
        report["human"] = summarize(hrows)
        report["human_vs_model"] = {
            "agreement": round(agree / both, 4) if both else None,
            "both_answered": both,
        }

    o = report["overall"]
    print("=" * 62)
    print("cases %d | answered %d | unable %d | missing %d"
          % (o["n"], o["answered"], o["unable"], o["missing"]))
    print("accuracy          %.3f  (95%% CI %.3f-%.3f)" % (o["acc_all"], *o["acc_all_ci95"]))
    print("accuracy/answered %.3f   unable rate %.3f"
          % (o["acc_answered_only"] or 0, o["unable_rate"] or 0))
    print("bias: chose 'left' %.3f   chose 'A' %.3f" % (o["left_rate"] or 0, o["a_rate"] or 0))
    for name in ("human",):
        if name in report:
            h = report[name]
            print("%s accuracy      %.3f  (answered %d, unable %d)"
                  % (name, h["acc_all"], h["answered"], h["unable"]))
    if "human_vs_model" in report:
        print("human/model agreement %.3f over %d cases"
              % (report["human_vs_model"]["agreement"], report["human_vs_model"]["both_answered"]))

    if "by_stratum" in report:
        print("-" * 62)
        print("%-12s %5s %6s %6s %8s" % ("stratum", "n", "acc", "unable", "A-rate"))
        for s, m in report["by_stratum"].items():
            print("%-12s %5d %6.3f %6.3f %8.3f"
                  % (s, m["n"], m["acc_all"], m["unable_rate"], m["a_rate"]))

    print("-" * 62)
    print("%-40s %4s %6s %6s" % ("finding", "n", "acc", "unable"))
    for g, m in report["by_finding"].items():
        print("%-40s %4d %6.3f %6.3f" % (g[:40], m["n"], m["acc_all"], m["unable_rate"]))

    worst = [r for r in rows if r["answer"] in ("A", "B") and not r["correct"]]
    if worst:
        print("-" * 62)
        print("wrong items:", " ".join("%d%s" % (r["case"], r["answer"]) for r in worst))

    if a.json:
        json.dump(report, open(a.json, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print("report -> %s" % a.json)
    return 0


if __name__ == "__main__":
    sys.exit(main())
