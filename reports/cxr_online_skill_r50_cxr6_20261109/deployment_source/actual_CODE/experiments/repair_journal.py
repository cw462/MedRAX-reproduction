"""Drop journal pairs whose terminal is not a real answer, so an arm can resume.

Only infrastructure failures are dropped (`monetary_*`, `interrupted_*`): those are
the guard refusing to write, not a question the model answered. A real completion,
including one with no parsable letter (`invalid_answer`), is kept.
"""
import json
import sys
from pathlib import Path

DROP_PREFIXES = ("monetary_", "interrupted_")


def main(argv):
    path = Path(argv[1])
    if not path.exists():
        print("no journal at", path)
        return 0
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    by_q = {}
    for row in rows:
        by_q.setdefault(row["question_id"], []).append(row)
    keep, dropped = [], []
    for qid, group in by_q.items():
        terminal = next((r for r in group if r.get("record_type") == "terminal"), None)
        status = (terminal or {}).get("status") or ""
        if terminal is not None and status.startswith(DROP_PREFIXES):
            dropped.append((qid, status))
            continue
        keep.extend(group)
    if dropped:
        path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in keep) + "\n",
                        encoding="utf-8")
    starts = {r["question_id"] for r in keep if r.get("record_type") == "started"}
    terms = {r["question_id"] for r in keep if r.get("record_type") == "terminal"}
    print(f"kept {len(keep)} records, dropped {len(dropped)} bad pairs, unpaired={sorted(starts ^ terms)}")
    for qid, status in dropped:
        print("  dropped", qid, status)
    return 0 if starts == terms else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
