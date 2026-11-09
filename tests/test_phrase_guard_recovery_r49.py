"""Synthetic policy/recovery proofs only; no model, label, provider or GPU calls."""
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
sys.path.insert(0, str(Path(__file__).resolve().parent))
import score_online_skill_r49 as score
from online_memory_r49 import read, save_once
from export_cxr_vqa_extension import RequestEvidencePublisher
from verify_public_online_skill_r49 import asset_normalizer
import test_registered_cuda_recovery_r49 as cuda_fixture
from PIL import Image


def overwrite(path, value):
    path.write_text(json.dumps(value), encoding='utf-8')


class Tests(unittest.TestCase):
    def fixture(self, root, cuda=False):
        cuda_selection = cuda_fixture.Tests().fixture(root)[1] if cuda else None
        key = score.PHRASE_OLD_KEY; identity = {'backend': score.PHRASE_TOOL,
            'revision': score.PHRASE_REVISION, 'image': 'copied-legacy-name', 'args': {'phrase': 'synthetic'}}
        common = {'status': 'completed', 'backend': score.PHRASE_TOOL, 'identity': identity,
                  'original_image': '/native/synthetic.png', 'actual_model_events': [{'status': 'completed'}]}
        failure = dict(common, observation=[{'error': ''}, {'analysis_status': 'failed'}],
                       elapsed_s=22.626826583, backend_compute_seconds=19.67407546)
        old = dict(failure, tool=score.PHRASE_TOOL, cache_key=key, cache_hit=False)
        save_once(root/'services/tool_cache'/key/'started.json', {'identity': identity, 'utc': '2026-11-09T00:00:00Z'})
        save_once(root/'services/tool_cache'/key/'result.json', failure)
        profile = {'tag_token_ids': {k: v for k, v in score.PHRASE_TOKENS.items() if k != 'eos'}, 'eos_token_id': 2,
            'do_sample': False, 'num_beams': 1, 'forced_eos_token_id': None, 'is_loaded_in_8bit': True,
            'model_dtype': 'torch.float16', 'visible_model_device': 'cuda:0'}
        tokens = [32000, 7, 32001, 32202, 8, 32203, 2]
        masks = [{'step': step, 'batch_row': 0, 'generated_length': step-1,
                  'unclosed_obj_depth': obj, 'unclosed_box_depth': box, 'masked_token_id': 2}
                 for step, obj, box in ((2, 1, 0), (3, 1, 0), (5, 0, 1), (6, 0, 1))]
        policy = {'policy_id': score.PHRASE_POLICY, 'profile': profile, 'inserted_tokens': 0,
                  'parse_fallback': False, 'forced_box': False,
                  'calls': [{'prompt_length': 2, 'max_new_tokens': 300, 'use_cache': True,
                    'masking_steps': masks, 'masking_step_count': 4, 'processor_invocations': len(tokens),
                    'existing_logits_processors': 0, 'generation_policy_changed': True}]}
        factory = [{'model_revision': score.PHRASE_MODEL_REVISION,
                    'source_commit': score.PHRASE_REVISION.removeprefix('MedRAX-'), 'cuda_visible_devices': '1',
                    'model_device': 'cuda:0', 'model_dtype': 'torch.float16', 'is_loaded_in_8bit': True}]
        evidence = {**policy, 'factory': factory, 'capture_complete': True, 'eos_terminated': True,
                    'policy_healthy': True, 'final_generated_token_ids': [2], 'cuda_visible_devices': '1',
                    'generation_policy_changed': True, 'same_generation_settings': False,
                    'clinical_prompt_changed': False, 'parser_changed': False, 'diagnostic_result_reused': False}
        healthy = dict(common, observation=[{'predictions': ['synthetic']}, {'analysis_status': 'completed'}],
                       generation_policy_evidence=evidence, cuda_visible_devices='1', elapsed_s=15., backend_compute_seconds=12.)
        folder = root/'services/tool_cache'/(key+'_phrase_guard_1')
        for name, value in {'started': {'identity': identity, 'policy_id': score.PHRASE_POLICY,
              'generation_policy_changed': True, 'automatic_retry': False, 'utc': '2026-11-09T00:02:00Z'},
              'request': {'tool': score.PHRASE_TOOL, 'backend': score.PHRASE_TOOL,
                  'args': identity['args'], 'image': common['original_image']}, 'result': healthy}.items():
            save_once(folder/(name+'.json'), value)
        records = {'generation_tokens': [{'prompt_length': 2, 'output_token_ids': [[42, 43]+tokens],
                    'generated_token_ids': [tokens], 'max_new_tokens': 300, 'use_cache': True}],
                   'decode': [{'input_token_ids': tokens, 'kwargs': {'skip_special_tokens': True}, 'decoded_text': 'synthetic'}],
                   'conversion_inputs': [{'text': 'synthetic', 'kwargs': {}}], 'swallowed_exceptions': [],
                   'observability_errors': [], 'factory': factory, 'eos_guard': policy,
                   'policy_status': {'capture_complete': True, 'policy_healthy': True, 'eos_terminated': True}}
        for name, value in records.items(): save_once(folder/'artifacts'/(name+'.json'), value)
        active = dict(healthy, tool=score.PHRASE_TOOL, cache_key=folder.name, cache_hit=False,
                      generation_policy={'policy_id': score.PHRASE_POLICY, 'source': 'guarded_new',
                        'generation_policy_changed': True, 'same_generation_settings': False,
                        'applied_actual_invocation': True, 'bound_original_image': common['original_image']})
        diagnostic = {'diagnostic_id': 'r49_phrase_grounding_diagnostic_20261109', 'tool_invocations': 1,
            'main_api_calls': 0, 'meta_api_calls': 0, 'embedding_api_calls': 0, 'elapsed_s': 23.471671,
            'status': 'failed', 'capture_complete': True, 'result_reused_in_R49': False}
        registration = {'schema': 'r49_registered_phrase_guard_retry_v1', 'recovery_id': 'phrase_guard_1',
            'dataset': 'chexbench', 'arm': score.ARM, 'question_id': score.PHRASE_QID, 'question_ordinal': 169,
            'logical_tool_ordinal': 1, 'tool': score.PHRASE_TOOL, 'backend': score.PHRASE_TOOL,
            'original_cache_key': key, 'retry_cache_key': folder.name,
            'original_selection_archive_relative': 'failure_events/phrase_guard_1_original_selection.json',
            'identity': identity, 'canonical_original_image': common['original_image'], 'original_selection': old,
            'active_selection': active, 'policy_id': score.PHRASE_POLICY, 'generation_policy_changed': True,
            'same_generation_settings': False, 'diagnostic': diagnostic, 'guarded_production_retry_limit': 1,
            'automatic_retry': False, 'status': 'healthy_guarded_production_retry_registered'}
        save_once(root/'failure_events/phrase_guard_1_original_selection.json', old)
        save_once(root/'failure_events/phrase_guard_1_registration.json', registration)
        save_once(root/'services/tool_selections/R49-AGENT'/score.PHRASE_QID/'1.json', active)
        order = [{'question_id': 'synthetic_'+str(i)} for i in range(170)]
        order[168]['question_id'] = score.PHRASE_QID
        if cuda: order[40]['question_id'] = 'chexbench_rad_restruct_0163'
        save_once(root/'manifest.json', {'dataset': 'chexbench', 'order': order})
        amendment = {'schema': 'r49_phrase_guard_amendment_v1', 'recovery_id': 'phrase_guard_1', 'dataset': 'chexbench',
            'arm': score.ARM, 'policy_id': score.PHRASE_POLICY, 'activation_boundary_chexbench': 168,
            'activation_committed_questions': 168, 'scope': 'all_new_physical_MAIRA_calls_after_activation',
            'token_ids': score.PHRASE_TOKENS, 'max_new_tokens': 300, 'generation_policy_changed': True,
            'same_generation_settings': False, 'legacy_healthy_cache_reuse': True, 'automatic_retry': False,
            'clinical_prompt_changed': False, 'parser_changed': False, 'diagnostic_result_reused': False,
            'cache_naming': 'unchanged_legacy_identity_and_key_plus_explicit_policy_suffix; image_fingerprint_is_existing_naming_not_a_validation_gate',
            'legacy_cache_keys_at_activation': sorted([key]+(['old', 'old_cuda_1'] if cuda else [])),
            'protected_existing_selections': ['services/tool_selections/R49-AGENT/chexbench_rad_restruct_0163/1.json'] if cuda else [],
            'utc': '2026-11-09T00:01:00Z'}
        save_once(root/'failure_events/phrase_guard_1_amendment.json', amendment)
        (root/'services/calls').mkdir(exist_ok=True)
        return registration, active, cuda_selection

    def test_two_distinct_historical_failures_and_two_healthy_production_caches_once(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); _, active, cuda = self.fixture(root, cuda=True)
            tools = [cuda, active]; attempts = score.tool_attempt_accounting(root, tools, {x['cache_key'] for x in tools})
            amendment = score.validate_phrase_guard_amendment(root)
            resources = score.resources(root, {}, tools, attempts, phrase_amendment=amendment)
            self.assertEqual(resources['tools']['fresh_backend_attempts'], 4)
            self.assertEqual(resources['tools']['registered_failed_historical_attempts'], 2)
            self.assertEqual(resources['tools']['registered_cuda_failed_attempts'], 1)
            self.assertEqual(resources['tools']['registered_phrase_failed_attempts'], 1)
            self.assertEqual(resources['tools']['backend_elapsed_seconds_known'], 4.+6.+22.626826583+15.)
            self.assertEqual(resources['isolated_phrase_diagnostic']['elapsed_s'], 23.471671)
            self.assertFalse(resources['isolated_phrase_diagnostic']['included_in_production_attempts'])
            self.assertEqual(amendment['guarded_physical_attempts'], 1)
            self.assertEqual(amendment['masked_eos_steps'], 4)

    def test_non_EOS_incomplete_capture_and_changed_factory_still_stop(self):
        for field, value in [('eos_terminated', False), ('capture_complete', False), ('policy_healthy', False),
                             ('final_generated_token_ids', [7])]:
            with self.subTest(field=field), tempfile.TemporaryDirectory() as temp:
                root = Path(temp); self.fixture(root)
                path = root/'services/tool_cache'/(score.PHRASE_OLD_KEY+'_phrase_guard_1')/'result.json'
                result = read(path); result['generation_policy_evidence'][field] = value; overwrite(path, result)
                with self.assertRaisesRegex(ValueError, 'runtime_healthy_complete_EOS2'):
                    score.phrase_guarded_backend(root, path.parent.name)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); self.fixture(root)
            path = root/'services/tool_cache'/(score.PHRASE_OLD_KEY+'_phrase_guard_1')/'artifacts/factory.json'
            factory = read(path); factory[0]['model_dtype'] = 'torch.float32'; overwrite(path, factory)
            with self.assertRaises(ValueError): score.phrase_guarded_backend(root, path.parent.parent.name)

    def test_mask_tampering_unknown_original_and_extra_orphan_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); _, active, _ = self.fixture(root)
            save_once(root/'services/tool_cache/extra/result.json', {'status': 'failed'})
            with self.assertRaisesRegex(ValueError, 'orphan_or_unknown'):
                score.tool_attempt_accounting(root, [active], {active['cache_key']})
            path = root/'services/tool_cache'/active['cache_key']/'artifacts/generation_tokens.json'
            generation = read(path); generation[0]['generated_token_ids'][0][-1] = 7; overwrite(path, generation)
            with self.assertRaisesRegex(ValueError, 'raw_tokens_original_max300'):
                score.phrase_guarded_backend(root, active['cache_key'])
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); _, active, _ = self.fixture(root)
            folder = root/'services/tool_cache'/active['cache_key']; result = read(folder/'result.json')
            policy = read(folder/'artifacts/eos_guard.json'); policy['calls'][0]['masking_steps'].pop()
            policy['calls'][0]['masking_step_count'] -= 1
            result['generation_policy_evidence']['calls'] = policy['calls']
            overwrite(folder/'result.json', result); overwrite(folder/'artifacts/eos_guard.json', policy)
            with self.assertRaisesRegex(ValueError, 'actual_EOS_only_mask_steps'): score.phrase_guarded_backend(root, active['cache_key'])
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); self.fixture(root)
            path = root/'services/tool_cache'/score.PHRASE_OLD_KEY/'result.json'
            failed = read(path); failed['status'] = 'started_unknown'; overwrite(path, failed)
            with self.assertRaisesRegex(ValueError, 'closed_preserved_failure'): score.registered_phrase_guard_retry(root)

    def test_future_guarded_cache_source_and_declared_activation(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); _, active, _ = self.fixture(root)
            future = copy.deepcopy(active); future['cache_hit'] = True
            future['generation_policy'].update(source='guarded_cache', applied_actual_invocation=False)
            save_once(root/'services/tool_selections/R49-AGENT/synthetic_169/1.json', future)
            counts = score.validate_phrase_guard_amendment(root)
            self.assertEqual((counts['guarded_new_selections'], counts['guarded_cache_selections'], counts['guarded_physical_attempts']), (1, 1, 1))
            path = root/'failure_events/phrase_guard_1_amendment.json'; changed = read(path); path.unlink()
            with self.assertRaisesRegex(ValueError, 'requires_its_declared_policy_boundary'): score.validate_phrase_guard_amendment(root)
            changed['utc'] = '2026-11-09T00:03:00Z'; overwrite(path, changed)
            with self.assertRaisesRegex(ValueError, 'precedes_declared_activation'): score.validate_phrase_guard_amendment(root)

    def test_old_saved_healthy_MAIRA_and_later_legacy_cache_hit_are_not_recomputed(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); _, active, _ = self.fixture(root)
            legacy = {k: v for k, v in active.items() if k not in ('generation_policy_evidence', 'generation_policy', 'tool', 'cache_key', 'cache_hit')}
            key = 'legacy_healthy_maira'
            save_once(root/'services/tool_cache'/key/'started.json', {'identity': legacy['identity'], 'utc': '2026-11-09T00:00:00Z'})
            save_once(root/'services/tool_cache'/key/'result.json', legacy)
            previous = dict(legacy, tool=score.PHRASE_TOOL, cache_key=key, cache_hit=False)
            protected = 'services/tool_selections/R49-AGENT/synthetic_1/1.json'
            save_once(root/protected, previous)
            future = dict(previous, cache_hit=True, generation_policy={
                'policy_id': 'legacy_original_maira', 'source': 'legacy_healthy_cache',
                'generation_policy_changed': False, 'same_generation_settings': True,
                'applied_actual_invocation': False, 'bound_original_image': legacy['original_image']})
            future_path = root/'services/tool_selections/R49-AGENT/synthetic_169/1.json'; save_once(future_path, future)
            path = root/'failure_events/phrase_guard_1_amendment.json'; amendment = read(path)
            amendment['protected_existing_selections'] = [protected]
            amendment['legacy_cache_keys_at_activation'] = sorted(amendment['legacy_cache_keys_at_activation']+[key]); overwrite(path, amendment)
            counts = score.validate_phrase_guard_amendment(root)
            self.assertEqual((counts['legacy_saved_selections'], counts['legacy_healthy_cache_selections']), (1, 1))
            self.assertEqual(read(root/protected), previous)
            future['cache_hit'] = False; overwrite(future_path, future)
            with self.assertRaisesRegex(ValueError, 'reclassified_or_recomputed'): score.validate_phrase_guard_amendment(root)

    def test_actual_execution_commit_registry_is_portable_and_preserves_original(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); private = root/'private'; registry, active, _ = self.fixture(private)
            recovery = root/'recovery'; recovery.mkdir(); save_once(recovery/'original_selection.json', registry['original_selection'])
            (private/'failure_events/phrase_guard_1_registration.json').unlink()
            selected = private/'services/tool_selections/R49-AGENT'/score.PHRASE_QID/'1.json'
            overwrite(selected, registry['original_selection'])
            source = Path(__file__).resolve().parents[1]/'local_assets/recover_cxr_online_skill_r49_phrase_guard.py'
            tree = ast.parse(source.read_text(encoding='utf-8'))
            node = next(x for x in tree.body if isinstance(x, ast.FunctionDef) and x.name == 'commit_known_retry')
            namespace = {'Path': Path, 'read': read, 'json': json,
                         'write_once': lambda p, v: overwrite(p, v) if p.exists() else save_once(p, v),
                         'RECOVERY': 'phrase_guard_1', 'ARM': score.ARM, 'TOOL': score.PHRASE_TOOL, 'QID': score.PHRASE_QID,
                         'OLD_KEY': score.PHRASE_OLD_KEY, 'SUFFIX': '_phrase_guard_1', 'POLICY_ID': score.PHRASE_POLICY}
            exec(compile(ast.Module(body=[node], type_ignores=[]), str(source), 'exec'), namespace)
            namespace['commit_known_retry'](private, recovery, registry['original_selection'], active, {'diagnostic': registry['diagnostic']})
            self.assertIsNotNone(score.registered_phrase_guard_retry(private))
            public = root/'public'; publisher = RequestEvidencePublisher(public, root/'unused.json')
            buffer = BytesIO(); Image.new('RGB', (2, 2), 'white').save(buffer, format='PNG')
            publisher.alias('/native/synthetic.png', publisher.put_image(buffer.getvalue()))
            for path in private.rglob('*.json'): publisher.copy_json(path, public/path.relative_to(private))
            publisher.emit(public/'image_assets.json', [{'path': publisher.rel(asset['target'], public/'image_assets.json')}
                                                       for asset in publisher.assets.values()])
            private.rename(root/'private_unavailable')
            normalizer = asset_normalizer(public)
            original_read = score.read
            with patch.object(score, 'read', side_effect=lambda path: normalizer(original_read(path), Path(path))):
                self.assertIsNotNone(score.registered_phrase_guard_retry(public))
                self.assertEqual(score.validate_phrase_guard_amendment(public)['guarded_physical_attempts'], 1)


if __name__ == '__main__': unittest.main()
