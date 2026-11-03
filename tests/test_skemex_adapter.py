import json
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'experiments'))
from skemex_adapter.contracts import require_baseline,require_matched_agent,require_source_isolation,case_windows,MATCH_FIELDS


class Contracts(unittest.TestCase):
    def test_missing_A0_prevents_paid_progress(self):
        with self.assertRaises(ValueError):require_baseline({'target_question_n':402,'A0':{'status':'unresolved'}})

    def test_partial_A0_does_not_reduce_denominator(self):
        with self.assertRaises(ValueError):require_baseline({'target_question_n':402,'A0':{'status':'matched_complete','common_question_n':60}})

    def test_changed_agent_tools_rejected(self):
        a={k:'same' for k in MATCH_FIELDS};b=dict(a,tools='new tool')
        with self.assertRaises(ValueError):require_matched_agent(a,b)

    def test_utility_from_target_fold_rejected(self):
        with self.assertRaises(ValueError):require_source_isolation(['source'],['target'],[{'source_case_ids':['source']}],[{'source_case_ids':['target']}])

    def test_unknown_skill_provenance_rejected(self):
        with self.assertRaises(ValueError):require_source_isolation(['source'],['target'],[{}],[])

    def test_case_windows_never_split_patients(self):
        rows=[{'case_id':'a','q':i} for i in range(29)]+[{'case_id':'b','q':i} for i in range(4)]+[{'case_id':'c','q':0}]
        windows=list(case_windows(rows,30));self.assertEqual([len(w) for w in windows],[33,1])

    def test_experiment_defaults_not_class_defaults(self):
        p=Path(__file__).resolve().parents[1]/'third_party/skemex/configs/evolution/default.json';c=json.loads(p.read_text(encoding='utf-8'))
        self.assertEqual(c['retrieval']['embedding_model'],'text-embedding-3-large')
        self.assertEqual([c['retrieval']['lambda_'+k] for k in ('similarity','utility','memory')],[.4,.4,.2])
        self.assertEqual((c['buffer']['window_size'],c['buffer']['capacity']),(30,20))


class AdmissionRegression(unittest.TestCase):
    def test_provenance_is_not_skill_content(self):
        from evolve_skemex_a1 import prohibited
        row={'question_id':'case_123_q','case_id':'123','question':'Which finding is present? A) none B) opacity'}
        draft={'source_trajectory_ids':['case_123_q'],'name':'Side comparison','description':'Compare both sides before assessing asymmetry','applicable_conditions':'When asymmetry is uncertain','core_action':'Inspect both sides in the original image before comparing candidate findings.'}
        self.assertTrue(prohibited(json.dumps(draft),row))
        content=' '.join(str(draft.get(k) or '') for k in ('name','description','applicable_conditions','core_action','Core Action'))
        self.assertFalse(prohibited(content,row))

class ReuseRegression(unittest.TestCase):
    def test_exact_completed_request_reuses_without_worker_or_ledger(self):
        import tempfile
        from skemex_adapter.transport import PaidTransport
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);row={'question_id':'q','case_id':'c','question':'A) yes\nB) no','images':[]}
            messages=[{'role':'system','content':'s'},{'role':'user','content':'u'}]
            request={'model':'qwen3.7-plus','messages':messages,'temperature':.2,'top_p':.95,'max_tokens':2048,'extra_body':{'enable_thinking':False},'stream':False}
            folder=root/'old/calls/job__1/checkpoints/q/sample_1';folder.mkdir(parents=True)
            (folder/'request.json').write_text(json.dumps(request));(folder/'terminal.json').write_text(json.dumps({'raw_response':'Answer: A','answer':'A','status':'completed'}))
            cfg={'root':str(root),'reuse_original_run':'old','model':'qwen3.7-plus','top_p':.95,'extra_body':{'enable_thinking':False}}
            t=PaidTransport(cfg,'dummy-not-a-real-key',root/'new');t.set_context('job',row)
            with patch('run_sampled_vlm.run',side_effect=AssertionError('must not call paid worker')):
                raw,value=t.call(messages,actor=True)
            self.assertEqual(raw,'Answer: A');self.assertTrue(value['reused_call']['exact_payload_match'])

if __name__=='__main__':unittest.main()
