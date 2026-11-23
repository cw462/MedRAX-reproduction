import csv
from pathlib import Path
from .io import read_json, write_json
from .engine import primary_arms


def report(run_dir):
    root = Path(run_dir)
    rows = [read_json(p) for p in sorted((root / "primary").glob("q*/completed.json"))]
    config = read_json(root / "run_identity.json")["config"]
    planned = config["expected_questions"]
    arms = primary_arms(config)
    table = []
    for r in rows:
        table.append({"index": r["index"]+1, "id": r["case"]["id"], "dataset": r["case"]["dataset"],
                      **{arm: r["correct"][arm] for arm in arms},
                      "rrsi_commit_used": r["commits"]["rrsi_acc"]})
    scores = {}
    for label, subset in [("overall", rows)] + [(d, [r for r in rows if r["case"]["dataset"] == d])
                                              for d in sorted({r["case"]["dataset"] for r in rows})]:
        scores[label] = {a: {"correct": sum(r["correct"][a] for r in subset), "n": len(subset),
                     "accuracy": sum(r["correct"][a] for r in subset)/len(subset) if subset else None} for a in arms}
    search = [read_json(p) for p in sorted((root / "search" / "checkpoints").glob("after_*/done.json"))]
    out = {"completed": len(rows), "planned": planned, "complete": len(rows)==planned,
           "interpretation": "full-label question-wise online feedback; not unseen-patient generalization",
           "primary_arms": list(arms), "scores": scores,
           "comparison_available": "fixed_m5" in arms,
           "rounds": sum(r.get("round") is not None for r in search),
           "accepted_rounds": sum(bool(r.get("accepted")) for r in search),
           "no_replay_in_primary_denominator": True}
    if "fixed_m5" in arms:
        out["fixed_wrong_rrsi_right"] = sum(r["correct"]["fixed_m5"]==0 and r["correct"]["rrsi_acc"]==1 for r in rows)
        out["fixed_right_rrsi_wrong"] = sum(r["correct"]["fixed_m5"]==1 and r["correct"]["rrsi_acc"]==0 for r in rows)
    (root / "report").mkdir(exist_ok=True)
    csv_name = "paired_primary.csv" if "fixed_m5" in arms else "primary.csv"
    with (root / "report" / csv_name).open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["index", "id", "dataset", *arms, "rrsi_commit_used"])
        writer.writeheader(); writer.writerows(table)
    # Runtime usage receipts include primary, replay, migration, smoke and unsuccessful work.
    receipts = [read_json(p) for p in (root / "runtime_audit").glob("*/receipt.json")]
    out["runtime_operations"] = len(receipts)
    out["runtime_tokens_logged"] = sum((r.get("usage") or {}).get("total_tokens", 0) for r in receipts)
    usage = root / "search" / "search_usage.jsonl"
    if usage.exists():
        import json
        logs = [json.loads(x) for x in usage.read_text().splitlines() if x.strip()]
        out["search_tokens_logged"] = sum((r.get("usage") or {}).get("total_tokens", 0) for r in logs)
        out["search_requests_logged"] = len(logs)
    out["usage_caveat"] = "Failed requests without usage cannot be assumed free; consult provider/gateway billing logs."
    write_json(root / "report" / "summary.json", out)
    return out
