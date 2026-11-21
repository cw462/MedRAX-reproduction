"""Metrics for development, replay, snapshot validation and paired evaluation.

The experiment runner supplies the existing scorer's binary `correct` field.
This module never reads reference answers or changes prediction records.
"""
from __future__ import annotations

import argparse
import csv
import json
import random
from collections import defaultdict, deque
from pathlib import Path
from typing import Any, Iterable

Row = dict[str, Any]
Key = tuple[str, str]


def key(row: Row) -> Key:
    return str(row["dataset"]), str(row["qid"])


def score(row: Row) -> int:
    value = row["correct"]
    if type(value) not in (bool, int, float) or value not in (0, 1):
        raise ValueError(f"correct must be 0/1, not {value!r}: {key(row)}")
    return int(value)


def first_pass(rows: Iterable[Row], phase: str, arm: str,
               checkpoint: str | None = None) -> list[Row]:
    selected = [r for r in rows if r.get("phase") == phase
                and r.get("arm") == arm and r.get("kind") == "first_pass"
                and (checkpoint is None or r.get("checkpoint") == checkpoint)]
    selected.sort(key=lambda r: int(r["step"]))
    keys = [key(r) for r in selected]
    steps = [int(r["step"]) for r in selected]
    if len(set(keys)) != len(keys) or len(set(steps)) != len(steps):
        raise ValueError("Duplicate first-pass question or stream step")
    for row in selected:
        score(row)
    return selected


def summary(rows: list[Row], planned: int | None = None) -> Row:
    n = len(rows)
    if planned is not None and n > planned:
        raise ValueError(f"Observed {n} rows exceeds planned {planned}")
    correct = sum(score(r) for r in rows)
    grouped: dict[str, list[Row]] = defaultdict(list)
    for row in rows:
        grouped[str(row["dataset"])].append(row)
    per_dataset = {}
    for dataset, items in sorted(grouped.items()):
        hits = sum(score(r) for r in items)
        per_dataset[dataset] = {"n": len(items), "correct": hits,
                                "accuracy": hits / len(items)}
    return {"n": n, "planned": planned,
            "status": ("complete" if n == planned else "partial")
            if planned is not None else "observed",
            "correct": correct, "accuracy": correct / n if n else None,
            "per_dataset": per_dataset}


def online_curve(rows: list[Row], window: int = 20) -> list[Row]:
    if window < 1:
        raise ValueError("window must be positive")
    curve, recent, total = [], deque(maxlen=window), 0
    for n, row in enumerate(rows, 1):
        value = score(row)
        total += value
        recent.append(value)
        curve.append({"step": row["step"], "dataset": row["dataset"],
                      "qid": row["qid"], "correct": value,
                      "completed": n, "cumulative_correct": total,
                      "cumulative_accuracy": total / n,
                      "rolling_n": len(recent),
                      "rolling_accuracy": sum(recent) / len(recent)})
    return curve


def select_snapshot(rows: Iterable[Row], expected: int = 100,
                    names: tuple[str, ...] = ("S0", "S50", "S100"),
                    arm: str = "RSI") -> Row:
    records = list(rows)
    outputs, reference = [], None
    for name in names:
        items = first_pass(records, "val", arm, name)
        if len(items) != expected:
            raise ValueError(f"{name}: {len(items)}/{expected} validation rows")
        current = [key(r) for r in items]
        if reference is not None and current != reference:
            raise ValueError("Validation snapshots must use identical question order")
        reference = current
        outputs.append({"checkpoint": name, **summary(items, expected)})
    # max retains the first occurrence when scores tie.
    winner = max(outputs, key=lambda s: s["correct"])
    return {"selected": winner["checkpoint"], "metric": "first_pass_micro_accuracy",
            "tie_break": "earliest_checkpoint", "snapshots": outputs}


def paired_summary(baseline: list[Row], method: list[Row],
                   planned: int = 848) -> Row:
    if [key(r) for r in baseline] != [key(r) for r in method]:
        raise ValueError("Paired arms must have identical questions and order")
    if len({key(r) for r in baseline}) != len(baseline):
        raise ValueError("Duplicate paired question")
    b, m = summary(baseline, planned), summary(method, planned)
    corrections = sum(score(x) == 0 and score(y) == 1
                      for x, y in zip(baseline, method))
    harms = sum(score(x) == 1 and score(y) == 0
                for x, y in zip(baseline, method))
    n = len(baseline)
    per_dataset = {}
    for dataset in sorted({str(r["dataset"]) for r in baseline}):
        pairs = [(x, y) for x, y in zip(baseline, method)
                 if str(x["dataset"]) == dataset]
        fixed = sum(score(x) == 0 and score(y) == 1 for x, y in pairs)
        hurt = sum(score(x) == 1 and score(y) == 0 for x, y in pairs)
        per_dataset[dataset] = {"n": len(pairs), "corrections": fixed,
                               "harms": hurt, "net": fixed - hurt,
                               "delta_pp": 100 * (fixed - hurt) / len(pairs)}
    return {"baseline": b, "method": m, "compared_n": n,
            "status": b["status"], "corrections": corrections, "harms": harms,
            "net": corrections - harms,
            "delta_pp": 100 * (corrections - harms) / n if n else None,
            "per_dataset": per_dataset}


