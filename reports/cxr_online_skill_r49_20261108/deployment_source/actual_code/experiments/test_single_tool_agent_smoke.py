"""Offline guard tests only; no API or clinical inference."""
import io
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import single_tool_agent_smoke as smoke
from r0 import CaseBudget, BudgetExceeded

class FakeInvoke:
    def __init__(self,result):self.result=result;self.calls=0
    def invoke(self,*args,**kwargs):self.calls+=1;return self.result

class SmokeTests(unittest.TestCase):
    def context(self,image):
        trace=io.StringIO();budget=CaseBudget(1,2,60,trace)
        return {'budget':budget,'trace':trace,'case_hash':'fake-case','thread_id':'fake-thread',
                'allowed_images':{image.resolve()},'actual_tool_attempts':0,
                'validated_tool_returns':0,'usage_records':[]}

    def test_usage_fallback_and_missing_are_distinct(self):
        self.assertIsNone(smoke.numeric_usage(SimpleNamespace()))
        m=SimpleNamespace(response_metadata={'token_usage':{'prompt_tokens':3,'completion_tokens':2,'total_tokens':5}})
        self.assertEqual(smoke.numeric_usage(m),{'input_tokens':3,'output_tokens':2,'total_tokens':5})
        self.assertIsNone(smoke.numeric_usage(SimpleNamespace(usage_metadata={'input_tokens':True})))

    def test_answer_parser_rejects_narrative(self):
        self.assertEqual(smoke.answer_letter(' B. \n'),'B')
        self.assertIsNone(smoke.answer_letter('The answer is B'))
        self.assertIsNone(smoke.answer_letter(['B']))

    def test_partial_usage_remains_unknown(self):
        observed, complete = smoke.aggregate_usage([{'input_tokens': 3}], 1)
        self.assertEqual(observed, {'input_tokens': 3, 'output_tokens': None, 'total_tokens': None})
        self.assertFalse(complete)
        record = {'input_tokens': 3, 'output_tokens': 2, 'total_tokens': 5}
        self.assertFalse(smoke.aggregate_usage([record], 2)[1])
        self.assertTrue(smoke.aggregate_usage([record], 1)[1])
        self.assertEqual(smoke.aggregate_usage([], 1), (None, False))

    def test_allowed_tool_return_is_validated_and_budgeted(self):
        with TemporaryDirectory() as temp:
            image=Path(temp)/'fake.png';image.write_bytes(b'fake fixture only')
            labels=[f'label{i}' for i in range(18)]
            fake=FakeInvoke(({name:0.5 for name in labels},{'analysis_status':'completed','image_path':str(image)}))
            ctx=self.context(image);wrapped=smoke.TrackedInvoke(fake,'tool','classifier',ctx,labels)
            wrapped.invoke({'image_path':str(image)})
            self.assertEqual(ctx['actual_tool_attempts'],1)
            self.assertEqual(ctx['validated_tool_returns'],1)
            with self.assertRaises(BudgetExceeded):wrapped.invoke({'image_path':str(image)})
            self.assertEqual(fake.calls,1)
            self.assertNotIn(str(image),ctx['trace'].getvalue())
            self.assertIn('clinical_evidence',ctx['trace'].getvalue())

    def test_other_image_is_rejected_before_tool(self):
        with TemporaryDirectory() as temp:
            image=Path(temp)/'allowed.png';image.write_bytes(b'fake')
            fake=FakeInvoke(None);ctx=self.context(image)
            wrapped=smoke.TrackedInvoke(fake,'tool','classifier',ctx,[])
            with self.assertRaises(ValueError):wrapped.invoke({'image_path':str(Path(temp)/'other.png')})
            self.assertEqual(fake.calls,0)
            self.assertEqual(ctx['actual_tool_attempts'],0)

    def test_failed_tool_is_not_verified(self):
        with TemporaryDirectory() as temp:
            image=Path(temp)/'allowed.png';image.write_bytes(b'fake')
            fake=FakeInvoke(({'error':'fake error'},{'analysis_status':'failed'}));ctx=self.context(image)
            smoke.TrackedInvoke(fake,'tool','classifier',ctx,[]).invoke({'image_path':str(image)})
            self.assertEqual(ctx['actual_tool_attempts'],1)
            self.assertEqual(ctx['validated_tool_returns'],0)
            self.assertIn('failed_or_invalid',ctx['trace'].getvalue())

if __name__=='__main__':unittest.main()
