"""Synthetic actual-assess/closed-META representative selection and public proof."""
import ast
import copy
from io import BytesIO
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'experiments'))
import score_online_skill_r49 as scoring
from online_memory_r49 import read, save_once
from skill_lifecycle_r49 import assess, DEFAULTS
from skill_prompts_r49 import ANALYZE
from export_cxr_vqa_extension import RequestEvidencePublisher
from verify_public_online_skill_r49 import asset_normalizer
from PIL import Image


def overwrite(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding='utf-8')


class Tests(unittest.TestCase):
    def actual_helpers(self):
        source = Path(__file__).resolve().parents[1]/'local_assets/recover_cxr_online_skill_r49_adoption.py'
        tree = ast.parse(source.read_text(encoding='utf-8'))
        constants = {node.targets[0].id: ast.literal_eval(node.value) for node in tree.body
                     if isinstance(node, ast.Assign) and len(node.targets) == 1
                     and isinstance(node.targets[0], ast.Name)
                     and node.targets[0].id in ('ANALYSIS_CLARIFICATION', 'SELECTION_INSTRUCTION')}
        self.assertEqual(constants['ANALYSIS_CLARIFICATION'], scoring.ANALYSIS_UNIQUE_CLARIFICATION)
        self.assertEqual(constants['SELECTION_INSTRUCTION'], scoring.ADOPTION_SELECTION_INSTRUCTION)
        names = {'duplicate_entries', 'effective_adoption', 'representative_choice', 'assessment_evolve_overlay'}
        nodes = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in names]
        def immutable(path, value):
            if path.is_file(): self.assertEqual(read(path), value)
            else: save_once(path, value)
        namespace = {'Path': Path, 'json': json, 'read': read, 'write_once': immutable, 'RECOVERY': 'adoption_1',
            'ARM': scoring.ARM, 'SOURCE_IDS': scoring.ADOPTION_SOURCES, 'DUPLICATE_SKILL': scoring.ADOPTION_SKILL,
            'SELECTION_INSTRUCTION': constants['SELECTION_INSTRUCTION']}
        exec(compile(ast.Module(body=nodes, type_ignores=[]), str(source), 'exec'), namespace)
        return namespace

    def call_record(self, root, event, messages, response, later=False):
        folder = root/'services/calls/R49-META'/event/'1'
        stamp = '2026-11-09T00:02:00Z' if later else '2026-11-09T00:00:00Z'
        request = {'model': 'qwen3.7-plus', 'temperature': .2, 'top_p': .95, 'max_tokens': 2048,
                   'extra_body': {'enable_thinking': False}, 'stream': False, 'messages': messages}
        for name, value in {'request': request, 'started': {'request_id': event, 'utc': stamp},
            'response': {'choices': [{'message': {'content': json.dumps(response)}}]},
            'result': {'request_id': event, 'utc': stamp, 'response_received': True, 'error': None,
                'model_returned': 'qwen3.7-plus', 'usage': {'prompt_tokens': 4, 'completion_tokens': 1},
                'elapsed_s': 1., 'settlement': {'charged_cny': '1'}}}.items(): save_once(folder/(name+'.json'), value)
        return folder

    def fixture(self, root, bad_choice=None):
        helper = self.actual_helpers(); window = root/'windows/0006'
        ids = ['synthetic_'+str(i) for i in range(211)]
        ids[196:198] = list(scoring.ADOPTION_SOURCES); ids[210] = 'synthetic_future'
        save_once(root/'manifest.json', {'dataset': 'chexbench', 'order': [{'question_id': qid} for qid in ids]})
        skill = lambda: {'c': {'branch': 'task_level'}, 'u': .5, 'u_by_category': {}, 'usage': 0, 'last_reinforced': 0}
        snapshot = {'skills': {scoring.ADOPTION_SKILL: skill(), 'other': skill()}, 'baselines': {},
                    'clock': 180, 'window': 6, 'frozen': False}
        save_once(window/'read_snapshot.json', snapshot)
        batch = []; analyses = {}
        for qid in scoring.ADOPTION_SOURCES:
            trajectory = {'id': qid, 'injected': [scoring.ADOPTION_SKILL, 'other'], 'steps': [{}, {}, {}],
                          'category': 'presence', 'reward': 1}
            analysis = {'skill_adoption': [
                {'skill_id': scoring.ADOPTION_SKILL, 'status': 'ADOPTED_POSITIVE', 'step_index': 0, 'evidence': 'synthetic first step'},
                {'skill_id': scoring.ADOPTION_SKILL, 'status': 'ADOPTED_POSITIVE', 'step_index': 1, 'evidence': 'synthetic second step'},
                {'skill_id': 'other', 'status': 'IGNORED'}], 'extracted_pattern': 'synthetic unchanged', 'output_intent': 'NONE'}
            batch.append(trajectory); analyses[qid] = analysis
            save_once(window/'trajectories'/(qid+'.json'), trajectory)
            messages = [{'role': 'system', 'content': ANALYZE}, {'role': 'user', 'content': [
                {'type': 'text', 'text': json.dumps({'trajectory': trajectory, 'available_tools': []}, ensure_ascii=False)},
                {'type': 'image_url', 'image_url': {'url': '/native/synthetic.png'}}]}]
            self.call_record(root, 'analysis_'+qid, messages, analysis)
        original_analyses = copy.deepcopy(analyses); module = types.SimpleNamespace(assess=assess)
        fixture = self
        class Service:
            def call(self, row, arm, ordinal, messages):
                self_event = row['question_id']; self_qid = self_event.removeprefix('analysis_').removesuffix('_adoption_1')
                answer = bad_choice if bad_choice is not None else {'selected_duplicate_index': scoring.ADOPTION_SOURCES.index(self_qid)}
                fixture.call_record(root, self_event, messages, answer, later=True)
                return json.dumps(answer)
        def original_evolve(service, snapshot, batch, wi, window, data, tools, config):
            self.assertEqual(analyses, original_analyses)  # Cached write/MUTATE source remains original.
            result = copy.deepcopy(snapshot); result['clock'] += len(batch)
            credits = module.assess(result, batch, analyses, config)
            save_once(window/'events.json', {'write': [], 'credit': credits, 'govern': []})
            return result
        recovery = root/'standalone_recovery'
        evolve = helper['assessment_evolve_overlay'](original_evolve, module, recovery, 'chexbench',
                                                    {'window_question_ids': list(scoring.ADOPTION_SOURCES)})
        result = evolve(Service(), snapshot, batch, 6, window, root, [], DEFAULTS)
        self.assertEqual(analyses, original_analyses)
        amendment = {'schema': 'r49_analysis_unique_adoption_amendment_v1', 'recovery_id': 'adoption_1',
            'dataset': 'chexbench', 'arm': scoring.ARM, 'activation_committed_questions': 210,
            'original_system': ANALYZE, 'clarification': scoring.ANALYSIS_UNIQUE_CLARIFICATION,
            'ordinary_event_rule': "system == original ANALYZE and event == 'analysis_' + payload['trajectory']['id']",
            'extra_ordinary_meta_calls': 0, 'automatic_future_repair': False, 'new_clinical_information': False,
            'status': 'active', 'protected_original_events': ['analysis_'+qid for qid in scoring.ADOPTION_SOURCES],
            'utc': '2026-11-09T00:01:00Z'}
        save_once(root/'failure_events/analysis_unique_adoption_amendment.json', amendment)
        return result, original_analyses

    def test_actual_overlay_keeps_write_inputs_and_credits_once_and_charges_choices_once(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); repo, original = self.fixture(root)
            proof = scoring.registered_adoption_repair(root)
            self.assertEqual(repo['skills'][scoring.ADOPTION_SKILL]['usage'], 2)
            self.assertEqual(len(read(root/'windows/0006/events.json')['credit']), 2)
            self.assertEqual([item['selected_duplicate_index'] for item in proof['repairs']], [0, 1])
            for qid, item in zip(scoring.ADOPTION_SOURCES, proof['repairs']):
                self.assertEqual(item['effective_adoption'][-1], original[qid]['skill_adoption'][-1])
                self.assertEqual(len(original[qid]['skill_adoption']), 3)
            resources = scoring.resources(root, {}, [], {'physical': [], 'healthy': 0, 'registered': None},
                adoption_repair=proof, analysis_unique_amendment=scoring.validate_analysis_unique_amendment(root))
            self.assertEqual(resources['R49_META']['requests'], 4)
            self.assertEqual(resources['R49_META']['usage_cost_cny_proxy_known'], '4')
            self.assertEqual(resources['adoption_repair']['repair_request_resources']['requests'], 2)
            self.assertTrue(resources['adoption_repair']['included_in_R49_META_totals'])

    def test_bad_fresh_choice_stays_archived_and_never_registers_or_auto_ignores(self):
        for answer in ({'selected_duplicate_index': True}, {'selected_duplicate_index': 2},
                       {'selected_duplicate_index': 0, 'evidence': 'invented'}):
            with self.subTest(answer=answer), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                with self.assertRaises(ValueError): self.fixture(root, bad_choice=answer)
                self.assertFalse((root/'failure_events/adoption_1_registration.json').exists())
                self.assertTrue((root/'services/calls/R49-META/analysis_chexbench_slake_0081_adoption_1/1/response.json').is_file())
                with self.assertRaisesRegex(ValueError, 'unregistered_adoption_choice'): scoring.registered_adoption_repair(root)

    def test_rewritten_entry_double_credit_or_write_payload_change_is_rejected(self):
        for mode in ('entry', 'credit', 'write'):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as temp:
                root = Path(temp); _, original = self.fixture(root)
                if mode == 'entry':
                    path = root/'failure_events/adoption_1_registration.json'; value = read(path)
                    value['repairs'][0]['effective_adoption'][0]['evidence'] = 'rewritten'; overwrite(path, value)
                elif mode == 'credit':
                    path = root/'windows/0006/events.json'; value = read(path); value['credit'].append(value['credit'][0]); overwrite(path, value)
                else:
                    altered = copy.deepcopy(original[scoring.ADOPTION_SOURCES[0]]); altered['skill_adoption'] = []
                    overwrite(root/'services/calls/R49-META/mutation_chexbench_slake_0081/1/request.json',
                        {'messages': [{}, {'content': [{'text': json.dumps({'analysis': altered})}]}]})
                with self.assertRaises(ValueError): scoring.registered_adoption_repair(root)

    def test_future_clarifier_boundary_and_extra_unknown_namespace(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); self.fixture(root)
            trajectory = {'id': 'synthetic_future'}; save_once(root/'windows/0007/trajectories/synthetic_future.json', trajectory)
            messages = [{'role': 'system', 'content': ANALYZE+scoring.ANALYSIS_UNIQUE_CLARIFICATION},
                        {'role': 'user', 'content': [{'type': 'text', 'text': json.dumps({'trajectory': trajectory})}]}]
            folder = self.call_record(root, 'analysis_synthetic_future', messages, {}, later=True)
            stats = scoring.validate_analysis_unique_amendment(root)
            self.assertEqual((stats['original_system_requests'], stats['clarified_system_requests']), (2, 1))
            changed = read(folder/'request.json'); changed['messages'][0]['content'] = ANALYZE; overwrite(folder/'request.json', changed)
            with self.assertRaisesRegex(ValueError, 'new_or_unprotected'): scoring.validate_analysis_unique_amendment(root)
            (root/'services/calls/R49-META/analysis_extra_adoption_2').mkdir()
            with self.assertRaisesRegex(ValueError, 'extra_adoption_repair'): scoring.registered_adoption_repair(root)

    def test_public_proof_keeps_nested_source_assets_without_private_archive(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); private = root/'private'; self.fixture(private)
            public = root/'public'; publisher = RequestEvidencePublisher(public, root/'unused.json')
            buffer = BytesIO(); Image.new('RGB', (2, 2), 'white').save(buffer, format='PNG')
            publisher.alias('/native/synthetic.png', publisher.put_image(buffer.getvalue()))
            for path in private.rglob('*.json'):
                if 'standalone_recovery' not in path.parts: publisher.copy_json(path, public/path.relative_to(private))
            publisher.emit(public/'image_assets.json', [{'path': publisher.rel(asset['target'], public/'image_assets.json')}
                                                       for asset in publisher.assets.values()])
            private.rename(root/'private_unavailable'); normalize = asset_normalizer(public); raw_read = scoring.read
            with patch.object(scoring, 'read', side_effect=lambda p: normalize(raw_read(p), Path(p))):
                self.assertEqual(len(scoring.registered_adoption_repair(public)['repairs']), 2)
                self.assertEqual(scoring.validate_analysis_unique_amendment(public)['original_system_requests'], 2)


if __name__ == '__main__': unittest.main()
