"""Synthetic one-known-HTTP-failure proof, no funding marker or provider call."""
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
from online_memory_r49 import now, read, save_once
from export_cxr_vqa_extension import RequestEvidencePublisher
from verify_public_online_skill_r49 import asset_normalizer
from PIL import Image


class Tests(unittest.TestCase):
    def fixture(self, root):
        request = {'model': 'text-embedding-v4', 'input': json.dumps({'synthetic': '/native/synthetic.png'})}
        old = {'request': request, 'started': {'sent_intent': True, 'utc': now()},
               'result': {'response_received': False, 'error_type': 'BadRequestError',
                          'usage': None, 'elapsed_s': .1, 'utc': now()}}
        old_folder = root/'services/embeddings/000063'
        for name, value in old.items():
            save_once(old_folder/(name+'.json'), value)
        new_folder = root/'services/embeddings/000063_arrearage_1'
        response = {'model': request['model'], 'data': [{'embedding': [1.0]+[0.0]*1023}],
                    'usage': {'prompt_tokens': 4, 'total_tokens': 4}}
        receipt = {'response_received': True, 'model_returned': request['model'], 'usage': response['usage'],
                   'elapsed_s': .2, 'error': None, 'physical_requests': 1, 'automatic_retry': False, 'utc': now()}
        new = {'request': request, 'started': {'sent_intent': True, 'utc': now()},
               'response': response, 'result': receipt, 'wire_request': {**request, 'encoding_format': 'base64'},
               'http_response': {'http_status': 200, 'body': {'model': request['model']}}}
        for name, value in new.items():
            save_once(new_folder/(name+'.json'), value)
        save_once(root/'manifest.json', {'dataset': 'chexbench', 'embedding_model': request['model'], 'embedding_base_url': 'https://example.invalid/v1'})
        archive = 'failure_events/embedding_arrearage_1_original_failure.json'
        save_once(root/archive, old)
        diagnostic = {'diagnostic_id': 'r49_embedding_400_once_20261109', 'http_status': 400, 'error_code': 'Arrearage',
                      'elapsed_s': .05, 'embedding_requests': 1, 'usage': None, 'result_reused_in_R49': False,
                      'original_error_body_reconstructed': False}
        registry = {'schema': 'r49_registered_embedding_http_failure_v1', 'recovery_id': 'embedding_arrearage_1',
                    'dataset': 'chexbench', 'arm': scoring.ARM, 'original_embedding_id': '000063',
                    'retry_embedding_id': '000063_arrearage_1',
                    'original_call_relative': 'services/embeddings/000063',
                    'retry_call_relative': 'services/embeddings/000063_arrearage_1',
                    'original_failure_archive_relative': archive,
                    'identity': {**request, 'endpoint': 'https://example.invalid/v1',
                                 'encoding_format_argument': 'omitted_preserve_installed_SDK_default'},
                    'original_failure': {'error_type': 'BadRequestError', 'http_status': 400,
                        'http_status_evidence': 'installed_sdk_BadRequestError_status_code_400', 'sdk_version': '1.109.1',
                        'http_body_missing': True, 'specific_body_unknown': True, 'response_archive_absent': True},
                    'diagnostic': diagnostic, 'retry': {'response_received': True, 'model_returned': request['model'],
                        'dimensions': 1024, 'usage': response['usage'], 'elapsed_s': receipt['elapsed_s']},
                    'markers': {name: 'recovery/embedding_arrearage_1/'+file for name, file in (
                        ('scope', 'SCOPE.json'), ('review', 'REVIEW_READY.json'), ('funding', 'FUNDING_CONFIRMED.json'))},
                    'same_original_request': True, 'new_production_embedding_requests': 1,
                    'extra_agent_calls_for_repair': 0, 'extra_meta_calls_for_repair': 0, 'extra_tool_retries': 0,
                    'no_encoding_or_text_change': True, 'no_automatic_retry': True, 'status': 'healthy_embedding_retry_registered'}
        save_once(root/'failure_events/embedding_arrearage_1_registration.json', registry)
        (root/'services/calls').mkdir()
        return registry

    def test_failed_usage_cost_unknown_retry_once_and_diagnostic_separate(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); self.fixture(root)
            proof = scoring.registered_embedding_http_failure(root)
            value = scoring.resources(root, {}, [], {'physical': [], 'healthy': 0, 'registered': None},
                                      embedding_repair=proof)
            self.assertEqual(value['embedding']['requests'], 2)
            self.assertEqual(value['embedding']['successful_responses'], 1)
            self.assertEqual(value['embedding']['registered_http_failed_attempts'], 1)
            self.assertEqual(value['embedding']['usage_unknown_count'], 1)
            self.assertEqual(value['embedding']['cost_unknown_count'], 2)
            self.assertTrue(value['embedding_http_recovery']['original_specific_body_unknown'])
            self.assertFalse(value['isolated_embedding_diagnostic']['included_in_production_embedding_totals'])
            self.assertTrue(value['isolated_embedding_diagnostic']['cost_unknown'])

    def test_other_unknown_embedding_and_original_body_reconstruction_still_reject(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); registry = self.fixture(root)
            proof = scoring.registered_embedding_http_failure(root)
            save_once(root/'services/embeddings/000064/started.json', {'sent_intent': True})
            with self.assertRaisesRegex(ValueError, 'unclosed_embedding_request'):
                scoring.resources(root, {}, [], {'physical': [], 'healthy': 0, 'registered': None},
                                  embedding_repair=proof)
            manifest = read(root/'manifest.json'); manifest['dataset'] = 'vqarad'
            (root/'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'only_permitted_in_CheXbench'):
                scoring.registered_embedding_http_failure(root)
            manifest['dataset'] = 'chexbench'
            (root/'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
            registry['original_failure']['error_code'] = 'Arrearage'
            (root/'failure_events/embedding_arrearage_1_registration.json').write_text(json.dumps(registry), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'body_must_remain_unknown'):
                scoring.registered_embedding_http_failure(root)

    def test_retry_input_change_zero_vector_and_missing_response_reject(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); self.fixture(root)
            folder = root/'services/embeddings/000063_arrearage_1'
            request = read(folder/'request.json'); request['input'] += 'changed'
            (folder/'request.json').write_text(json.dumps(request), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'retry_was_changed'):
                scoring.registered_embedding_http_failure(root)
            request['input'] = read(root/'services/embeddings/000063/request.json')['input']
            (folder/'request.json').write_text(json.dumps(request), encoding='utf-8')
            response = read(folder/'response.json'); response['data'][0]['embedding'] = [0.0]*1024
            (folder/'response.json').write_text(json.dumps(response), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'nonzero_vector'):
                scoring.registered_embedding_http_failure(root)
            (folder/'response.json').unlink()
            with self.assertRaisesRegex(ValueError, 'unknown_or_unclosed'):
                scoring.registered_embedding_http_failure(root)

    def test_public_semantic_archive_and_vector_proof_without_private_paths(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); private = root/'private'; self.fixture(private)
            public = root/'public'; publisher = RequestEvidencePublisher(public, root/'unused.json')
            buffer = BytesIO(); Image.new('RGB', (2, 2), 'white').save(buffer, format='PNG')
            publisher.alias('/native/synthetic.png', publisher.put_image(buffer.getvalue()))
            for path in private.rglob('*.json'):
                publisher.copy_json(path, public/path.relative_to(private))
            publisher.emit(public/'image_assets.json', [{'path': publisher.rel(asset['target'], public/'image_assets.json')}
                                                       for asset in publisher.assets.values()])
            private.rename(root/'private_unavailable')
            normalize = asset_normalizer(public); raw_read = scoring.read
            with patch.object(scoring, 'read', side_effect=lambda path: normalize(raw_read(path), Path(path))):
                proof = scoring.registered_embedding_http_failure(public)
            self.assertEqual(proof['registration']['retry']['dimensions'], 1024)
            self.assertFalse((public/'services/embeddings/000063/response.json').exists())

    def test_actual_helper_registration_contract_without_any_SDK_call(self):
        repository = Path(__file__).resolve().parents[1]
        paths = [repository/'local_assets/recover_cxr_online_skill_r49_embedding_arrearage.py',
                 repository/'reports/cxr_online_skill_r49_20261108/deployment_source/recover_cxr_online_skill_r49_embedding_arrearage.py']
        source = next(path for path in paths if path.is_file())
        tree = ast.parse(source.read_text(encoding='utf-8'))
        names = ('read', 'write_once', 'original_failure', 'embedding_vector', 'embedding_overlay')
        functions = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in names]
        namespace = {'Path': Path, 'json': json, 'RECOVERY': 'embedding_arrearage_1', 'ARM': scoring.ARM,
                     'ORIGINAL_ID': '000063', 'RETRY_ID': '000063_arrearage_1', 'EMBED_MODEL': 'text-embedding-v4',
                     'EMBED_BASE': 'https://example.invalid/v1'}
        exec(compile(ast.Module(body=functions, type_ignores=[]), str(source), 'exec'), namespace)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); registry = self.fixture(root)
            (root/'failure_events/embedding_arrearage_1_registration.json').unlink()
            def saved_response(client, folder, request):
                self.assertEqual(request, read(root/'services/embeddings/000063/request.json'))
                return read(Path(folder)/'response.json')
            namespace['retry_once'] = saved_response
            service = types.SimpleNamespace(out=root/'services', embed_model='text-embedding-v4', embedding_client=object())
            plan = {'original_failure_bundle': read(root/'failure_events/embedding_arrearage_1_original_failure.json'),
                    'sdk_evidence': {'sdk_version': '1.109.1'}, 'diagnostic': registry['diagnostic']}
            overlay = namespace['embedding_overlay'](lambda *args: self.fail('unexpected delegate'), root/'services',
                                                       root/'shared_recovery', plan)
            overlay(service, plan['original_failure_bundle']['request']['input'])
            self.assertEqual(scoring.registered_embedding_http_failure(root)['registration']['retry']['dimensions'], 1024)


if __name__ == '__main__':
    unittest.main()
