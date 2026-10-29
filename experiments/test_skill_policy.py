"""Minimal correctness tests for skill_policy (V4 C/D). No GPU, no API."""

import unittest

import skill_policy as sp


SKILLS = [
    {"skill_id": "S001", "task_types": ["localization"],
     "trigger": "The question asks where a finding is located but observations only give an image-level label.",
     "required_information": ["finding", "location_or_laterality"],
     "required_capabilities": ["visual_localization"],
     "actions": [{"action_id": "a1", "operation": "select_capable_tool",
                  "capability": "visual_localization"}]},
    {"skill_id": "S002", "task_types": ["characterization"],
     "trigger": "The question asks about margin or attenuation character of a mass and no report text is available.",
     "required_information": ["margin_description"],
     "required_capabilities": ["report_generation"],
     "actions": [{"action_id": "a1", "operation": "select_capable_tool",
                  "capability": "report_generation"}]},
]


class SkillIndexTest(unittest.TestCase):
    def test_retrieves_the_matching_skill_first(self):
        index = sp.SkillIndex(SKILLS)
        hits = index.search("Where is the nodule located on this radiograph?", top_k=1)
        self.assertEqual(hits[0]["skill_id"], "S001")

    def test_retrieves_characterization_skill(self):
        index = sp.SkillIndex(SKILLS)
        hits = index.search("Describe the margin of the mass.", top_k=1)
        self.assertEqual(hits[0]["skill_id"], "S002")

    def test_empty_index_returns_nothing(self):
        self.assertEqual(sp.SkillIndex([]).search("anything"), [])


class StateTest(unittest.TestCase):
    def test_gaps_are_recomputed_from_observations(self):
        state = sp.AgentState(required_information=["finding", "location_or_laterality"])
        state.observe("chest_xray_classifier", "finding", "nodule")
        state.refresh_gaps()
        self.assertEqual(state.missing_information, ["location_or_laterality"])

    def test_absent_output_is_not_a_conflict(self):
        obs = [{"tool": "a", "attribute": "location", "finding": "nodule", "value": "left"},
               {"tool": "b", "attribute": "location", "finding": "nodule", "value": None}]
        self.assertEqual(sp.detect_conflicts(obs), [])

    def test_same_finding_same_attribute_conflicts(self):
        obs = [{"tool": "a", "attribute": "location", "finding": "nodule", "value": "left"},
               {"tool": "b", "attribute": "location", "finding": "nodule", "value": "right"}]
        conflicts = sp.detect_conflicts(obs)
        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0]["finding"], "nodule")

    def test_different_attributes_do_not_conflict(self):
        obs = [{"tool": "a", "attribute": "location", "finding": "nodule", "value": "left"},
               {"tool": "b", "attribute": "margin", "finding": "nodule", "value": "spiculated"}]
        self.assertEqual(sp.detect_conflicts(obs), [])


class DecideTest(unittest.TestCase):
    def _state(self, **kw):
        state = sp.AgentState(required_information=["finding", "location_or_laterality"],
                              remaining_tool_calls=4, remaining_seconds=120.0)
        for key, value in kw.items():
            setattr(state, key, value)
        return state

    def test_budget_exhaustion_stops_with_uncertainty(self):
        state = self._state(remaining_tool_calls=0)
        operation, detail = sp.decide(state, {"visual_localization": "t1"})
        self.assertEqual(operation, "stop_with_uncertainty")
        self.assertEqual(detail["reason"], "budget_exhausted")

    def test_answer_when_information_is_satisfied(self):
        state = self._state()
        state.observe("t1", "finding", "nodule")
        state.observe("t2", "location_or_laterality", "left upper zone")
        operation, detail = sp.decide(state, {"visual_localization": "t1"})
        self.assertEqual(operation, "answer")

    def test_fills_gap_with_an_unused_tool(self):
        state = self._state()
        state.observe("chest_xray_classifier", "finding", "nodule")
        operation, detail = sp.decide(state, {"visual_localization": "xray_phrase_grounding",
                                              "report_generation": "chest_xray_report_generator"})
        self.assertEqual(operation, "call_tool")
        self.assertIn(detail["capability"], ("visual_localization", "report_generation"))

    def test_conflict_without_alternative_stops(self):
        state = self._state()
        state.observe("t1", "finding", "nodule")
        state.observe("t2", "finding", "mass")
        operation, detail = sp.decide(state, {}, )
        self.assertEqual(operation, "stop_with_uncertainty")
        self.assertIn(detail["reason"], ("conflict_unresolved", "no_available_action_adds_information"))

    def test_roi_only_when_a_box_exists(self):
        state = self._state(applicable_branch="needs_local_review")
        state.observe("chest_xray_classifier", "finding", "nodule")
        with_box, _ = sp.decide(state, {}, has_roi_box=True)
        self.assertEqual(with_box, "local_reinspection")


if __name__ == "__main__":
    unittest.main(verbosity=2)
