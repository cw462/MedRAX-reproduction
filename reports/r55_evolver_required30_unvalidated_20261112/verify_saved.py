"""Check saved results, pairings and receipt counts offline."""
import json
from pathlib import Path

root = Path(__file__).resolve().parent
def read(name):
    return json.loads((root / name).read_text(encoding="utf-8"))

rows, cases, summary = read("per_question.json"), read("case_details.json"), read("summary.json")
experience = read("experience_receipts.json")
assert len(rows) == len(cases) == summary["questions"] == 30
assert [row["ordinal"] for row in rows] == list(range(1, 31))
for row, case in zip(rows, cases, strict=True):
    assert row["question_id"] == case["question"]["question_id"]
    assert row["required_pre_answer_search"] == case["steps"][0]["pre_answer_experience_search"]
assert [sum(row[key] for row in rows) for key in ("D_online_correct", "previous_E_correct", "E_correct")] == [21, 18, 22]
assert sum(row["required_pre_answer_search"]["status"] == "empty_bank" for row in rows) == 10
assert sum(bool(row["required_pre_answer_search"]["results"]) for row in rows) == 20
assert all(len(row["required_pre_answer_search"]["results"]) == 3 for row in rows[10:])
assert len(experience["cards"]) == len(experience["writer"]) == 29
assert [window["skills_after"] for window in experience["windows"]] == [9, 19, 29]
print("D 21/30, previous E 18/30, new E 22/30, experience delivered to 20/30, 29 cards")
