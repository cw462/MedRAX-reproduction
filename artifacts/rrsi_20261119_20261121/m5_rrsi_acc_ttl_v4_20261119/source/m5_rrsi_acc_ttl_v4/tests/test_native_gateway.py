"""Software boundary tests, without medical inference or provider requests."""

import copy
import hashlib
import io
import json
from pathlib import Path
import shutil
import tempfile
import types
import unittest
from unittest.mock import patch

from integration.native_gateway import GatewayError, Registry, model_tokens, validate_binding


class NoInferenceBackend:
    deepseek_key = 'software-fixture-only'
    def embed(self, text):
        raise AssertionError('These boundary tests must reject before backend execution')


class GatewayBoundary(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        image = self.root / 'fixture.png'
        image.write_bytes(b'explicit synthetic software fixture')
        self.case = {'id': 'software-only', 'question': 'software fixture', 'options': [],
                     'images': [{'path': str(image), 'sha256': hashlib.sha256(image.read_bytes()).hexdigest()}]}
        self.row = {'question_id': self.case['id'], 'question': self.case['question'], 'images': ['fixture.png'], 'image_id': 'fixture'}
        self.cfg = {'audit_dir': str(self.root / 'audit'), 'public_url': 'http://gateway:9055',
                    'session_timeout_seconds': 60,
                    'limits': {'model_calls': 1, 'tool_calls': 1, 'output_tokens': 2048},
                    'protocol': {'model': 'qwen3.7-plus', 'temperature': 0.2, 'top_p': 0.95,
                                 'max_output_tokens': 2048, 'enable_thinking': False},
                    'deepseek_verify_profile': {'model': 'deepseek-flash', 'max_tokens': 8192,
                                                'reasoning_effort': 'high', 'thinking': {'type': 'enabled'}},
                    'runtime': {'arms': {'M': {'tools': ['synthetic-tool']}}, 'tools': {
                        'synthetic-tool': {'description': 'boundary only', 'revision': 'fixture', 'backend': 'fixture',
                                           'python': '/private/native/python', 'weights': '/private/weights'}}}}
        self.registry = Registry(self.cfg, backend=NoInferenceBackend())

    def tearDown(self):
        self.temp.cleanup()

    def register(self, **overrides):
        request = {'action': 'register', 'operation': 'predict', 'seed': 42,
                   'limits': self.cfg['limits'], 'case': self.case, 'native_row': self.row,
                   'state_dir': str(self.root / 'state'),
                   'image_annotations': [{'modality': 'software-fixture', 'view': 'fixture'}],
                   'order_item': {'image_key': 'fixture', 'previous_ids': []}, 'ordinal': 1}
        request.update(overrides)
        value = self.registry.control(request)
        return value, self.registry.sessions[value['session']]

    def test_only_registered_operations_exist(self):
        value, _ = self.register()
        for route in ('register', 'read_file', 'proxy', 'references'):
            with self.subTest(route=route), self.assertRaises(GatewayError):
                self.registry.request('/v1/session/' + value['session'] + '/' + route, {})

    def test_limits_are_owned_by_coordinator_configuration(self):
        with self.assertRaises(GatewayError):
            self.register(limits={'model_calls': None, 'tool_calls': None, 'output_tokens': 9999})

    def test_extra_model_and_url_fields_are_rejected(self):
        _, session = self.register()
        with self.assertRaises(GatewayError):
            session.dispatch('main', {'messages': [{'role': 'user', 'content': 'fixture'}], 'model': 'different'})
        with self.assertRaises(GatewayError):
            session.dispatch('main', {'messages': [], 'url': 'https://example.invalid'})

    def test_external_and_unbound_images_are_rejected(self):
        _, session = self.register()
        for uri in ('https://example.invalid/image.png', 'file:///private/reference', 'data:image/png;base64,eA=='):
            with self.subTest(uri=uri), self.assertRaises(GatewayError):
                session.check_messages([{'role': 'user', 'content': [{'type': 'image_url', 'image_url': {'url': uri}}]}])

    def test_original_pixels_are_bound(self):
        _, session = self.register()
        uri = next(iter(session.allowed_images))
        session.check_messages([{'role': 'user', 'content': [{'type': 'image_url', 'image_url': {'url': uri}}]}])
        changed = copy.deepcopy(self.case)
        changed['images'][0]['sha256'] = '0' * 64
        with self.assertRaises(GatewayError):
            self.register(case=changed)

    def test_other_question_row_is_rejected(self):
        _, session = self.register()
        row = dict(self.row, question_id='different-case')
        with self.assertRaises(GatewayError):
            session.tool({'row': row, 'action': {'tool': 'synthetic-tool', 'args': {}}, 'ordinal': 1})

    def test_metadata_contains_only_current_case_and_public_catalog(self):
        _, session = self.register()
        metadata = session.dispatch('metadata', {})
        self.assertEqual(metadata['native_row'], self.row)
        self.assertEqual(metadata['image_views'], {'fixture.png': '/case_images/0.png'})
        self.assertNotIn('python', metadata['runtime_catalog']['tools']['synthetic-tool'])
        self.assertNotIn('weights', metadata['runtime_catalog']['tools']['synthetic-tool'])
        self.assertNotIn('reference', metadata)

    def test_call_budget_is_enforced_before_backend(self):
        _, session = self.register()
        session.claim('model_calls')
        with self.assertRaises(GatewayError):
            session.claim('model_calls')
        self.assertEqual(session.usage()['model_calls'], 1)

    def test_unlimited_native_counts_are_preserved(self):
        self.cfg['limits'].update(model_calls=None, tool_calls=None)
        _, session = self.register()
        for _ in range(4):
            session.claim('model_calls')
        self.assertEqual(session.usage()['model_calls'], 4)

    def test_no_model_request_during_deterministic_migration(self):
        _, session = self.register(operation='migrate', case=None)
        with self.assertRaises(GatewayError):
            session.dispatch('memory', {'messages': [{'role': 'user', 'content': 'fixture'}]})

    def test_session_close_is_authoritative_and_revokes_access(self):
        value, session = self.register()
        session.counts['total_tokens'] = 17
        result = self.registry.control({'action': 'close', 'session': value['session']})
        self.assertEqual(result['total_tokens'], 17)
        self.assertTrue(result['authoritative'])
        with self.assertRaises(GatewayError):
            session.dispatch('metadata', {})

    def test_unknown_usage_cannot_be_reported_as_free(self):
        with self.assertRaises(GatewayError):
            model_tokens({'choices': []})
        self.assertEqual(model_tokens({'usage': {'prompt_tokens': 4, 'completion_tokens': 2}}), 6)

    def test_current_image_view_map_uses_session_paths(self):
        _, session = self.register()
        views = session.runtime['backend_config']['r54_image_views_by_path']
        self.assertEqual(views, {str((session.image_root / 'fixture.png').resolve()):
                                {'modality': 'software-fixture', 'view': 'fixture'}})
        self.assertNotIn('/future/image.png', views)

    def test_tool_cannot_select_url_file_or_model(self):
        _, session = self.register()
        for key in ('url', 'path', 'file', 'model', 'revision', 'runtime'):
            with self.subTest(key=key), self.assertRaises(GatewayError):
                session.tool({'row': self.row, 'action': {'tool': 'synthetic-tool', 'args': {key: 'other'}}, 'ordinal': 1})

    def test_native_cache_follows_copied_state_without_changing_key_or_text(self):
        _, first = self.register()
        cache = first.native_out / 'tool_cache' / 'native-identity-key'
        cache.mkdir(parents=True)
        image = cache / 'artifacts' / 'derived.png'
        image.parent.mkdir()
        image.write_bytes(b'synthetic derived software fixture')
        record = {'derived_images': [str(image)], 'observation': {'text': str(image)}, 'cache_key': 'native-identity-key'}
        (cache / 'result.json').write_text(json.dumps(record))
        copied = self.root / 'copied_state'
        shutil.copytree(self.root / 'state', copied)
        _, second = self.register(state_dir=str(copied))
        restored = json.loads((second.native_out / 'tool_cache/native-identity-key/result.json').read_text())
        self.assertEqual(restored['cache_key'], record['cache_key'])
        self.assertEqual(restored['observation']['text'], record['observation']['text'])
        self.assertEqual(restored['derived_images'], [str(second.native_out / 'tool_cache/native-identity-key/artifacts/derived.png')])
        self.assertTrue(Path(restored['derived_images'][0]).is_file())

    def test_initialize_does_not_populate_empty_state(self):
        state = self.root / 'initial_state'
        state.mkdir()
        self.register(operation='initialize', case=None, state_dir=str(state))
        self.assertEqual(list(state.iterdir()), [])

    def test_invalid_verifier_json_is_a_native_failure_observation_receipt(self):
        _, session = self.register()
        recovery = types.ModuleType('r55_top4_verify_recovery')
        recovery.inspect_reply = lambda raw, model: ({}, None, 'r55_verifier_invalid_response')
        with patch.dict('sys.modules', {'r55_top4_verify_recovery': recovery}), \
                patch('integration.native_gateway.urlopen', return_value=io.BytesIO(b'[]')):
            with self.assertRaisesRegex(ValueError, '^r55_verifier_invalid_response$'):
                session.native_verify('verify_software-only_1', [{'role': 'user', 'content': 'fixture'}])
        folder = session.native_out / 'calls/R55-VERIFY/verify_software-only_1/1'
        result = json.loads((folder / 'result.json').read_text())
        self.assertEqual(result['request_id'], 'r55:R55-VERIFY:verify_software-only_1:1')
        self.assertEqual(result['error'], 'r55_verifier_invalid_response')
        self.assertTrue(result['response_received'])

    def test_verifier_transport_failure_keeps_native_exception_and_request_id(self):
        _, session = self.register()
        recovery = types.ModuleType('r55_top4_verify_recovery')
        with patch.dict('sys.modules', {'r55_top4_verify_recovery': recovery}), \
                patch('integration.native_gateway.urlopen', side_effect=TimeoutError('software fixture')):
            with self.assertRaisesRegex(RuntimeError, '^r55_verifier_transport_failed:TimeoutError$'):
                session.native_verify('verify_software-only_1', [{'role': 'user', 'content': 'fixture'}])
        folder = session.native_out / 'calls/R55-VERIFY/verify_software-only_1/1'
        result = json.loads((folder / 'result.json').read_text())
        started = json.loads((folder / 'started.json').read_text())
        self.assertEqual(result['request_id'], started['request_id'])
        self.assertEqual(result['error'], 'TimeoutError')
        self.assertEqual(result['failure_stage'], 'transport')
        self.assertFalse(result['response_received'])


class FixedBinding(unittest.TestCase):
    def config(self):
        names = ['chest_xray_expert', 'llava_med_qa', 'medgemma', 'llava_rad', 'medvlm_r1',
                 'maira2_grounded_report', 'xray_phrase_grounding', 'roi_crop', 'medret', 'reflect', 'verify']
        return {'protocol': {'model': 'qwen3.7-plus', 'max_output_tokens': 2048,
                             'temperature': 0.2, 'top_p': 0.95, 'enable_thinking': False},
                'limits': {'model_calls': None, 'tool_calls': None, 'output_tokens': 2048},
                'runtime': {'arms': {'M': {'tools': names}}, 'tools': {'chest_xray_expert': {
                    'revision': '4934e91451945c8218c267aae9c34929a7677829'}}},
                'deepseek_memory_profile': {'model': 'deepseek-flash', 'max_tokens': 2048,
                                            'temperature': 0, 'thinking': {'type': 'disabled'}},
                'deepseek_verify_profile': {'model': 'deepseek-flash', 'max_tokens': 8192,
                                            'reasoning_effort': 'high', 'thinking': {'type': 'enabled'}}}

    def test_native_profiles_preserve_separate_verify_budget(self):
        validate_binding(self.config())

    def test_main_model_cannot_be_replaced(self):
        config = self.config()
        config['protocol']['model'] = 'another-model'
        with self.assertRaises(GatewayError):
            validate_binding(config)

    def test_tool_revision_cannot_be_replaced(self):
        config = self.config()
        config['runtime']['tools']['chest_xray_expert']['revision'] = 'different'
        with self.assertRaises(GatewayError):
            validate_binding(config)

    def test_verify_cannot_be_silently_cut_to_main_token_budget(self):
        config = self.config()
        config['deepseek_verify_profile']['max_tokens'] = 2048
        with self.assertRaises(GatewayError):
            validate_binding(config)


if __name__ == '__main__':
    unittest.main()
