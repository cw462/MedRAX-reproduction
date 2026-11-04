"""Focused offline regressions for the four tools-v2 defects; no paid clients."""
import ast
from dataclasses import dataclass
import json
import logging
from pathlib import Path
import sys
from types import SimpleNamespace
import typing
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'experiments'))
from skemex_adapter.evidence_revision import (reflection_steps, parse_bound_answer,
    report_projection, skill_policy_rejection, TOOL_CONTRACT)
from skemex_adapter.tool_episode import parse_plan
from skemex_adapter.transport import RequestAdapter


class EvidenceRevision(unittest.TestCase):
    def setUp(self):
        self.row = {'question_id': 'q', 'case_id': 'c',
                    'question': 'Which finding explains the opacity?\nA) Left lung collapse\nB) Massive left pleural effusion',
                    'images': ['figures/c/x.jpg']}

    def test_real_official_encode_request_has_untruncated_source_context(self):
        # Execute upstream encoder class and prompt builder unchanged. Omit only
        # platform/provider imports so this test runs on Windows with a fake LLM.
        folder = ROOT / 'third_party/skemex/src/medmem_agent/evolution'
        ns = dict(vars(typing), dataclass=dataclass, json=json, logger=logging.getLogger(__name__),
                  LLMConfig=object, EvoConfig=object, SkillStore=object,
                  ContentFilterError=type('FakeFilter', (Exception,), {}))
        exec(compile((folder/'types.py').read_text(encoding='utf-8'), 'upstream/types.py', 'exec'), ns)
        exec(compile((folder/'prompts.py').read_text(encoding='utf-8'), 'upstream/prompts.py', 'exec'), ns)
        tree = ast.parse((folder/'encode.py').read_text(encoding='utf-8'))
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'TrajectoryEncoder')
        exec(compile(ast.Module(body=[cls], type_ignores=[]), 'upstream/encode.py', 'exec'), ns)
        observed = []
        def generate(**kwargs):
            observed.append(kwargs)
            return SimpleNamespace(content='{"output_intent":"NONE","extracted_pattern":"no rule"}')
        encoder = ns['TrajectoryEncoder'](None, SimpleNamespace(
            context_guard=SimpleNamespace(context_trim_observation_chars=4),
            encode=SimpleNamespace(model='offline')))
        prediction = {'answer': 'A', 'raw_response': 'Answer A; reason says effusion',
                      'trajectory_steps': [{'action': 'answer', 'answer': 'A'}],
                      'tool_observations': [{'usable': True, 'model_observation': {'static_report': 'effusion evidence sentinel'}}]}
        trajectory = ns['Trajectory'](id='q', dataset='ChestAgentBench', query='unused',
            steps=reflection_steps(self.row, prediction, 'B', [{'result': 'raw report sentinel'}]),
            ground_truth='B', eval_result=0.0)
        with patch.object(type(encoder), '_build_llm', return_value=SimpleNamespace(generate=generate)):
            encoder.encode(trajectory, TOOL_CONTRACT)
        sent = observed[0]['user_prompt']
        for value in ('Which finding explains', 'Left lung collapse', 'Massive left pleural effusion',
                      'old_answer_text', 'correct_answer_text', 'effusion evidence sentinel', 'raw report sentinel'):
            self.assertIn(value, sent)

    def test_letter_and_verbatim_option_are_required_at_actual_worker_parser(self):
        adapter = RequestAdapter([], self.row, True, [], bound_options=True)
        options = adapter.legal(self.row)
        good = {'answer': 'B', 'option_text': options['B'], 'reason': 'Effusion is supported.'}
        self.assertEqual(adapter.parse(json.dumps(good), options)['answer'], 'B')
        bad = dict(good, answer='A')
        value = adapter.parse(json.dumps(bad), options)
        self.assertIsNone(value['answer'])
        self.assertEqual(value['answer_contract_error'], 'letter_option_text_mismatch')
        self.assertIsNone(parse_bound_answer('Answer: B', options)['answer'])

    def test_optional_tool_plan_does_not_change_v1(self):
        empty = '{"calls":[],"reason":"No relevant additional evidence"}'
        self.assertEqual(parse_plan(empty, self.row, self.row['images'], optional=True)['calls'], [])
        with self.assertRaises(ValueError):
            parse_plan(empty, self.row, self.row['images'])

    def test_single_image_temporal_claims_withheld_static_claims_unverified(self):
        raw = 'Large left pleural effusion. Interval increase in opacity. Improved aeration. No pneumothorax.'
        view = report_projection(raw)
        self.assertEqual(view['withheld_temporal_clause_count'], 2)
        self.assertIn('Large left pleural effusion', view['static_report'])
        self.assertNotIn('Interval increase', json.dumps(view))
        self.assertFalse(view['chronology_evidence'])
        self.assertIn('Interval increase', raw)

    def test_known_unsafe_rules_rejected_but_limitations_learnable(self):
        for text in ('Invoke chest_xray_classifier to obtain objective severity scores.',
                     'Apply the classifier to CTs.', 'mandatory_image_tool_invocation_for_radiology_tasks'):
            self.assertIsNotNone(skill_policy_rejection(text), text)
        self.assertIsNone(skill_policy_rejection('Classifier scores are not severity measurements. Never apply a classifier to CT.'))

    def test_new_request_policy_requires_matching_approval_before_key_or_subprocess(self):
        from run_skemex_pipeline import run
        approval = {'status': 'approved', 'experiment_id': 'skemex_a1_20261103',
                    'A0': 'D', 'model': 'qwen3.7-plus', 'tool_agent': True, 'plan_version': 'tools-v2'}
        cfg = {'tool_agent': True, 'plan_version': 'tools-v2', 'evidence_revision': 'tools-v2',
               'request_count_unbounded': True}
        with patch('run_skemex_pipeline.read', side_effect=[approval, cfg]), \
             patch('run_skemex_pipeline.subprocess.run', side_effect=AssertionError('no process')):
            with self.assertRaisesRegex(ValueError, 'tools_v2_unlimited_request_authorization'):
                run(Path('unused'), Path('approval'), execute=True)

    def test_revised_actor_has_one_output_contract_and_no_reference(self):
        from contextlib import nullcontext
        from skemex_adapter.tool_episode import episode
        seen = []
        row = self.row
        class Transport:
            factory = None
            def call(self, messages, **kwargs):
                seen.append(messages)
                if not kwargs['actor']:
                    return '{"calls":[],"reason":"Tools do not resolve the question"}', {'status': 'completed'}
                return '{"answer":"A","option_text":"Left lung collapse","reason":"pixels"}', {'answer': 'A', 'status': 'completed'}
        retrieval = SimpleNamespace(retrieved_skills_block='', injected_skill_ids=[], candidates=[])
        runtime = {'store': SimpleNamespace(list_skills=lambda **kw: []), 'config': None,
                   'modules': {'categories': SimpleNamespace(DynamicTaskCategoryRegistry=lambda *a:
                       SimpleNamespace(classify=lambda q: ['finding']))},
                   'retriever': SimpleNamespace(retrieve=lambda *a, **kw: retrieval)}
        tools = SimpleNamespace(eligible=lambda r: r['images'],
                                invoke=lambda *a: self.fail('optional empty plan must not call tools'))
        with patch('skemex_adapter.tool_episode.budgeted_llm_bindings', return_value=nullcontext()), \
             patch('skemex_adapter.tool_episode.request_for', return_value=(
                 [{'role': 'system', 'content': 'Return two lines: Answer/Reason'},
                  {'role': 'user', 'content': row['question']}], [])), \
             patch('skemex_adapter.tool_episode.frozen_write'):
            result = episode(runtime, Transport(), row, {'evidence_revision': 'tools-v2'},
                             Path('unused'), 0, {}, tools)
        self.assertIsNone(result['tool_plan_error'])
        self.assertIn('strict JSON', seen[-1][0]['content'])
        self.assertNotIn('Return two lines', seen[-1][0]['content'])
        self.assertNotIn('correct_answer', json.dumps(seen))

    def test_preparer_uses_fresh_namespace_without_old_memory_or_counter_io(self):
        import tempfile
        from configure_skemex_tools import configure
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            original = root/'runs/skemex_a1_20261103'
            (original/'inputs').mkdir(parents=True)
            (original/'training').mkdir()
            (original/'pipeline_status.json').write_text('{"status":"completed"}')
            inherited = {'global_request_counter': 'shared/counter.json', 'cap_CNY': '200'}
            (original/'config.json').write_text(json.dumps(inherited))
            (original/'embedding_version.json').write_text('{}')
            (original/'evolution').mkdir()
            (original/'evolution/old_skill.md').write_text('must not copy')
            code = root/'code'
            (code/'configs').mkdir(parents=True)
            (code/'configs/skemex_tools_v2_protocol.json').write_text('{"status":"awaiting_user_confirmation"}')
            manifest = code/'reports/case_information_20261103/03_E3/caption_modalities.json'
            manifest.parent.mkdir(parents=True)
            manifest.write_text('{}')
            receipt = configure(root, code, 'existing_repo', revision=True)
            out = root/'runs/skemex_tools_v2_20261104'
            cfg = json.loads((out/'config.json').read_text())
            self.assertEqual(cfg['global_request_counter'], inherited['global_request_counter'])
            self.assertEqual(cfg['cap_CNY'], '200')
            self.assertTrue(cfg['request_count_unbounded'])
            self.assertIsNone(cfg['global_max_requests'])
            self.assertFalse((out/'evolution').exists())
            self.assertEqual(receipt['new_api_calls'], 0)


    def test_unlimited_count_preserves_dedup_reservation_and_legacy_limits(self):
        import tempfile
        from run_sampled_vlm import claim_global
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/'counter.json'
            state = {'request_ids': ['old'+str(i) for i in range(5250)],
                     'extra_request_ids': [], 'max_requests': 5250, 'max_extra_requests': 250}
            path.write_text(json.dumps(state))
            cfg = {'root': temp, 'global_request_counter': 'counter.json',
                   'global_max_requests': None, 'global_max_extra_requests': None,
                   'experiment_id': 'skemex_tools_v2_20261104', 'evidence_revision': 'tools-v2',
                   'request_count_unbounded': True,
                   'request_limit_authorization': 'user_20261104_request_count_unlimited'}
            reserve = __import__('unittest.mock', fromlist=['Mock']).Mock(return_value='reservation')
            self.assertEqual(claim_global(cfg, 'new', False, reserve), 'reservation')
            result = json.loads(path.read_text())
            self.assertEqual(len(result['request_ids']), 5251)
            self.assertEqual(result['max_requests'], 5250)
            self.assertFalse(result['scoped_request_limits'][cfg['experiment_id']]['monetary_cap_changed'])
            with self.assertRaisesRegex(ValueError, 'already_claimed'):
                claim_global(cfg, 'new', False, reserve)
            self.assertEqual(reserve.call_count, 1)
            with self.assertRaisesRegex(ValueError, 'explicit_skemex_v2_scope'):
                claim_global(dict(cfg, experiment_id='unapproved'), 'another', False, reserve)
            legacy = dict(cfg, request_count_unbounded=False, global_max_requests=5250, global_max_extra_requests=250)
            with self.assertRaisesRegex(ValueError, 'global_request_limit_reached'):
                claim_global(legacy, 'legacy', False, reserve)
            self.assertEqual(reserve.call_count, 1)


if __name__ == '__main__':
    unittest.main()
