"""Offline tests for skill_branch_runner using fake tools and a fake model."""

import unittest

import skill_branch_runner as runner


CHECKPOINT = {
    "checkpoint_id": "q1#1",
    "question_id": "q1",
    "question": "Where is the effusion?",
    "images": ["a.jpg"],
    "prefix_observations": [
        {"tool": "chest_xray_classifier", "execution_status": "completed",
         "facts": {"top_findings": [{"finding": "Effusion", "score": 0.62}]}}],
    "target_action": {"tool": "xray_phrase_grounding",
                      "arguments": {"image_path": "a.jpg", "phrase": "effusion"},
                      "facts": {"grounded_regions": [{"phrase": "left"}]},
                      "execution_status": "completed"},
    "rebuild_status": "usable",
}


class FakeTools:
    def __init__(self):
        self.calls = []
        self.fail = set()

    def __call__(self, tool, arguments):
        self.calls.append((tool, dict(arguments)))
        if tool in self.fail:
            raise RuntimeError("tool exploded")
        return {"facts": {"ok": True, "tool": tool}}


class FakeModel:
    def __init__(self):
        self.seen = []

    def __call__(self, messages):
        self.seen.append(messages[0]["content"])
        return "B"


class ContinuationTest(unittest.TestCase):
    def test_do_action_executes_the_target_and_shows_it(self):
        tools, model = FakeTools(), FakeModel()
        result = runner.continue_from_checkpoint(CHECKPOINT, call_tool=tools,
                                                 ask_model=model, branch="do_action")
        self.assertEqual([c[0] for c in tools.calls], ["xray_phrase_grounding"])
        self.assertIn("NEW OBSERVATION", model.seen[0])
        self.assertEqual(result.answer, "B")
        self.assertIsNone(result.tool_error)

    def test_skip_action_executes_nothing_and_shows_nothing_new(self):
        tools, model = FakeTools(), FakeModel()
        runner.continue_from_checkpoint(CHECKPOINT, call_tool=tools,
                                        ask_model=model, branch="skip_action")
        self.assertEqual(tools.calls, [])
        self.assertNotIn("NEW OBSERVATION", model.seen[0])
        self.assertIn("chest_xray_classifier", model.seen[0])

    def test_alternate_action_uses_the_other_tool(self):
        tools, model = FakeTools(), FakeModel()
        runner.continue_from_checkpoint(CHECKPOINT, call_tool=tools, ask_model=model,
                                        branch="alternate_action",
                                        alternative_tool="llava_med_qa")
        self.assertEqual(tools.calls[0][0], "llava_med_qa")

    def test_tool_failure_is_recorded_not_hidden(self):
        tools, model = FakeTools(), FakeModel()
        tools.fail.add("xray_phrase_grounding")
        result = runner.continue_from_checkpoint(CHECKPOINT, call_tool=tools,
                                                 ask_model=model, branch="do_action")
        self.assertIn("RuntimeError", result.tool_error)
        self.assertEqual(result.stopped_reason, "answered_after_tool_error")
        self.assertNotIn("NEW OBSERVATION", model.seen[0])   # no fabricated observation

    def test_unusable_checkpoint_is_refused(self):
        bad = dict(CHECKPOINT, rebuild_status="unusable_missing_observation")
        result = runner.continue_from_checkpoint(bad, call_tool=FakeTools(),
                                                 ask_model=FakeModel(), branch="do_action")
        self.assertEqual(result.stopped_reason, "checkpoint_unusable")

    def test_budget_exhaustion_stops_before_calling(self):
        tools, model = FakeTools(), FakeModel()
        result = runner.continue_from_checkpoint(CHECKPOINT, call_tool=tools, ask_model=model,
                                                 branch="do_action", remaining_tool_calls=0)
        self.assertEqual(result.stopped_reason, "no_tool_budget")
        self.assertEqual(tools.calls, [])
        self.assertEqual(model.seen, [])

    def test_model_error_is_recorded(self):
        def boom(messages):
            raise TimeoutError("slow")
        result = runner.continue_from_checkpoint(CHECKPOINT, call_tool=FakeTools(),
                                                 ask_model=boom, branch="skip_action")
        self.assertIn("TimeoutError", result.stopped_reason)
        self.assertEqual(result.answer, "")

    def test_pair_runs_both_sides_from_one_checkpoint(self):
        tools, model = FakeTools(), FakeModel()
        pair = runner.run_replay_pair(CHECKPOINT, call_tool=tools, ask_model=model)
        self.assertEqual(pair["checkpoint_id"], "q1#1")
        self.assertEqual(pair["do_action"]["branch"], "do_action")
        self.assertEqual(pair["other"]["branch"], "skip_action")
        self.assertEqual(len(tools.calls), 1)               # only the do side ran a tool


if __name__ == "__main__":
    unittest.main(verbosity=2)
