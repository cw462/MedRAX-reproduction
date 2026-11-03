"""Synthetic E1 model routing checks; no API, benchmark, or real ledger access."""
from copy import deepcopy
from decimal import Decimal
import io
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from PIL import Image

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'experiments'))
import run_sampled_vlm as runner

PROFILE_FILES = {
    'deepseek-v4.1-flash-1017': 'deepseek_v41_flash_1017_token_plan_profile.json',
    'qwen3.8-flash': 'qwen38_flash_token_plan_profile.json',
}


def configuration(model, root='synthetic-root'):
    profile = json.loads((REPO / 'configs' / PROFILE_FILES[model]).read_text(encoding='utf-8'))
    return dict(root=str(root), input='questions.jsonl', image_root='images', run_id='synthetic_flash',
                model=model, credential_slot='token_plan', prompt_variant='answer', samples=1,
                temperature=.2, top_p=.95, max_output_tokens=2048, request_timeout_seconds=10,
                figure_labels=False, high_resolution=False, extra_body={'enable_thinking': False},
                profile=profile, ledger='unused_mock_ledger.json', cap_cny='10',
                budget_authorization='synthetic-only', max_requests=2, max_extra_requests=1,
                global_request_counter='counter.json', global_max_requests=2,
                global_max_extra_requests=1)


