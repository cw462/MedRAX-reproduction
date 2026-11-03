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


if __name__=='__main__':unittest.main()
