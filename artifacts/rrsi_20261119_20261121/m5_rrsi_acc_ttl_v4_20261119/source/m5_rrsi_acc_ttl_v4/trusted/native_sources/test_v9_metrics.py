"""Synthetic scoring oracles; no real benchmark labels, model or network."""
from copy import deepcopy
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import v9_metrics as metrics


def fixture():
    selection = {"planned_n": 8, "rows": [{"question_id": f"case{i}_q", "case_id": f"case{i}",
                                            "official_group": f"G{i % 5}"} for i in range(1, 9)]}
    initial = ["B", "A", "A", "A", "B", "B", "A", None]
    candidate = ["A", "B", "B", None, "A", "A", "B", None]
    final = ["A", "A", "A", "A", "B", "B", "B", None]
    decisions = ["accept", "retain", "gate_error", "not_called", "retain", "gate_error", "accept", "not_called"]
    p0 = [{"question_id": f"case{i}_q", "initial": initial[i-1], "status": "p0_failed" if i == 8 else "ok"}
          for i in range(1, 9)]
    rows = []
    for i in range(1, 9):
        for group in metrics.GROUPS:
            row = {"question_id": f"case{i}_q", "group": group, "initial": initial[i-1],
                   "candidate": candidate[i-1] if group == "D" else initial[i-1],
                   "final": final[i-1] if group == "D" else initial[i-1],
                   "gate": {"decision": decisions[i-1] if group == "D" else "no_change"},
                   "new_observations": [], "changed_attributes": ["MODEL_HYPOTHESIS_SENTINEL"]}
            if group == "D":
                row.update(candidate_error="timeout" if i == 4 else None,
                           gate_error="malformed_json" if i in (3, 6) else None,
                           fallback="candidate_error" if i == 4 else "gate_error" if i in (3, 6) else None)
            rows.append(row)
    labels = {f"case{i}_q": "A" for i in range(1, 9)}
    return selection, p0, rows, labels