def replay_summary(rows: Iterable[Row]) -> list[Row]:
    groups: dict[tuple[int, str], list[Row]] = defaultdict(list)
    for row in rows:
        if row.get("kind") == "replay":
            groups[(int(row["round"]), str(row["variant"]))].append(row)
    output = []
    for (round_no, variant), items in sorted(groups.items()):
        items.sort(key=lambda r: (int(r["trial"]), int(r["step"])))
        signature = [(int(r["trial"]), key(r)) for r in items]
        if len(set(signature)) != len(signature):
            raise ValueError(f"Duplicate replay row: round {round_no}, {variant}")
        incumbent = sorted(groups.get((round_no, "incumbent"), []),
                           key=lambda r: (int(r["trial"]), int(r["step"])))
        inc_signature = [(int(r["trial"]), key(r)) for r in incumbent]
        comparable = bool(incumbent) and signature == inc_signature
        acc = sum(score(r) for r in items) / len(items)
        inc_acc = (sum(score(r) for r in incumbent) / len(incumbent)
                   if incumbent else None)
        output.append({"round": round_no, "variant": variant,
                       "n_executions": len(items),
                       "n_questions": len({key(r) for r in items}),
                       "n_trials": len({int(r["trial"]) for r in items}),
                       "accuracy": acc, "comparable_to_incumbent": comparable,
                       "delta_pp": 100 * (acc - inc_acc) if comparable else None})
    return output


def sample_dev100(rows: Iterable[Row], seed: int = 42) -> list[Row]:
    """Sample canonical train_new metadata; the first 50 are a fixed prefix.

    Dataset names must be `rad_restruct` or `slake`. Perform any existing
    split-overlap exclusions before calling this function.
    """
    rows = list(rows)
    if len({key(r) for r in rows}) != len(rows):
        raise ValueError("Duplicate development-pool question")
    rng = random.Random(seed)
    groups = {}
    for dataset, count in (("rad_restruct", 73), ("slake", 27)):
        items = sorted([r for r in rows if r["dataset"] == dataset], key=key)
        if len(items) < count:
            raise ValueError(f"{dataset}: need {count}, found {len(items)}")
        rng.shuffle(items)
        groups[dataset] = items[:count]
    prefix = groups["rad_restruct"][:37] + groups["slake"][:13]
    suffix = groups["rad_restruct"][37:] + groups["slake"][13:]
    rng.shuffle(prefix)
    rng.shuffle(suffix)
    return [{**row, "step": i} for i, row in enumerate(prefix + suffix, 1)]


def read_jsonl(path: Path) -> list[Row]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[Row]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        if rows:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("sample", "development", "replay", "select", "paired"):
        cmd = sub.add_parser(name)
        cmd.add_argument("--input", type=Path, required=True)
        cmd.add_argument("--out", type=Path, required=True)
        if name == "sample":
            cmd.add_argument("--seed", type=int, default=42)
        elif name == "development":
            cmd.add_argument("--arm", default="RSI")
            cmd.add_argument("--planned", type=int, default=100)
        elif name == "select":
            cmd.add_argument("--expected", type=int, default=100)
            cmd.add_argument("--names", nargs="+", default=["S0", "S50", "S100"])
        elif name == "paired":
            cmd.add_argument("--planned", type=int, default=848)
    args = parser.parse_args()
    rows = read_jsonl(args.input)
    if args.command == "sample":
        chosen = sample_dev100(rows, args.seed)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n"
                                    for r in chosen), encoding="utf-8")
    elif args.command == "development":
        chosen = first_pass(rows, "dev", args.arm)
        write_json(args.out / "dev_summary.json", summary(chosen, args.planned))
        write_csv(args.out / "dev_curve.csv", online_curve(chosen))
    elif args.command == "replay":
        write_csv(args.out, replay_summary(rows))
    elif args.command == "select":
        write_json(args.out, select_snapshot(rows, args.expected, tuple(args.names)))
    elif args.command == "paired":
        baseline = first_pass(rows, "test", "M")
        method = first_pass(rows, "test", "RSI_selected")
        write_json(args.out, paired_summary(baseline, method, args.planned))


if __name__ == "__main__":
    main()
