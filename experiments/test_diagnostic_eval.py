"""Synthetic offline diagnostics tests; no API, server, labels or GPU calls."""
from copy import deepcopy
import io
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import diagnostic_eval as diag


class FakeLimit(RuntimeError):
    pass


class FakeGuard:
    def __init__(self, allowed=1000):
        self.allowed, self.reserved, self.settled = allowed, [], []
        from decimal import Decimal
        self.remaining = Decimal('100')

    def policy_snapshot(self):
        return {'budget_cny': '100', 'kind': 'synthetic_test_only'}

    def reserve(self, **kwargs):
        if len(self.reserved) >= self.allowed:
            raise FakeLimit('synthetic exhausted')
        self.reserved.append(deepcopy(kwargs))
        return str(len(self.reserved))

    def settle(self, reservation, **kwargs):
        self.settled.append((reservation, deepcopy(kwargs)))
        return {'charged_cny': '0', 'remaining_cny': '100', 'synthetic': True}


class Message:
    def __init__(self, content, *, usage=True, finish='stop', tool_calls=None):
        self.content = content
        self.usage_metadata = {'input_tokens': 10, 'output_tokens': 2, 'total_tokens': 12} if usage else None
        self.response_metadata = {'finish_reason': finish, 'model_name': diag.MODEL}
        self.tool_calls = tool_calls or []


class FakeModel:
    def __init__(self, responses):
        self.responses, self.histories = list(responses), []

    def bind_tools(self, tools):
        return self

    def invoke(self, messages):
        self.histories.append(list(messages))
        result = self.responses.pop(0)
        if isinstance(result, BaseException):
            raise result
        return result


class FakeTool:
    name = 'chest_xray_classifier'

    def __init__(self, fail=False):
        self.model = SimpleNamespace(pathologies=[f'label-{i}' for i in range(18)])
        self.calls, self.fail = 0, fail

    def invoke(self, params):
        self.calls += 1
        if self.fail:
            return ({'error': 'synthetic'}, {'analysis_status': 'failed'})
        return ({x: 0.5 for x in self.model.pathologies}, {'analysis_status': 'completed'})


class FakeAgent:
    instances = []

    def __init__(self, model, tools, checkpointer, system_prompt, log_tools):
        self.model = model.bind_tools(tools)
        self.tools = {tool.name: tool for tool in tools}
        self.history, self.checkpointer = [], checkpointer
        self.workflow = self
        self.instances.append(self)

    def stream(self, state, config):
        self.history.extend(state['messages'])
        while True:
            response = self.model.invoke(self.history)
            self.history.append(response)
            yield {'process': {'messages': [response]}}
            if not response.tool_calls:
                return
            results = []
            for call in response.tool_calls:
                result = self.tools[call['name']].invoke(call['args'])
                results.append(SimpleNamespace(content=str(result), name=call['name'], tool_call_id=call['id']))
            self.history.extend(results)
            yield {'execute': {'messages': results}}


def fake_messages(runtime, row, paths, detail, arm):
    return [Message('synthetic visible question ' + row['question_id'])]


def arguments():
    return SimpleNamespace(max_case_seconds=60, request_timeout_seconds=60, image_detail='auto',
                           device='cpu', arms=('direct', 'agent'), arm_order_seed=None)


def runtime(model, tool=None):
    return SimpleNamespace(model=model, tool=tool or FakeTool(), Agent=FakeAgent, MemorySaver=object,
                           HumanMessage=Message, SystemMessage=Message,
                           agent_system='synthetic system with tools', direct_system='synthetic system')


def simple_plan(rows, root, arms=('direct', 'agent')):
    return {'planned_question_count': len(rows), 'question_ids': [x['question_id'] for x in rows],
            'arms': list(arms), 'schedule': diag.make_schedule([x['question_id'] for x in rows], arms),
            'monetary_ledger_path': str(root / 'shared-ledger.json'),
            'records': [diag.inspect_input(x, root)[0] for x in rows], 'model': diag.MODEL}


