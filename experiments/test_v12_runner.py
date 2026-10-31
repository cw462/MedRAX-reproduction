"""Synthetic execution-boundary tests; no providers, tools, labels or ledger."""
import copy
import json
from pathlib import Path
import sys
import tempfile
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_v12_ab as runner
from v12_evidence import classify_tool_return, observation_projection


def image(image_id='image:1', modality='CXR'):
    return {'image_id': image_id, 'path': '/synthetic/' + image_id.replace(':', '_') + '.png',
            'size': [480, 500], 'role': 'original', 'modality': modality,
            'figure_label': 'Figure ' + image_id[-1], 'comparison_object': 'unknown'}


class RunnerBoundaries(unittest.TestCase):
    def test_model_inputs_hide_initial_answer_and_keep_full_options_with_equal_caps(self):
        calls, caps = [], []
        mae = ModuleType('memory_agent_eval')
        mae.BudgetedModel = lambda *args: object()
        mae.TrackedTool = Mock(side_effect=AssertionError('real tool forbidden'))
        recovery = ModuleType('run_bc_recovery')
        def new_ctx(qid, thread_id, images, runtime, args, trace, tool_cap, model_cap):
            caps.append((tool_cap, model_cap))
            return {'thread_id': thread_id, 'actual_model_calls': 0,
                    'actual_tool_attempts': 0, 'usage_records': [], 'issues': set()}
        recovery.new_ctx = new_ctx
        row = {'question_id': 'synthetic', 'question': 'Which pattern is supported?\nA) Smooth\nB) Irregular\nC) Unresolved'}
        raw = {'first_answer': 'A', 'observations': [], 'hypotheses': [],
               'patient_conditions': [], 'discriminators': [], 'uncertainties': [],
               'image_metadata': [{'image_id': 'image:1', 'modality': 'CXR',
                                   'comparison_object': 'left opacity'}]}
        observation = observation_projection(raw)
        def fake_call(model, ctx, prompt, payload, images, extras, folder, filename):
            calls.append((ctx['arm'], filename, copy.deepcopy(payload)))
            ctx['actual_model_calls'] += 1
            if filename == 'plan':
                return json.dumps({'actions': [{'kind': 'visual', 'image_id': 'image:1',
                    'question': 'Is the margin smooth?', 'expected_attribute': 'margin'}]})
            if filename == 'targeted_read':
                return json.dumps({'candidate_answer': 'B', 'observations': [], 'hypotheses': [], 'uncertainties': ['margin unresolved']})
            return json.dumps({'answer': 'C', 'uncertain': True, 'observations': [],
                'option_checks': [{'option': x, 'support': [], 'conflict': [], 'unknown': ['margin']} for x in 'ABC'],
                'missing_evidence': []})
        retriever = SimpleNamespace(retrieve=Mock(return_value={'k_block': '', 'e_block': '', 'k_ids': [], 'e_ids': []}))
        runtime = SimpleNamespace(model=object(), tools={}, tool_provenance={})
        with tempfile.TemporaryDirectory() as directory, patch.dict(sys.modules, {
                'memory_agent_eval': mae, 'run_bc_recovery': recovery}), patch.object(runner, 'call', fake_call):
            args = SimpleNamespace(run_id='synthetic', artifact_root=Path(directory))
            results = [runner.run_branch(runtime, None, None, args, row, [image()], observation,
                       None, retriever, group, Path(directory)/group, initial_answer='A') for group in ('B', 'A')]
        self.assertEqual(caps, [(2, 3), (2, 3)])
        for result in results:
            self.assertEqual(result['status'], 'completed', result.get('error'))
            self.assertEqual(result['answer'], 'C')
            self.assertEqual(result['solver_answer'], 'C')
            self.assertEqual(result['candidate_answer'], 'B')
            self.assertFalse(result['fallback_to_initial'])
            self.assertEqual(result['accounting']['model_calls'], 3)
            self.assertEqual(result['accounting']['tool_calls'], 0)
        self.assertEqual([item[1] for item in calls], ['plan', 'targeted_read', 'final'] * 2)
        for group, filename, payload in calls:
            self.assertNotIn('first_answer', json.dumps(payload))
            self.assertNotIn('candidate_answer', json.dumps(payload))
            self.assertEqual(payload['full_question_and_all_options'], row['question'])
            if filename in ('plan', 'final'):
                self.assertEqual(payload['shared_first_observation'], observation)
        self.assertEqual(raw['first_answer'], 'A')
        self.assertEqual(retriever.retrieve.call_count, 2)

    def test_failure_falls_back_only_in_controller_and_only_with_legal_initial(self):
        mae = ModuleType('memory_agent_eval')
        mae.BudgetedModel = lambda *args: object()
        mae.TrackedTool = Mock(side_effect=AssertionError('tool must not execute'))
        recovery = ModuleType('run_bc_recovery')
        recovery.new_ctx = lambda *args: {'thread_id': 'synthetic', 'actual_model_calls': 0,
                                         'actual_tool_attempts': 0, 'issues': set()}
        runtime = SimpleNamespace(model=object(), tools={}, tool_provenance={})
        retriever = SimpleNamespace(retrieve=Mock(return_value={}))
        row = {'question_id': 'synthetic', 'question': 'Pattern?\nA) Smooth\nB) Irregular\nC) Unresolved'}
        observation = {'observations': [], 'hypotheses': [], 'patient_conditions': [],
                       'discriminators': [], 'uncertainties': [], 'image_metadata': []}
        captured = []
        def fake_call(model, ctx, prompt, payload, images, extras, folder, filename):
            captured.append(copy.deepcopy(payload));ctx['actual_model_calls'] += 1
            if filename == 'plan': return '{"actions":[]}'
            if filename == 'targeted_read':
                return '{"candidate_answer":"B","observations":[],"hypotheses":[],"uncertainties":[]}'
            raise RuntimeError('synthetic final provider error')
        with tempfile.TemporaryDirectory() as directory, patch.dict(sys.modules, {
                'memory_agent_eval': mae, 'run_bc_recovery': recovery}), patch.object(runner, 'call', fake_call):
            args = SimpleNamespace(run_id='synthetic', artifact_root=Path(directory))
            for index,first in enumerate(('A', None, 'F')):
                result = runner.run_branch(runtime, None, None, args, row, [image()], observation,
                    None, retriever, 'B', Path(directory)/str(index), initial_answer=first)
                self.assertEqual(result['status'], 'fallback_initial' if first == 'A' else 'failed')
                self.assertEqual(result['answer'], 'A' if first == 'A' else None)
                self.assertEqual(result['fallback_to_initial'], first == 'A')
                self.assertIsNone(result['solver_answer'])
                self.assertEqual(result['candidate_answer'], 'B')
                self.assertIn('synthetic final provider error', result['error'])
                self.assertEqual(result['accounting']['model_calls'], 3)
        for payload in captured:
            self.assertNotIn('first_answer', json.dumps(payload))
            self.assertNotIn('candidate_answer', json.dumps(payload))

    def test_unusable_tool_returns_never_become_patient_evidence(self):
        for raw in ('No', 'pneumothorax', {'error': 'CUDA out of memory'}):
            item = runner.evidence_for_model([{'evidence_ref': 'B:tool:1', 'result': raw,
                       'classification': classify_tool_return(raw)}])[0]
            self.assertFalse(item['classification']['usable'])
            self.assertIsNone(item['patient_evidence'])
            self.assertNotIn('result', item)
            self.assertNotIn('unverified_tool_hypothesis', item)

    def test_generic_xray_and_ct_never_enable_chest_report(self):
        for name in ('CT', 'Xray', 'radiograph', 'unknown'):
            self.assertFalse(runner.tool_allowed('chest_xray_report_generator', image(modality=runner.modality(name))), name)
        self.assertTrue(runner.tool_allowed('chest_xray_report_generator', image(modality=runner.modality('CXR'))))

    def test_comparison_object_survives_image_binding(self):
        bound = runner.bound_images([image()], {'image_metadata': [{'image_id': 'image:1',
            'modality': 'CT', 'comparison_object': 'left upper lobe lesion',
            'timepoint': 'follow-up', 'timepoint_source_quote': 'follow-up'}]})
        self.assertEqual(bound[0]['comparison_object'], 'left upper lobe lesion')
        self.assertEqual(bound[0]['timepoint'], 'follow-up')
        self.assertEqual(bound[0]['figure_label'], 'Figure 1')

    def test_single_image_tool_cannot_silently_drop_second_image(self):
        schema = SimpleNamespace(model_json_schema=lambda: {'properties': {'image_path': {}, 'question': {}}})
        tool = SimpleNamespace(name='llava_med_qa', args_schema=schema)
        action = {'image_id': 'image:1', 'image_ids': ['image:1', 'image:2'],
                  'question': 'Compare the same lesion', 'tool_args': {}}
        with self.assertRaises(ValueError):
            runner.prepare_tool_args(action, tool, [image(), image('image:2')])

    def test_thin_crop_is_rejected_before_any_image_operation(self):
        fake = ModuleType('v10_visual')
        fake.crop_image = Mock(side_effect=AssertionError('no image operation expected'))
        with patch.dict(sys.modules, {'v10_visual': fake}), self.assertRaisesRegex(ValueError, 'minimum'):
            runner.checked_crop({'image_id': 'image:1', 'box': [0, 0, .1, .01]}, [image()], Path('/unused'))
        fake.crop_image.assert_not_called()

    def test_completed_run_is_read_only_and_does_not_initialize_provider(self):
        rows = [{'question_id': 'q' + str(i)} for i in range(60)]
        initials = [{'question_id': r['question_id'], 'status': 'completed'} for r in rows]
        branches = [{'question_id': r['question_id'], 'group': group, 'status': 'completed'}
                    for group in ('B', 'A') for r in rows]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for filename, records in [('initial_results.jsonl', initials), ('branch_results.jsonl', branches)]:
                (root/filename).write_text(''.join(json.dumps(r) + '\n' for r in records))
            before = {p.name: p.read_bytes() for p in root.iterdir()}
            with patch.object(runner, 'prepare', return_value={'rows': rows}), \
                    patch.object(runner, 'initial_read', side_effect=AssertionError('no repeated initial')), \
                    patch.object(runner, 'run_branch', side_effect=AssertionError('no repeated branch')):
                code = runner.run(SimpleNamespace(prepare_only=False, api_key_stdin=False), {'root': directory}, root)
            self.assertEqual(code, 0)
            self.assertEqual(json.loads((root/'status.json').read_text())['status'], 'generation_complete')
            for filename, content in before.items():
                self.assertEqual((root/filename).read_bytes(), content)

    def test_complete_counts_do_not_accept_unknown_ids_wrong_order_or_nonterminals(self):
        rows = [{'question_id': 'q' + str(i)} for i in range(60)]
        for kind in ('unknown_id', 'wrong_order', 'nonterminal'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                initials = [{'question_id': r['question_id'], 'status': 'completed'} for r in rows]
                branches = [{'question_id': r['question_id'], 'group': group, 'status': 'completed'}
                            for group in ('B', 'A') for r in rows]
                if kind == 'unknown_id':
                    initials[-1]['question_id'] = 'unplanned'
                elif kind == 'wrong_order':
                    branches = branches[60:] + branches[:60]
                else:
                    branches[-1]['status'] = 'running'
                for filename, records in [('initial_results.jsonl', initials), ('branch_results.jsonl', branches)]:
                    (root/filename).write_text(''.join(json.dumps(r) + '\n' for r in records))
                with patch.object(runner, 'prepare', return_value={'rows': rows}), self.assertRaises(ValueError):
                    runner.run(SimpleNamespace(prepare_only=False, api_key_stdin=False), {'root': directory}, root)

    def test_last_terminal_append_recovery_needs_no_provider_or_api_key(self):
        rows = [{'question_id': 'q' + str(i)} for i in range(60)]
        initials = [{'question_id': r['question_id'], 'status': 'completed'} for r in rows]
        branches = [{'question_id': r['question_id'], 'group': group, 'status': 'completed'}
                    for group in ('B', 'A') for r in rows]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for filename, records in [('initial_results.jsonl', initials), ('branch_results.jsonl', branches[:-1])]:
                (root/filename).write_text(''.join(json.dumps(r) + '\n' for r in records))
            checkpoint = root/'checkpoints'/'q59'/'A'/'terminal.json'
            checkpoint.parent.mkdir(parents=True)
            checkpoint.write_text(json.dumps(branches[-1]))
            with patch.object(runner, 'prepare', return_value={'rows': rows}), \
                    patch.object(runner, 'run_branch', side_effect=AssertionError('do not regenerate terminal')):
                code = runner.run(SimpleNamespace(prepare_only=False, api_key_stdin=False), {'root': directory}, root)
            self.assertEqual(code, 0)
            self.assertEqual(runner.read_jsonl(root/'branch_results.jsonl'), branches)
            self.assertEqual(json.loads((root/'status.json').read_text())['status'], 'generation_complete')


if __name__ == '__main__':
    unittest.main()
