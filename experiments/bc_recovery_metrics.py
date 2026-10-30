"""V7 metrics: corrections, harms, retention and prevention for P1/PB/PC and GB/GC.

Reads `runs/v7_recovery/round1.jsonl` plus the frozen labels and reports, on all 60
planned questions as the denominator:

  corrections = P0 wrong and the variant right
  harms       = P0 right and the variant wrong
  net         = corrections - harms
  retention   = of the branch's corrections, the share the gate still gets right
  prevention  = of the branch's harms, the share the gate keeps at P0's correct answer

A gate that only blocks harms is not a result: retention has to be reported next to it.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path


def read_jsonl(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines()
            if line.strip()]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run", type=Path, required=True)
    ap.add_argument("--labels", type=Path, required=True)
    ap.add_argument("--types", type=Path, help="metadata.jsonl.new for the type split")
    ap.add_argument("--json-out", type=Path)
    ap.add_argument("--md-out", type=Path)
    args = ap.parse_args(argv)

    labels = {str(r["question_id"]): str(r["answer"]).strip().upper()
              for r in read_jsonl(args.labels)}
    records = {r["question_id"]: r for r in read_jsonl(args.run)}

    types = {}
    if args.types and args.types.exists():
        for row in read_jsonl(args.types):
            qid = str(row.get("full_question_id") or row.get("question_id"))
            parts = qid.split("_")
            if len(parts) == 3:
                qid = parts[0] + "_" + parts[2]
            cat = row.get("categories") or row.get("type")
            if isinstance(cat, list) and cat:
                cat = cat[0]
            if isinstance(cat, str):
                types[qid] = cat

    variants = ["P0", "P1", "PB", "PC", "GB", "GC"]
    counts = {v: {"correct": 0, "wrong": 0, "missing": 0} for v in variants}
    skipped = []
    pairs = defaultdict(Counter)

    for qid, rec in records.items():
        label = labels.get(qid)
        if label is None or rec.get("status") != "ok":
            skipped.append(qid)
            continue
        letters = rec.get("letters") or {}
        p0 = letters.get("P0")
        for v in variants:
            letter = letters.get(v) if v != "P0" else p0
            if letter is None:
                counts[v]["missing"] += 1
            elif letter == label:
                counts[v]["correct"] += 1
            else:
                counts[v]["wrong"] += 1
        for name in ("P1", "PB", "PC", "GB", "GC"):
            letter = letters.get(name)
            if letter is None or p0 is None:
                continue
            # relative to P0
            if p0 != label and letter == label:
                pairs[name]["corrected"] += 1
            elif p0 == label and letter != label:
                pairs[name]["harmed"] += 1
            elif p0 == label and letter == label:
                pairs[name]["kept_correct"] += 1
            elif p0 != label and letter != label:
                pairs[name]["still_wrong"] += 1

    # gates: retention/prevention relative to their branch
    gate_stats = {}
    for gate, branch in (("GB", "PB"), ("GC", "PC")):
        corrected = harmed = kept = saved = 0
        for qid, rec in records.items():
            label = labels.get(qid)
            if label is None or rec.get("status") != "ok":
                continue
            letters = rec.get("letters") or {}
            p0, cand, final = letters.get("P0"), letters.get(branch), letters.get(gate)
            if None in (p0, cand, final):
                continue
            if p0 != label and cand == label:
                corrected += 1
                kept += final == label
            if p0 == label and cand != label:
                harmed += 1
                saved += final == label
        gate_stats[gate] = {
            "branch_corrections": corrected,
            "retained": kept,
            "retention": round(kept / corrected, 3) if corrected else None,
            "branch_harms": harmed,
            "prevented": saved,
            "prevention": round(saved / harmed, 3) if harmed else None,
        }

    total = len(records)
    rows = []
    for v in variants:
        c = counts[v]
        graded = c["correct"] + c["wrong"]
        rows.append({"variant": v, "correct": c["correct"], "wrong": c["wrong"],
                     "missing": c["missing"],
                     "accuracy": round(c["correct"] / graded, 4) if graded else None,
                     "over_planned": round(c["correct"] / total, 4) if total else None})

    changed = {}
    for name in ("P1", "PB", "PC"):
        n = changed_count = 0
        for rec in records.values():
            letters = rec.get("letters") or {}
            if rec.get("status") != "ok" or not letters.get(name) or not letters.get("P0"):
                continue
            n += 1
            changed_count += letters[name] != letters["P0"]
        changed[name] = {"n": n, "changed": changed_count,
                         "rate": round(changed_count / n, 3) if n else None}

    payload = {"questions_in_file": total, "scored": total - len(skipped),
               "skipped": skipped, "variants": rows, "paired_vs_p0": {k: dict(v) for k, v in pairs.items()},
               "gates": gate_stats, "change_rate": changed}

    lines = ["# V7 recovery: round 1 metrics", ""]
    lines.append(f"Questions in file: {total}; scored: {total - len(skipped)}. "
                 "Denominator is every planned question, failures count as not correct.")
    lines.append("")
    lines.append("## Accuracy by variant")
    lines.append("")
    lines.append("| variant | correct | wrong | missing | accuracy |")
    lines.append("|---|---:|---:|---:|---:|")
    for row in rows:
        lines.append(f"| {row['variant']} | {row['correct']} | {row['wrong']} | {row['missing']} | "
                     f"{row['accuracy']} |")
    lines.append("")
    lines.append("## Paired against P0")
    lines.append("")
    lines.append("| variant | corrected | harmed | net | kept correct | still wrong |")
    lines.append("|---|---:|---:|---:|---:|---:|")
    for name in ("P1", "PB", "PC", "GB", "GC"):
        p = pairs.get(name, {})
        corr, harm = p.get("corrected", 0), p.get("harmed", 0)
        lines.append(f"| {name} | {corr} | {harm} | {corr - harm:+d} | {p.get('kept_correct', 0)} | "
                     f"{p.get('still_wrong', 0)} |")
    lines.append("")
    lines.append("## Gate effectiveness (GB on PB, GC on PC)")
    lines.append("")
    lines.append("| gate | branch corrections | retained | retention | branch harms | prevented | prevention |")
    lines.append("|---|---:|---:|---|---:|---:|---|")
    for gate, s in gate_stats.items():
        lines.append(f"| {gate} | {s['branch_corrections']} | {s['retained']} | {s['retention']} | "
                     f"{s['branch_harms']} | {s['prevented']} | {s['prevention']} |")
    lines.append("")
    lines.append("## How often a branch changed the letter")
    lines.append("")
    lines.append("| branch | n | changed | rate |")
    lines.append("|---|---:|---:|---:|")
    for name, s in changed.items():
        lines.append(f"| {name} | {s['n']} | {s['changed']} | {s['rate']} |")
    lines.append("")
    text = "\n".join(lines) + "\n"
    print(text)
    if args.json_out:
        args.json_out.write_text(json.dumps(payload, ensure_ascii=False, indent=1) + "\n",
                                 encoding="utf-8")
    if args.md_out:
        args.md_out.write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
