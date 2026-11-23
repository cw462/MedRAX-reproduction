"""Protected R55 aligned metric applied to the locked terminal model response."""
import json
from pathlib import Path
import random
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent / "scorer_sources"))
from cxr_author_alignment import extract, choice
from r54_author_metrics import outcomes

METRIC_ID = "r55_original_aligned_correct"


def score(record):
    raw = record.get("terminal_raw")
    if not isinstance(raw, str):
        raise ValueError("R55 scoring requires the locked terminal_raw response")
    ordered = record["options"]
    labels = [item["label"] for item in ordered]
    if len(labels) != len(set(labels)):
        raise ValueError("duplicate option labels")
    options = {item["label"]: item["text"] for item in ordered}
    row = {"question_id": record["id"], "options": options}
    explicit = extract(raw, row["question_id"], options).answer
    adapted = {"explicit_answer": explicit,
               "choice": choice(explicit, options) if explicit is not None and options else None}
    reference = record["reference"]
    if isinstance(reference, dict):
        reference = reference["answer"]
    result = outcomes(row, adapted, reference, random.Random(0))
    return {"correct": int(result["aligned_correct"]), "metric_id": METRIC_ID}

if __name__ == "__main__":
    print(json.dumps(score(json.load(sys.stdin)), ensure_ascii=False))
