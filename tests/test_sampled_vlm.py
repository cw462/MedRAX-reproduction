"""Synthetic contract checks; no benchmark labels, network or real ledger."""
from decimal import Decimal
import base64
import io
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'experiments'))
import run_sampled_vlm as runner


def config(root):
    return dict(root=str(root), input='questions.jsonl', image_root='images',
        run_id='synthetic_test', model='qwen3-vl-plus', credential_slot='dashscope', prompt_variant='answer',
        samples=1, temperature=.2, top_p=.95, max_output_tokens=256,
        request_timeout_seconds=10, figure_labels=False, high_resolution=False,
        extra_body={'enable_thinking':False}, profile=dict(
            base_url='https://example.invalid/v1', identity_prefixes=['qwen3-vl-plus'],
            input_cny_per_million='4', output_cny_per_million='12',
            price_basis='synthetic test only', max_input_tokens=10000, max_output_tokens=1024),
        ledger='unused_mock_ledger.json', cap_cny='10', budget_authorization='synthetic',
        max_requests=2, max_extra_requests=1, global_request_counter='counter.json',
        global_max_requests=2, global_max_extra_requests=1)


class Parsing(unittest.TestCase):
    def test_full_options_and_last_explicit_answer(self):
        for text in ('**Answer:** **b**. Full option\nReason: short',
                     'Answer: A) First thought\nAnswer: B) Revised final',
                     'Evidence summary.\nFinal Answer: (B)', 'B'):
            self.assertEqual(runner.parse_answer(text, {'A','B'})['answer'], 'B')

    def test_no_guess_from_reason_or_ambiguous_final(self):
        for text in ('Reason: B fits', 'Answer: A or B', 'Answer: A) or B',
                     'Answer: A/B', 'Answer: A\nAnswer: cannot determine',
                     'Answer: Z\nReason: B is plausible', None):
            self.assertIsNone(runner.parse_answer(text, {'A','B'})['answer'], text)

    def test_baseline_system_prompt_is_unchanged(self):
        self.assertIn('Reason:', runner.SYSTEM_PROMPT)
        self.assertIn('at most 150 words', runner.COT_PROMPT)


