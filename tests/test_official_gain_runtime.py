"""Offline regressions for the repaired run's answer and final-call boundary."""
import importlib.util
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from langchain_core.messages import AIMessage, HumanMessage

from official_gain.runtime import (
    Client, OfficialModelProxy, CaseBudget, StopRun, answer, read,
    FINAL_CALL_INSTRUCTION, request_identifier, request_tool_parameters,
)


TOOL = {'type': 'function', 'function': {
    'name': 'inspect_image', 'description': 'Observe the selected image.',
    'parameters': {'type': 'object', 'properties': {'image_path': {'type': 'string'}},
                   'required': ['image_path']},
}}


class FakeLedger:
    def __init__(self):
        self.reservations = []

    def reserve(self, **kwargs):
        self.reservations.append(kwargs)
        return 'test-reservation'

    def settle(self, reservation, **kwargs):
        return {'charged_cny': '0.01'}


class RecordingModel:
    def __init__(self):
        self.requests = []

    def bind(self, **kwargs):
        owner = self

        class Bound:
            def invoke(self, wire):
                return owner.respond(wire, kwargs)
        return Bound()

    def invoke(self, wire):
        return self.respond(wire, {})

    def respond(self, wire, kwargs):
        self.requests.append({'messages': wire, **kwargs})
        return AIMessage(content='Return Answer: B, the visible relation is supported.',
                         usage_metadata={'input_tokens': 10, 'output_tokens': 8, 'total_tokens': 18},
                         response_metadata={'model_name': 'qwen3-vl-plus'})


def fake_client(out):
    # No Client constructor, real ledger, provider key or network is used.
    client = Client.__new__(Client)
    client.cfg = dict(model='qwen3-vl-plus', temperature=.2, top_p=.95,
                      max_tokens=2048, max_requests=528, max_extra_requests=48,
                      run_id='official_gain60_fixed', repaired_execution=True)
    client.out = Path(out)
    client.status = lambda **kwargs: None
    client.profile = SimpleNamespace(max_input_tokens=32768,
                                     identity_ok=lambda name: name == 'qwen3-vl-plus')
    client.ledger = FakeLedger()
    client.model = RecordingModel()
    client.used = 0
    client.extra = 0
    return client


