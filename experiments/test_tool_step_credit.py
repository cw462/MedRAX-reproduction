"""Tests for tool_step_replay and tool_step_credit (V4 E). Pure logic, free."""

import unittest

import tool_step_credit as credit
import tool_step_replay as replay

ROWS = [
    {"question_id": "q1", "tool_name": "chest_xray_classifier",
     "arguments": {"image_path": "a.jpg"},
     "observation": {"execution_status": "completed", "facts": {"top_findings": []}}},
    {"question_id": "q1", "tool_name": "xray_phrase_grounding",
     "arguments": {"image_path": "a.jpg", "phrase": "effusion"},
     "observation": {"execution_status": "completed",
                     "facts": {"grounded_regions": [{"box": [0.1, 0.2, 0.4, 0.5]}]}}},
    {"question_id": "q1", "tool_name": "chest_xray_report_generator",
     "arguments": {"image_path": "a.jpg"},
     "observation": {"execution_status": "failed", "facts": {"error": "x"}}},
]


class ReplayTest(unittest.TestCase):
    def test_plan_skips_failed_target_calls(self):
        plans = replay.plan_replays({"q1": ROWS}, max_states=5)
        targets = [p["checkpoint"]["target_action"]["tool"] for p in plans]
        self.assertNotIn("chest_xray_report_generator", targets)
        self.assertIn("xray_phrase_grounding", targets)

    def test_checkpoint_records_prefix_only(self):
        cp = replay.build_checkpoint(ROWS, 1, question="Where is the effusion?",
                                     images=["a.jpg"])
        self.assertEqual(len(cp["prefix_observations"]), 1)
        self.assertEqual(cp["prefix_observations"][0]["tool"], "chest_xray_classifier")
        self.assertEqual(cp["rebuild_status"], "usable")
        self.assertEqual(cp["target_action"]["tool"], "xray_phrase_grounding")

    def test_branches_include_do_skip_and_alternative(self):
        cp = replay.build_checkpoint(ROWS, 1)
        names = {b["branch"] for b in replay.branches_for(cp, ["llava_med_qa"])}
        self.assertEqual(names, {"do_action", "skip_action", "alternate_action"})

    def test_skip_branch_declares_compensation_risk(self):
        cp = replay.build_checkpoint(ROWS, 1)
        skip = [b for b in replay.branches_for(cp, ["llava_med_qa"]) if b["branch"] == "skip_action"][0]
        self.assertIn("compensated", skip["compensation_note"])

    def test_index_outside_range_rejected(self):
        with self.assertRaises(ValueError):
            replay.build_checkpoint(ROWS, 9)


class CreditTest(unittest.TestCase):
    def test_delta_is_paired_mean_difference(self):
        delta, n = credit.delta_step([1, 0, 1], [1, 1, 0])
        self.assertEqual(n, 3)
        self.assertAlmostEqual(delta, 0.0)

    def test_no_pairs_yields_none(self):
        self.assertEqual(credit.delta_step([], []), (None, 0))

    def test_shrink_reduces_small_samples(self):
        self.assertLess(credit.shrink(1.0, 1), credit.shrink(1.0, 100))
        self.assertIsNone(credit.shrink(None, 3))

    def test_aggregate_groups_and_marks_insufficient(self):
        rows = [
            {"task_type": "localization", "capability": "visual_localization",
             "branch": "do_action", "scores": [1, 1], "cost_cny": 0.1},
            {"task_type": "localization", "capability": "visual_localization",
             "branch": "skip_action", "scores": [0, 1], "cost_cny": 0.1},
            {"task_type": "diagnosis", "capability": "report_generation",
             "branch": "do_action", "scores": [1]},
        ]
        table = credit.aggregate(rows)
        loc = [r for r in table if r["capability"] == "visual_localization"][0]
        self.assertEqual(loc["status"], "estimated")
        self.assertAlmostEqual(loc["delta_step"], 0.5)
        self.assertLess(abs(loc["delta_shrunk"]), abs(loc["delta_step"]))
        diag = [r for r in table if r["capability"] == "report_generation"][0]
        self.assertEqual(diag["status"], "insufficient_pairs")
        self.assertIsNone(diag["weight"])

    def test_unknown_capability_is_neutral(self):
        table = [{"capability": "visual_localization", "weight": 0.4}]
        self.assertEqual(credit.credit_for("report_generation", table), 0.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
