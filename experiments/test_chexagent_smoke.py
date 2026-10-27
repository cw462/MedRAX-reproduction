"""Pure/synthetic smoke guards; never imports or executes HF custom model code."""
from contextlib import ExitStack
import hashlib
import json
from pathlib import Path
import socket
import sys
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import chexagent_smoke as smoke


def fixture(root):
    main, vision, repo = root / 'main', root / 'vision', root / 'repo'
    main.mkdir(); vision.mkdir(); (repo / 'medrax/tools').mkdir(parents=True)
    tool = repo / smoke.TOOL_RELATIVE; tool.write_bytes(b'# Synthetic test fixture. Never executed.\n')
    models = {}
    for key, path, model_id, revision, names in (
        ('main', main, smoke.MODEL_ID, smoke.MODEL_REVISION, smoke.MAIN_FILES),
        ('vision', vision, smoke.VISION_ID, smoke.VISION_REVISION, smoke.VISION_FILES)):
        files = {}
        for name in names:
            raw = ('synthetic fixture ' + name).encode()
            (path / name).write_bytes(raw)
            files[name] = {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
        models[key] = {'repo_id': model_id, 'revision': revision, 'files': files}
    manifest = root / 'approved.json'
    manifest.write_text(json.dumps({'schema_version': 1, 'review_status': 'static_source_review_completed',
                                   'required_transformers': '4.40.0', 'models': models}))
    return main, vision, manifest, repo, smoke.sha256_file(manifest), smoke.sha256_file(tool)


class SmokeTests(unittest.TestCase):
    def test_preapproved_manifest_all_files_and_official_tool_checked(self):
        with TemporaryDirectory() as temp:
            main, vision, manifest, repo, mh, th = fixture(Path(temp))
            with patch.object(smoke, 'APPROVED_MANIFEST_SHA256', mh), patch.object(smoke, 'TOOL_LF_SHA256', th):
                result = smoke.verify_assets(main, vision, manifest, repo)
                self.assertEqual(result['models']['vision']['revision'], smoke.VISION_REVISION)
                (main / 'modeling_visual.py').write_text('modified')
                with self.assertRaises(ValueError): smoke.verify_assets(main, vision, manifest, repo)

    def test_modified_manifest_is_rejected_before_any_custom_code_import(self):
        with TemporaryDirectory() as temp:
            main, vision, manifest, repo, mh, th = fixture(Path(temp))
            with patch.object(smoke, 'APPROVED_MANIFEST_SHA256', mh), patch.object(smoke, 'TOOL_LF_SHA256', th):
                manifest.write_text(manifest.read_text() + ' ')
                with patch.object(smoke.importlib.util, 'spec_from_file_location', side_effect=AssertionError('must not import')):
                    with self.assertRaises(ValueError): smoke.verify_assets(main, vision, manifest, repo)

    def test_unexpected_python_and_pickle_files_are_rejected(self):
        for directory, filename in [('vision', 'extra.py'), ('main', 'pytorch_model.bin')]:
            with self.subTest(filename=filename), TemporaryDirectory() as temp:
                root = Path(temp); main, vision, manifest, repo, mh, th = fixture(root)
                (root / directory / filename).write_text('unreviewed')
                with patch.object(smoke, 'APPROVED_MANIFEST_SHA256', mh), patch.object(smoke, 'TOOL_LF_SHA256', th):
                    with self.assertRaises(ValueError): smoke.verify_assets(main, vision, manifest, repo)

    def test_incomplete_vision_assets_block_main_model_execution(self):
        with TemporaryDirectory() as temp:
            main, vision, manifest, repo, mh, th = fixture(Path(temp))
            (vision / 'spiece.model').unlink()
            with patch.object(smoke, 'APPROVED_MANIFEST_SHA256', mh), patch.object(smoke, 'TOOL_LF_SHA256', th):
                with self.assertRaises(ValueError): smoke.verify_assets(main, vision, manifest, repo)

    def test_lf_and_crlf_source_are_equivalent_with_distinct_recorded_raw_hashes(self):
        with TemporaryDirectory() as temp:
            main, vision, manifest, repo, mh, th = fixture(Path(temp))
            tool = repo / smoke.TOOL_RELATIVE
            raw_lf = tool.read_bytes()
            with patch.object(smoke, 'TOOL_LF_SHA256', th), patch.object(smoke, 'APPROVED_MANIFEST_SHA256', mh):
                first = smoke.verify_tool_source(repo)
                smoke.verify_assets(main, vision, manifest, repo)
                tool.write_bytes(raw_lf.replace(b'\n', b'\r\n'))
                second = smoke.verify_tool_source(repo)
                smoke.verify_assets(main, vision, manifest, repo)
            self.assertEqual(first['lf_sha256'], second['lf_sha256'])
            self.assertNotEqual(first['sha256'], second['sha256'])
            self.assertEqual(first['sha256'], th)
            self.assertEqual(second['sha256'], smoke.sha256_file(tool))
            self.assertEqual(smoke.sha256_file(manifest), mh)

    def test_source_content_edits_or_lone_cr_are_rejected_before_execution(self):
        with TemporaryDirectory() as temp:
            main, vision, manifest, repo, mh, th = fixture(Path(temp))
            tool = repo / smoke.TOOL_RELATIVE
            original = tool.read_bytes()
            with patch.object(smoke, 'TOOL_LF_SHA256', th), patch.object(smoke, 'APPROVED_MANIFEST_SHA256', mh):
                for changed in (original.replace(b'fixture', b'CHANGED'), original.replace(b'\n', b'\r'), original + b' '):
                    tool.write_bytes(changed)
                    with self.assertRaises(ValueError): smoke.verify_tool_source(repo)
                    with self.assertRaises(ValueError): smoke.verify_assets(main, vision, manifest, repo)

    def test_worker_metadata_uses_shared_source_checker_and_retains_raw_evidence(self):
        import medical_tool_worker as worker
        schema = {'type': 'object', 'properties': {}}
        fields = {name: SimpleNamespace(default=value) for name, value in {
            'name': 'chest_xray_expert', 'description': 'SYNTHETIC metadata only', 'return_direct': True,
            'args_schema': SimpleNamespace(model_json_schema=lambda: schema)}.items()}
        module = SimpleNamespace(XRayVQATool=SimpleNamespace(model_fields=fields))
        module_spec = SimpleNamespace(name='_synthetic_chexagent_test',
                                      loader=SimpleNamespace(exec_module=lambda value: None))
        source = {'filename': smoke.TOOL_RELATIVE, 'sha256': 'a' * 64, 'lf_sha256': smoke.TOOL_LF_SHA256,
                  'reviewed_upstream_commit': smoke.TOOL_REVIEWED_COMMIT, 'normalization': 'CRLF_to_LF_only'}
        spec = SimpleNamespace(kind='chexagent', repo='synthetic_repo', asset_manifest='synthetic_manifest')
        with patch.dict(sys.modules, {'transformers': SimpleNamespace(__version__='4.40.0')}), \
                patch.object(smoke, 'verify_tool_source', return_value=source) as checked, \
                patch.object(worker.bridge, 'file_digest', return_value=smoke.APPROVED_MANIFEST_SHA256), \
                patch.object(worker.importlib.util, 'spec_from_file_location', return_value=module_spec), \
                patch.object(worker.importlib.util, 'module_from_spec', return_value=module):
            result = worker.describe(spec)
            checked.assert_called_once_with('synthetic_repo')
            self.assertEqual(result['source']['sha256'], 'a' * 64)
            self.assertEqual(result['source']['lf_sha256'], smoke.TOOL_LF_SHA256)
            self.assertEqual(result['source']['review_manifest_sha256'], smoke.APPROVED_MANIFEST_SHA256)

    def test_loaders_map_only_known_ids_locally_without_changing_device_or_dtype(self):
        records, classes = [], {}
        def fake_class(name):
            class Loader:
                @staticmethod
                def from_pretrained(path, *args, **kwargs):
                    records.append((name, path, kwargs)); return 'synthetic-loaded'
            return Loader
        for name in ('AutoTokenizer', 'AutoModelForCausalLM', 'AutoModel', 'AutoProcessor'):
            classes[name] = fake_class(name)
        transformers = SimpleNamespace(**classes)
        calls = []
        with TemporaryDirectory() as temp:
            main, vision = Path(temp) / 'main', Path(temp) / 'vision'
            with smoke.local_loaders(transformers, main, vision, calls):
                transformers.AutoModelForCausalLM.from_pretrained(smoke.MODEL_ID, device_map='cuda:1')
                transformers.AutoModel.from_pretrained(smoke.VISION_ID)
                transformers.AutoProcessor.from_pretrained(smoke.VISION_ID)
                transformers.AutoTokenizer.from_pretrained(smoke.MODEL_ID)
                with self.assertRaises(ValueError): transformers.AutoModel.from_pretrained('unreviewed/repository')
                with self.assertRaises(ValueError): transformers.AutoModel.from_pretrained(smoke.VISION_ID, revision='main')
            self.assertEqual(len(records), 4)
            self.assertEqual(records[0][1], str(main.resolve()))
            self.assertEqual(records[0][2]['device_map'], 'cuda:1')
            self.assertNotIn('torch_dtype', records[0][2])
            self.assertTrue(all(x[2]['local_files_only'] for x in records))
            self.assertFalse(records[1][2]['trust_remote_code'])
            self.assertTrue(records[0][2]['use_safetensors'])

    def test_network_guard_blocks_socket_and_http_and_restores_after_context(self):
        import requests
        original = socket.create_connection
        with smoke.block_network():
            with self.assertRaises(RuntimeError): socket.create_connection(('example.invalid', 443))
            with self.assertRaises(RuntimeError): requests.get('https://example.invalid')
        self.assertIs(socket.create_connection, original)

    def test_request_rejects_control_tag_injection_and_unbounded_generation(self):
        with TemporaryDirectory() as temp:
            image = Path(temp) / 'image.png'; image.write_bytes(b'synthetic')
            self.assertEqual(smoke.validate_request(image, 'short question', 64), image.resolve())
            for prompt, cap in [('<|img|>/other/file', 64), ('x' * 513, 64), ('ok', 1024), ('ok', True)]:
                with self.assertRaises(ValueError): smoke.validate_request(image, prompt, cap)

    def test_generation_audit_distinguishes_eos_from_last_token_discard_at_cap(self):
        natural = smoke.generation_audit(1050, [7, 8, 50256], 50256, 64)
        self.assertEqual(natural['termination'], 'eos')
        self.assertFalse(natural['non_eos_last_token_dropped'])
        truncated = smoke.generation_audit(1050, [7, 8], 50256, 2)
        self.assertTrue(truncated['output_at_cap'])
        self.assertTrue(truncated['non_eos_last_token_dropped'])
        self.assertEqual(truncated['termination'], 'length_or_other')

    def test_nonempty_text_without_real_vision_and_generation_is_not_success(self):
        result = ({'response': 'synthetic test response'}, {'analysis_status': 'completed'})
        for audit in ({'generate_calls': 0, 'visual_forward_calls': 0},
                      {'generate_calls': 1, 'visual_forward_calls': 0}):
            with self.assertRaises(ValueError): smoke.validate_result(result, audit)
        valid = smoke.validate_result(result, {'generate_calls': 1, 'visual_forward_calls': 1})
        self.assertTrue(valid['tool_execution_verified'])
        self.assertFalse(valid['clinical_correctness_verified'])
        with self.assertRaises(ValueError):
            smoke.validate_result(({'error': 'synthetic'}, {'analysis_status': 'failed'}),
                                  {'generate_calls': 1, 'visual_forward_calls': 1})


if __name__ == '__main__':
    unittest.main()
