"""Meaningful extraction/grading boundary and full-denominator failure checks."""
from pathlib import Path
import random
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'experiments'))
from score_cxr_author_alignment import adapt, outcomes


def source(raw):
    return {'raw':raw,'call_path':'example.json','ordinal':'1','reuse_chain':['M'],
            'evidence_status':'received_terminal_text','technical_stop':False}


class ScoringBoundaryTests(unittest.TestCase):
    def test_answer_recovery_is_separate_from_json_contract(self):
        row={'question_id':'q'}
        record=adapt(row,{'answer':None,'status':'missing_invalid_final_json'},source('{"answer":"No","extra":1}'))
        self.assertFalse(record['legacy_M_contract_compliant'])
        self.assertTrue(outcomes(row,record,'No',random.Random(0))['aligned_correct'])
        self.assertFalse(outcomes(row,record,'Yes',random.Random(0))['aligned_correct'])
        self.assertEqual(record['explicit_answer'],'No')

    def test_missing_technical_answer_gets_no_random_credit(self):
        row={'question_id':'q','options':{'A':'yes','B':'no'}}
        record=adapt(row,{'answer':None,'status':'missing_tool_unhealthy_stop'},source(None))
        for reference in ['A','B']:
            graded=outcomes(row,record,reference,random.Random(0))
            self.assertFalse(graded['aligned_correct'])
            self.assertFalse(graded['legacy_seeded_correct'])
            self.assertFalse(graded['legacy_random_draw'])

    def test_letter_text_conflict_is_not_resolved_by_reference(self):
        row={'question_id':'q','options':{'A':'yes','B':'no'}}
        record=adapt(row,{'answer':'A. no','status':'completed'},source('{"answer":"A. no"}'))
        self.assertIsNone(record['choice'])
        self.assertTrue(record['choice_domain_invalid'])
        self.assertFalse(outcomes(row,record,'B',random.Random(0))['aligned_correct'])


if __name__=='__main__':
    unittest.main()