class InputAndBudgetContracts(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name); (self.root/'images').mkdir()
        self.cfg=config(self.root)
        self.row={'question_id':'q1','case_id':'case1',
            'question':'Compare Figure 2 with Figure 1.\nA) Alpha\nB) Beta',
            'images':['figure_1.png','figure_2.png'], 'figure_labels':['Figure 1','Figure 2']}
        for index in (1,2):
            Image.new('RGB',(20+index,25),(index,2,3)).save(self.root/'images'/f'figure_{index}.png')
        (self.root/'questions.jsonl').write_text(json.dumps(self.row)+'\n',encoding='utf-8')

    def test_native_bytes_are_bound_to_correct_figure_after_ordering(self):
        self.cfg['figure_labels']=True
        messages, images=runner.request_for(self.row,self.cfg)
        self.assertEqual([x['figure_label'] for x in images], ['Figure 2','Figure 1'])
        content=messages[1]['content']
        payload_images=[x for x in content if x['type']=='image_url']
        for expected, item in zip(('figure_2.png','figure_1.png'),payload_images):
            self.assertEqual(base64.b64decode(item['image_url']['url'].split(',',1)[1]),
                             (self.root/'images'/expected).read_bytes())
        for i,item in enumerate(content):
            if item['type']=='image_url': self.assertRegex(content[i-1]['text'],r'^Figure [12]:$')
        self.assertTrue(all(x['timepoint']=='unknown' for x in images))

    def test_text_only_never_loads_images(self):
        self.cfg['prompt_variant']='text_only'
        row=dict(self.row,images=['missing.png'])
        messages,images=runner.request_for(row,self.cfg)
        self.assertEqual(images,[]);self.assertEqual(messages[1]['content'],row['question'])

    def test_references_and_metadata_cannot_enter_input(self):
        row=dict(self.row,correct_answer='B')
        (self.root/'questions.jsonl').write_text(json.dumps(row)+'\n',encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'forbidden'):
            runner.prepare(self.cfg,self.root/'out')

    def test_immutable_config_and_records(self):
        runner.prepare(self.cfg,self.root/'out')
        runner.prepare(self.cfg,self.root/'out')
        self.cfg['temperature']=.7
        with self.assertRaisesRegex(ValueError,'immutable'):
            runner.prepare(self.cfg,self.root/'out')

    def test_explicit_rates_and_thinking_are_required(self):
        self.cfg['profile']['price_basis']=''
        with self.assertRaisesRegex(ValueError,'explicit_cost'):runner.validate_cfg(self.cfg)
        self.cfg=config(self.root);self.cfg['extra_body']={}
        with self.assertRaisesRegex(ValueError,'pin_qwen'):runner.validate_cfg(self.cfg)
        self.cfg=config(self.root);self.cfg['prompt_variant']='think'
        with self.assertRaisesRegex(ValueError,'enable_thinking'):runner.validate_cfg(self.cfg)

    def gpt4o_config(self):
        self.cfg.update(model='gpt-4o', credential_slot='apiyi', extra_body={})
        self.cfg['profile']['identity_prefixes']=['gpt-4o']
        self.cfg['profile'].update(max_input_tokens=120000,max_output_tokens=8192)
        return self.cfg

    def token_plan_config(self):
        self.cfg.update(model='qwen3.7-plus', credential_slot='token_plan')
        self.cfg['profile'].update(base_url=runner.TOKEN_PLAN_BASE_URL,
                                   identity_prefixes=['qwen3.7-plus'])
        return self.cfg

    def test_token_plan_identity_and_accounting_are_explicit(self):
        profile=runner.validate_cfg(self.token_plan_config())
        for identity in ('qwen3.7-plus','qwen3.7-plus-2026-05-26'):
            self.assertTrue(profile.identity_ok(identity),identity)
        for identity in (None,'','qwen3-vl-plus','qwen3.7-plus-mini',
                         'qwen3.7-plus-2026-05-26-other','qwen3x7-plus-2026-05-26'):
            self.assertFalse(profile.identity_ok(identity),identity)
        self.assertIn(runner.TOKEN_PLAN_ACCOUNTING_NOTE,profile.price_basis)
        self.assertEqual(profile.input_cny_per_million,Decimal('4'))
        self.assertEqual(profile.output_cny_per_million,Decimal('12'))

    def test_token_plan_requires_its_own_key_route_endpoint_and_family(self):
        self.token_plan_config()
        for slot in ('dashscope','apiyi',None):
            self.cfg['credential_slot']=slot
            with self.assertRaisesRegex(ValueError,'credential_slot'):runner.validate_cfg(self.cfg)
        self.cfg['credential_slot']='token_plan'
        for endpoint in ('https://example.invalid/v1',runner.TOKEN_PLAN_BASE_URL+'/',
                         runner.TOKEN_PLAN_BASE_URL+'?provider=other'):
            self.cfg['profile']['base_url']=endpoint
            with self.assertRaisesRegex(ValueError,'token_plan_endpoint'):runner.validate_cfg(self.cfg)
        self.cfg['profile']['base_url']=runner.TOKEN_PLAN_BASE_URL
        self.cfg['profile']['identity_prefixes']=['qwen3.7-plus','qwen3-vl-plus']
        with self.assertRaisesRegex(ValueError,'exact_family_identity'):runner.validate_cfg(self.cfg)

    def test_token_plan_high_resolution_payload_is_explicit_and_unchanged(self):
        cfg=self.token_plan_config()
        cfg.update(high_resolution=True,capability_confirmed=True)
        cfg['extra_body']['vl_high_resolution_images']=True
        runner.validate_cfg(cfg)
        cfg['extra_body'].pop('enable_thinking')
        with self.assertRaisesRegex(ValueError,'pin_qwen'):runner.validate_cfg(cfg)
        cfg['extra_body']['enable_thinking']=False
        raw={'model':'qwen3.7-plus-2026-05-26',
             'choices':[{'message':{'content':'Answer: B'},'finish_reason':'stop'}],
             'usage':{'prompt_tokens':10,'completion_tokens':5}}
        create=Mock(return_value=SimpleNamespace(model_dump=lambda **_:raw))
        client=SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
        factory=Mock(return_value=client)
        class MockLedger:
            def __init__(self,*args,**kwargs):self.remaining=Decimal('10')
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def reserve(self,**kwargs):return 'mock-id'
            def settle(self,*args,**kwargs):return {'charged_cny':'0','status':'settled'}
        out=self.root/'token-plan-out';out.mkdir()
        with patch.dict(sys.modules,{'openai':SimpleNamespace(OpenAI=factory),
                                    'v12_ledger':SimpleNamespace(V12ProviderLedger=MockLedger)}):
            with patch.object(sys,'stdin',io.StringIO('synthetic-token-plan-key\n')):
                self.assertEqual(runner.run(SimpleNamespace(prepare_only=False,api_key_stdin=True),cfg,out),0)
        self.assertEqual(factory.call_args.kwargs['base_url'],runner.TOKEN_PLAN_BASE_URL)
        self.assertEqual(factory.call_args.kwargs['api_key'],'synthetic-token-plan-key')
        sent=create.call_args.kwargs
        self.assertEqual(sent['model'],'qwen3.7-plus')
        self.assertEqual(sent['extra_body'],{'enable_thinking':False,'vl_high_resolution_images':True})
        self.assertTrue(any(item.get('image_url',{}).get('url','').startswith('data:image/')
                            for item in sent['messages'][1]['content']))
        terminal=runner.read(out/'checkpoints/q1/sample_1/terminal.json')
        self.assertEqual(terminal['attempts'][0]['response_model'],'qwen3.7-plus-2026-05-26')

    def test_gpt4o_baseline_sampling_and_provider_parameters(self):
        self.gpt4o_config()
        runner.validate_cfg(self.cfg)
        self.cfg['temperature']=.7
        runner.validate_cfg(self.cfg)
        for key,value in {'enable_thinking':False,'thinking_budget':4096,
                          'reasoning_effort':'low','vl_high_resolution_images':False}.items():
            self.cfg['extra_body']={key:value}
            with self.assertRaisesRegex(ValueError,'gpt4o_no_provider'):runner.validate_cfg(self.cfg)
        self.cfg['extra_body']={};self.cfg['prompt_variant']='think'
        with self.assertRaisesRegex(ValueError,'gpt4o_no_provider'):runner.validate_cfg(self.cfg)

    def test_gpt4o_identity_cannot_accept_mini_or_unknown_snapshot_suffix(self):
        profile=runner.validate_cfg(self.gpt4o_config())
        for identity in ('gpt-4o','gpt-4o-2024-05-13','gpt-4o-2024-08-06','gpt-4o-2024-11-20'):
            self.assertTrue(profile.identity_ok(identity), identity)
        for identity in (None,'','gpt-4o-mini','gpt-4o-mini-2024-07-18','gpt-4o-2024-08-06-other','other'):
            self.assertFalse(profile.identity_ok(identity), identity)

    def test_gpt4o_context_and_credential_slot_are_explicit(self):
        self.gpt4o_config();self.cfg['profile']['max_input_tokens']=131072
        with self.assertRaisesRegex(ValueError,'gpt4o_context'):runner.validate_cfg(self.cfg)
        self.cfg['profile']['max_input_tokens']=120000
        self.cfg['profile']['max_output_tokens']=16384
        with self.assertRaisesRegex(ValueError,'gpt4o_context'):runner.validate_cfg(self.cfg)
        self.cfg['profile']['max_output_tokens']=8192;self.cfg['credential_slot']='dashscope'
        with self.assertRaisesRegex(ValueError,'credential_slot'):runner.validate_cfg(self.cfg)

    def test_gpt4o_actual_mock_payload_uses_images_and_archives_returned_snapshot(self):
        cfg=self.gpt4o_config();cfg['max_output_tokens']=2048
        raw={'model':'gpt-4o-2024-11-20','choices':[{'message':{'content':'Answer: B'},'finish_reason':'stop'}],
             'usage':{'prompt_tokens':10,'completion_tokens':5}}
        create=Mock(return_value=SimpleNamespace(model_dump=lambda **_:raw))
        client=SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
        class MockLedger:
            def __init__(self,*args,**kwargs):self.remaining=Decimal('10')
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def reserve(self,**kwargs):return 'mock-id'
            def settle(self,*args,**kwargs):return {'charged_cny':'0','status':'settled'}
        out=self.root/'gpt-out';out.mkdir()
        with patch.dict(sys.modules,{'openai':SimpleNamespace(OpenAI=lambda **_:client),
                                    'v12_ledger':SimpleNamespace(V12ProviderLedger=MockLedger)}):
            with patch.object(sys,'stdin',io.StringIO('synthetic-apiyi-key\n')):
                self.assertEqual(runner.run(SimpleNamespace(prepare_only=False,api_key_stdin=True),cfg,out),0)
        sent=create.call_args.kwargs
        self.assertEqual(sent['model'],'gpt-4o');self.assertEqual(sent['max_tokens'],2048)
        self.assertEqual(sent['temperature'],.2);self.assertEqual(sent['top_p'],.95)
        self.assertEqual(sent.get('extra_body',{}),{})
        self.assertTrue(any(item.get('image_url',{}).get('url','').startswith('data:image/')
                            for item in sent['messages'][1]['content']))
        terminal=runner.read(out/'checkpoints/q1/sample_1/terminal.json')
        self.assertEqual(terminal['attempts'][0]['response_model'],'gpt-4o-2024-11-20')
        self.assertEqual(terminal['model'],'gpt-4o')
        self.assertIs(runner.read(out/'checkpoints/q1/sample_1/image_metadata.json')['native_bytes_sent'],True)

    def test_global_cap_precedes_monetary_reservation_and_survives_resume(self):
        reserve=Mock(return_value='mock-reservation')
        self.assertEqual(runner.claim_global(self.cfg,'r1',False,reserve),'mock-reservation')
        runner.claim_global(self.cfg,'r2',True,reserve)
        with self.assertRaisesRegex(ValueError,'global_request_limit'):
            runner.claim_global(self.cfg,'r3',False,reserve)
        self.assertEqual(reserve.call_count,2)
        with self.assertRaisesRegex(ValueError,'already_claimed'):
            runner.claim_global(self.cfg,'r1',False,reserve)
        self.assertEqual(reserve.call_count,2)

    def test_unsent_counter_write_failure_exposes_reservation(self):
        with patch.object(runner,'write',side_effect=OSError('simulated disk full')):
            with self.assertRaises(OSError) as caught:
                runner.claim_global(self.cfg,'r1',False,lambda:'reserved')
        self.assertEqual(caught.exception.unsent_reservation,'reserved')


