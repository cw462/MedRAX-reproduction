"""Counterfactual memory credit (R4) from paired replays.

Reads one reference memory arm plus one scored ablation run per dropped retrieval
rank, and attributes the change in final-answer correctness to the removed
memory. This is the "paired replay adapter" that memory_core/schema.py requires
before any non-null step credit may exist: it produces evidence from actual
paired executions instead of inventing a score from structural metadata.

No API calls, no GPU: it only reads frozen run artefacts, so it can be run
before spending anything.

Usage:
  python experiments/memory_credit.py \
      --reference runs/val29_full_r3 \
      --ablation runs/credit_r3_drop1 --ablation runs/credit_r3_drop2 \
      --ablation runs/credit_r3_drop3 \
      --report runs/memory_credit_r3.json

Each run directory must contain results.jsonl + manifest.json, and a sibling
"<run>_scored/outcomes.json" produced by experiments/score_memory_runs.py.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path


def read_jsonl(path):
    with Path(path).open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def load_outcomes(run_dir):
    """question_id -> task_outcome, from the independent scorer sidecar."""
    scored = run_dir.parent / (run_dir.name + "_scored") / "outcomes.json"
    if not scored.exists():
        raise SystemExit(f"missing scored outcomes: {scored}")
    payload = json.loads(scored.read_text(encoding="utf-8"))
    table = {}
    for row in payload["outcomes"]:
        if row.get("arm", "agent") == "agent":
            table[row["question_id"]] = row["task_outcome"]
    return table, payload


def load_manifest(run_dir):
    path = Path(run_dir) / "manifest.json"
    if not path.exists():
        raise SystemExit(f"missing manifest: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def load_retrieval(run_dir):
    """question_id -> retrieval record (carries drop_rank / dropped_memory_id)."""
    path = Path(run_dir) / "retrieval.jsonl"
    if not path.exists():
        raise SystemExit(f"missing retrieval log: {path}")
    table = {}
    for row in read_jsonl(path):
        qid = row["question_id"]
        # keep the last record for a question (a resumed run may log it twice)
        table[qid] = row
    return table


def classify(reference_outcome, ablated_outcome):
    """Attribute the effect of the removed memory on answer correctness."""
    bad = {"error", "invalid", "unknown", None}
    if reference_outcome in bad or ablated_outcome in bad:
        return "unresolved"
    if reference_outcome == "correct" and ablated_outcome != "correct":
        return "supporting"
    if reference_outcome != "correct" and ablated_outcome == "correct":
        return "harmful"
    return "inert"


def mcnemar_exact(b, c):
    """Two-sided exact McNemar on discordant pairs (b, c)."""
    n = b + c
    if n == 0:
        return 1.0
    tail = sum(_comb(n, i) for i in range(0, min(b, c) + 1)) / (2 ** n)
    return min(1.0, 2 * tail)


def _comb(n, k):
    from math import comb
    return comb(n, k)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--ablation", type=Path, action="append", required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args(argv)

    ref_dir = args.reference.resolve()
    ref_out, ref_payload = load_outcomes(ref_dir)
    ref_manifest = load_manifest(ref_dir)
    ref_retrieval = load_retrieval(ref_dir)
    ref_pool = (ref_manifest.get("plan", {}).get("memory") or {}).get("pool_sha256")

    if (ref_manifest.get("plan", {}).get("memory") or {}).get("drop_memory_rank"):
        raise SystemExit("the reference run must not itself be an ablation")

    per_memory = defaultdict(Counter)
    by_rank = {}
    pairwise = {}

    for abl_dir in (p.resolve() for p in args.ablation):
        abl_manifest = load_manifest(abl_dir)
        memory_cfg = abl_manifest.get("plan", {}).get("memory") or {}
        rank = memory_cfg.get("drop_memory_rank") or 0
        if not rank:
            raise SystemExit(f"{abl_dir.name}: ablation run recorded no dropped rank")
        if memory_cfg.get("pool_sha256") != ref_pool:
            raise SystemExit(f"{abl_dir.name}: pool digest differs from the reference run")
        abl_out, _ = load_outcomes(abl_dir)
        abl_retrieval = load_retrieval(abl_dir)

        shared = sorted(set(ref_out) & set(abl_out))
        if not shared:
            raise SystemExit(f"{abl_dir.name}: no shared questions with the reference")
        missing = sorted(set(ref_out) - set(abl_out))
        if missing:
            print(f"warning: {abl_dir.name} is missing {len(missing)} reference questions",
                  file=sys.stderr)

        effects = Counter()
        dropped_here = 0
        for qid in shared:
            record = abl_retrieval.get(qid) or {}
            dropped_id = record.get("dropped_memory_id")
            if not dropped_id:
                # nothing was removed for this question (fewer hits than the rank)
                continue
            dropped_here += 1
            effect = classify(ref_out[qid], abl_out[qid])
            effects[effect] += 1
            per_memory[dropped_id][effect] += 1
            per_memory[dropped_id]["_seen"] += 1

        ref_correct = sum(1 for q in shared if ref_out[q] == "correct")
        abl_correct = sum(1 for q in shared if abl_out[q] == "correct")
        b = sum(1 for q in shared if ref_out[q] == "correct" and abl_out[q] != "correct")
        c = sum(1 for q in shared if ref_out[q] != "correct" and abl_out[q] == "correct")
        by_rank[str(rank)] = {
            "run": abl_dir.name,
            "shared_questions": len(shared),
            "questions_with_a_drop": dropped_here,
            "reference_correct": ref_correct,
            "ablated_correct": abl_correct,
            "accuracy_delta": round((abl_correct - ref_correct) / len(shared), 4),
            "discordant_reference_only": b,
            "discordant_ablated_only": c,
            "mcnemar_exact_p": round(mcnemar_exact(b, c), 4),
            "effects": dict(effects),
        }
        pairwise[abl_dir.name] = len(shared)

    credits = []
    for memory_id, counts in per_memory.items():
        resolved = counts["supporting"] + counts["harmful"] + counts["inert"]
        if resolved == 0:
            continue
        credits.append({
            "memory_id": memory_id,
            "times_dropped": counts["_seen"],
            "supporting": counts["supporting"],
            "harmful": counts["harmful"],
            "inert": counts["inert"],
            "unresolved": counts["unresolved"],
            "net_credit": counts["supporting"] - counts["harmful"],
            "credit_rate": round((counts["supporting"] - counts["harmful"]) / resolved, 4),
        })
    credits.sort(key=lambda row: (-row["net_credit"], -row["times_dropped"], row["memory_id"]))

    totals = Counter()
    for row in credits:
        for key in ("supporting", "harmful", "inert", "unresolved"):
            totals[key] += row[key]

    report = {
        "schema_version": 1,
        "kind": "counterfactual_memory_credit_v1",
        "reference_run": ref_dir.name,
        "reference_pool_sha256": ref_pool,
        "reference_outcomes_sha256": ref_payload.get("source_results_sha256"),
        "runs_compared": pairwise,
        "by_rank": by_rank,
        "totals": dict(totals),
        "memories": credits,
        "limitations": [
            "Single seed; each memory is dropped once per question, so one flip is weak evidence.",
            "A drop can change the rendered block length and therefore the prompt globally; the "
            "comparison isolates the retrieved set, not a token-level effect.",
            "task_outcome comes from the frozen label sidecar; it is not clinical validation.",
            "Memories retrieved for few questions cannot be adjudicated individually.",
        ],
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=1) + "\n",
                           encoding="utf-8")

    print(f"reference {ref_dir.name}: {len(ref_out)} questions")
    for rank, row in sorted(by_rank.items(), key=lambda kv: int(kv[0])):
        print(f"  drop rank {rank}: {row['questions_with_a_drop']} drops, "
              f"acc {row['reference_correct']}->{row['ablated_correct']} "
              f"(delta {row['accuracy_delta']:+.4f}), "
              f"p={row['mcnemar_exact_p']}, effects={row['effects']}")
    print(f"memories with evidence: {len(credits)} | totals {dict(totals)}")
    for row in credits[:10]:
        print(f"  {row['memory_id'][:12]} seen={row['times_dropped']} "
              f"+{row['supporting']}/-{row['harmful']}/={row['inert']} rate={row['credit_rate']}")
    print(f"report -> {args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
