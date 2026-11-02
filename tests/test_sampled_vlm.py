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


if __name__=='__main__':unittest.main()