class Recovery(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)

    def test_unknown_started_attempt_is_not_retryable(self):
        folder=self.root/'attempt_1'
        runner.frozen_write(folder/'started.json',{'request_id':'test'})
        result=runner.recover_attempt(folder,{'A','B'})
        self.assertEqual(result['error_type'],'InterruptedUnknown')
        self.assertFalse(result['retryable'])

    def test_saved_response_keeps_reasoning_and_usage_without_request(self):
        folder=self.root/'attempt_1'
        runner.frozen_write(folder/'started.json',{'request_id':'test'})
        runner.frozen_write(folder/'response.json',{'model':'qwen3-vl-plus',
            'choices':[{'message':{'content':'Answer: B','reasoning_content':'saved observable'},'finish_reason':'stop'}],
            'usage':{'prompt_tokens':10,'completion_tokens':20,'completion_tokens_details':{'reasoning_tokens':15}}})
        result=runner.recover_attempt(folder,{'A','B'},runner.profile_for(config(self.root)))
        self.assertEqual(result['parsed']['answer'],'B')
        self.assertEqual(result['usage']['completion_tokens'],20)
        self.assertEqual(result['reasoning_content'],'saved observable')
        self.assertFalse(result['retryable'])
        self.assertIsNone(result['settlement'])

    def test_recovered_wrong_model_is_not_accepted(self):
        folder=self.root/'attempt_1'
        runner.frozen_write(folder/'started.json',{'request_id':'test'})
        runner.frozen_write(folder/'response.json',{'model':'other',
            'choices':[{'message':{'content':'Answer: B'}}]})
        result=runner.recover_attempt(folder,{'A','B'},runner.profile_for(config(self.root)))
        self.assertIn('identity_mismatch',result['error_message'])

    def test_stream_keeps_reasoning_chunks_and_final_full_completion_usage(self):
        chunks=[{'model':'qwen3-vl-plus','choices':[{'delta':{'reasoning_content':'observable reasoning'}}]},
                {'choices':[{'delta':{'content':'Answer: B'},'finish_reason':'stop'}]},
                {'choices':[],'usage':{'prompt_tokens':20,'completion_tokens':100,
                                      'completion_tokens_details':{'reasoning_tokens':90}}}]
        create=Mock(return_value=iter(SimpleNamespace(model_dump=lambda item=item,**_:item) for item in chunks))
        client=SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
        raw=runner.invoke(client,{'stream':True},self.root)
        self.assertEqual(raw['usage']['completion_tokens'],100)
        self.assertEqual(raw['choices'][0]['message']['reasoning_content'],'observable reasoning')
        self.assertEqual(len((self.root/'stream_chunks.jsonl').read_text(encoding='utf-8').splitlines()),3)
        self.assertEqual(runner.read(self.root/'response.json'),raw)

    def test_full_run_resume_never_reissues_saved_terminal(self):
        cfg=config(self.root);cfg['prompt_variant']='text_only'
        row={'question_id':'q1','case_id':'c1','question':'Choose.\nA) Alpha\nB) Beta','images':[]}
        (self.root/'questions.jsonl').write_text(json.dumps(row)+'\n',encoding='utf-8')
        raw={'model':'qwen3-vl-plus','choices':[{'message':{'content':'Answer: B\nReason: brief'},'finish_reason':'stop'}],
             'usage':{'prompt_tokens':10,'completion_tokens':5}}
        create=Mock(return_value=SimpleNamespace(model_dump=lambda **_:raw))
        client=SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
        class MockLedger:
            def __init__(self,*args,**kwargs):self.remaining=Decimal('10')
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def reserve(self,**kwargs):return 'mock-id'
            def settle(self,*args,**kwargs):
                self.remaining-=Decimal('.001')
                return {'charged_cny':'.001','status':'settled'}
        args=SimpleNamespace(prepare_only=False,api_key_stdin=True)
        out=self.root/'out';out.mkdir()
        with patch.dict(sys.modules,{'openai':SimpleNamespace(OpenAI=lambda **_:client),
                                    'v12_ledger':SimpleNamespace(V12ProviderLedger=MockLedger)}):
            with patch.object(sys,'stdin',io.StringIO('synthetic-test-key\n')):
                self.assertEqual(runner.run(args,cfg,out),0)
            before=(out/'checkpoints/q1/sample_1/terminal.json').read_bytes()
            # Completion recovery requires neither key nor ledger nor any model call.
            with patch.object(sys,'stdin',io.StringIO('')):
                self.assertEqual(runner.run(args,cfg,out),0)
        self.assertEqual(create.call_count,1)
        self.assertEqual(before,(out/'checkpoints/q1/sample_1/terminal.json').read_bytes())
        self.assertEqual(runner.read(out/'status.json')['status'],'generation_complete')


