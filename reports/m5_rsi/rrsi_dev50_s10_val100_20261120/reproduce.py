"""Reproduce paired validation totals from the saved first-pass records."""
from collections import Counter, defaultdict
from pathlib import Path
import json


def main():
    root = Path(__file__).resolve().parent
    counts, groups = Counter(), defaultdict(Counter)
    for step in range(1, 101):
        records = [json.loads((root / "validation" / name / f"q{step:06d}.json").read_text(encoding="utf-8"))
                   for name in ("M5", "S10")]
        m, s = [r["completed"]["first_pass"][0] for r in records]
        if (m["step"], m["dataset"], m["qid"]) != (s["step"], s["dataset"], s["qid"]):
            raise ValueError(f"Question order differs at step {step}")
        mc, sc = m["correct"], s["correct"]
        if mc not in (0, 1) or sc not in (0, 1):
            raise ValueError(f"Invalid saved score at step {step}")
        counts.update(n=1, M5_correct=mc, S10_correct=sc,
                      corrected=int(not mc and sc), harmed=int(mc and not sc))
        groups[m["dataset"]].update(n=1, M5_correct=mc, S10_correct=sc)
    published = json.loads((root / "validation/summary.json").read_text(encoding="utf-8"))
    if (counts["M5_correct"], counts["S10_correct"]) != (published["M5_correct"], published["S10_correct"]):
        raise ValueError("Saved records and published totals differ")
    print(json.dumps({"validation":dict(counts), "by_dataset":{k:dict(v) for k,v in groups.items()}}, indent=2))


if __name__ == "__main__":
    main()
