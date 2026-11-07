"""Source identity repair cannot import another case or alter clinical text."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'experiments'))
from finalize_cxr_skill_v32 import candidates


class SourceIdentityTest(unittest.TestCase):
    def run_case(self,identity,source_ids,fenced=False):
        card={'id':identity,'source_ids':source_ids,'topic':'Pleural observation','tasks':['presence'],
              'requires_pair':False,'required_question_terms':[],
              'actions':[{'observe':'Inspect each pleural space','tool':'none','when':'Question concerns pleura','stop':'Evidence or limitation recorded'}],
              'avoid':'No negative inference from missing evidence','source_evidence':'Source evidence only'}
        raw=json.dumps(card)
        if fenced:raw='```json\n'+raw+'\n```'
        source={'cases':[{'case_id':'case1','source_trajectories':[{'source_id':'case1_q1'}]}]}
        with tempfile.TemporaryDirectory() as folder:
            out=Path(folder);p=out/'calls/M-S/case1/1/response.json';p.parent.mkdir(parents=True)
            p.write_text(json.dumps({'choices':[{'message':{'content':raw}}]}))
            result=candidates(source,out,[])
            self.assertEqual(json.loads(p.read_text())['choices'][0]['message']['content'],raw)
        return card,result

    def test_member_question_id_maps_to_enclosing_case_only(self):
        original,(cards,rejected,bindings)=self.run_case('case1_q1',['case1_q1'])
        self.assertEqual(cards[0]['id'],'case1');self.assertEqual(cards[0]['source_ids'],['case1'])
        self.assertEqual({k:v for k,v in cards[0].items() if k not in ['id','source_ids']},{k:v for k,v in original.items() if k not in ['id','source_ids']})
        self.assertFalse(rejected);self.assertEqual(bindings[0]['returned_id'],'case1_q1')

    def test_foreign_case_identifier_is_rejected(self):
        _,(cards,rejected,_)=self.run_case('other_case',['other_case'])
        self.assertFalse(cards);self.assertEqual(len(rejected),1)

    def test_invalid_source_json_not_semantically_repaired(self):
        _,(cards,rejected,_)=self.run_case('case1',['case1'],fenced=True)
        self.assertFalse(cards);self.assertEqual(len(rejected),1)


if __name__=='__main__':unittest.main()
