"""V9 contracts exercised with synthetic data and an in-memory fake model only."""
import copy
import io
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_v9_diagnostic as controller


def attribute(**changes):
    result = {"attribute": "pleural line", "object": "lung", "side": "left", "location": "apex",
              "timepoint": "unresolved", "image_ids": ["image:1"], "status": "unresolved", "evidence_refs": []}
    result.update(changes)
    return result


def candidate(**changes):
    result = {"answer": "B", "uncertain": False, "changed_attributes": ["pleural line"],
              "evidence_refs": ["image:1"], "observations": [attribute(status="observed_present",
              evidence_refs=["image:1"], value="visible linear boundary")]}
    result.update(changes)
    return result


def gate(**changes):
    result = {"decision": "accept", "changed_attributes": ["pleural line"], "evidence_refs": ["image:1"],
              "unmet_requirements": [], "reason": "The referenced original image shows the stated boundary."}
    result.update(changes)
    return result


class ParsingTests(unittest.TestCase):
    def test_options_support_dot_parenthesis_and_continuation(self):
        self.assertEqual(controller.options_of("Question?\nA. first option\ncontinuation\nB) second option"),
                         {"A": "first option continuation", "B": "second option"})
        for bad in ("No options", "A) only one", "A) first\nA. duplicate", "A)\nB) second"):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                controller.options_of(bad)

    def test_strict_json_rejects_duplicate_keys_and_nonfinite_nested_numbers(self):
        for bad in ('{"decision":"retain","decision":"accept"}', '{"outer":{"a":1,"a":2}}',
                    '{"x":NaN}', '{"x":Infinity}', '{"x":-Infinity}', 'Explanation {"a":1}', '[]'):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                controller.strict_json(bad)
        self.assertEqual(controller.strict_json('```json\n{"a":1}\n```'), {"a": 1})

    def test_gate_decision_is_json_field_not_accept_word_in_reason(self):
        obj = gate(decision="retain", evidence_refs=[], reason="Do not accept the candidate: evidence remains unresolved.")
        self.assertEqual(controller.parse_gate(json.dumps(obj), {"image:1"})["decision"], "retain")
        for bad in [gate(decision="ACCEPT"), gate(evidence_refs=[]), gate(evidence_refs=["invented:tool:1"]),
                    gate(unmet_requirements=["unknown side"]), gate(reason=""), gate(changed_attributes=[{}]),
                    dict(gate(), extra="unexpected")]:
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                controller.parse_gate(json.dumps(bad), {"image:1"})

    def test_candidate_allows_uncertain_without_observations_and_requires_consistency(self):
        obj = candidate(answer=None, uncertain=True, changed_attributes=[], evidence_refs=[], observations=[])
        answer, payload = controller.parse_candidate(json.dumps(obj), {"A": "x", "B": "y"}, {"image:1"})
        self.assertIsNone(answer)
        self.assertTrue(payload["uncertain"])
        for bad in [candidate(answer=None, uncertain=False), candidate(answer="B", uncertain=True),
                    candidate(answer="C"), candidate(changed_attributes=[{}]), candidate(evidence_refs=[]),
                    candidate(observations=[]), {"answer": "B"}]:
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                controller.parse_candidate(json.dumps(bad), {"A": "x", "B": "y"}, {"image:1"})

    def test_candidate_observations_need_typed_current_image_binding_and_evidence(self):
        valid = candidate()
        self.assertEqual(controller.parse_candidate(json.dumps(valid), {"A": "x", "B": "y"}, {"image:1"})[0], "B")
        for change in ({"status": "normal"}, {"side": None}, {"object": ""}, {"timepoint": 1},
                       {"image_ids": []}, {"image_ids": ["image:2"]}, {"image_ids": [{}]},
                       {"evidence_refs": []}, {"evidence_refs": ["hallucinated"]}):
            bad = candidate(observations=[attribute(status="observed_present", evidence_refs=["image:1"],
                                                    value="present", **change)]) if "status" not in change and "evidence_refs" not in change else None
            if bad is None:
                obs = attribute(status="observed_present", evidence_refs=["image:1"], value="present")
                obs.update(change)
                bad = candidate(observations=[obs])
            with self.subTest(change=change), self.assertRaises(ValueError):
                controller.parse_candidate(json.dumps(bad), {"A": "x", "B": "y"}, {"image:1"})

    def test_plan_separates_unknown_absence_and_rejects_unreferenced_observation(self):
        obj = {"attributes": [attribute()], "evidence_gaps": ["Inspect the left apex"]}
        self.assertEqual(controller.parse_plan(json.dumps(obj), ["image:1"], {"image:1"}), obj)
        for changes in ({"status": "absent"}, {"status": "observed_absent", "evidence_refs": []},
                        {"image_ids": ["image:2"]}, {"evidence_refs": ["missing"]}):
            bad = {"attributes": [attribute(**changes)], "evidence_gaps": []}
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                controller.parse_plan(json.dumps(bad), ["image:1"], {"image:1"})

    def test_fallback_matrix_preserves_p0_and_never_fabricates_answer(self):
        cases = [(None, "B", {"decision": "accept"}, None, None, (None, "p0_failed")),
                 ("A", None, None, "timeout", None, ("A", "candidate_error")),
                 ("A", None, None, None, None, ("A", "candidate_uncertain")),
                 ("A", "B", None, None, "invalid_json", ("A", "gate_error")),
                 ("A", "B", {"decision": "retain"}, None, None, ("A", None)),
                 ("A", "B", {"decision": "accept"}, None, None, ("B", None)),
                 ("A", "A", {"decision": "not_called"}, None, None, ("A", None))]
        for initial, alternative, decision, cerror, gerror, expected in cases:
            with self.subTest(initial=initial, alternative=alternative, decision=decision):
                self.assertEqual(controller.final_choice(initial, alternative, decision, cerror, gerror), expected)

    def test_fixed_twenty_selection_invariant_to_input_order_and_without_mutation(self):
        rows = [{"question_id": f"{group}_{number:02d}", "question": "A) x\nB) y", "images": ["x.png"]}
                for group in range(5) for number in range(12)]
        mapping = {row["question_id"]: "group_"+row["question_id"].split("_", 1)[0] for row in rows}
        before = copy.deepcopy(rows)
        first = controller.fixed_selection(rows, mapping, 20261030)
        reverse = controller.fixed_selection(list(reversed(rows)), mapping, 20261030)
        self.assertEqual(first, reverse)
        self.assertEqual(rows, before)
        self.assertEqual(first["planned_n"], 20)
        self.assertEqual(len({row["question_id"] for row in first["rows"]}), 20)
        for group in sorted(set(mapping.values())):
            chosen = [row["question_id"] for row in first["rows"] if row["official_group"] == group]
            self.assertEqual(len(chosen), 4)
            self.assertEqual(chosen, sorted(chosen))
        with self.assertRaises(ValueError):
            controller.fixed_selection(rows, {}, 20261030)
        with self.assertRaises(ValueError):
            controller.fixed_selection(rows[:12], mapping, 20261030)


