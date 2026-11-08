"""Focused timing, prefix, replay, and fixed-policy regressions for R47."""
import copy
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'experiments'))
import cxr_image_memory_gt_r47 as memory
import run_cxr_image_memory_gt_r47 as runner


class ImmutableTransport:
    """Real immutable artifacts and replay; a second send cannot overwrite one."""
    key = ''

    def __init__(self, out):
        self.out, self.sends, self.messages = Path(out), 0, []

    def call(self, row, arm, ordinal, messages, **kwargs):
        folder = self.out / 'calls' / arm / row['question_id'] / str(ordinal)
        if (folder / 'started.json').exists() and not (folder / 'response.json').exists():
            raise RuntimeError('unknown_sent_no_reissue')
        memory.save_once(folder / 'request.json', messages)
        if (folder / 'response.json').exists():
            return memory.read(folder / 'response.json')['raw']
        self.sends += 1
        self.messages.append(copy.deepcopy(messages))
        memory.save_once(folder / 'started.json', {'utc': memory.now()})
        raw = json.dumps({'answer': 'new answer', 'reason': 'visible evidence'})
        memory.save_once(folder / 'response.json', {'raw': raw})
        memory.save_once(folder / 'result.json', {'error': None, 'response_received': True})
        return raw


def fixture(root):
    inputs = [
        {'question_id': 'q0', 'question': 'prior same-image question', 'options': {'A': 'old finding', 'B': 'true finding'}, 'images': ['a.png']},
        {'question_id': 'q1', 'question': 'other image question', 'images': ['b.png']},
        {'question_id': 'q2', 'question': 'current question', 'options': {'A': 'true finding', 'B': 'old finding'}, 'images': ['a.png']},
    ]
    order = [
        {'question_id': 'q0', 'image_key': 'image-a', 'previous_ids': []},
        {'question_id': 'q1', 'image_key': 'image-b', 'previous_ids': []},
        {'question_id': 'q2', 'image_key': 'image-a', 'previous_ids': ['q0']},
    ]
    references = [
        {'question_id': 'q0', 'answer': 'B', 'answer_text': 'TRUE_PRIOR_LABEL'},
        {'question_id': 'q1', 'answer': 'OTHER_IMAGE_LABEL', 'answer_text': 'OTHER_IMAGE_TEXT'},
        {'question_id': 'q2', 'answer': 'CURRENT_SECRET_LABEL', 'answer_text': 'CURRENT_SECRET_TEXT'},
    ]
    manifest = {}
    for reference in references:
        qid = reference['question_id']
        path = root / 'vault' / (qid + '.json')
        memory.save_once(path, reference)
        manifest[qid] = {'file': qid + '.json'}
    baseline = {row['question_id']: {'question_id': row['question_id'], 'answer': 'A',
                'reason': 'unchanged old error', 'status': 'completed', 'observations': []} for row in inputs}
    frozen = {'inputs': inputs, 'order': order, 'policy': {row['question_id']: 'M' for row in inputs},
              'baseline': baseline, 'reference_files': manifest, 'data': str(root),
              'memory_max_chars': 12000, 'memory_max_entries': 8,
              'new_main_ceiling': 644, 'new_tool_ceiling': 384}
    out = root / 'generation'
    return frozen, out, memory.ReferenceVault(root / 'vault', manifest)


def fake_base():
    base = SimpleNamespace(agent_system=lambda arm: 'No cross-case skills, sibling question context or additional patient history is available.',
                           write=memory.save_once, now=memory.now,
                           safe_error=lambda exc, key: str(exc))

    def episode(row, arm, data, protocol, runtime, out, paid, tools, *, conditioning=None):
        messages = [{'role': 'system', 'content': base.agent_system(arm)},
                    {'role': 'user', 'content': row['question']}]
        if conditioning:
            messages.append({'role': 'user', 'content': conditioning})
        raw = paid.call(row, arm, 1, messages)
        return dict(json.loads(raw), status='completed', main_calls=1, tool_calls=0, observations=[])

    base.episode = episode
    return base