class TokenPlanFlashModels(unittest.TestCase):
    def test_only_two_requested_models_are_added(self):
        self.assertEqual(runner.MODELS, {'qwen3-vl-plus', 'qwen3.7-plus', 'qwen3.8-max-0902',
                                        'gpt-4o', *PROFILE_FILES})

    def test_deepseek_snapshot_is_exact_without_alias_substitution(self):
        profile = runner.validate_cfg(configuration('deepseek-v4.1-flash-1017'))
        self.assertTrue(profile.identity_ok('deepseek-v4.1-flash-1017'))
        for returned in (None, '', 'deepseek-v4.1-flash', 'deepseek-v4.1-flash-1018',
                         'deepseek-v4.1-flash-1017-mini', 'deepseek-v4.1-flash-2026-10-17'):
            self.assertFalse(profile.identity_ok(returned), returned)

    def test_qwen_flash_identity_rejects_siblings_and_partial_dates(self):
        profile = runner.validate_cfg(configuration('qwen3.8-flash'))
        for returned in ('qwen3.8-flash', 'qwen3.8-flash-2026-10-17'):
            self.assertTrue(profile.identity_ok(returned), returned)
        for returned in (None, '', 'qwen3.8-plus', 'qwen3.8-flash-mini', 'qwen3.8-flash-1017',
                         'qwen3.8-flash-2026-10-17-other', 'qwen3x8-flash-2026-10-17'):
            self.assertFalse(profile.identity_ok(returned), returned)

    def test_both_models_require_the_token_plan_key_and_exact_endpoint(self):
        for model in PROFILE_FILES:
            for slot in ('dashscope', 'apiyi', None):
                cfg = configuration(model); cfg['credential_slot'] = slot
                with self.subTest(model=model, slot=slot), self.assertRaisesRegex(ValueError, 'credential_slot'):
                    runner.validate_cfg(cfg)
            for endpoint in ('https://dashscope.aliyuncs.com/compatible-mode/v1',
                             runner.TOKEN_PLAN_BASE_URL + '/',
                             runner.TOKEN_PLAN_BASE_URL + '?redirect=other'):
                cfg = configuration(model); cfg['profile']['base_url'] = endpoint
                with self.subTest(model=model, endpoint=endpoint), self.assertRaisesRegex(ValueError, 'token_plan_endpoint'):
                    runner.validate_cfg(cfg)

    def test_profile_identity_list_cannot_widen_accepted_family(self):
        for model in PROFILE_FILES:
            cfg = configuration(model); cfg['profile']['identity_prefixes'] = [model, 'other']
            with self.subTest(model=model), self.assertRaisesRegex(ValueError, 'exact_family_identity'):
                runner.validate_cfg(cfg)

    def test_non_thinking_is_explicit_for_both_models(self):
        for model in PROFILE_FILES:
            for extra, variant in (({}, 'answer'), ({'enable_thinking': True}, 'answer'),
                                   ({'enable_thinking': True}, 'think')):
                cfg = configuration(model); cfg.update(extra_body=extra, prompt_variant=variant)
                with self.subTest(model=model, extra=extra, variant=variant), self.assertRaises(ValueError):
                    runner.validate_cfg(cfg)

    def test_public_profiles_disclose_proxy_without_claiming_actual_prices(self):
        for model in PROFILE_FILES:
            profile = runner.validate_cfg(configuration(model))
            with self.subTest(model=model):
                self.assertEqual(profile.input_cny_per_million, Decimal('4'))
                self.assertEqual(profile.output_cny_per_million, Decimal('12'))
                self.assertIn(runner.TOKEN_PLAN_FLASH_ACCOUNTING_NOTE, profile.price_basis)
                self.assertIn('not actual provider prices', profile.price_basis)
                self.assertIn('original cumulative budget cap is unchanged', profile.price_basis)

    def test_prior_models_keep_their_routes_and_identity_behavior(self):
        for model, slot in [('qwen3-vl-plus', 'dashscope'), ('qwen3.8-max-0902', 'dashscope'),
                            ('qwen3.7-plus', 'token_plan'), ('gpt-4o', 'apiyi')]:
            cfg = configuration('qwen3.8-flash')
            cfg.update(model=model, credential_slot=slot)
            cfg['profile'].update(identity_prefixes=[model], price_basis='synthetic old-model profile')
            if slot != 'token_plan':
                cfg['profile']['base_url'] = 'https://example.invalid/v1'
            if model == 'gpt-4o':
                cfg.update(extra_body={}); cfg['profile']['max_input_tokens'] = 120000
            with self.subTest(model=model):
                profile = runner.validate_cfg(cfg)
                self.assertTrue(profile.identity_ok(model))
                if model in ('gpt-4o', 'qwen3.7-plus'):
                    self.assertFalse(profile.identity_ok(model + '-mini'))
                bad = deepcopy(cfg); bad['credential_slot'] = 'apiyi' if slot == 'token_plan' else 'token_plan'
                with self.assertRaisesRegex(ValueError, 'credential_slot'):
                    runner.validate_cfg(bad)

    def test_mock_execution_keeps_native_images_and_non_thinking_payload(self):
        for model in PROFILE_FILES:
            with self.subTest(model=model), tempfile.TemporaryDirectory() as temp:
                root = Path(temp); (root/'images').mkdir()
                Image.new('RGB', (19, 23), (17, 31, 63)).save(root/'images'/'figure.png')
                row = {'question_id': 'q1', 'case_id': 'c1', 'question': 'Figure 1.\nA) Alpha\nB) Beta',
                       'images': ['figure.png'], 'figure_labels': ['Figure 1']}
                (root/'questions.jsonl').write_text(json.dumps(row)+'\n', encoding='utf-8')
                cfg = configuration(model, root)
                returned = model if model.startswith('deepseek') else model + '-2026-10-17'
                raw = {'model': returned, 'choices': [{'message': {'content': 'Answer: B'}, 'finish_reason': 'stop'}],
                       'usage': {'prompt_tokens': 10, 'completion_tokens': 5}}
                create = Mock(return_value=SimpleNamespace(model_dump=lambda **_: raw))
                factory = Mock(return_value=SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create))))

                class MockLedger:
                    def __init__(self, *args, **kwargs): self.remaining = Decimal('10')
                    def __enter__(self): return self
                    def __exit__(self, *args): pass
                    def reserve(self, **kwargs): return 'mock-reservation'
                    def settle(self, *args, **kwargs): return {'charged_cny': '0', 'status': 'settled'}

                out = root/'out'; out.mkdir()
                with patch.dict(sys.modules, {'openai': SimpleNamespace(OpenAI=factory),
                                              'v12_ledger': SimpleNamespace(V12ProviderLedger=MockLedger)}):
                    with patch.object(sys, 'stdin', io.StringIO('synthetic-token-plan-key\n')):
                        code = runner.run(SimpleNamespace(prepare_only=False, api_key_stdin=True), cfg, out)
                self.assertEqual(code, 0)
                self.assertEqual(factory.call_args.kwargs['base_url'], runner.TOKEN_PLAN_BASE_URL)
                sent = create.call_args.kwargs
                self.assertEqual(sent['model'], model)
                self.assertEqual(sent['extra_body'], {'enable_thinking': False})
                self.assertEqual(sent['max_tokens'], 2048)
                self.assertEqual(sent['temperature'], .2)
                self.assertEqual(sent['top_p'], .95)
                self.assertTrue(any(item.get('image_url', {}).get('url', '').startswith('data:image/')
                                    for item in sent['messages'][1]['content']))
                terminal = runner.read(out/'checkpoints/q1/sample_1/terminal.json')
                self.assertEqual(terminal['attempts'][0]['response_model'], returned)
                self.assertEqual(terminal['answer'], 'B')