class ProjectionAndBranchTests(unittest.TestCase):
    @staticmethod
    def dependencies(queue, calls):
        from langchain_core.messages import AIMessage
        class FakeModel:
            def bind_tools(self, tools):
                return self
            def invoke(self, messages):
                calls.append(copy.deepcopy(messages))
                value = queue.pop(0)
                if isinstance(value, BaseException):
                    raise value
                return AIMessage(content=json.dumps(value) if isinstance(value, dict) else value)
        class FakeBudgeted:
            def __init__(self, wrapped, ledger, ctx, profile):
                self.wrapped, self.ctx = wrapped, ctx
            def invoke(self, messages):
                self.ctx['actual_model_calls'] += 1
                self.ctx['usage_records'].append({'input_tokens': 10, 'output_tokens': 5, 'total_tokens': 15})
                return self.wrapped.invoke(messages)
        def new_ctx(*args, **kwargs):
            return {'actual_model_calls': 0, 'actual_tool_attempts': 0, 'usage_records': [],
                    'ledger_settlements': [], 'issues': set(), 'allowed_images': set(args[2]),
                    'stop_run': False}
        modules = {'memory_agent_eval': SimpleNamespace(BudgetedModel=FakeBudgeted, TrackedTool=object),
                   'run_bc_recovery': SimpleNamespace(new_ctx=new_ctx)}
        return FakeModel(), modules

    def test_projection_includes_real_pixels_and_raw_returns_without_p0_assistant(self):
        with TemporaryDirectory() as folder:
            image = Path(folder) / 'image.png'
            image.write_bytes(b'CURRENT_CASE_IMAGE_BYTES')
            row = {'question_id': 'q1', 'question': 'CURRENT_QUESTION\nA) x\nB) y', 'images': ['image.png']}
            evidence = [{'evidence_ref': 'p0:tool:1', 'result': {'finding': 'RAW_CURRENT_OBSERVATION'}}]
            messages, images = controller.projection(row, [image], evidence)
            serialized = json.dumps([message.content for message in messages])
            self.assertIn('RAW_CURRENT_OBSERVATION', serialized)
            self.assertIn('data:image/png;base64,', serialized)
            self.assertIn('CURRENT_QUESTION', serialized)
            self.assertNotIn('P0_FINAL_ANSWER_SENTINEL', serialized)
            self.assertEqual(images[0]['image_id'], 'image:1')
            self.assertEqual(evidence[0]['result']['finding'], 'RAW_CURRENT_OBSERVATION')

    def run_fake_branch(self, final, decision=None):
        plan = {'attributes': [attribute()], 'evidence_gaps': ['Inspect left apex']}
        queue = [plan, 'No available tool can resolve this further.', final]
        if decision is not None:
            queue.append(decision)
        calls = []
        model, modules = self.dependencies(queue, calls)
        runtime = SimpleNamespace(model=model, tools={}, tool_provenance={})
        retriever = SimpleNamespace(retrieve=lambda *args, **kwargs: {
            'k_block': '', 'e_block': '', 'k_ids': [], 'e_ids': []})
        with TemporaryDirectory() as folder:
            image = Path(folder) / 'image.png'
            image.write_bytes(b'CURRENT_CASE_IMAGE_BYTES')
            row = {'question_id': 'q1', 'question': 'QUESTION\nA) x\nB) y', 'images': ['image.png']}
            shared = [{'evidence_ref': 'p0:tool:1', 'result': {'finding': 'RAW_CURRENT_OBSERVATION'}}]
            with patch.dict(sys.modules, modules):
                result = controller.run_branch(runtime, None, None, SimpleNamespace(run_id='synthetic', artifact_root=Path(folder)), row, [image],
                                               'A', shared, io.StringIO(), retriever, 'D', Path(folder)/'D')
            return result, calls, queue

    def test_no_tool_candidate_and_gate_receive_pixels_and_complete_raw_evidence(self):
        result, calls, queue = self.run_fake_branch(candidate(), gate())
        self.assertEqual(result['candidate'], 'B')
        self.assertEqual(result['final'], 'B')
        self.assertIsNone(result['candidate_error'])
        self.assertIsNone(result['gate_error'])
        self.assertEqual(result['candidate_accounting']['model_calls'], 3)
        self.assertEqual(result['gate_accounting']['model_calls'], 1)
        self.assertEqual(result['accounting']['model_calls'], 4)
        self.assertEqual(result['accounting']['tool_calls'], 0)
        gate_payload = json.dumps([message.content for message in calls[-1]])
        self.assertIn('data:image/png;base64,', gate_payload)
        self.assertIn('RAW_CURRENT_OBSERVATION', gate_payload)
        self.assertIn('initial', gate_payload)
        self.assertFalse(queue)

    def test_uncertain_candidate_does_not_call_gate_and_retains_p0(self):
        result, calls, queue = self.run_fake_branch(candidate(answer=None, uncertain=True, observations=[], evidence_refs=[]))
        self.assertIsNone(result['candidate'])
        self.assertEqual(result['final'], 'A')
        self.assertEqual(result['fallback'], 'candidate_uncertain')
        self.assertNotIn('gate_accounting', result)
        self.assertEqual(len(calls), 3)
        self.assertFalse(queue)

    def test_candidate_or_gate_parse_failure_retains_p0_and_is_recorded(self):
        result, calls, queue = self.run_fake_branch({'answer': 'B'})
        self.assertIsNotNone(result['candidate_error'])
        self.assertEqual(result['fallback'], 'candidate_error')
        self.assertEqual(result['final'], 'A')
        malformed_gate = '{"decision":"retain","decision":"accept","changed_attributes":[],"evidence_refs":["image:1"],"unmet_requirements":[],"reason":"visible"}'
        result, calls, queue = self.run_fake_branch(candidate(), malformed_gate)
        self.assertIsNotNone(result['gate_error'])
        self.assertEqual(result['fallback'], 'gate_error')
        self.assertEqual(result['final'], 'A')


if __name__ == '__main__':
    unittest.main()
