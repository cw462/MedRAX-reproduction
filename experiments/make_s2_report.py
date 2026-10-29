"""Turn the S2 analysis JSON into the round-1 report.

The point of generating the narrative instead of typing it is that the conditional
sentences are decided by the numbers: a comparison whose interval spans zero must not
be described as an improvement, and the report says so mechanically.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ARMS = ("A", "B", "C")
LABEL = {"A": "A no memory", "B": "B structural memory", "C": "C semantic skill"}


def fmt(x, nd=3):
    return "n/a" if x is None else f"{x:.{nd}f}"


def verdict(row, better, worse):
    """Plain sentence for one paired comparison."""
    if not row or not row.get("n_cases"):
        return "not measured (one or both arms have no scored run)."
    diff = row["mean_diff"]
    lo, hi = row["ci95"]
    p = (row.get("sign_test") or {}).get("p_two_sided")
    if lo is None:
        return "not measured."
    if lo > 0:
        return (f"**{better} better** by {diff:+.3f} accuracy per question "
                f"(95% CI {lo:+.3f} to {hi:+.3f}, exact paired p={p}).")
    if hi < 0:
        return (f"**{worse} better** by {abs(diff):.3f} (95% CI {lo:+.3f} to {hi:+.3f}, "
                f"exact paired p={p}).")
    return (f"**no detectable difference** at this sample: {diff:+.3f} "
            f"(95% CI {lo:+.3f} to {hi:+.3f}, exact paired p={p}); the interval is consistent "
            "with both a small loss and a small gain.")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--analysis", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--ledger-note", default="")
    ap.add_argument("--faults", type=int, default=0)
    ap.add_argument("--lost-questions", type=int, default=0)
    ap.add_argument("--date", default="2026-10-29")
    args = ap.parse_args(argv)

    data = json.loads(args.analysis.read_text(encoding="utf-8"))
    runs = data.get("runs", {})
    paired = data.get("paired", {})
    by_type = data.get("by_type", {})
    effort = data.get("effort", {})

    lines = ["# V4 S2, round 1: A/B/C on the 60 fixed questions", ""]
    lines.append(f"Date: {args.date}. **Round 1 only**: rounds 2-3 were cancelled before "
                 "they started so this table could be reviewed first.")
    lines.append("")
    lines.append("Input: `runs/v4_validation60/inputs.jsonl` — 60 questions from cases never "
                 "used in development, 12 per official question-type group, one question per "
                 "case. Nothing here is a re-read of the development set.")
    lines.append("")
    lines.append("## Per arm")
    lines.append("")
    lines.append("| arm | n | correct | accuracy | Wilson 95% |")
    lines.append("|---|---:|---:|---:|---|")
    for arm in ARMS:
        key = f"{arm}_r1"
        row = runs.get(key)
        if not row:
            lines.append(f"| {LABEL[arm]} | — | — | — | — |")
            continue
        lines.append(f"| {LABEL[arm]} | {row['n']} | {row['correct']} | {fmt(row['accuracy'])} | "
                     f"{row['wilson']} |")
    lines.append("")
    lines.append("## Paired comparisons")
    lines.append("")
    lines.append("Same questions in every arm, so the comparison is within-question. The interval "
                 "is a percentile bootstrap over cases (one question per case here); the test is "
                 "the exact paired test on discordant questions.")
    lines.append("")
    lines.append("| comparison | cases | mean diff | 95% CI | discordant (better/other/tied) | exact p |")
    lines.append("|---|---:|---:|---|---|---:|")
    for name in ("A->B", "B->C", "A->C"):
        row = paired.get(name) or {}
        s = row.get("sign_test") or {}
        if not row.get("n_cases"):
            lines.append(f"| {name} | — | — | — | — | — |")
            continue
        lines.append(f"| {name} | {row['n_cases']} | {fmt(row['mean_diff'])} | "
                     f"{row['ci95']} | {s.get('b_better')}/{s.get('a_better')}/{s.get('tied')} | "
                     f"{s.get('p_two_sided')} |")
    lines.append("")
    lines.append("Reading, arm by arm:")
    lines.append("")
    lines.append(f"* A→B (does structural memory help?): {verdict(paired.get('A->B'), 'B', 'A')}")
    lines.append(f"* B→C (does the semantic representation beat structural memory?): "
                 f"{verdict(paired.get('B->C'), 'C', 'B')}")
    lines.append("")
    if by_type:
        lines.append("## By official question type")
        lines.append("")
        lines.append("| categories | n | A | B | C | B−A (95% CI) | C−B (95% CI) |")
        lines.append("|---|---:|---:|---:|---:|---|---|")
        for label, entry in by_type.items():
            cells = []
            for name in ("A->B", "B->C"):
                row = entry.get(name) or {}
                cells.append("—" if not row.get("n_cases")
                             else f"{fmt(row['mean_diff'])} {row['ci95']}")
            arms = entry["arms"]
            lines.append(f"| {label} | {entry['questions']} | {fmt(arms['A']['mean'])} | "
                         f"{fmt(arms['B']['mean'])} | {fmt(arms['C']['mean'])} | "
                         f"{cells[0]} | {cells[1]} |")
        lines.append("")
        lines.append("These are 12-question subgroups: they are descriptive, not powered tests.")
        lines.append("")
    if effort:
        lines.append("## Cost and effort")
        lines.append("")
        lines.append("| run | n | tool calls / q | model calls / q | charged CNY | CNY / q |")
        lines.append("|---|---:|---:|---:|---:|---:|")
        total = 0.0
        for name, row in effort.items():
            total += row["charged_cny"]
            lines.append(f"| {name} | {row['n']} | {row['mean_tool_calls']} | "
                         f"{row['mean_model_calls']} | {row['charged_cny']} | "
                         f"{row['cny_per_question']} |")
        lines.append("")
        lines.append(f"Round-1 spend in these runs: **{total:.2f} CNY** (conservative internal "
                     "bound at assumed prices, not the provider bill).")
        if args.ledger_note:
            lines.append("")
            lines.append(args.ledger_note)
        lines.append("")
    lines.append("## What this round cannot settle")
    lines.append("")
    half = None
    for name in ("A->B", "B->C"):
        row = paired.get(name) or {}
        if row.get("ci95") and row["ci95"][0] is not None:
            half = max(half or 0, (row["ci95"][1] - row["ci95"][0]) / 2)
    if half:
        lines.append(f"* **Power.** The 95% interval half-width here is about "
                     f"{half * 100:.0f} accuracy points. A real difference smaller than that "
                     "would be invisible at n=60; 'no detectable difference' is not 'no difference'.")
    lines.append("* **Prompt length is not held equal.** In S0, C's block sat at the 1400-character "
                 "cap while B's ran 554–1126 characters. Any B→C difference mixes representation "
                 "with prompt length until the planned `B_length_control` ablation is run.")
    lines.append("* **Repeats.** One round means model sampling noise is not averaged out; the same "
                 "questions were not re-run.")
    lines.append("")
    lines.append("## Pipeline integrity")
    lines.append("")
    lines.append("Every terminal below is a real tool-using episode: the scorer reads only the run's "
                 "`results.jsonl` and the labels, and the ledger's per-call settlements are recorded "
                 "in each terminal.")
    if args.faults:
        lines.append("")
        lines.append(f"The run survived {args.faults} ledger-guard faults; {args.lost_questions} "
                     "question(s) were lost and re-run, everything else was resumed, not repaid.")
    lines.append("")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
