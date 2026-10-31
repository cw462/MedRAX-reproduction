"""Small synthetic checks; no real images, labels, ledger or model calls."""
import sys
from pathlib import Path
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'experiments'))
from run_direct_vlm import parse_answer, SYSTEM_PROMPT
from compare_direct_vlm import paired, derived_answer


class AnswerParsing(unittest.TestCase):
    def test_explicit_answer(self):
        for text in ('Answer: B\nReason: briefly', '**Answer:** **b**\nReason: briefly', 'b'):
            self.assertEqual(parse_answer(text, {'A', 'B'})['answer'], 'B')

    def test_no_reason_guess(self):
        for text in ('Reason: option B is plausible', 'Answer: Z\nReason: B', 'Answer: A\nAnswer: B', 'Answer: A or B'):
            self.assertIsNone(parse_answer(text, {'A', 'B'})['answer'])

    def test_missing_reason_keeps_answer(self):
        self.assertEqual(parse_answer('Answer: A', {'A', 'B'}), {'answer': 'A', 'status': 'completed', 'reason_missing': True})

    def test_no_tool_or_long_trace_prompt(self):
        self.assertIn('Do not output a long reasoning trace.', SYSTEM_PROMPT)

    def test_four_transitions_net_matches_full_denominator(self):
        qids=list('12345'); labels=dict.fromkeys(qids,'A')
        old=dict(zip(qids,['B','A',None,'A','A']))
        new=dict(zip(qids,['A','B','A',None,'A']))
        result=paired(old,new,labels,qids)
        for key in ('legal_wrong_to_correct','correct_to_legal_wrong','missing_to_correct','correct_to_missing'):
            self.assertEqual(result[key],1)
        self.assertEqual(result['net'],0)

    def test_separate_derived_explicit_option_text_parser(self):
        self.assertEqual(derived_answer('Answer: A) Chronic condition\nReason: B differs', {'A','B'}),'A')
        self.assertEqual(derived_answer('**Answer:** B. Full option\nReason: short', {'A','B'}),'B')
        for text in ('Answer: A or B','Answer: A) text\nAnswer: B','Reason: B','Answer: Z. text'):
            self.assertIsNone(derived_answer(text,{'A','B'}))


if __name__ == '__main__': unittest.main()
