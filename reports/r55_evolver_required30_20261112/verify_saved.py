"""Check the saved answer outcomes and required-search receipts offline."""
import json
from pathlib import Path
root = Path(__file__).resolve().parent
def read(name):
    return json.loads((root / name).read_text(encoding="utf-8"))
rows, cases, summary = read("per_question.json"), read("case_details.json"), read("summary.json")
assert len(rows) == len(cases) == summary["questions"] == 30
assert [row["ordinal"] for row in rows] == list(range(1, 31))
assert len({row["question_id"] for row in rows}) == 30
for row, case in zip(rows, cases, strict=True):
    assert row["question_id"] == case["question"]["question_id"]
    assert row["required_pre_answer_search"] == case["steps"][0]["pre_answer_experience_search"]
assert sum(row["E_correct"] for row in rows) == summary["correct"] == 18
assert sum(row["D_online_correct"] for row in rows) == 21
assert sum(row["required_pre_answer_search"]["status"] == "empty_bank" for row in rows) == 30
assert sum(bool(row["required_pre_answer_search"]["results"]) for row in rows) == 0
print("30 cases, E 18/30, D 21/30, 30 empty-bank checks, 0 deliveries")
