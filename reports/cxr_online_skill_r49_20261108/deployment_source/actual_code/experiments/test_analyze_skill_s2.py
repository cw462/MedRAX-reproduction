"""Offline test for analyze_skill_s2: synthetic runs, known answers."""
import json
from pathlib import Path

import analyze_skill_s2 as a

root = Path(__file__).with_name("_s2test")
for arm in ("A", "B", "C"):
    for rnd in (1, 2):
        run = root / f"v4_{arm}_r{rnd}"
        scored = root / f"v4_{arm}_r{rnd}_scored"
        run.mkdir(parents=True, exist_ok=True)
        scored.mkdir(parents=True, exist_ok=True)
        detail = []
        for q in range(8):
            # B beats A on 3 questions, C beats B on 1; the rest are stable
            base = {0: True, 1: True, 2: False, 3: False, 4: True, 5: False, 6: False, 7: True}
            correct = dict(base)
            if arm == "B" and q in (2, 3, 5):
                correct[q] = True
            if arm == "C" and q == 5:
                correct[q] = False
            detail.append({"question_id": f"{10000 + q}_8353", "status": "completed",
                           "letter": "A", "reference": "A",
                           "task_outcome": "correct" if correct[q] else "incorrect",
                           "model_calls": 3, "tool_calls": 2})
        (scored / "score.json").write_text(json.dumps({
            "graded_denominator": 8,
            "accuracy_among_graded": sum(d["task_outcome"] == "correct" for d in detail) / 8,
            "outcome_counts": {},
            "wilson_95ci_among_graded": [0.2, 0.8],
            "detail": detail}, ensure_ascii=False), encoding="utf-8")

meta = root / "metadata.jsonl"
meta.write_text("\n".join(json.dumps({"full_question_id": f"{10000 + q}_{10000 + q}_8353",
                                      "categories": "classification, reasoning" if q < 4
                                      else "detection, reasoning"}) for q in range(8)) + "\n",
               encoding="utf-8")

report = {}
rc = a.main(["--runs", str(root), "--metadata", str(meta),
             "--rounds", "1", "2", "--json-out", str(root / "report.json")])
assert rc == 0
data = json.loads((root / "report.json").read_text(encoding="utf-8"))
print("runs:", sorted(data["runs"]))
print("pooled A/B/C:", [data["pooled"][k]["mean_of_question_means"] for k in "ABC"])
print("A->B:", data["paired"]["A->B"])
print("B->C:", data["paired"]["B->C"])
assert data["pooled"]["A"]["mean_of_question_means"] == 0.5      # 4 of 8
assert data["pooled"]["B"]["mean_of_question_means"] == 0.875    # 7 of 8
assert data["pooled"]["C"]["mean_of_question_means"] == 0.5      # base, q5 stays wrong
assert data["paired"]["A->B"]["mean_diff"] == 0.375
assert data["paired"]["B->C"]["mean_diff"] == -0.375
assert set(data["by_type"]) == {"classification, reasoning", "detection, reasoning"}
print("OK: synthetic labels, pooling, pairing and type split all match")