class SamplingAdapterHooks(unittest.TestCase):
    def test_adapter_callbacks_preserve_accounting_and_existing_terminals(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); out = root/'out'; out.mkdir()
            cfg = configuration('qwen3.8-flash', root)
            row = {'question_id': 'case1', 'case_id': 'case1', 'question': 'Synthetic grouped case'}
            legal = {'q1': {'A', 'B'}, 'q2': {'C', 'D'}}
            parsed = {'answer': 'CASE', 'status': 'completed', 'case_answers': {'q1': 'B', 'q2': 'D'}}
            messages = [{'role': 'user', 'content': 'Synthetic grouped request'}]
            adapter = SimpleNamespace(prepare=Mock(return_value=[row]), legal=Mock(return_value=legal),
                                      request=Mock(return_value=(messages, [])), parse=Mock(return_value=parsed))
            raw = {'model': 'qwen3.8-flash',
                   'choices': [{'message': {'content': 'synthetic-case-output'}, 'finish_reason': 'stop'}],
                   'usage': {'prompt_tokens': 10, 'completion_tokens': 5}}
            create = Mock(return_value=SimpleNamespace(model_dump=lambda **_: raw))
            factory = Mock(return_value=SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create))))
            reserve = Mock(return_value='mock-reservation')
            settle = Mock(return_value={'charged_cny': '0', 'status': 'settled'})

            class MockLedger:
                def __init__(self, *args, **kwargs): self.remaining = Decimal('10')
                def __enter__(self): return self
                def __exit__(self, *args): pass
                def reserve(self, **kwargs): return reserve(**kwargs)
                def settle(self, *args, **kwargs): return settle(*args, **kwargs)

            args = SimpleNamespace(prepare_only=False, api_key_stdin=True)
            with patch.dict(sys.modules, {'openai': SimpleNamespace(OpenAI=factory),
                                          'v12_ledger': SimpleNamespace(V12ProviderLedger=MockLedger)}):
                with patch.object(sys, 'stdin', io.StringIO('synthetic-token-plan-key\n')):
                    self.assertEqual(runner.run(args, cfg, out, adapter=adapter), 0)
                # A second pass must use the saved terminal without credential/API access.
                with patch.object(sys, 'stdin', Mock(readline=Mock(side_effect=AssertionError('no key reread')))):
                    self.assertEqual(runner.run(args, cfg, out, adapter=adapter), 0)
            adapter.legal.assert_called_once_with(row)
            adapter.request.assert_called_once_with(row, cfg, out)
            adapter.parse.assert_called_once_with('synthetic-case-output', legal)
            create.assert_called_once()
            reserve.assert_called_once()
            settle.assert_called_once()
            self.assertEqual(create.call_args.kwargs['messages'], messages)
            terminal = runner.read(out/'checkpoints/case1/sample_1/terminal.json')
            self.assertEqual(terminal['case_answers'], parsed['case_answers'])
            self.assertEqual(terminal['answer'], 'CASE')
            self.assertEqual(terminal['question_id'], 'case1')
            self.assertEqual(len(runner.read(root/'counter.json')['request_ids']), 1)

    def test_adapter_prepare_only_never_reads_a_key_or_opens_a_client(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); out = root/'out'; out.mkdir()
            cfg = configuration('qwen3.8-flash', root)
            adapter = SimpleNamespace(prepare=Mock(return_value=[{'question_id': 'case1'}]),
                                      parse=Mock(), request=Mock(), legal=Mock())
            factory = Mock(side_effect=AssertionError('no client during prepare'))
            with patch.dict(sys.modules, {'openai': SimpleNamespace(OpenAI=factory)}):
                with patch.object(sys, 'stdin', Mock(readline=Mock(side_effect=AssertionError('no key during prepare')))):
                    code = runner.run(SimpleNamespace(prepare_only=True, api_key_stdin=True), cfg, out, adapter=adapter)
            self.assertEqual(code, 0)
            adapter.request.assert_not_called()
            adapter.legal.assert_not_called()
            factory.assert_not_called()
            self.assertEqual(runner.read(out/'status.json')['status'], 'prepared')

    def test_recovery_uses_adapter_parser_without_reissuing_saved_response(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            runner.write(folder/'started.json', {'request_id': 'synthetic-request'})
            runner.write(folder/'response.json', {'model': 'qwen3.8-flash',
                         'choices': [{'message': {'content': 'saved-case-answer'}}],
                         'usage': {'prompt_tokens': 10, 'completion_tokens': 5}})
            parsed = {'answer': 'CASE', 'status': 'completed', 'case_answers': {'q1': 'B'}}
            parse_fn = Mock(return_value=parsed)
            result = runner.recover_attempt(folder, {'q1': {'A', 'B'}},
                                            runner.profile_for(configuration('qwen3.8-flash')), parse_fn=parse_fn)
            self.assertEqual(result['parsed'], parsed)
            self.assertEqual(result['recovery'], 'saved_response_reused_no_new_request')
            parse_fn.assert_called_once_with('saved-case-answer', {'q1': {'A', 'B'}})
            again = runner.recover_attempt(folder, {}, parse_fn=Mock(side_effect=AssertionError('no reparse')))
            self.assertEqual(again, result)


if __name__ == '__main__':
    unittest.main()
