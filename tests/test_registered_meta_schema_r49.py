"""Synthetic one-event META schema repair proof; no targets or endpoints."""
import ast
import copy
from io import BytesIO
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'experiments'))
import score_online_skill_r49 as scoring
from skill_prompts_r49 import MUTATE
from online_memory_r49 import now, read, save_once
from export_cxr_vqa_extension import RequestEvidencePublisher
from verify_public_online_skill_r49 import asset_normalizer
from PIL import Image


SOURCE = 'mutation_chexbench_slake_0004'
REPAIR = SOURCE+'_schema_1'
TARGET = 'synthetic_skill'


class Tests(unittest.TestCase):
    def fixture(self, root, *, none=False):
        content = {'name': 'Synthetic procedure', 'description': 'Inspect evidence',
                   'applicable_conditions': 'When relevant', 'branch': 'general', 'tool_name': None,
                   'task_category': 'presence', 'required_tools': [], 'risk_level': 'low',
                   'core_action': 'Inspect the actual image.'}
        snapshot = {'skills': {TARGET: {'c': content}}}
        trajectory = {'id': 'chexbench_slake_0004', 'row': {'images': ['/native/synthetic.png']}}
        payload = {'analysis': {'output_intent': 'PATCH'}, 'trajectory': trajectory,
                   'snapshot': snapshot['skills'], 'tools': []}
        original = {'operation': 'PATCH', 'patch_section': 'c', 'patch_target_id': TARGET,
                    'patch_content': {'core_action': 'synthetic invalid whole-container patch'}}
        fresh = {'operation': 'NONE'} if none else {'operation': 'PATCH', 'patch_section': 'core_action',
                  'patch_target_id': TARGET, 'patch_content': 'Inspect the requested region.'}
        instruction = scoring.META_SCHEMA_INSTRUCTION.format(target_json=json.dumps(TARGET, ensure_ascii=False))
        for event, system, draft, cost in ((SOURCE, MUTATE, original, '0.1'), (REPAIR, MUTATE+instruction, fresh, '0.2')):
            folder = root/'services/calls/R49-META'/event/'1'
            save_once(folder/'request.json', {'model': 'qwen3.7-plus', 'temperature': .2, 'top_p': .95,
                'max_tokens': 2048, 'messages': [{'role': 'system', 'content': system},
                    {'role': 'user', 'content': [{'type': 'text', 'text': json.dumps(payload, ensure_ascii=False)}]}]})
            save_once(folder/'started.json', {'request_id': event, 'utc': now()})
            save_once(folder/'response.json', {'choices': [{'message': {'content': json.dumps(draft)}, 'finish_reason': 'stop'}]})
            save_once(folder/'result.json', {'request_id': event, 'utc': now(), 'error': None,
                      'response_received': True, 'model_returned': 'qwen3.7-plus',
                      'usage': {'prompt_tokens': 2, 'completion_tokens': 1},
                      'settlement': {'charged_cny': cost}, 'elapsed_s': .5})
        save_once(root/'windows/0003/read_snapshot.json', snapshot)
        save_once(root/'windows/0003/trajectories/chexbench_slake_0004.json', trajectory)
        control = lambda value: {k: value.get(k) for k in ('operation', 'patch_section', 'patch_target_id')}
        registration = {'schema': 'r49_registered_meta_schema_repair_v1', 'recovery_id': 'meta_schema_1',
            'dataset': 'chexbench', 'arm': scoring.ARM, 'source_question_id': 'chexbench_slake_0004',
            'source_event': SOURCE, 'repair_event': REPAIR, 'window_index': 3, 'target_skill_id': TARGET,
            'original_call_relative': 'services/calls/R49-META/'+SOURCE+'/1',
            'repair_call_relative': 'services/calls/R49-META/'+REPAIR+'/1',
            'original_control': control(original), 'repair_control': control(fresh), 'repair_instruction': instruction,
            'same_original_payload': True, 'new_meta_calls': 1, 'extra_agent_calls': 0, 'extra_embedding_calls': 0,
            'extra_tool_calls': 0, 'automatic_invalid_to_none': False, 'new_clinical_information': False,
            'status': 'valid_meta_schema_repair_registered'}
        save_once(root/'failure_events/meta_schema_1_registration.json', registration)
        return registration

    def test_strict_PATCH_proof_and_both_META_charges_count_once(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); self.fixture(root)
            proof = scoring.registered_meta_schema_repair(root)
            value = scoring.resources(root, {}, [], {'physical': [], 'healthy': 0, 'registered': None}, proof)
            self.assertEqual(value['R49_META']['requests'], 2)
            self.assertEqual(value['R49_META']['usage_cost_cny_proxy_known'], '0.3')
            self.assertEqual(value['meta_schema_repair']['repair_request_resources']['requests'], 1)
            self.assertEqual(value['meta_schema_repair']['repair_request_resources']['usage_cost_cny_proxy_known'], '0.2')
            self.assertTrue(value['meta_schema_repair']['included_in_R49_META_totals'])

    def test_actual_model_NONE_allowed_but_original_invalid_not_coerced(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); self.fixture(root, none=True)
            self.assertEqual(scoring.registered_meta_schema_repair(root)['repair_draft'], {'operation': 'NONE'})
            path = root/'services/calls/R49-META'/SOURCE/'1/response.json'
            value = read(path); value['choices'][0]['message']['content'] = '{"operation":"NONE"}'
            path.write_text(json.dumps(value), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'actual_old_or_new_meta_control'):
                scoring.registered_meta_schema_repair(root)

    def test_changed_source_payload_or_an_unknown_send_stops(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); self.fixture(root)
            path = root/'services/calls/R49-META'/REPAIR/'1/request.json'
            value = read(path); payload = json.loads(value['messages'][1]['content'][0]['text'])
            payload['extra_fact'] = 'not in the original source'
            value['messages'][1]['content'][0]['text'] = json.dumps(payload)
            path.write_text(json.dumps(value), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'changed_source_payload'):
                scoring.registered_meta_schema_repair(root)
            (path.parent/'response.json').unlink()
            with self.assertRaisesRegex(ValueError, 'unclosed_request'):
                scoring.registered_meta_schema_repair(root)

    def test_new_bad_section_or_extra_repair_namespace_is_not_forgiven(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); registration = self.fixture(root)
            response = root/'services/calls/R49-META'/REPAIR/'1/response.json'
            value = read(response); draft = json.loads(value['choices'][0]['message']['content'])
            draft['patch_section'] = 'c'; value['choices'][0]['message']['content'] = json.dumps(draft)
            response.write_text(json.dumps(value), encoding='utf-8')
            path = root/'failure_events/meta_schema_1_registration.json'
            registration['repair_control']['patch_section'] = 'c'; path.write_text(json.dumps(registration), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'strict_allowed_section'):
                scoring.registered_meta_schema_repair(root)
            draft['patch_section'] = 'core_action'
            value['choices'][0]['message']['content'] = json.dumps(draft)
            response.write_text(json.dumps(value), encoding='utf-8')
            registration['repair_control']['patch_section'] = 'core_action'
            path.write_text(json.dumps(registration), encoding='utf-8')
            (root/'services/calls/R49-META'/(SOURCE+'_schema_2')).mkdir()
            with self.assertRaisesRegex(ValueError, 'unrecognized_meta_schema_repair_namespace'):
                scoring.registered_meta_schema_repair(root)

    def test_public_control_chain_works_without_private_image_paths(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); private = root/'private'; self.fixture(private)
            public = root/'public'; publisher = RequestEvidencePublisher(public, root/'unused.json')
            buffer = BytesIO(); Image.new('RGB', (2, 2), 'white').save(buffer, format='PNG')
            publisher.alias('/native/synthetic.png', publisher.put_image(buffer.getvalue()))
            for path in private.rglob('*.json'):
                publisher.copy_json(path, public/path.relative_to(private))
            publisher.emit(public/'image_assets.json', [{'path': publisher.rel(asset['target'], public/'image_assets.json')}
                                                       for asset in publisher.assets.values()])
            normalize = asset_normalizer(public); raw_read = scoring.read
            private.rename(root/'private_unavailable')
            with patch.object(scoring, 'read', side_effect=lambda p: normalize(raw_read(p), Path(p))):
                proof = scoring.registered_meta_schema_repair(public)
            self.assertEqual(proof['repair_draft']['operation'], 'PATCH')

    def test_instruction_matches_actual_operational_helper(self):
        repository = Path(__file__).resolve().parents[1]
        choices = [repository/'local_assets/recover_cxr_online_skill_r49_meta_schema.py',
                   repository/'reports/cxr_online_skill_r49_20261108/deployment_source/recover_cxr_online_skill_r49_meta_schema.py']
        source = next(path for path in choices if path.is_file())
        tree = ast.parse(source.read_text(encoding='utf-8'))
        actual = next(ast.literal_eval(node.value) for node in tree.body if isinstance(node, ast.Assign)
                      and any(isinstance(target, ast.Name) and target.id == 'REPAIR_INSTRUCTION' for target in node.targets))
        self.assertEqual(scoring.META_SCHEMA_INSTRUCTION, actual)


if __name__ == '__main__':
    unittest.main()
