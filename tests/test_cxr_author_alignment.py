"""Scientific score-adapter regressions, independent of benchmark references."""
import sys
import random
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'experiments'))
from cxr_author_alignment import choice, extract, legacy_choice, m4cxr_normalize, m4cxr_recall


class AnswerAdapterTests(unittest.TestCase):
    def test_missing_reason_extra_fields_and_fences(self):
        for raw in ['{"answer":"No"}', '{"answer":"No","other":3}', '```json\n{"answer":"No"}\n```']:
            self.assertEqual(extract(raw, 'q').answer, 'No')

    def test_reasons_and_other_questions_are_not_answer_sources(self):
        self.assertIsNone(extract('{"reason":"No"}', 'q').answer)
        self.assertIsNone(extract('{"reason":{"answer":"No"}}', 'q').answer)
        self.assertIsNone(extract('{"reason":{"answer":"No"}', 'q').answer)
        self.assertIsNone(extract('{"answers":{"other":{"answer":"No"}}}', 'q').answer)
        self.assertEqual(extract('{"answers":{"q":{"answer":"No"}}}', 'q').answer, 'No')
        self.assertEqual(extract('{"q":{"answer":"No"}}', 'q').answer, 'No')
        self.assertIsNone(extract('{"q":{"answer":"Yes"},"q":{"answer":"No"}}', 'q').answer)

    def test_ambiguous_answers_and_duplicate_answer_keys(self):
        self.assertEqual(extract('First {"answer":"Yes"} then {"answer":"No"}', 'q').mechanism,
                         'conflicting_explicit_answers')
        self.assertIsNone(extract('{"answer":"Yes","answer":"No"}', 'q').answer)
        self.assertEqual(extract('{"answer":"No","answer":"No"}', 'q').answer, 'No')

    def test_embedded_json_preserves_explicit_answer_only(self):
        self.assertEqual(extract('Explanation. {"answer":"A","reason":"B"}', 'q').answer, 'A')
        self.assertIsNone(extract('Explanation. {"reason":{"answer":"B"}}', 'q').answer)

    def test_choice_forms_do_not_guess_from_words_or_conflicts(self):
        options = {'A':'yes','B':'no'}
        for value in ['A','(A)','A. yes','yes']:
            self.assertEqual(choice(value, options), 'A')
        for value in ['Cardiomegaly','A. no','The answer might be A or B']:
            self.assertIsNone(choice(value, options))

    def test_author_text_metric_has_no_boolean_synonym_invention(self):
        self.assertEqual(m4cxr_normalize('<s>Yes.</s>'), 'yes')
        self.assertNotEqual(m4cxr_normalize('true'), m4cxr_normalize('yes'))
        self.assertEqual(m4cxr_recall('No abnormality.', 'No'), 1.0)
        self.assertNotEqual(m4cxr_normalize('No abnormality.'), m4cxr_normalize('No'))

    def test_unexecuted_structured_plan_is_not_a_final_answer(self):
        raw = '{"answer":"A","reason":"tentative"}\nActually, use a tool.\n' + \
              '{"calls":[{"tool":"region_parse","args":{}}],"reason":"check"}'
        self.assertEqual(extract(raw,'q').mechanism, 'structured_tool_plan_not_final')
        self.assertIsNone(extract('{"answer":"A","calls":[{"tool":"x"}]}','q').answer)

    def test_author_mcq_fallback_is_explicit(self):
        self.assertEqual(legacy_choice('(B)', {'A':'yes','B':'no'}), ('B', False))
        self.assertEqual(legacy_choice('B', {'A':'yes','B':'no'}), (None, True))
        self.assertEqual(legacy_choice(None, {'A':'yes','B':'no'}, random.Random(0)), (None, True))


if __name__ == '__main__':
    unittest.main()
