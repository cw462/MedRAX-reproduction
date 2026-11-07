"""Historical baseline sensitivity is mechanical and cannot infer an answer."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'experiments'))
from analyze_cxr_gain_v32 import historical_fence


class HistoricalFenceTest(unittest.TestCase):
    def recover(self,text):
        original={'question_id':'q','status':'missing_invalid_final_json','answer':None,'reason':None}
        call={'ordinal':'1','response':{'choices':[{'message':{'content':text}}]}}
        return original,historical_fence(original,[call])

    def test_whole_fence_preserves_literal_answer(self):
        original,(value,changed)=self.recover('```json\n{"answer":"No.","reason":"visible evidence"}\n```')
        self.assertTrue(changed);self.assertEqual(value['answer'],'No.');self.assertIsNone(original['answer'])

    def test_prose_or_reason_does_not_supply_answer(self):
        for text in ['Answer is yes.','```json\n{"reason":"the answer is yes"}\n```','Explanation\n```json\n{"answer":"yes","reason":"evidence"}\n```']:
            original,(value,changed)=self.recover(text)
            self.assertFalse(changed);self.assertEqual(value,original)

    def test_completed_original_is_not_reinterpreted(self):
        original={'status':'completed','answer':'no','reason':'evidence'}
        self.assertEqual(historical_fence(original,[]),(original,False))


if __name__=='__main__':unittest.main()
