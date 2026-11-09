"""Synthetic fixed-case-2 and protected ordinary prompt boundary checks."""
import ast
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'experiments'))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_registered_meta_schema_r49 as first_case
import score_online_skill_r49 as scoring
from skill_prompts_r49 import MUTATE
from online_memory_r49 import read, save_once

SOURCE2 = 'mutation_chexbench_slake_0013'
REPAIR2 = SOURCE2+'_schema_2'
FUTURE = 'synthetic_future'


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8')


class Tests(unittest.TestCase):
    def fixture(self, root):
        first_case.Tests().fixture(root)
        reg1 = read(root/'failure_events/meta_schema_1_registration.json')
        snapshot = read(root/'windows/0003/read_snapshot.json')
        trajectory = {'id': 'chexbench_slake_0013', 'row': {'images': ['/native/synthetic.png']}}
        payload = {'analysis': {'output_intent': 'PATCH'}, 'trajectory': trajectory,
                   'snapshot': snapshot['skills'], 'tools': []}
        instruction = scoring.META_SCHEMA_2_INSTRUCTION.format(target_json=json.dumps(reg1['target_skill_id'], ensure_ascii=False))
        for event, template, system in ((SOURCE2, first_case.SOURCE, MUTATE),
                                        (REPAIR2, first_case.REPAIR, MUTATE+instruction)):
            old_folder = root/'services/calls/R49-META'/template/'1'
            folder = root/'services/calls/R49-META'/event/'1'
            for name in ('request', 'started', 'response', 'result'):
                value = copy.deepcopy(read(old_folder/(name+'.json')))
                if name == 'request':
                    value['messages'][0]['content'] = system
                    value['messages'][1]['content'][0]['text'] = json.dumps(payload, ensure_ascii=False)
                if name in ('started', 'result'):
                    value['request_id'] = event
                if name == 'response' and event == SOURCE2:
                    draft = json.loads(value['choices'][0]['message']['content']); draft['patch_section'] = 'content'
                    value['choices'][0]['message']['content'] = json.dumps(draft)
                save_once(folder/(name+'.json'), value)
        reg2 = copy.deepcopy(reg1)
        reg2.update(schema='r49_registered_meta_schema_repair_v2', recovery_id='mutation_fields_2',
                    source_question_id='chexbench_slake_0013', source_event=SOURCE2, repair_event=REPAIR2,
                    window_index=4, repair_instruction=instruction,
                    original_call_relative='services/calls/R49-META/'+SOURCE2+'/1',
                    repair_call_relative='services/calls/R49-META/'+REPAIR2+'/1')
        reg2['original_control']['patch_section'] = 'content'
        save_once(root/'failure_events/meta_schema_2_registration.json', reg2)
        save_once(root/'windows/0004/read_snapshot.json', snapshot)
        save_once(root/'windows/0004/trajectories/chexbench_slake_0013.json', trajectory)
        ids = ['synthetic_'+str(i) for i in range(151)]
        ids[90], ids[120], ids[150] = 'chexbench_slake_0004', 'chexbench_slake_0013', FUTURE
        save_once(root/'manifest.json', {'dataset': 'chexbench', 'defaults': {'window': 30},
                  'order': [{'question_id': qid} for qid in ids]})
        amendment = {'schema': 'r49_mutation_fields_amendment_v1', 'recovery_id': 'mutation_fields_2',
              'dataset': 'chexbench', 'arm': scoring.ARM, 'original_system': MUTATE,
              'clarification': scoring.MUTATION_FIELDS_CLARIFICATION,
              'allowed_sections': ['name', 'description', 'applicable_conditions', 'required_tools', 'risk_level', 'core_action'],
              'ordinary_event_rule': "system == original MUTATE and event == 'mutation_' + payload['trajectory']['id']",
              'protected_original_events': sorted([first_case.SOURCE, SOURCE2]),
              'extra_ordinary_meta_calls': 0, 'new_clinical_information': False, 'same_original_payload': True,
              'cached_original_or_clarified_replay': True, 'automatic_future_repair': False, 'status': 'active',
              'committed_questions_at_activation': 150, 'utc': '2026-12-01T00:00:00+00:00'}
        save_once(root/'failure_events/mutation_fields_2_amendment.json', amendment)
        future = {'id': FUTURE, 'row': {'images': ['/native/synthetic.png']}}
        payload['trajectory'] = future
        save_once(root/'windows/0005/read_snapshot.json', snapshot)
        save_once(root/'windows/0005/trajectories'/(FUTURE+'.json'), future)
        folder = root/'services/calls/R49-META'/('mutation_'+FUTURE)/'1'
        for name in ('request', 'started', 'response', 'result'):
            value = copy.deepcopy(read(root/'services/calls/R49-META'/REPAIR2/'1'/(name+'.json')))
            if name == 'request':
                value['messages'][0]['content'] = MUTATE+scoring.MUTATION_FIELDS_CLARIFICATION
                value['messages'][1]['content'][0]['text'] = json.dumps(payload, ensure_ascii=False)
            if name in ('started', 'result'):
                value['request_id'] = 'mutation_'+FUTURE; value['utc'] = '2026-12-02T00:00:00+00:00'
            save_once(folder/(name+'.json'), value)
        return amendment

    def test_two_fixed_repairs_and_original_clarified_counts_without_extra_ordinary_calls(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); self.fixture(root)
            proofs = scoring.registered_meta_schema_repairs(root)
            self.assertIsNotNone(proofs['meta_schema_1']); self.assertIsNotNone(proofs['meta_schema_2'])
            self.assertEqual(scoring.registered_meta_schema_repair(root)['registration']['source_event'], first_case.SOURCE)
            modes = scoring.validate_mutation_fields_amendment(root)
            self.assertEqual((modes['original_system_requests'], modes['clarified_system_requests']), (2, 1))
            self.assertEqual(modes['extra_ordinary_meta_calls'], 0)
            resource = scoring.resources(root, {}, [], {'physical': [], 'healthy': 0, 'registered': None},
                                         proofs['meta_schema_1'], proofs['meta_schema_2'], modes)
            self.assertEqual(resource['R49_META']['requests'], 5)
            self.assertEqual(resource['meta_schema_repair']['added_meta_requests'], 1)
            self.assertEqual(resource['meta_schema_repair_2']['added_meta_requests'], 1)

    def test_unknown_prompt_or_reclassified_old_event_stops(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); amendment = self.fixture(root)
            path = root/'services/calls/R49-META'/('mutation_'+FUTURE)/'1/request.json'
            value = read(path); value['messages'][0]['content'] += 'Unrecognized change.'
            write(path, value)
            with self.assertRaisesRegex(ValueError, 'unrecognized_ordinary_mutation_system'):
                scoring.validate_mutation_fields_amendment(root)
            value['messages'][0]['content'] = MUTATE+scoring.MUTATION_FIELDS_CLARIFICATION; write(path, value)
            amendment['protected_original_events'].append('mutation_'+FUTURE)
            amendment['protected_original_events'].sort()
            write(root/'failure_events/mutation_fields_2_amendment.json', amendment)
            with self.assertRaisesRegex(ValueError, 'valid_declared_boundary'):
                scoring.validate_mutation_fields_amendment(root)

    def test_no_undeclared_second_repair_or_generic_third_namespace(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); self.fixture(root)
            (root/'failure_events/mutation_fields_2_amendment.json').unlink()
            with self.assertRaisesRegex(ValueError, 'requires_the_declared'):
                scoring.validate_mutation_fields_amendment(root)
            (root/'services/calls/R49-META/mutation_other_schema_3').mkdir()
            with self.assertRaisesRegex(ValueError, 'unrecognized_meta_schema_repair_namespace'):
                scoring.registered_meta_schema_repairs(root)

    def test_literals_match_actual_operational_helper(self):
        repository = Path(__file__).resolve().parents[1]
        paths = [repository/'local_assets/recover_cxr_online_skill_r49_mutation_fields.py',
                 repository/'reports/cxr_online_skill_r49_20261108/deployment_source/recover_cxr_online_skill_r49_mutation_fields.py']
        source = next(path for path in paths if path.is_file())
        tree = ast.parse(source.read_text(encoding='utf-8'))
        literals = {target.id: ast.literal_eval(node.value) for node in tree.body if isinstance(node, ast.Assign)
                    for target in node.targets if isinstance(target, ast.Name) and target.id in ('FIELDS_CLARIFICATION', 'REPAIR_INSTRUCTION')}
        self.assertEqual(scoring.MUTATION_FIELDS_CLARIFICATION, literals['FIELDS_CLARIFICATION'])
        self.assertEqual(scoring.META_SCHEMA_2_INSTRUCTION, literals['REPAIR_INSTRUCTION'])


if __name__ == '__main__':
    unittest.main()
