"""Synthetic closed-attempt accounting boundaries; no targets or API calls."""
import copy
import ast
import json
from io import BytesIO
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'experiments'))
import score_online_skill_r49 as scoring
from online_memory_r49 import read, save_once
from export_cxr_vqa_extension import RequestEvidencePublisher
from verify_public_online_skill_r49 import asset_normalizer
from PIL import Image


QID = 'chexbench_rad_restruct_0163'


class Tests(unittest.TestCase):
    def fixture(self, root):
        identity = {'backend': 'chest_xray_expert', 'revision': 'fixed-version',
                    'image': 'opaque-existing-cache-identity', 'args': {'question': 'synthetic'}}
        common = {'status': 'completed', 'backend': 'chest_xray_expert', 'identity': identity,
                  'original_image': '/native/synthetic.png'}
        failed = dict(common, observation=[{'error': 'synthetic CUDA failure'}, {'analysis_status': 'failed'}],
                      actual_model_events=[{'status': 'failed'}], backend_compute_seconds=2.0, elapsed_s=4.0)
        healthy = dict(common, observation=[{'response': 'synthetic healthy output'}],
                       actual_model_events=[{'status': 'completed'}], backend_compute_seconds=3.0, elapsed_s=6.0)
        provenance = {'recovery_id': 'cuda_1', 'original_cache_key': 'old', 'retry_cache_key': 'old_cuda_1',
                      'original_failure_preserved': True, 'production_retry': True}
        old_selection = dict(failed, cache_key='old', cache_hit=False, tool='chest_xray_expert')
        replacement = dict(healthy, cache_key='old_cuda_1', cache_hit=False, tool='chest_xray_expert',
                           cuda_recovery=provenance)
        registration = {'schema': 'r49_registered_cuda_retry_v1', 'recovery_id': 'cuda_1',
                        'dataset': 'chexbench', 'arm': scoring.ARM, 'question_id': QID, 'logical_ordinal': 1,
                        'tool': 'chest_xray_expert', 'backend': 'chest_xray_expert', 'revision': 'fixed-version',
                        'original_image': '/native/synthetic.png', 'args': identity['args'], 'identity': identity,
                        'original_cache_key': 'old', 'retry_cache_key': 'old_cuda_1',
                        'original_selection': old_selection, 'retry_selection': replacement,
                        'original_selection_archive_relative': 'failure_events/cuda_1_original_selection.json',
                        'original_selection_archive': '/native/recovery/original_selection.json',
                        'status': 'healthy_production_retry_registered', 'new_tool_attempts': 1,
                        'main_api_calls': 0, 'diagnostic_result_reused': False, 'automatic_retry': False,
                        'production_debug_flags': {'CUDA_LAUNCH_BLOCKING': None, 'TORCH_SHOW_CPP_STACKTRACES': None},
                        'diagnostic': {'tool_invocations': 1, 'main_api_calls': 0, 'meta_api_calls': 0,
                                       'embedding_api_calls': 0, 'elapsed_s': 1.25, 'result_reused_in_R49': False}}
        save_once(root/'failure_events/cuda_1_registration.json', registration)
        save_once(root/'failure_events/cuda_1_original_selection.json', old_selection)
        save_once(root/'services/tool_selections/R49-AGENT'/QID/'1.json', replacement)
        for name, value in [('old', failed), ('old_cuda_1', healthy)]:
            save_once(root/'services/tool_cache'/name/'started.json', {'identity': identity})
            save_once(root/'services/tool_cache'/name/'result.json', value)
        (root/'services/calls').mkdir()
        return registration, replacement

    def test_one_closed_failure_counts_both_physical_attempts_not_cache_hits_or_diagnostic(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); registration, active = self.fixture(root)
            future_cache_hit = dict(active, cache_hit=True)
            attempts = scoring.tool_attempt_accounting(root, [active, future_cache_hit], {'old_cuda_1'})
            resource = scoring.resources(root, {}, [active, future_cache_hit], attempts)
            self.assertEqual(resource['tools']['logical_calls'], 2)
            self.assertEqual(resource['tools']['cache_hits'], 1)
            self.assertEqual(resource['tools']['fresh_backend_attempts'], 2)
            self.assertEqual(resource['tools']['registered_failed_historical_attempts'], 1)
            self.assertEqual(resource['tools']['backend_compute_seconds_known'], 5.0)
            self.assertEqual(resource['tools']['backend_elapsed_seconds_known'], 10.0)
            self.assertEqual(resource['tools']['failed_or_unknown_tools'], 0)
            self.assertEqual(resource['isolated_cuda_diagnostic']['elapsed_s'], 1.25)
            self.assertFalse(resource['isolated_cuda_diagnostic']['included_in_production_attempts'])

    def test_unknown_or_unclosed_original_is_never_forgiven(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); self.fixture(root)
            (root/'services/tool_cache/old/result.json').unlink()
            with self.assertRaisesRegex(ValueError, 'unknown_or_unclosed'):
                scoring.registered_cuda_retry(root)

    def test_extra_closed_failed_orphan_still_stops(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); _, active = self.fixture(root)
            save_once(root/'services/tool_cache/extra/started.json', {'identity': {}})
            save_once(root/'services/tool_cache/extra/result.json', {'status': 'failed'})
            with self.assertRaisesRegex(ValueError, 'orphan_or_unknown'):
                scoring.tool_attempt_accounting(root, [active], {'old_cuda_1'})

    def test_orphan_result_without_started_is_not_ignored_or_unmetered(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); _, active = self.fixture(root)
            save_once(root/'services/tool_cache/extra/result.json', {'status': 'failed'})
            with self.assertRaisesRegex(ValueError, 'orphan_or_unknown'):
                scoring.tool_attempt_accounting(root, [active], {'old_cuda_1'})

    def test_unknown_status_cannot_be_registered_as_known_failed(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); registration, active = self.fixture(root)
            for path in (root/'services/tool_cache/old/result.json',
                         root/'failure_events/cuda_1_original_selection.json',
                         root/'failure_events/cuda_1_registration.json'):
                value = read(path)
                if path.name == 'cuda_1_registration.json':
                    value['original_selection']['status'] = 'started_unknown'
                else:
                    value['status'] = 'started_unknown'
                path.write_text(__import__('json').dumps(value), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'closed_actual_failure'):
                scoring.registered_cuda_retry(root)

    def test_original_archive_or_future_alias_change_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); _, active = self.fixture(root)
            altered = dict(active, cache_hit=True, cuda_recovery={})
            with self.assertRaisesRegex(ValueError, 'alias_provenance_changed'):
                scoring.tool_attempt_accounting(root, [active, altered], {'old_cuda_1'})
            archive = root/'failure_events/cuda_1_original_selection.json'
            changed = read(archive); changed['tool'] = 'different_tool'
            archive.write_text(__import__('json').dumps(changed), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'archive_changed'):
                scoring.registered_cuda_retry(root)

    def test_portable_registered_attempt_proof_normalizes_nested_image_paths(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); private = root/'private'; self.fixture(private)
            public = root/'public'; publisher = RequestEvidencePublisher(public, root/'unused.json')
            buffer = BytesIO(); Image.new('RGB', (2, 2), 'white').save(buffer, format='PNG')
            publisher.alias('/native/synthetic.png', publisher.put_image(buffer.getvalue()))
            for path in private.rglob('*.json'):
                publisher.copy_json(path, public/path.relative_to(private))
            publisher.emit(public/'image_assets.json', [
                {'path': publisher.rel(asset['target'], public/'image_assets.json')}
                for asset in publisher.assets.values()])
            private.rename(root/'private_no_longer_available')
            normalize = asset_normalizer(public); original_read = scoring.read
            with patch.object(scoring, 'read', side_effect=lambda p: normalize(original_read(p), Path(p))):
                checked = scoring.registered_cuda_retry(public)
            self.assertEqual(checked['registration']['original_cache_key'], 'old')
            self.assertEqual(checked['original_result']['original_image'], checked['retry_result']['original_image'])

    def test_actual_operational_commit_schema_is_accepted_without_endpoint_or_worker(self):
        repository = Path(__file__).resolve().parents[1]
        candidates = [repository/'local_assets/recover_cxr_online_skill_r49_cuda.py',
                      repository/'reports/cxr_online_skill_r49_20261108/deployment_source/recover_cxr_online_skill_r49_cuda.py']
        source = next(path for path in candidates if path.is_file())
        tree = ast.parse(source.read_text(encoding='utf-8'))
        functions = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                     and node.name in ('write_once', 'commit_healthy_retry')]
        namespace = {'Path': Path, 'json': json, 'QID': QID, 'ARM': scoring.ARM}
        # Execute the actual two pure file-commit functions, excluding all
        # deployment imports, credentials, controllers, workers and endpoints.
        exec(compile(ast.Module(body=functions, type_ignores=[]), str(source), 'exec'), namespace)
        commit_healthy_retry = namespace['commit_healthy_retry']
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); registration, _ = self.fixture(root)
            for name in ('cuda_1_registration.json', 'cuda_1_original_selection.json'):
                (root/'failure_events'/name).unlink()
            selected = root/'services/tool_selections/R49-AGENT'/QID/'1.json'
            selected.write_text(__import__('json').dumps(registration['original_selection']), encoding='utf-8')
            healthy = read(root/'services/tool_cache/old_cuda_1/result.json')
            actual = commit_healthy_retry(root/'services', root/'shared_recovery/cuda_1',
                                          registration['original_selection'], healthy, registration['diagnostic'])
            checked = scoring.registered_cuda_retry(root)
            self.assertEqual(actual, checked['registration'])


if __name__ == '__main__':
    unittest.main()
