#!/usr/bin/env python3
"""Disentangle 'label ambiguity' from 'shared model bias'.

The previous analysis showed MAIRA agrees with gold 83% on M5's hits but only
48% on M5's misses. That pattern is confounded: any reader correlated with M5
reproduces it even if the labels are perfect.

The discriminating test: when MAIRA is wrong on an M5-miss, is its error the
same side M5 chose?
  - mostly yes  -> MAIRA just repeats M5; shared bias, labels uninformative
  - about half  -> MAIRA fails independently; consistent with genuine ambiguity
"""
import json
import pathlib
from collections import Counter, defaultdict

HERE = pathlib.Path(__file__).resolve().parent.parent
R = HERE / "results"


def side_from_letter(t, letter):
    letter = str(letter).strip().upper()
    if letter == "A":
        return t["diff_a"]
    if letter == "B":
        return t["diff_b"]
    return None


def main():
    tasks = {t["qid"]: t for t in json.load(open(R / "maira2_20261123" / "lat_tasks_maira.json", encoding="utf-8"))}
    rep = {r["qid"]: r for r in json.load(open(R / "maira2_20261123" / "maira_report_scored.json", encoding="utf-8"))}
    p0 = {r["qid"]: r for r in json.load(open(R / "p0_side_result.json", encoding="utf-8"))}

    tab = defaultdict(Counter)
    for q, t in tasks.items():
        if t["kind"] != "side" or q not in p0 or q not in rep:
            continue
        mr = rep[q].get("pred")
        if not mr:
            continue
        strat = "m5_right" if p0[q]["okA"] else "m5_wrong"
        m5_side = side_from_letter(t, p0[q]["predA"])
        ok = mr == t["gold_attr"]
        if ok:
            tab[strat]["maira_correct"] += 1
        else:
            tab[strat]["maira_wrong"] += 1
            if m5_side and mr == m5_side:
                tab[strat]["error_equals_m5_answer"] += 1
            else:
                tab[strat]["error_differs_from_m5"] += 1

    print("MAIRA's error composition, split by whether M5 was right:")
    for s in ("m5_right", "m5_wrong"):
        c = tab[s]
        w = c["maira_wrong"]
        print(f"\n{s}  (n answered = {c['maira_correct'] + w})")
        print(f"  MAIRA correct: {c['maira_correct']}")
        print(f"  MAIRA wrong  : {w}")
        if w:
            same = c["error_equals_m5_answer"]
            print(f"    of which its error == M5's chosen side: {same} ({100*same/w:.0f}%)")
            print(f"    error in a different direction        : {w-same} ({100*(w-same)/w:.0f}%)")

    print()
    print("=== verdict ===")
    cw = tab["m5_wrong"]
    if cw["maira_wrong"]:
        share = cw["error_equals_m5_answer"] / cw["maira_wrong"]
        if share >= 0.75:
            print(f"{100*share:.0f}% of MAIRA's failures on M5's misses land exactly where M5")
            print("landed. That is shared bias, not independent failure: the 48% number is")
            print("an artifact of the stratification, and says nothing about label quality.")
        elif share >= 0.45:
            print(f"{100*share:.0f}% of MAIRA's failures coincide with M5's answer — a mix.")
            print("Some shared bias, some genuine difficulty. Ambiguous evidence.")
        else:
            print(f"Only {100*share:.0f}% of MAIRA's failures coincide with M5's answer, i.e.")
            print("MAIRA fails independently. That supports genuine label ambiguity.")


if __name__ == "__main__":
    main()