class DiagnosticTests(unittest.TestCase):
    def run_case(self, model, guard=None, arm='direct', paths=(), tool=None, qid='q1'):
        guard = guard if guard is not None else FakeGuard()
        trace = io.StringIO()
        result = diag.run_arm(runtime(model, tool), guard, {'question_id': qid, 'question': 'fixture', 'images': []},
            list(paths), arm, {'thread_id': 'thread-' + qid}, 'run-fixture', arguments(), trace,
            limit_errors=(FakeLimit,), message_builder=fake_messages)
        return result, guard, trace.getvalue()

    def test_input_rejects_labels_duplicates_and_wrong_denominator(self):
        with TemporaryDirectory() as temp:
            path = Path(temp) / 'inputs.jsonl'
            base = {'question_id': 'q1', 'question': 'fixture', 'images': []}
            path.write_text(json.dumps(base) + '\n')
            self.assertEqual(len(diag.load_rows(path, planned_count=1)), 1)
            with self.assertRaises(ValueError): diag.load_rows(path)
            for key in ('answer', 'correct_answer', 'explanation'):
                path.write_text(json.dumps(dict(base, **{key: 'do not read'})) + '\n')
                with self.assertRaises(ValueError): diag.load_rows(path, 1)
            path.write_text('{"question_id":"q1","question":"fixture","images":[],"question":"override"}\n')
            with self.assertRaises(ValueError): diag.load_rows(path, 1)

    def test_schedule_balances_first_arm_and_is_seed_reproducible(self):
        ids = [f'q{i}' for i in range(50)]
        schedule = diag.make_schedule(ids)
        self.assertEqual(len(schedule), 100)
        self.assertEqual([x['arm'] for x in schedule[:4]], ['direct', 'agent', 'agent', 'direct'])
        shuffled = diag.make_schedule(ids, seed=17)
        self.assertEqual(shuffled, diag.make_schedule(ids, seed=17))
        self.assertEqual(sum(x['arm'] == 'direct' for x in shuffled[::2]), 25)
        self.assertEqual({(x['question_id'], x['arm']) for x in shuffled}, {(x['question_id'], x['arm']) for x in schedule})

    def test_direct_two_stages_guard_each_request_and_hide_reasoning(self):
        secret_reasoning = 'SYNTHETIC_REASONING_MUST_NOT_BE_SAVED'
        model = FakeModel([Message(secret_reasoning, finish='length'), Message('B')])
        result, guard, trace = self.run_case(model)
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(result['answer_letter'], 'B')
        self.assertEqual(result['actual_model_calls'], 2)
        self.assertEqual(len(guard.reserved), 2)
        self.assertEqual(len(guard.settled), 2)
        self.assertEqual(guard.reserved[0]['max_input_tokens'], 128000)
        self.assertEqual(guard.reserved[0]['max_output_tokens'], 512)
        self.assertEqual(guard.reserved[0]['model'], 'gpt-4o-2024-11-20')
        self.assertEqual(guard.settled[0][1]['usage'], {'prompt_tokens': 10, 'completion_tokens': 2})
        self.assertIn('model_output_truncated', result['issue_tags'])
        self.assertEqual(result['phase_outcomes'][0]['finish_reason'], 'length')
        self.assertEqual(result['final_finish_reason'], 'stop')
        self.assertNotIn(secret_reasoning, trace + json.dumps(result))
        self.assertEqual(model.histories[1][-1].content, diag.smoke.FOLLOWUP)

    def test_direct_question_histories_are_independent(self):
        model = FakeModel([Message('reason one'), Message('A'), Message('reason two'), Message('B')])
        self.run_case(model, qid='q1')
        self.run_case(model, qid='q2')
        self.assertEqual(len(model.histories[0]), 2)
        self.assertEqual(len(model.histories[2]), 2)
        self.assertNotIn('q1', str([x.content for x in model.histories[2]]))

    def test_matched_direct_prompt_removes_only_tool_invitation(self):
        suffix = '\nvisible fixture question\nImage located at /fixture/image.png'
        image_block = {'type': 'image_url', 'image_url': {'url': 'data:image/png;base64,synthetic'}}
        def upstream(*args):
            return [Message([{'type': 'text', 'text': diag.AGENT_PREFIX + suffix}, deepcopy(image_block)])]
        with patch.object(diag.smoke, 'initial_messages', upstream):
            direct = diag.initial_messages(None, {}, [], 'auto', 'direct')[0].content
            agent = diag.initial_messages(None, {}, [], 'auto', 'agent')[0].content
        self.assertEqual(direct[0]['text'], diag.DIRECT_PREFIX + suffix)
        self.assertEqual(agent[0]['text'], diag.AGENT_PREFIX + suffix)
        self.assertEqual(direct[1:], agent[1:])

    def test_real_money_guard_integrates_offline_with_complete_usage(self):
        from decimal import Decimal
        from money_guard import MoneyGuard
        with TemporaryDirectory() as temp:
            with MoneyGuard(Path(temp) / 'synthetic-ledger.json', budget_cny='100', model=diag.MODEL,
                            max_input_tokens=128000, max_output_tokens=512) as guard:
                result, _, _ = self.run_case(FakeModel([Message('synthetic reason'), Message('A')]), guard)
                self.assertEqual(result['status'], 'completed')
                self.assertEqual(len(result['ledger_settlements']), 2)
                self.assertEqual(guard.remaining, Decimal('99.44986'))
                self.assertEqual(diag.ledger_summary(guard)['conservative_spent_cny'], '0.55014')

    def test_missing_usage_settles_full_reservation_not_zero(self):
        result, guard, _ = self.run_case(FakeModel([Message('reason', usage=False), Message('C', usage=False)]))
        self.assertTrue(all(x[1]['usage'] is None for x in guard.settled))
        self.assertFalse(result['usage_complete'])
        self.assertIsNone(result['observed_usage_sum'])
        self.assertIn('token_usage_incomplete', result['issue_tags'])

    def test_model_exception_settles_then_preserves_failure(self):
        result, guard, trace = self.run_case(FakeModel([TimeoutError('do not save raw exception')]))
        self.assertEqual(result['status'], 'model_error')
        self.assertEqual(result['actual_model_calls'], 1)
        self.assertEqual(len(guard.settled), 1)
        self.assertIsNone(guard.settled[0][1]['usage'])
        self.assertFalse(guard.settled[0][1]['response_received'])
        self.assertNotIn('do not save raw exception', trace + json.dumps(result))

    def test_no_budget_prevents_model_call_and_never_settles_unreserved(self):
        model = FakeModel([Message('not reached')])
        result, guard, _ = self.run_case(model, FakeGuard(allowed=0))
        self.assertEqual(result['status'], 'monetary_budget_exceeded')
        self.assertTrue(result['stop_run'])
        self.assertEqual(model.histories, [])
        self.assertEqual(result['actual_model_calls'], 0)
        self.assertEqual(guard.settled, [])
        with self.assertRaises(ValueError): diag.DiagnosticModel(model, None, {})

    def test_settlement_failure_stops_all_further_requests(self):
        class BrokenGuard(FakeGuard):
            def settle(self, reservation, **kwargs):
                raise ValueError('synthetic ledger integrity failure')
        model = FakeModel([Message('reason'), Message('not reached')])
        result, _, _ = self.run_case(model, BrokenGuard())
        self.assertEqual(result['status'], 'monetary_guard_error')
        self.assertTrue(result['stop_run'])
        self.assertEqual(len(model.histories), 1)

    def test_agent_real_wrapper_calls_logs_repeated_and_failed_tool_returns(self):
        with TemporaryDirectory() as temp:
            image = Path(temp) / 'fixture.png'; image.write_bytes(b'synthetic image only')
            call = {'id': 'call1', 'name': FakeTool.name, 'args': {'image_path': str(image)}}
            model = FakeModel([Message('', tool_calls=[call, dict(call, id='call2')]), Message('reason'), Message('D')])
            tool = FakeTool(fail=True)
            result, guard, trace = self.run_case(model, arm='agent', paths=[image], tool=tool)
            self.assertEqual(result['answer_letter'], 'D')
            self.assertEqual(result['actual_model_calls'], 3)
            self.assertEqual(tool.calls, 2)
            self.assertEqual(result['repeated_tool_calls'], 1)
            self.assertEqual(result['failed_tool_returns'], 2)
            self.assertFalse(result['tool_execution_verified'])
            self.assertIn('tool_failed_or_invalid', result['issue_tags'])
            self.assertIn('repeated_tool_call', result['issue_tags'])
            self.assertNotIn(str(image), trace)

    def test_agent_tool_limit_keeps_original_loop_bounded(self):
        with TemporaryDirectory() as temp:
            image = Path(temp) / 'fixture.png'; image.write_bytes(b'fixture')
            calls = [{'id': str(i), 'name': FakeTool.name, 'args': {'image_path': str(image)}} for i in range(3)]
            result, guard, _ = self.run_case(FakeModel([Message('', tool_calls=calls)]), arm='agent', paths=[image])
            self.assertEqual(result['status'], 'case_budget_exceeded')
            self.assertEqual(result['actual_tool_attempts'], 2)
            self.assertEqual(result['validated_tool_returns'], 2)
            self.assertEqual(len(guard.reserved), 1)

    def test_no_tool_agent_result_is_not_tool_verification(self):
        result, _, _ = self.run_case(FakeModel([Message('reason'), Message('A')]), arm='agent')
        self.assertEqual(result['status'], 'completed')
        self.assertFalse(result['tool_execution_verified'])
        self.assertIn('no_tool_call', result['issue_tags'])

    def test_resume_does_not_repeat_started_or_completed_arms(self):
        with TemporaryDirectory() as temp:
            root = Path(temp); rows = [{'question_id': 'q1', 'question': 'fixture', 'images': []}]
            plan = simple_plan(rows, root); output = root / 'run'
            journal = diag.RunJournal(output, plan)
            first = journal.start('q1', 'direct')
            journal.finish(dict(first, status='completed', answer_letter='A', issue_tags=[]))
            journal.start('q1', 'agent'); journal.close()
            restored = diag.RunJournal(output, plan, resume=True)
            self.assertEqual(restored.terminals[('q1', 'agent')]['status'], 'interrupted_no_retry')
            def unexpected_runner(*args, **kwargs):
                self.fail('Resume repeated an already started arm')
            summary = diag.execute_schedule(restored, None, FakeGuard(), rows, root, arguments(), io.StringIO(), runner=unexpected_runner)
            self.assertEqual(summary['terminal_count'], 2)
            restored.close()
            again = diag.RunJournal(output, plan, resume=True)
            self.assertEqual(len(again.terminals), 2)
            again.close()

    def test_resume_rejects_config_mismatch_and_partial_journal_tail(self):
        with TemporaryDirectory() as temp:
            root = Path(temp); rows = [{'question_id': 'q1', 'question': 'fixture', 'images': []}]
            plan = simple_plan(rows, root); output = root / 'run'
            journal = diag.RunJournal(output, plan); journal.close()
            changed = deepcopy(plan); changed['model'] = 'different'
            with self.assertRaises(ValueError): diag.RunJournal(output, changed, resume=True)
            changed = deepcopy(plan); changed['monetary_ledger_path'] = str(root / 'different-ledger.json')
            with self.assertRaises(ValueError): diag.RunJournal(output, changed, resume=True)
            with (output / 'results.jsonl').open('a') as handle: handle.write('{"record_type":')
            with self.assertRaises(ValueError): diag.RunJournal(output, plan, resume=True)

    def test_monetary_stop_retains_all_fifty_question_denominators(self):
        with TemporaryDirectory() as temp:
            root = Path(temp); image = root / 'fixture.png'; image.write_bytes(b'synthetic')
            rows = [{'question_id': f'q{i}', 'question': 'fixture', 'images': ['fixture.png']} for i in range(50)]
            journal = diag.RunJournal(root / 'run', simple_plan(rows, root))
            calls = []
            def stop_runner(runtime, guard, row, paths, arm, start, *args, **kwargs):
                calls.append((row['question_id'], arm))
                return {'question_id': row['question_id'], 'arm': arm, 'thread_id': start['thread_id'],
                    'status': 'monetary_budget_exceeded', 'answer_letter': None, 'issue_tags': ['monetary_budget_exceeded'],
                    'actual_model_calls': 0, 'actual_tool_attempts': 0, 'stop_run': True}
            summary = diag.execute_schedule(journal, None, FakeGuard(), rows, root, arguments(), io.StringIO(), runner=stop_runner)
            self.assertEqual(summary['planned_question_count'], 50)
            self.assertEqual(len(summary['question_results']), 100)
            self.assertEqual(summary['terminal_count'], 1)
            self.assertEqual(sum(x['status'] == 'not_run_budget' for x in summary['question_results']), 99)
            self.assertEqual(len(calls), 1)
            journal.close()

    def test_missing_image_is_logged_without_api_and_stays_in_denominator(self):
        with TemporaryDirectory() as temp:
            root = Path(temp); rows = [{'question_id': 'q1', 'question': 'fixture', 'images': ['missing.png']}]
            journal = diag.RunJournal(root / 'run', simple_plan(rows, root))
            def unexpected_runner(*args, **kwargs): self.fail('Missing image reached API runner')
            summary = diag.execute_schedule(journal, None, FakeGuard(), rows, root, arguments(), io.StringIO(), runner=unexpected_runner)
            self.assertEqual(summary['terminal_count'], 2)
            self.assertTrue(all(x['status'] == 'missing_image' for x in summary['question_results']))
            self.assertTrue(all(x['actual_model_calls'] == 0 for x in summary['question_results']))
            journal.close()

    def test_auth_failure_stops_immediately_after_full_settlement(self):
        class AuthenticationError(RuntimeError):
            pass
        model = FakeModel([AuthenticationError('synthetic'), Message('not reached')])
        result, guard, _ = self.run_case(model)
        self.assertTrue(result['stop_run'])
        self.assertTrue(result['api_error'])
        self.assertEqual(result['stop_reason'], 'api_error')
        self.assertEqual(result['api_error_type'], 'AuthenticationError')
        self.assertEqual(len(model.histories), 1)
        self.assertIsNone(guard.settled[0][1]['usage'])

    def test_model_mismatch_does_not_refund_or_continue(self):
        response = Message('A'); response.response_metadata['model_name'] = 'different-model'
        result, guard, trace = self.run_case(FakeModel([response, Message('not reached')]))
        self.assertTrue(result['stop_run'])
        self.assertIn('model_identity_mismatch', result['issue_tags'])
        self.assertEqual(result['actual_model_calls'], 1)
        self.assertIsNone(guard.settled[0][1]['usage'])
        self.assertIsNone(result['answer_letter'])
        self.assertIn('different-model', trace)

    def test_three_consecutive_api_failures_stop_without_fourth_request(self):
        with TemporaryDirectory() as temp:
            root = Path(temp); (root / 'fixture.png').write_bytes(b'synthetic')
            rows = [{'question_id': f'q{i}', 'question': 'fixture', 'images': ['fixture.png']} for i in range(3)]
            plan = simple_plan(rows, root); journal = diag.RunJournal(root / 'run', plan)
            model = FakeModel([TimeoutError('synthetic') for _ in range(6)])
            guard = FakeGuard()
            def run_fake(*args, **kwargs):
                return diag.run_arm(*args, **kwargs, message_builder=fake_messages)
            summary = diag.execute_schedule(journal, runtime(model), guard, rows, root, arguments(), io.StringIO(),
                                            limit_errors=(FakeLimit,), runner=run_fake)
            self.assertEqual(summary['stop_reason'], 'api_error')
            self.assertEqual(summary['terminal_count'], 3)
            self.assertEqual(len(model.histories), 3)
            self.assertEqual(len(guard.settled), 3)
            self.assertTrue(all(x[1]['usage'] is None for x in guard.settled))
            self.assertEqual(sum(x['status'] == 'not_run_api_error' for x in summary['question_results']), 3)
            journal.close()
            resumed = diag.RunJournal(root / 'run', plan, resume=True)
            again = diag.execute_schedule(resumed, runtime(model), guard, rows, root, arguments(), io.StringIO(),
                                          limit_errors=(FakeLimit,), runner=run_fake)
            self.assertEqual(again['terminal_count'], 3)
            self.assertEqual(len(model.histories), 3)
            resumed.close()

    def test_invalid_answers_and_length_do_not_trigger_api_failure_stop(self):
        with TemporaryDirectory() as temp:
            root = Path(temp); (root / 'fixture.png').write_bytes(b'synthetic')
            rows = [{'question_id': f'q{i}', 'question': 'fixture', 'images': ['fixture.png']} for i in range(2)]
            journal = diag.RunJournal(root / 'run', simple_plan(rows, root, ('direct',)))
            model = FakeModel([Message('reason', finish='length'), Message('not a letter', finish='length'),
                               Message('reason', finish='length'), Message('B')])
            def run_fake(*args, **kwargs):
                return diag.run_arm(*args, **kwargs, message_builder=fake_messages)
            summary = diag.execute_schedule(journal, runtime(model), FakeGuard(), rows, root, arguments(), io.StringIO(), runner=run_fake)
            self.assertEqual(summary['stop_reason'], 'complete')
            self.assertEqual(summary['terminal_count'], 2)
            self.assertEqual(len(model.histories), 4)
            self.assertFalse(any(x.get('api_error') for x in summary['question_results']))
            journal.close()


if __name__ == '__main__':
    unittest.main()
