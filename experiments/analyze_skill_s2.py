"""S2 analysis: paired A->B->C comparison on the fixed 60-question set.

Reads the scored sidecars of the nine arm-runs (`v4_{A,B,C}_r{1,2,3}`), pairs the
same questions across arms, and reports:

  * per arm-run accuracy with a Wilson interval;
  * per arm pooled over repeats, and the per-question mean across repeats;
  * the paired difference between arms, bootstrapped over cases (the unit that
    was sampled: one question per case, so a case bootstrap is a question
    bootstrap here and is labelled as such);
  * a breakdown by the official `categories` label.

Nothing here re-scores answers: it only consumes the scorer's `detail` rows, so
the answer key is still read in exactly one place.
"""
from __future__ import annotations

import argparse
import json
import math
import random
from collections import Counter, defaultdict
from pathlib import Path

ARMS = ("A", "B", "C")
LABELS = {"A": "A no memory", "B": "B structural memory", "C": "C semantic skill"}


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def wilson(k, n, z=1.959963984540054):
    if n <= 0:
        return [None, None]
    p = k / n
    den = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return [round(max(0.0, centre - half), 4), round(min(1.0, centre + half), 4)]


def load_types(metadata_path):
    """question_id -> official categories string, with the id normalisation the
    dataset needs (`11583_11583_8353...` -> `11583_8353...`)."""
    types = {}
    path = Path(metadata_path)
    if not path.exists():
        return types
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            # the downloaded metadata has a few truncated lines; a type label is
            # not worth failing the whole analysis over
            continue
        qid = str(row.get("full_question_id") or row.get("question_id") or "")
        parts = qid.split("_")
        if len(parts) == 3:
            qid = parts[0] + "_" + parts[2]
        cat = row.get("categories") or row.get("type")
        if isinstance(cat, list) and cat:
            cat = cat[0]
        if isinstance(cat, str) and cat:
            types[qid] = cat
    return types


def collect(runs_root, rounds):
    """(arm, round) -> {question_id: outcome detail row}"""
    out, meta = {}, {}
    for arm in ARMS:
        for rnd in rounds:
            run = Path(runs_root) / f"v4_{arm}_r{rnd}"
            score = Path(runs_root) / f"v4_{arm}_r{rnd}_scored" / "score.json"
            if not score.exists():
                continue
            payload = read_json(score)
            rows = {str(d["question_id"]): d for d in payload.get("detail", [])}
            out[(arm, rnd)] = rows
            meta[(arm, rnd)] = {
                "graded": payload.get("graded_denominator"),
                "acc_graded": payload.get("accuracy_among_graded"),
                "counts": payload.get("outcome_counts"),
                "wilson": payload.get("wilson_95ci_among_graded"),
            }
    return out, meta


def per_question_means(collected, rounds):
    """arm -> question_id -> mean correctness over the rounds that have a result."""
    means = {}
    for arm in ARMS:
        acc = defaultdict(list)
        for rnd in rounds:
            for qid, row in collected.get((arm, rnd), {}).items():
                if row.get("task_outcome") in ("correct", "incorrect"):
                    acc[qid].append(1.0 if row["task_outcome"] == "correct" else 0.0)
        means[arm] = {qid: sum(v) / len(v) for qid, v in acc.items() if v}
    return means


def bootstrap_diff(means_a, means_b, qids, n_boot=10000, seed=20261029):
    diffs = [means_b[q] - means_a[q] for q in qids if q in means_a and q in means_b]
    if not diffs:
        return {"n_cases": 0, "mean_diff": None, "ci95": [None, None], "p_two_sided": None}
    rng = random.Random(seed)
    n = len(diffs)
    boots = sorted(sum(diffs[rng.randrange(n)] for _ in range(n)) / n for _ in range(n_boot))
    lo, hi = boots[int(0.025 * n_boot)], boots[int(0.975 * n_boot) - 1]
    mean = sum(diffs) / n
    # two-sided sign test on per-question differences (exact binomial, ties dropped)
    pos = sum(1 for d in diffs if d > 1e-9)
    neg = sum(1 for d in diffs if d < -1e-9)
    ties = n - pos - neg
    k, m = min(pos, neg), pos + neg
    p = 1.0 if m == 0 else min(1.0, 2 * sum(math.comb(m, i) for i in range(k + 1)) / (2 ** m))
    return {"n_cases": n, "mean_diff": round(mean, 4), "ci95": [round(lo, 4), round(hi, 4)],
            "sign_test": {"b_better": pos, "a_better": neg, "tied": ties,
                          "p_two_sided": round(p, 6)}}


