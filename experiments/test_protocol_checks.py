"""Fabricated protocol objects only; no models, SDK dependencies or network."""
from copy import deepcopy
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from protocol_checks import check_history, check_response


def wire_call(call_id='call_1', arguments='{"image_path":"fixture.png"}'):
    return {'id': call_id, 'type': 'function',
            'function': {'name': 'classifier', 'arguments': arguments}}


def ai(calls=None, invalid=None, raw=None, finish='stop'):
    return SimpleNamespace(type='ai', content='', tool_calls=calls or [], invalid_tool_calls=invalid or [],
                           additional_kwargs={} if raw is None else {'tool_calls': raw},
                           response_metadata={'finish_reason': finish})


def codes(report):
    return {issue.code for issue in report.issues}


class ProtocolTests(unittest.TestCase):
    def test_observed_shape_invalid_call_length_then_followup_is_blocked(self):
        malformed = '{"image_path":"DO_NOT_LOG_ARGUMENT_VALUE'
        raw = wire_call(arguments=malformed)
        message = ai(invalid=[{'id': 'call_1', 'name': 'classifier', 'args': malformed,
                               'error': 'DO_NOT_LOG_PARSER_EXCEPTION'}], raw=[raw], finish='length')
        history = [message, {'role': 'user', 'content': 'letter only'}]
        before = deepcopy(message.__dict__)
        result = check_history(history)
        self.assertFalse(result.ready_for_model)
        self.assertFalse(result.pending_calls_well_formed)
        self.assertTrue(result.length_terminated)
        self.assertEqual(result.declared_tool_call_count, 1)  # raw mirror must not double count
        self.assertEqual(result.invalid_tool_call_count, 1)
        self.assertEqual(result.pending_tool_call_ids, ('call_1',))
        self.assertTrue({'invalid_tool_calls_present', 'invalid_arguments_json', 'pending_tool_reply',
                         'non_tool_message_before_tool_replies'} <= codes(result))
        self.assertNotIn('DO_NOT_LOG', json.dumps(result.to_dict()))
        self.assertEqual(before, message.__dict__)

    def test_raw_fallback_bad_json_is_detected_without_normalized_fields(self):
        report = check_response(ai(raw=[wire_call(arguments='{"broken":')]))
        self.assertEqual(report.invalid_tool_call_count, 1)
        self.assertIn('invalid_arguments_json', codes(report))
        self.assertFalse(report.ready_for_model)
        self.assertFalse(report.pending_calls_well_formed)

    def test_valid_pending_call_is_not_ready_for_new_model_request(self):
        report = check_response({'role': 'assistant', 'tool_calls': [wire_call()]})
        self.assertEqual(report.invalid_tool_call_count, 0)
        self.assertEqual(report.pending_tool_call_ids, ('call_1',))
        self.assertFalse(report.ready_for_model)
        self.assertTrue(report.pending_calls_well_formed)

    def test_actual_parallel_tool_replies_can_arrive_in_either_order(self):
        history = [
            {'role': 'user', 'content': 'visible question'},
            {'role': 'assistant', 'tool_calls': [wire_call('call_1'), wire_call('call_2')]},
            {'role': 'tool', 'tool_call_id': 'call_2', 'content': 'actual result two'},
            {'role': 'tool', 'tool_call_id': 'call_1', 'content': 'actual result one'},
            {'role': 'assistant', 'content': 'A'},
            {'role': 'user', 'content': 'next turn'},
        ]
        self.assertTrue(check_history(history).ready_for_model)
        self.assertEqual(check_history(history).issues, ())

    def test_missing_one_parallel_reply_and_late_reply_do_not_hide_bad_order(self):
        history = [
            {'role': 'assistant', 'tool_calls': [wire_call('call_1'), wire_call('call_2')]},
            {'role': 'tool', 'tool_call_id': 'call_1', 'content': 'actual result'},
            {'role': 'user', 'content': 'followup'},
        ]
        report = check_history(history)
        self.assertEqual(report.pending_tool_call_ids, ('call_2',))
        self.assertIn('non_tool_message_before_tool_replies', codes(report))
        history.append({'role': 'tool', 'tool_call_id': 'call_2', 'content': 'late result'})
        report = check_history(history)
        self.assertEqual(report.pending_tool_call_ids, ())
        self.assertFalse(report.ready_for_model)

    def test_mixed_valid_and_invalid_calls_remain_unsafe_after_valid_reply(self):
        message = ai(calls=[{'id': 'good', 'name': 'classifier', 'args': {'image_path': 'fixture.png'}}],
                     invalid=[{'id': 'bad', 'name': 'classifier', 'args': '{'}])
        report = check_history([message, {'role': 'tool', 'tool_call_id': 'good', 'content': 'actual result'}])
        self.assertEqual(report.declared_tool_call_count, 2)
        self.assertEqual(report.invalid_tool_call_count, 1)
        self.assertEqual(report.pending_tool_call_ids, ('bad',))
        self.assertFalse(report.ready_for_model)

    def test_duplicate_call_ids_duplicate_and_orphan_replies_are_errors(self):
        report = check_history([{'role': 'assistant', 'tool_calls': [wire_call(), wire_call()]}])
        self.assertIn('duplicate_tool_call_id', codes(report))
        report = check_history([{'role': 'tool', 'tool_call_id': 'unknown', 'content': 'result'}])
        self.assertIn('orphan_tool_reply', codes(report))
        history = [{'role': 'assistant', 'tool_calls': [wire_call()]},
                   {'role': 'tool', 'tool_call_id': 'call_1', 'content': 'result'},
                   {'role': 'tool', 'tool_call_id': 'call_1', 'content': 'duplicate'}]
        self.assertIn('duplicate_tool_reply', codes(check_history(history)))

    def test_reply_to_invalid_call_does_not_make_bad_json_valid(self):
        history = [{'role': 'assistant', 'tool_calls': [wire_call(arguments='{')]},
                   {'role': 'tool', 'tool_call_id': 'call_1', 'content': 'error reply'}]
        report = check_history(history)
        self.assertEqual(report.pending_tool_call_ids, ())
        self.assertFalse(report.ready_for_model)
        self.assertIn('invalid_arguments_json', codes(report))

    def test_length_is_warning_not_proof_of_json_error_and_strict_policy_is_explicit(self):
        message = {'role': 'assistant', 'content': 'A'}
        before = deepcopy(message)
        report = check_response(message, finish_reason='length')
        self.assertTrue(report.ready_for_model)
        self.assertTrue(report.length_terminated)
        self.assertEqual(report.invalid_tool_call_count, 0)
        self.assertFalse(check_response(message, finish_reason='length', reject_length=True).ready_for_model)
        self.assertEqual(before, message)

    def test_json_shape_duplicate_keys_and_nonfinite_values_are_rejected(self):
        for arguments in ('[]', 'null', '1', '{"a":NaN}', '{"a":1,"a":2}', '{"a":'):
            with self.subTest(arguments=arguments):
                report = check_response({'role': 'assistant', 'tool_calls': [wire_call(arguments=arguments)]})
                self.assertEqual(report.invalid_tool_call_count, 1)
                self.assertFalse(report.ready_for_model)

    def test_structured_calls_take_same_precedence_as_fixed_sdk(self):
        normalized = {'id': 'good', 'name': 'classifier', 'args': {}}
        message = ai(calls=[normalized], raw=[wire_call('ignored_raw', arguments='{')])
        report = check_history([message, {'role': 'tool', 'tool_call_id': 'good', 'content': 'actual result'}])
        self.assertEqual(report.declared_tool_call_count, 1)
        self.assertEqual(report.invalid_tool_call_count, 0)
        self.assertTrue(report.ready_for_model)

    def test_explicit_invalid_flag_cannot_be_erased_by_reparsable_json(self):
        report = check_response(ai(invalid=[{'id': 'call_1', 'name': 'classifier', 'args': '{}'}]))
        self.assertEqual(report.invalid_tool_call_count, 1)
        self.assertIn('invalid_tool_calls_present', codes(report))

    def test_malformed_shapes_missing_ids_and_unsupported_legacy_fail_closed(self):
        for message, expected in (
            ({'role': 'assistant', 'tool_calls': 'not a list'}, 'tool_calls_not_sequence'),
            ({'role': 'assistant', 'tool_calls': [42]}, 'tool_call_not_object'),
            ({'role': 'assistant', 'tool_calls': [wire_call(call_id=None)]}, 'missing_tool_call_id'),
            ({'role': 'assistant', 'function_call': {'name': 'old', 'arguments': '{}'}}, 'legacy_function_call_not_supported'),
            ({'role': 'assistant', 'finish_reason': 'tool_calls'}, 'tool_finish_without_calls'),
            ({'role': 'tool', 'content': 'result'}, 'missing_tool_reply_id'),
            ({'role': ['invalid']}, 'unsupported_message_role'),
        ):
            with self.subTest(expected=expected):
                report = check_response(message)
                self.assertIn(expected, codes(report))
                self.assertFalse(report.ready_for_model)


if __name__ == '__main__':
    unittest.main()