class HTTPFailure(RuntimeError):
    def __init__(self,status,code=None,param=None):
        super().__init__('synthetic HTTP rejection')
        self.status_code=status
        self.body={'error':{'code':code,'param':param}}


class FailureContinuation(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.out=self.root/'out';self.out.mkdir()
        self.cfg=config(self.root);self.cfg.update(prompt_variant='text_only',max_requests=30,
            max_extra_requests=10,global_max_requests=30,global_max_extra_requests=10)
        self.args=SimpleNamespace(prepare_only=False,api_key_stdin=True)
        self.settlements=[];self.reservations=[]
        settlements,reservations=self.settlements,self.reservations
        class Ledger:
            def __init__(self,*args,**kwargs):self.remaining=Decimal('10')
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def reserve(self,**kwargs):
                reservations.append(kwargs);return 'mock-'+str(len(reservations))
            def settle(self,*args,**kwargs):
                settlements.append(kwargs)
                charge=Decimal('.043072') if kwargs.get('error_type') else Decimal('.001')
                self.remaining-=charge
                return {'charged_cny':str(charge),'status':'unknown' if kwargs.get('error_type') else 'settled'}
        self.ledger=Ledger

    def rows(self,n):
        (self.root/'questions.jsonl').write_text(''.join(json.dumps({'question_id':f'q{i}','case_id':f'c{i}',
            'question':'Choose.\nA) Alpha\nB) Beta','images':[]})+'\n' for i in range(1,n+1)),encoding='utf-8')

    @staticmethod
    def reply(text='Answer: B'):
        raw={'model':'qwen3-vl-plus','choices':[{'message':{'content':text},'finish_reason':'stop'}],
            'usage':{'prompt_tokens':10,'completion_tokens':5}}
        return SimpleNamespace(model_dump=lambda **_:raw)

    def execute(self,create):
        client=SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
        with patch.dict(sys.modules,{'openai':SimpleNamespace(OpenAI=lambda **_:client),
                                    'v12_ledger':SimpleNamespace(V12ProviderLedger=self.ledger)}), \
             patch.object(sys,'stdin',io.StringIO('synthetic-key\n')),patch.object(runner.time,'sleep'):
            return runner.run(self.args,self.cfg,self.out)

    def terminal(self,n):
        return runner.read(self.out/f'checkpoints/q{n}/sample_1/terminal.json')

    @staticmethod
    def media_download_error(message='Download multimodal file timed out', *, status=400,
                             code='invalid_parameter_error', error_type='invalid_request_error',
                             param=None, nested=True):
        # Exact observed provider body, wrapped in the same .status_code/.body
        # interface as an SDK HTTP exception; no SDK version/network dependency.
        error={'code':code,'type':error_type,'message':message,'param':param}
        exc=HTTPFailure(status,code,param)
        exc.body={'error':error} if nested else error
        return exc

    def test_explicit_media_download_rejection_continues_without_resend_or_free_charge(self):
        self.rows(2)
        create=Mock(side_effect=[self.media_download_error(),self.reply()])
        self.assertEqual(self.execute(create),0)
        self.assertEqual(create.call_count,2)
        terminal=self.terminal(1)
        self.assertEqual(terminal['status'],'request_failed')
        self.assertEqual(terminal['failure_class'],'sample_rejected')
        self.assertEqual(len(terminal['attempts']),1)
        attempt=terminal['attempts'][0]
        self.assertFalse(attempt['fatal']);self.assertFalse(attempt['retryable'])
        self.assertEqual(attempt['billing_outcome'],'unknown_conservative_reservation_not_invoice')
        self.assertEqual(attempt['settlement']['status'],'unknown')
        self.assertEqual(Decimal(attempt['settlement']['charged_cny']),Decimal('.043072'))
        self.assertIsNone(self.settlements[0]['usage'])
        self.assertFalse(self.settlements[0]['response_received'])
        self.assertEqual(self.terminal(2)['answer'],'B')
        saved=(self.out/'checkpoints/q1/sample_1/terminal.json').read_bytes()
        self.assertEqual(self.execute(create),0)
        self.assertEqual(create.call_count,2)
        self.assertEqual(saved,(self.out/'checkpoints/q1/sample_1/terminal.json').read_bytes())

    def test_media_download_rejection_matches_exact_normalized_sdk_payload(self):
        for nested in (True,False):
            result=runner.failure_details(self.media_download_error(
                ' \tDOWNLOAD   multimodal\n file timed OUT \r\n',
                code='INVALID_PARAMETER_ERROR',error_type='INVALID_REQUEST_ERROR',nested=nested))
            self.assertEqual(result['failure_class'],'sample_rejected')
            self.assertFalse(result['fatal']);self.assertFalse(result['retryable'])

    def test_media_download_exception_never_masks_other_configuration_auth_or_quota_errors(self):
        errors=[self.media_download_error('Invalid max_tokens'),
                self.media_download_error('Download multimodal file timed out: other condition'),
                self.media_download_error(param='model'),
                self.media_download_error(code='invalid_api_key'),
                self.media_download_error(code='unsupported_parameter'),
                self.media_download_error(error_type='authentication_error'),
                self.media_download_error(status=401),self.media_download_error(status=403)]
        for error in errors:
            result=runner.failure_details(error)
            self.assertTrue(result['fatal'],result)
            self.assertFalse(result['retryable'])
            self.assertNotEqual(result['failure_class'],'sample_rejected')
        ordinary=runner.failure_details(self.media_download_error('Invalid max_tokens'))
        self.assertEqual(ordinary['failure_class'],'provider_configuration')
        for error in (self.media_download_error(code='insufficient_quota'),
                      self.media_download_error(error_type='Arrearage')):
            result=runner.failure_details(error)
            self.assertEqual(result['failure_class'],'provider_quota_or_balance')
            self.assertTrue(result['fatal']);self.assertFalse(result['retryable'])

    def test_five_explicit_media_download_rejections_still_stop(self):
        self.rows(6)
        create=Mock(side_effect=[self.media_download_error() for _ in range(5)]+[self.reply()])
        self.assertEqual(self.execute(create),2)
        self.assertEqual(create.call_count,5)
        state=runner.read(self.out/'status.json')
        self.assertEqual(state['error'],'consecutive_failed_samples_limit')
        self.assertEqual(state['consecutive_failed_samples'],5)
        self.assertFalse((self.out/'checkpoints/q6/sample_1/attempt_1/started.json').exists())

    def test_rejected_samples_continue_and_keep_conservative_error_accounting(self):
        self.rows(4)
        create=Mock(side_effect=[HTTPFailure(400),HTTPFailure(413),HTTPFailure(422),self.reply()])
        self.assertEqual(self.execute(create),0)
        self.assertEqual(create.call_count,4)
        for i in range(1,4):
            terminal=self.terminal(i)
            self.assertIsNone(terminal['answer']);self.assertEqual(terminal['status'],'request_failed')
            self.assertEqual(terminal['failure_class'],'sample_rejected')
            self.assertEqual(terminal['attempts'][0]['settlement']['status'],'unknown')
            self.assertEqual(terminal['attempts'][0]['billing_outcome'],'unknown_conservative_reservation_not_invoice')
            self.assertIsNone(self.settlements[i-1]['usage'])
            self.assertFalse(self.settlements[i-1]['response_received'])
            self.assertTrue(self.settlements[i-1]['error_type'])
        self.assertEqual(self.terminal(4)['answer'],'B')
        metadata=runner.read(self.out/'checkpoints/q1/sample_1/image_metadata.json')
        self.assertNotIn('native_bytes_no_resizing',metadata)
        self.assertIs(metadata['native_bytes_sent'],False)

    def test_five_failed_samples_stop_and_restart_cannot_bypass_threshold(self):
        self.rows(6);create=Mock(side_effect=[HTTPFailure(400) for _ in range(5)]+[self.reply()])
        self.assertEqual(self.execute(create),2)
        self.assertEqual(create.call_count,5)
        state=runner.read(self.out/'status.json')
        self.assertEqual(state['error'],'consecutive_failed_samples_limit')
        self.assertEqual(state['consecutive_failed_samples'],5)
        before=(self.out/'checkpoints/q5/sample_1/terminal.json').read_bytes()
        self.assertEqual(self.execute(create),2)
        self.assertEqual(create.call_count,5)
        self.assertEqual(before,(self.out/'checkpoints/q5/sample_1/terminal.json').read_bytes())
        self.assertFalse((self.out/'checkpoints/q6/sample_1/attempt_1/started.json').exists())

    def test_explicit_one_use_acknowledgement_resets_only_at_stopped_boundary(self):
        self.rows(11)
        create=Mock(side_effect=[HTTPFailure(400) for _ in range(10)]+[self.reply()])
        self.assertEqual(self.execute(create),2)
        first=runner.read(self.out/'status.json')['stop_event_id']
        self.assertRegex(first,r'^[A-Za-z0-9_.-]{1,200}$')
        original=(self.out/'checkpoints/q5/sample_1/terminal.json').read_bytes()
        self.args.acknowledge_stop='wrong-event'
        with self.assertRaisesRegex(ValueError,'current_unacknowledged'):self.execute(create)
        self.assertEqual(create.call_count,5)
        self.args.acknowledge_stop=first
        self.assertEqual(self.execute(create),2)
        self.assertEqual(create.call_count,10)
        self.assertTrue((self.out/'stop_acknowledgements'/(first+'.json')).exists())
        self.assertEqual(original,(self.out/'checkpoints/q5/sample_1/terminal.json').read_bytes())
        second=runner.read(self.out/'status.json')['stop_event_id']
        self.assertNotEqual(second,first)
        with self.assertRaisesRegex(ValueError,'current_unacknowledged'):self.execute(create)
        self.assertEqual(create.call_count,10)
        self.args.acknowledge_stop=second
        self.assertEqual(self.execute(create),0)
        self.assertEqual(create.call_count,11)
        self.assertEqual(self.terminal(11)['answer'],'B')
        self.assertEqual(len(self.reservations),11)

    def test_operator_can_resume_after_auth_fix_without_retrying_failed_sample(self):
        self.rows(2);create=Mock(side_effect=[HTTPFailure(401),self.reply()])
        self.assertEqual(self.execute(create),2)
        stopped=runner.read(self.out/'status.json')['stop_event_id']
        original=(self.out/'checkpoints/q1/sample_1/terminal.json').read_bytes()
        self.args.acknowledge_stop=stopped;self.args.prepare_only=True
        with self.assertRaisesRegex(ValueError,'prepare_cannot'):self.execute(create)
        self.args.prepare_only=False
        self.assertEqual(self.execute(create),0)
        self.assertEqual(create.call_count,2)
        self.assertEqual(original,(self.out/'checkpoints/q1/sample_1/terminal.json').read_bytes())
        self.assertEqual(self.terminal(2)['answer'],'B')

    def test_successful_provider_reply_resets_failure_streak_even_if_unparsed(self):
        self.rows(10)
        effects=[HTTPFailure(400) for _ in range(4)]+[self.reply('No final option')]
        effects += [HTTPFailure(422) for _ in range(4)]+[self.reply()]
        create=Mock(side_effect=effects)
        self.assertEqual(self.execute(create),0)
        self.assertEqual(create.call_count,10)
        self.assertEqual(self.terminal(5)['status'],'unparsed')
        self.assertEqual(self.terminal(5)['consecutive_failed_samples'],0)
        self.assertEqual(self.terminal(9)['consecutive_failed_samples'],4)

    def test_unknown_timeout_and_5xx_never_resend_same_sample(self):
        self.rows(3);create=Mock(side_effect=[TimeoutError('synthetic timeout'),HTTPFailure(503),self.reply()])
        self.assertEqual(self.execute(create),0)
        self.assertEqual(create.call_count,3)
        for i in (1,2):
            terminal=self.terminal(i)
            self.assertEqual(terminal['failure_class'],'unknown_provider_outcome')
            self.assertEqual(len(terminal['attempts']),1)
            self.assertFalse(terminal['attempts'][0]['retryable'])
        self.assertEqual(self.execute(create),0)
        self.assertEqual(create.call_count,3)

    def test_interrupted_unknown_restores_streak_and_never_reissues(self):
        self.rows(6)
        create=Mock(side_effect=[HTTPFailure(400) for _ in range(4)]+[KeyboardInterrupt()])
        with self.assertRaises(KeyboardInterrupt):self.execute(create)
        self.assertEqual(create.call_count,5)
        self.assertEqual(self.execute(create),2)
        self.assertEqual(create.call_count,5)
        terminal=self.terminal(5)
        self.assertEqual(terminal['attempts'][0]['error_type'],'InterruptedUnknown')
        self.assertEqual(terminal['consecutive_failed_samples'],5)

    def test_systemic_errors_stop_immediately_and_do_not_resume_by_skipping_terminal(self):
        self.rows(2);create=Mock(side_effect=[HTTPFailure(400,'model_not_found'),self.reply()])
        self.assertEqual(self.execute(create),2)
        self.assertEqual(create.call_count,1)
        self.assertEqual(self.terminal(1)['fatal_reason'],'provider_configuration')
        self.assertEqual(self.execute(create),2)
        self.assertEqual(create.call_count,1)
        for exc in (HTTPFailure(401),HTTPFailure(403),HTTPFailure(404),HTTPFailure(429,'insufficient_quota'),
                    HTTPFailure(400,'unsupported_parameter'),HTTPFailure(400,None,'temperature'),
                    HTTPFailure(429,'organization_spend_limit_exceeded'),HTTPFailure(429,'project_spend_limit_exceeded'),
                    HTTPFailure(429,'organization_usage_limit_exceeded'),
                    RuntimeError('returned_model_identity_mismatch'),OSError('disk failure')):
            self.assertTrue(runner.failure_details(exc)['fatal'],repr(exc))
            self.assertFalse(runner.failure_details(exc)['retryable'])
        self.assertNotIn('provider_error_code',runner.failure_details(HTTPFailure(400,'synthetic-key'),'synthetic-key'))
        self.assertNotIn('provider_error_code',runner.failure_details(HTTPFailure(400,'sk-synthetic-only')))

    def test_only_explicit_rate_rejection_gets_one_authorized_retry(self):
        self.rows(1);create=Mock(side_effect=[HTTPFailure(429,'rate_limit_exceeded'),self.reply()])
        self.assertEqual(self.execute(create),0)
        self.assertEqual(create.call_count,2)
        self.assertEqual(len(self.terminal(1)['attempts']),2)
        self.assertEqual(self.terminal(1)['answer'],'B')
        self.assertEqual(runner.read(self.out/'status.json')['extra_requests_used'],1)

    def test_dashscope_http400_arrearage_stops_before_next_sample(self):
        self.rows(2)
        error = HTTPFailure(400, 'Arrearage')
        error.body['error'].update(type='Arrearage', message=(
            'Access denied. Please make sure your account is in good standing. '
            'See https://help.example.invalid/errors#overdue-payment'))
        create = Mock(side_effect=[error, self.reply()])
        self.assertEqual(self.execute(create), 2)
        self.assertEqual(create.call_count, 1)
        terminal = self.terminal(1)
        attempt = terminal['attempts'][0]
        self.assertEqual(terminal['fatal_reason'], 'provider_quota_or_balance')
        self.assertEqual(attempt['status_code'], 400)
        self.assertEqual(attempt['provider_error_code'], 'Arrearage')
        self.assertEqual(attempt['provider_error_type'], 'Arrearage')
        self.assertFalse(attempt['retryable'])
        self.assertEqual(attempt['billing_outcome'], 'unknown_conservative_reservation_not_invoice')
        original = (self.out/'checkpoints/q1/sample_1/terminal.json').read_bytes()
        self.assertEqual(self.execute(create), 2)
        self.assertEqual(create.call_count, 1)
        self.assertEqual(original, (self.out/'checkpoints/q1/sample_1/terminal.json').read_bytes())

    def test_overdue_payment_markers_are_systemic_but_old_terminals_unchanged(self):
        for fields in ({'type': 'Arrearage'}, {'code': 'overdue-payment'},
                       {'message': 'Access denied: account overdue payment'},
                       {'message': 'See https://help.example.invalid/errors#overdue-payment'}):
            error = HTTPFailure(400)
            error.body['error'].update(fields)
            result = runner.failure_details(error)
            self.assertEqual(result['failure_class'], 'provider_quota_or_balance')
            self.assertTrue(result['fatal'])
            self.assertFalse(result['retryable'])
        # Recovery reads the original saved decision instead of retrospectively
        # changing the five historical sample_rejected terminal records.
        old = {'status': 'request_failed', 'failure_class': 'sample_rejected',
               'attempts': [{'failure_class': 'sample_rejected', 'fatal': False,
                             'provider_error_code': 'Arrearage'}]}
        self.assertEqual(runner.terminal_failure(old), (True, None))

    def test_malformed_response_is_a_controller_error_not_sample_rejection(self):
        self.rows(2)
        bad=SimpleNamespace(model_dump=lambda **_:{'model':'qwen3-vl-plus','choices':[],
            'usage':{'prompt_tokens':10,'completion_tokens':5}})
        create=Mock(side_effect=[bad,self.reply()])
        self.assertEqual(self.execute(create),2)
        self.assertEqual(create.call_count,1)
        self.assertEqual(self.terminal(1)['fatal_reason'],'response_processing_failure')


if __name__=='__main__':unittest.main()