def fmt(x, nd=3):
    return "n/a" if x is None else f"{x:.{nd}f}"


def collect_effort(runs_root, rounds):
    """Per arm-run cost and call counts, read from the eval's terminal records."""
    effort = {}
    for arm in ARMS:
        for rnd in rounds:
            run = Path(runs_root) / f"v4_{arm}_r{rnd}"
            results = run / "results.jsonl"
            if not results.exists():
                continue
            terminals = []
            for line in results.read_text(encoding="utf-8", errors="replace").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if row.get("record_type") == "terminal":
                    terminals.append(row)
            if not terminals:
                continue
            charged = sum(float(s.get("charged_cny") or 0)
                          for t in terminals for s in (t.get("ledger_settlements") or []))
            effort[f"{arm}_r{rnd}"] = {
                "n": len(terminals),
                "mean_tool_calls": round(sum(t.get("actual_tool_attempts") or 0
                                             for t in terminals) / len(terminals), 2),
                "mean_model_calls": round(sum(t.get("actual_model_calls") or 0
                                              for t in terminals) / len(terminals), 2),
                "charged_cny": round(charged, 4),
                "cny_per_question": round(charged / len(terminals), 4),
            }
    return effort


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--runs", type=Path, required=True)
    ap.add_argument("--rounds", type=int, nargs="+", default=[1, 2, 3])
    ap.add_argument("--metadata", type=Path, required=True)
    ap.add_argument("--json-out", type=Path)
    ap.add_argument("--md-out", type=Path)
    args = ap.parse_args(argv)

    collected, meta = collect(args.runs, args.rounds)
    if not collected:
        raise SystemExit("no scored arm-runs found")
    means = per_question_means(collected, args.rounds)
    # The raw download truncates a few metadata lines; the repaired copy is the
    # one that labels all 2,500 questions, so prefer whichever covers more of the
    # questions this analysis actually has.
    candidates = [args.metadata, args.metadata.with_name(args.metadata.name + ".new")]
    types = {}
    for path in candidates:
        if not path.exists():
            continue
        loaded = load_types(path)
        if sum(1 for arm in ARMS for q in means[arm] if q in loaded) > \
                sum(1 for arm in ARMS for q in means[arm] if q in types):
            types = loaded
    qids = sorted({q for arm in ARMS for q in means[arm]})

    report = {"rounds": args.rounds, "questions_with_results": len(qids), "runs": {},
              "pooled": {}, "paired": {}, "by_type": {}}

    # --- per run
    for (arm, rnd), rows in sorted(collected.items()):
        n = len(rows)
        k = sum(1 for r in rows.values() if r.get("task_outcome") == "correct")
        report["runs"][f"{arm}_r{rnd}"] = {
            "n": n, "correct": k, "accuracy": round(k / n, 4) if n else None,
            "wilson": wilson(k, n),
            "outcome_counts": dict(Counter(r.get("task_outcome") for r in rows.values()))}
    # --- pooled per arm (each question counted once per round it ran)
    for arm in ARMS:
        cells = [(q, means[arm][q]) for q in qids if q in means[arm]]
        k = sum(v for _q, v in cells)
        n = len(cells)
        report["pooled"][arm] = {
            "questions": n, "mean_of_question_means": round(k / n, 4) if n else None,
            "wilson_on_question_means": wilson(k, n)}

    # --- paired differences
    for a, b in (("A", "B"), ("B", "C"), ("A", "C")):
        report["paired"][f"{a}->{b}"] = bootstrap_diff(means[a], means[b], qids)

    # --- by official type
    by_type = defaultdict(list)
    for q in qids:
        by_type[types.get(q, "unlabelled")].append(q)
    for label, group in sorted(by_type.items()):
        entry = {"questions": len(group), "arms": {}}
        for arm in ARMS:
            k = sum(means[arm][q] for q in group if q in means[arm])
            n = sum(1 for q in group if q in means[arm])
            entry["arms"][arm] = {"mean": round(k / n, 4) if n else None, "n": n}
        for a, b in (("A", "B"), ("B", "C")):
            entry[f"{a}->{b}"] = bootstrap_diff(means[a], means[b], group)
        report["by_type"][label] = entry

    effort = collect_effort(args.runs, args.rounds)
    report["effort"] = effort
    letters = {}
    for (arm, rnd), rows in collected.items():
        for qid, row in rows.items():
            letters[(arm, qid)] = row.get("letter") or row.get("status") or "?"

    # --- markdown
    lines = ["# S2 paired comparison", ""]
    lines.append(f"Rounds analysed: {args.rounds}. Questions with at least one result: {len(qids)}.")
    if len(args.rounds) == 1:
        lines.append("One round only, so the paired test below is McNemar's exact test on the "
                     "discordant questions.")
    lines.append("")
    lines.append("## Per arm-run")
    lines.append("")
    lines.append("| run | n | correct | accuracy | Wilson 95% |")
    lines.append("|---|---:|---:|---:|---|")
    for name, row in report["runs"].items():
        lines.append(f"| {name} | {row['n']} | {row['correct']} | {fmt(row['accuracy'])} | "
                     f"{row['wilson']} |")
    lines.append("")
    lines.append("## Paired difference (per question mean over rounds, bootstrap over cases)")
    lines.append("")
    lines.append("| comparison | cases | mean diff | 95% CI | B better / A better / tied | sign-test p |")
    lines.append("|---|---:|---:|---|---|---:|")
    for name, row in report["paired"].items():
        s = row.get("sign_test") or {}
        if not row.get("n_cases"):
            lines.append(f"| {name} | 0 | — | — | — | — |")
            continue
        lines.append(f"| {name} | {row['n_cases']} | {fmt(row['mean_diff'])} | {row['ci95']} | "
                     f"{s.get('b_better')}/{s.get('a_better')}/{s.get('tied')} | {s.get('p_two_sided')} |")
    lines.append("")
    lines.append("## By official categories")
    lines.append("")
    lines.append("| categories | n | A | B | C | B-A (95% CI) | C-B (95% CI) |")
    lines.append("|---|---:|---:|---:|---:|---|---|")
    for label, entry in report["by_type"].items():
        a = entry["arms"]["A"]["mean"]; b = entry["arms"]["B"]["mean"]; c = entry["arms"]["C"]["mean"]
        ab = entry["A->B"]; bc = entry["B->C"]
        cells = []
        for row in (ab, bc):
            cells.append("—" if not row.get("n_cases")
                         else f"{fmt(row['mean_diff'])} {row['ci95']}")
        lines.append(f"| {label} | {entry['questions']} | {fmt(a)} | {fmt(b)} | {fmt(c)} | "
                     f"{cells[0]} | {cells[1]} |")
    lines.append("")
    if effort:
        lines.append("## Cost and effort per arm-run (from the terminal records)")
        lines.append("")
        lines.append("| run | n | tool calls / q | model calls / q | charged CNY | CNY / q |")
        lines.append("|---|---:|---:|---:|---:|---:|")
        for name, row in effort.items():
            mark = "*" if row["n"] < 60 else ""
            lines.append(f"| {name} | {row['n']}{mark} | {row['mean_tool_calls']} | "
                         f"{row['mean_model_calls']} | {row['charged_cny']} | "
                         f"{row['cny_per_question']} |")
        lines.append("")
        if any(row["n"] < 60 for row in effort.values()):
            lines.append("* fewer than 60 terminals: the arm was still running when this file was written.")
            lines.append("")
    if letters:
        short = {}
        for i, label in enumerate(sorted(report["by_type"]), 1):
            short[label] = f"T{i}"
        lines.append("## Per-question matrix")
        lines.append("")
        lines.append("Type codes: " + ", ".join(f"{code}={label}" for label, code in short.items()))
        lines.append("")
        lines.append("| question | type | A | B | C |")
        lines.append("|---|---|---|---|---|")
        for q in qids:
            t = short.get(types.get(q, ""), "?")
            cells = [letters.get((arm, q), "-") for arm in ARMS]
            lines.append(f"| {q} | {t} | " + " | ".join(str(c) for c in cells) + " |")
        lines.append("")
    text = "\n".join(lines) + "\n"
    print(text)
    if args.json_out:
        Path(args.json_out).write_text(json.dumps(report, ensure_ascii=False, indent=1) + "\n",
                                       encoding="utf-8")
    if args.md_out:
        Path(args.md_out).write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