class V9MetricsTests(unittest.TestCase):
    def test_plan_denominator_missing_harm_and_fallback_do_not_erase_errors(self):
        report = metrics.score(*fixture())
        self.assertEqual(report["planned_n"], 8)
        self.assertEqual(report["p0"]["correct"], 4)
        self.assertEqual(report["p0"]["missing"], 1)
        self.assertEqual(report["p0"]["accuracy_over_planned"], 0.5)
        group = report["groups"]["D"]
        self.assertEqual(group["raw_candidate"]["correct"], 3)
        self.assertEqual(group["candidate_paired"]["corrections"], 3)
        self.assertEqual(group["candidate_paired"]["harms"], 4)
        self.assertEqual(group["candidate_paired"]["harms_missing"], 1)
        self.assertEqual(group["candidate_paired"]["net"], -1)
        self.assertEqual(group["policies"]["evidence_gate"]["paired"]["corrections"], 1)
        self.assertEqual(group["policies"]["evidence_gate"]["paired"]["harms"], 1)
        self.assertEqual(group["policies"]["evidence_gate"]["summary"]["accuracy_over_planned"], 0.5)
        self.assertEqual(group["policies"]["always_retain"]["summary"]["correct"], 4)
        self.assertEqual(group["policies"]["always_accept"]["summary"]["correct"], 4)

    def test_gate_opportunities_exclude_missing_candidate_and_no_success_credit_for_error(self):
        report = metrics.score(*fixture())
        gate = report["groups"]["D"]["gate"]
        expected = {"correction_candidates": 3, "harmful_candidates": 3, "corrections_retained": 1,
                    "harms_prevented": 1, "false_rejected_corrections": 1, "wrong_acceptances": 1,
                    "corrections_lost_to_error": 1, "harms_saved_by_fallback": 1,
                    "candidate_errors": 1, "gate_errors": 2, "exception_fallbacks": 3}
        for key, value in expected.items():
            with self.subTest(key=key):
                self.assertEqual(gate[key], value)
        self.assertEqual(gate["correction_retention_rate"], 0.333333)
        self.assertEqual(gate["harm_prevention_rate"], 0.333333)
        untouched = report["groups"]["DK"]["gate"]
        self.assertIsNone(untouched["correction_retention_rate"])
        self.assertIsNone(untouched["harm_prevention_rate"])

    def test_common_completed_table_is_secondary_and_excludes_missing(self):
        report = metrics.score(*fixture())
        common = report["groups"]["D"]["common_completed"]
        self.assertEqual(common["n"], 6)
        self.assertEqual(common["p0"]["correct"], 3)
        self.assertEqual(common["candidate"]["correct"], 3)
        self.assertEqual(common["final"]["correct"], 3)
        self.assertEqual(report["all_groups_common_completed"]["n"], 6)

    def test_accounting_unknown_is_not_zero_and_duration_not_derived_from_calls(self):
        selection, p0, rows, labels = fixture()
        target = next(row for row in rows if row["group"] == "D")
        target["accounting"] = {"model_calls": 3, "tool_calls": 1, "input_tokens": 500,
                                "output_tokens": 100, "logical_cost_cny": "0.0081",
                                "incremental_cost_cny": "0.0081", "provider_actual_cost_cny": None,
                                "cost_basis": "usage_settlement_not_invoice"}
        target["timing"] = {"elapsed_s": 12.25, "started_utc": "2026-10-30T01:00:00Z",
                            "ended_utc": "2026-10-30T01:00:12.25Z"}
        resource = metrics.score(selection, p0, rows, labels)["groups"]["D"]["resources"]
        self.assertEqual(resource["elapsed_s"]["sum_observed"], 12.25)
        self.assertEqual(resource["elapsed_s"]["missing_n"], 7)
        self.assertEqual(resource["model_calls"]["sum_observed"], 3)
        self.assertEqual(resource["logical_cost_cny"]["sum_observed"], 0.0081)
        self.assertIsNone(resource["provider_actual_cost_cny"]["sum_observed"])
        self.assertIsNone(resource["total_tokens"]["sum_observed"])
        self.assertEqual(resource["cost_bases"], ["usage_settlement_not_invoice"])

    def test_tool_return_not_automatically_new_information(self):
        selection, p0, rows, labels = fixture()
        rows[0]["new_observations"] = [{"id": "one", "tool": "report"},
                                        {"id": "two", "is_new_usable": False},
                                        {"id": "three", "is_new_usable": True}]
        obs = metrics.score(selection, p0, rows, labels)["groups"]["D"]["observations"]
        self.assertEqual(obs["collected_observations"], 3)
        self.assertEqual(obs["explicit_new_usable"], 1)
        self.assertEqual(obs["explicit_not_new_usable"], 1)
        self.assertEqual(obs["unadjudicated"], 1)

    def test_uncertainty_and_p0_failure_are_not_exception_fallback_successes(self):
        selection, p0, rows, labels = fixture()
        target = next(row for row in rows if row["group"] == "DK" and row["question_id"] == "case1_q")
        target.update(candidate=None, final="B", fallback="candidate_uncertain", candidate_error=None)
        skipped = next(row for row in rows if row["group"] == "DK" and row["question_id"] == "case8_q")
        skipped.update(candidate_error="p0_failed", fallback="p0_failed", status="skipped_p0_failed")
        gate = metrics.score(selection, p0, rows, labels)["groups"]["DK"]["gate"]
        self.assertEqual(gate["exception_fallbacks"], 0)
        self.assertEqual(gate["candidate_errors"], 0)
        self.assertEqual(gate["uncertain_candidates"], 1)
        self.assertEqual(gate["skipped_p0_failures"], 1)

    def test_runner_evidence_refs_and_context_token_estimates_preserved(self):
        selection, p0, rows, labels = fixture()
        rows[0]["new_observations"] = [{"evidence_ref": "D:tool:1", "is_new_usable": None}]
        rows[0]["memory_tokens"] = {"k_token_estimate": 100, "e_token_estimate": 0, "token_count_method": "chars_4"}
        report = metrics.score(selection, p0, rows, labels)
        event = next(event for event in report["case_events"] if event["question_id"] == "case1_q" and event["group"] == "D")
        self.assertEqual(event["new_observation_refs"], ["D:tool:1"])
        mem = report["groups"]["D"]["resources"]["memory_context_token_estimates"]
        self.assertEqual(mem["knowledge"]["sum_observed"], 100)
        self.assertEqual(mem["experience"]["sum_observed"], 0)
        self.assertEqual(mem["methods"], ["chars_4"])

    def test_duplicate_unplanned_unknown_group_and_different_p0_rejected(self):
        selection, p0, rows, labels = fixture()
        for bad in [rows+[rows[0]], rows+[dict(rows[0], question_id="outside")],
                    [dict(rows[0], group="merged_E")]+rows[1:],
                    [dict(rows[0], initial="C")]+rows[1:]]:
            with self.subTest(bad=bad[0]), self.assertRaises(ValueError):
                metrics.score(selection, p0, bad, labels)
        with self.assertRaises(ValueError):
            metrics.score(selection, p0+[p0[0]], rows, labels)

    def test_third_answer_and_fabricated_p0_recovery_rejected(self):
        selection, p0, rows, labels = fixture()
        with self.assertRaisesRegex(ValueError, "third answer"):
            metrics.score(selection, p0, [dict(rows[0], final="C")]+rows[1:], labels)
        bad = deepcopy(rows)
        bad[-1]["final"] = "A"
        with self.assertRaisesRegex(ValueError, "fabricated final"):
            metrics.score(selection, p0, bad, labels)

    def test_partial_requires_explicit_flag_and_unrun_groups_marked(self):
        selection, p0, rows, labels = fixture()
        with self.assertRaisesRegex(ValueError, "incomplete terminals"):
            metrics.score(selection, p0, rows[:1], labels)
        report = metrics.score(selection, p0, rows[:1], labels, allow_partial=True)
        self.assertEqual(report["run_status"], "incomplete_provisional")
        self.assertEqual(report["groups"]["DK"]["status"], "未运行")
        self.assertIn("DK (未运行)", metrics._markdown(report))
        self.assertEqual(report["groups"]["D"]["raw_candidate"]["planned_n"], 8)

    def test_case_review_has_all_harms_and_corrections_and_explicit_hypothesis_label(self):
        report = metrics.score(*fixture())
        events = {(event["question_id"], event["group"]): event for event in report["case_events"]}
        self.assertEqual(set(events), {(f"case{i}_q", "D") for i in range(1, 8)})
        self.assertIn("candidate_harm_missing", events[("case4_q", "D")]["events"])
        text = metrics._review(report)
        self.assertIn("hypotheses until checked", text)
        self.assertIn("MODEL_HYPOTHESIS_SENTINEL", text)

    def test_report_generation_keeps_inference_files_unchanged_and_writes_three_artifacts(self):
        selection, p0, rows, labels = fixture()
        with TemporaryDirectory() as folder:
            run = Path(folder)
            (run / "selection.json").write_text(json.dumps(selection), encoding="utf-8")
            for name, data in (("p0_results.jsonl", p0), ("candidate_results.jsonl", rows),
                               ("isolated_labels.jsonl", [{"question_id": qid, "answer": answer} for qid, answer in labels.items()])):
                (run / name).write_text("\n".join(json.dumps(row) for row in data)+"\n", encoding="utf-8")
            before = {name: (run / name).read_bytes() for name in ("p0_results.jsonl", "candidate_results.jsonl", "selection.json")}
            report = metrics.generate_report(run, run / "isolated_labels.jsonl")
            self.assertEqual(report["run_status"], "completed")
            for name, content in before.items():
                self.assertEqual((run / name).read_bytes(), content)
            for name in ("paired_metrics.json", "paired_metrics.md", "case_review.md"):
                self.assertTrue((run / name).is_file())
                self.assertFalse((run / (name+".tmp")).exists())

    def test_incomplete_generation_rejected_before_labels_opened(self):
        selection, p0, rows, labels = fixture()
        with TemporaryDirectory() as folder:
            run = Path(folder)
            (run / "selection.json").write_text(json.dumps(selection), encoding="utf-8")
            with patch.object(metrics, "_labels", side_effect=AssertionError("must not open labels")):
                with self.assertRaisesRegex(ValueError, "labels have not been opened"):
                    metrics.generate_report(run, run / "nonexistent_labels.jsonl")


if __name__ == "__main__":
    unittest.main()