class RuntimeTests(unittest.TestCase):
    def test_same_explicit_answer_rule_without_guessing(self):
        legal = set('ABCDEF')
        cases = [
            ('Return Answer: B followed by a short reason.', 'B'),
            ('Answer: C, a directly described feature.', 'C'),
            ('Analysis.\n\nA) Complete option text', 'A'),
            ('B. Complete option text\n\nEvidence explanation.', 'B'),
            ('Answer: None of the options are supported.', None),
            ('Answer: B\nAnswer: C', None),
            ('A) one\n\nB) two', None),
            ('Let me call another tool.', None),
        ]
        for text, expected in cases:
            with self.subTest(text=text):
                self.assertEqual(answer(text, legal), expected)

    def test_request_ids_are_stable_and_run_specific(self):
        out = Path('run')
        folder = out / 'predictions/example/M/calls/model_1'
        cfg = {'run_id': 'official_gain60_fixed', 'repaired_execution': True}
        first = request_identifier(cfg, out, folder, 1)
        self.assertEqual(first, request_identifier(cfg, out, folder, 1))
        self.assertNotEqual(first, request_identifier({'run_id': 'other_run'}, out, folder, 1))
        self.assertNotEqual(first, request_identifier({}, out, folder, 1))
        self.assertNotIn('\\', first)
        with self.assertRaises(StopRun):
            request_identifier({'repaired_execution': True}, out, folder, 1)
        with self.assertRaises(StopRun):
            request_identifier({'run_id': '../private'}, out, folder, 1)

    def test_fourth_call_removes_schema_and_submits_within_same_budget(self):
        with tempfile.TemporaryDirectory() as directory:
            client = fake_client(directory)
            folder = Path(directory) / 'predictions/example/M/calls'
            messages = [HumanMessage(content='Inspect image:1. A) first B) second C) third.')]
            proxy = OfficialModelProxy(client, folder, client.status).bind_tools([TOOL])
            for _ in range(4):
                response = proxy.invoke(messages)
            self.assertEqual(answer(response.content, set('ABC')), 'B')
            self.assertEqual(len(messages), 1)  # Do not mutate official history.
            self.assertEqual(client.used, 4)
            self.assertEqual(len(client.model.requests), 4)
            self.assertTrue(all('tools' in r for r in client.model.requests[:3]))
            actual = client.model.requests[-1]
            saved = read(folder / 'model_4/request.json')
            self.assertNotIn('tools', actual)
            self.assertNotIn('tool_choice', actual)
            self.assertNotIn('tools', saved)
            self.assertNotIn('tool_choice', saved)
            self.assertEqual(saved['messages'], actual['messages'])
            self.assertEqual(saved['messages'][-1]['content'], FINAL_CALL_INSTRUCTION)
            self.assertIn('budget is 0', saved['messages'][-1]['content'])
            with self.assertRaises(CaseBudget):
                proxy.invoke(messages)
            self.assertEqual(client.used, 4)
            self.assertTrue(all(r['request_id'].startswith('official:official_gain60_fixed:')
                                for r in client.ledger.reservations))
            # A same-run replay uses saved responses; it does not reserve/pay again.
            replay = OfficialModelProxy(client, folder, client.status).bind_tools([TOOL])
            for _ in range(4):
                replay.invoke(messages)
            self.assertEqual(len(client.model.requests), 4)
            self.assertEqual(len(client.ledger.reservations), 4)

    def test_tool_free_p_request_does_not_claim_a_tool_choice(self):
        with tempfile.TemporaryDirectory() as directory:
            client = fake_client(directory)
            folder = Path(directory) / 'predictions/example/P/calls/final'
            client.invoke(folder, [HumanMessage(content='Choose the best complete option.')])
            saved = read(folder / 'request.json')
            self.assertNotIn('tools', saved)
            self.assertNotIn('tool_choice', saved)
            self.assertEqual(saved['messages'], client.model.requests[0]['messages'])

    def test_existing_hard_request_limit_stops_before_reservation(self):
        with tempfile.TemporaryDirectory() as directory:
            client = fake_client(directory)
            client.used = 528
            with self.assertRaises(StopRun):
                client.invoke(Path(directory) / 'predictions/example/P/calls/final',
                              [HumanMessage(content='Choose an option.')])
            self.assertEqual(client.ledger.reservations, [])
            self.assertEqual(client.model.requests, [])

    @unittest.skipUnless(importlib.util.find_spec('langchain_openai'),
                         'server SDK payload check: langchain_openai unavailable locally')
    def test_actual_chatopenai_sdk_final_payload_has_no_tool_schema(self):
        from langchain_openai import ChatOpenAI
        model = ChatOpenAI(model='qwen3-vl-plus', api_key='dry-not-a-credential',
                           base_url='https://dashscope.aliyuncs.com/compatible-mode/v1',
                           temperature=.2, top_p=.95, max_tokens=2048,
                           timeout=120, max_retries=0)
        messages = [HumanMessage(content='Question and complete options.'),
                    HumanMessage(content=FINAL_CALL_INSTRUCTION)]
        final = model._get_request_payload(messages, **request_tool_parameters([TOOL], True))
        normal = model._get_request_payload(messages[:1], **request_tool_parameters([TOOL]))
        self.assertNotIn('tools', final)
        self.assertNotIn('tool_choice', final)
        self.assertIn('tools', normal)
        self.assertEqual(normal['tool_choice'], 'auto')
        self.assertEqual(final['messages'][-1]['content'], FINAL_CALL_INSTRUCTION)


if __name__ == '__main__':
    unittest.main()