class FeedbackTimingTests(unittest.TestCase):
    def test_vault_refuses_reference_before_prediction_without_opening_label(self):
        with tempfile.TemporaryDirectory() as name:
            frozen, out, vault = fixture(Path(name))
            with patch.object(memory, 'read', side_effect=AssertionError('label read')):
                with self.assertRaisesRegex(ValueError, 'before_prediction_save'):
                    vault.after_prediction('q0', out / 'predictions' / memory.ARM / 'q0.json')

    def test_full_sequential_feedback_timing_and_current_label_absent(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            frozen, out, vault = fixture(root)
            paid, released = ImmutableTransport(out), []

            def callback(qid, prediction_path):
                self.assertTrue(prediction_path.is_file())
                self.assertFalse((out / 'feedback_events' / (qid + '.json')).exists())
                released.append(qid)
                if qid == 'q2':
                    self.assertEqual(paid.sends, 1)
                return vault.after_prediction(qid, prediction_path)

            runner.generate(frozen, out, fake_base(), None,
                            SimpleNamespace(decision=lambda *args: 'preserve_accepted_answer'),
                            paid, None, {}, {}, callback)
            self.assertEqual(released, ['q0', 'q1', 'q2'])
            self.assertEqual(paid.sends, 1)
            serialized = json.dumps(paid.messages)
            self.assertIn('TRUE_PRIOR_LABEL', serialized)
            self.assertIn('true finding', serialized)
            for secret in ('CURRENT_SECRET_LABEL', 'CURRENT_SECRET_TEXT', 'OTHER_IMAGE_LABEL', 'OTHER_IMAGE_TEXT', 'other image question'):
                self.assertNotIn(secret, serialized)
            prior = memory.read(out / 'predictions' / memory.ARM / 'q0.json')
            self.assertEqual((prior['answer'], prior['reason'], prior['status']), ('A', 'unchanged old error', 'completed'))
            trace = memory.read(out / 'memory_context' / 'q2.json')
            self.assertEqual(trace['included_ids'], ['q0'])
            shown = json.loads(trace['memory'].split('\n', 1)[1])[0]
            self.assertEqual(shown['previous_answer'], 'A')
            self.assertEqual(shown['reference_annotation']['answer'], 'B')
            self.assertEqual(shown['reference_annotation']['answer_text'], 'TRUE_PRIOR_LABEL')
            self.assertEqual(shown['reference_annotation']['option_text'], 'true finding')
            self.assertNotIn('_feedback_event', shown)
            for qid in released:
                prediction_path = out / 'predictions' / memory.ARM / (qid + '.json')
                event = memory.read(out / 'feedback_events' / (qid + '.json'))
                prediction = memory.read(prediction_path)
                self.assertEqual(event['saved_prediction'], {key: prediction[key] for key in ('answer', 'reason', 'status', 'prediction_saved_at')})
                self.assertEqual(event['reference_file'], qid + '.json')
                self.assertLessEqual(prediction['prediction_saved_at'], event['released_at'])
            self.assertEqual(runner.audit_complete(frozen, out)['feedback_events'], 3)

    def test_restart_does_not_send_reopen_reference_or_rewrite_artifacts(self):
        with tempfile.TemporaryDirectory() as name:
            frozen, out, vault = fixture(Path(name))
            paid, base = ImmutableTransport(out), fake_base()
            completion = SimpleNamespace(decision=lambda *args: 'preserve_accepted_answer')
            runner.generate(frozen, out, base, None, completion, paid, None, {}, {}, vault.after_prediction)
            before = {str(path.relative_to(out)): (memory.read(path), path.stat().st_mtime_ns) for path in out.rglob('*.json')}
            runner.generate(frozen, out, base, None, completion, paid, None, {}, {},
                            lambda *args: self.fail('committed feedback reopened reference'))
            after = {str(path.relative_to(out)): (memory.read(path), path.stat().st_mtime_ns) for path in out.rglob('*.json')}
            self.assertEqual(before, after)
            self.assertEqual(paid.sends, 1)

    def test_prediction_saved_but_no_feedback_resumes_without_prediction_call(self):
        with tempfile.TemporaryDirectory() as name:
            frozen, out, vault = fixture(Path(name))
            paid = ImmutableTransport(out)
            completion = SimpleNamespace(decision=lambda *args: 'preserve_accepted_answer')

            def crash(qid, path):
                if qid == 'q2':
                    raise RuntimeError('crash after immutable prediction')
                return vault.after_prediction(qid, path)

            with self.assertRaisesRegex(RuntimeError, 'crash after immutable'):
                runner.generate(frozen, out, fake_base(), None, completion, paid, None, {}, {}, crash)
            previous = memory.read(out / 'predictions' / memory.ARM / 'q2.json')
            runner.generate(frozen, out, fake_base(), None, completion, paid, None, {}, {}, vault.after_prediction)
            self.assertEqual(paid.sends, 1)
            self.assertEqual(memory.read(out / 'predictions' / memory.ARM / 'q2.json'), previous)
            self.assertTrue((out / 'feedback_events' / 'q2.json').exists())

    def test_saved_prediction_feedback_binding_uses_semantic_values(self):
        with tempfile.TemporaryDirectory() as name:
            frozen, out, vault = fixture(Path(name))
            item = frozen['order'][0]
            path = out / 'predictions' / memory.ARM / 'q0.json'
            memory.save_once(path, runner.reuse_m43(frozen, 'q0', memory.now()))
            event = memory.feedback_after_save(out, item, 1, frozen['reference_files'], vault.after_prediction)
            ep = out / 'feedback_events' / 'q0.json'
            # Formatting can differ; saved model values retain their meaning.
            ep.write_text(json.dumps(event, separators=(',', ':')), encoding='utf-8')
            self.assertEqual(memory.feedback_after_save(out, item, 1, frozen['reference_files'], vault.after_prediction), event)
            prediction = memory.read(path)
            prediction['answer'] = 'rewritten'
            path.write_text(json.dumps(prediction), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'binding_changed'):
                memory.feedback_after_save(out, item, 1, frozen['reference_files'], vault.after_prediction)


class PrefixAndImmutabilityTests(unittest.TestCase):
    def test_context_filters_other_image_future_current_and_preserves_old_error(self):
        def entry(qid, image, ordinal):
            row = {'question_id': qid, 'question': qid}
            result = {'question_id': qid, 'answer': 'old error', 'reason': 'old reason', 'status': 'completed'}
            event = {'question_id': qid, 'image_key': image, 'ordinal': ordinal,
                     'reference_annotation': {'answer': 'truth-' + qid}}
            return memory.memory_entry(row, result, event)
        entries = [entry('prior', 'same', 1), entry('other', 'other', 2), entry('future', 'same', 9), entry('current', 'same', 3)]
        text, included = memory.context(entries, {'question_id': 'current', 'image_key': 'same', 'previous_ids': ['prior']}, 3)
        self.assertEqual(included, ['prior'])
        self.assertIn('old error', text)
        for qid in ('other', 'future', 'current'):
            self.assertNotIn('truth-' + qid, text)

    def test_repeat_with_oversized_memory_fails_instead_of_baseline_reuse(self):
        event = {'question_id': 'prior', 'image_key': 'same', 'ordinal': 1, 'reference_annotation': {'answer': 'truth'}}
        entry = memory.memory_entry({'question_id': 'prior', 'question': 'x' * 13000},
                                    {'question_id': 'prior', 'answer': 'A'}, event)
        with self.assertRaisesRegex(ValueError, 'repeat_question_has_empty_memory'):
            memory.context([entry], {'question_id': 'current', 'image_key': 'same', 'previous_ids': ['prior']}, 2)

    def test_actual_write_once_refuses_changed_value_and_keeps_values_mtime(self):
        with tempfile.TemporaryDirectory() as name:
            path = Path(name) / 'prediction.json'
            self.assertTrue(memory.save_once(path, {'answer': 'A'}))
            before = memory.read(path), path.stat().st_mtime_ns
            self.assertFalse(memory.save_once(path, {'answer': 'A'}))
            with self.assertRaisesRegex(ValueError, 'immutable_artifact_changed'):
                memory.save_once(path, {'answer': 'B'})
            self.assertEqual((memory.read(path), path.stat().st_mtime_ns), before)

    def test_future_artifact_or_feedback_before_prediction_rejected(self):
        with tempfile.TemporaryDirectory() as name:
            frozen, out, vault = fixture(Path(name))
            with self.assertRaisesRegex(ValueError, 'feedback_before_prediction_save'):
                memory.feedback_after_save(out, frozen['order'][0], 1, frozen['reference_files'], vault.after_prediction)
            memory.save_once(out / 'predictions' / memory.ARM / 'q2.json', {'question_id': 'q2'})
            with self.assertRaisesRegex(ValueError, 'not_processed_prefix'):
                memory.validate_resume_prefix(out, frozen['order'])

    def test_original_paid_transport_refuses_unknown_send_without_reissue(self):
        from run_cxr_vqa_toolsets import PaidCalls
        with tempfile.TemporaryDirectory() as name:
            out = Path(name)
            folder = out / 'calls' / memory.ARM / 'q' / '1'
            memory.save_once(folder / 'started.json', {'send_intent': True})
            transport = PaidCalls.__new__(PaidCalls)
            transport.out, transport.protocol = out, {'experiment_id': 'r47', 'request_archive': 'image_base64_content_addressed_v1'}
            with self.assertRaisesRegex(RuntimeError, 'unknown_sent_no_reissue'):
                transport.call({'question_id': 'q'}, memory.ARM, 1, [])
            with self.assertRaisesRegex(RuntimeError, 'unknown_sent_no_reissue'):
                memory.assert_no_unknown_sends(out)
            self.assertFalse((folder / 'request.json').exists())
            self.assertFalse((folder / 'response.json').exists())

    def test_known_unhealthy_receipt_stops_before_more_inference(self):
        with tempfile.TemporaryDirectory() as name:
            out = Path(name)
            folder = out / 'calls' / memory.ARM / 'q' / '1'
            memory.save_once(folder / 'started.json', {})
            memory.save_once(folder / 'response.json', {})
            # A saved response awaiting receipt can be recovered by the old transport.
            memory.assert_no_unknown_sends(out)
            memory.save_once(folder / 'result.json', {'error': 'identity mismatch', 'response_received': True})
            with self.assertRaisesRegex(RuntimeError, 'unhealthy_request_receipt_no_reissue'):
                memory.assert_no_unknown_sends(out)


class PolicyAndHealthTests(unittest.TestCase):
    def test_model_settings_match_original_semantic_values(self):
        protocol = {'model': 'qwen3.7-plus', 'temperature': 0.2, 'top_p': 0.95,
                    'enable_thinking': False, 'max_output_tokens': 2048}
        memory.validate_protocol(protocol)
        for key, changed in [('model', 'other'), ('temperature', 0), ('top_p', 1),
                             ('enable_thinking', True), ('max_output_tokens', 4096)]:
            with self.subTest(key=key):
                with self.assertRaisesRegex(ValueError, 'original_model_setting_required:' + key):
                    memory.validate_protocol(dict(protocol, **{key: changed}))

    def test_M_completion_uses_only_one_existing_R43_finalize_within_four(self):
        paid = SimpleNamespace(call=lambda *args, **kwargs: '{"answer":"Yes","reason":"seen"}')
        base = fake_base()
        calls = []

        def episode(row, arm, data, protocol, runtime, out, capture, bound, **kwargs):
            calls.append(('M', arm))
            capture.call(row, arm, 3, [{'role': 'user', 'content': 'original'}])
            return {'answer': None, 'reason': None, 'status': 'missing_invalid_final_json', 'main_calls': 3, 'tool_calls': 2, 'observations': []}

        base.episode = episode
        completion = SimpleNamespace(decision=lambda *args: 'complete_once', prompt=lambda row: 'finalize',
                                     accepted_reply=lambda row, raw: {'answer': 'Yes', 'reason': 'seen', 'status': 'completed'})
        result = runner.run_episode(base, None, completion, {'question_id': 'q'}, 'M', None, {}, {}, None, paid, None, 'prior feedback')
        self.assertEqual(result['main_calls'], 4)
        self.assertEqual(result['completion_outcome'], 'accepted')
        self.assertEqual(calls, [('M', 'M')])

    def test_C41_dispatch_does_not_invoke_M_finalize(self):
        base = fake_base()
        r41 = SimpleNamespace(episode=lambda *args: {'answer': 'B', 'reason': 'seen', 'status': 'completed', 'main_calls': 6, 'tool_calls': 4})
        completion = SimpleNamespace(decision=lambda *args: self.fail('C41 used R43 finalize'))
        result = runner.run_episode(base, r41, completion, {}, 'C41', None, {}, {}, None, None, None, 'prior feedback')
        self.assertEqual((result['main_calls'], result['tool_calls']), (6, 4))

    def test_nested_tool_failure_stops_and_is_never_medical_memory(self):
        bad = {'status': 'completed', 'observation': {'finding_scores': {'error': 'CUDA failure'}},
               'actual_model_events': [{'status': 'failed'}]}
        bound = runner.BoundTools(SimpleNamespace(call=lambda *args: bad))
        with self.assertRaisesRegex(RuntimeError, 'tool_unhealthy_stop'):
            bound.call({}, {}, 'M', 1)
        event = {'question_id': 'q', 'ordinal': 1, 'image_key': 'same', 'reference_annotation': {'answer': 'B'}}
        entry = memory.memory_entry({'question_id': 'q', 'question': 'x'}, {'question_id': 'q', 'observations': [bad]}, event)
        self.assertEqual(entry['tool_evidence'], [])

    def test_fresh_error_never_writes_prediction_feedback_or_registers_failure(self):
        with tempfile.TemporaryDirectory() as name:
            frozen, out, vault = fixture(Path(name))
            base = fake_base()
            base.episode = lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError('tool_unhealthy_stop'))
            # progress is intentionally mutable operational state, unlike records.
            base.write = lambda path, value: (Path(path).parent.mkdir(parents=True, exist_ok=True), Path(path).write_text(json.dumps(value), encoding='utf-8'))
            with self.assertRaisesRegex(RuntimeError, 'generation_stopped'):
                runner.generate(frozen, out, base, None, None, ImmutableTransport(out), None, {}, {}, vault.after_prediction)
            self.assertFalse((out / 'predictions' / memory.ARM / 'q2.json').exists())
            self.assertFalse((out / 'feedback_events' / 'q2.json').exists())
            self.assertFalse((out / 'recovery').exists())
            self.assertEqual(memory.read(out / 'progress.json')['status'], 'stopped')


if __name__ == '__main__':
    unittest.main()
