import io
import json
from pathlib import Path
import tempfile
import concurrent.futures
import unittest
import r0


class Msg:
    def __init__(self, content='', calls=None, name=None, call_id=None, status='success'):
        self.content, self.tool_calls = content, calls or []
        self.name, self.tool_call_id, self.status = name, call_id, status


class FakeWorkflow:
    def __init__(self): self.thread_ids = []
    def stream(self, data, config):
        self.thread_ids.append(config['configurable']['thread_id'])
        yield {'process': {'messages': [Msg(calls=[{'id':'call1', 'name':'classifier', 'args':{'image':'SECRET'}}])]}}
        yield {'execute': {'messages': [Msg('SECRET RESULT', name='classifier', call_id='call1')]}}
        yield {'process': {'messages': [Msg('B')]}}


class Tests(unittest.TestCase):
    def test_strict_field_boundary(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)/'in.jsonl'
            p.write_text(json.dumps({'question_id':1, 'question':'Q?', 'images':[], 'answer':'B'}), encoding='utf-8')
            with self.assertRaises(ValueError): r0.load_inputs(p, 1)

    def test_unique_threads_and_no_raw_tool_data(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d).resolve(); (root/'img.jpg').write_bytes(b'not a real image')
            row = {'question_id':1, 'question':'Q?', 'images':['img.jpg']}
            agent = type('Agent', (), {'workflow': FakeWorkflow()})()
            trace = io.StringIO()
            result = r0.run_case(agent, row, root, trace, 6)
            result2 = r0.run_case(agent, row, root, trace, 6)
            self.assertEqual(result['prediction'], 'B')
            self.assertEqual(result['status'], 'completed')
            self.assertNotEqual(result['thread_id'], result2['thread_id'])
            self.assertNotIn('SECRET', trace.getvalue())
            self.assertIn('classifier', trace.getvalue())

    def test_path_escape_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError): r0.image_paths({'images':['../other.jpg']}, Path(d).resolve())

    def test_concurrent_tool_calls_do_not_exceed_limit(self):
        class Tool:
            def invoke(self, value): return value
        trace = io.StringIO()
        budget = r0.CaseBudget(3, 1, 30, trace)
        proxy = r0.GuardedInvoke(Tool(), 'tool', 'fake', lambda: budget)
        def call(i):
            try:
                proxy.invoke(i)
                return True
            except r0.BudgetExceeded:
                return False
        with concurrent.futures.ThreadPoolExecutor(max_workers=12) as pool:
            outcomes = list(pool.map(call, range(30)))
        self.assertEqual(sum(outcomes), 3)
        self.assertEqual(budget.counts['tool'], 3)
        self.assertEqual(len([json.loads(x) for x in trace.getvalue().splitlines() if json.loads(x)['decision'] == 'blocked']), 27)

    def test_model_limit_and_deadline_stop_before_invocation(self):
        class Model:
            def __init__(self): self.calls = 0
            def invoke(self): self.calls += 1
        model = Model(); trace = io.StringIO()
        budget = r0.CaseBudget(1, 1, 30, trace)
        proxy = r0.GuardedInvoke(model, 'model', 'llm', lambda: budget)
        proxy.invoke()
        with self.assertRaises(r0.BudgetExceeded): proxy.invoke()
        self.assertEqual(model.calls, 1)
        expired = r0.CaseBudget(1, 1, -1, io.StringIO())
        with self.assertRaises(r0.BudgetExceeded):
            r0.GuardedInvoke(model, 'model', 'llm', lambda: expired).invoke()
        self.assertEqual(model.calls, 1)

    def test_no_budget_fails_closed(self):
        class Tool:
            def invoke(self): self.fail('must never execute')
        with self.assertRaises(RuntimeError):
            r0.GuardedInvoke(Tool(), 'tool', 'fake', lambda: None).invoke()

    def test_guarded_workflow_blocks_second_tool_and_records_case(self):
        class Invoke:
            def __init__(self): self.calls = 0
            def invoke(self, *args): self.calls += 1; return 'ok'
        class Workflow:
            def __init__(self, agent): self.agent = agent
            def stream(self, *_):
                self.agent.model.invoke('prompt')
                self.agent.tools['fake'].invoke('first')
                self.agent.tools['fake'].invoke('second')
                yield {}
        with tempfile.TemporaryDirectory() as d:
            root = Path(d).resolve(); (root/'img.jpg').write_bytes(b'image')
            original_model, original_tool = Invoke(), Invoke()
            agent = type('Agent', (), {})()
            agent.model, agent.tools, agent.workflow = original_model, {'fake': original_tool}, Workflow(agent)
            trace = io.StringIO(); budget = r0.CaseBudget(1, 1, 30, trace)
            r0.install_budget_guards(agent, lambda: budget)
            result = r0.run_case(agent, {'question_id':'case-q1', 'question':'Q', 'images':['img.jpg']}, root, trace, 10, budget)
            self.assertEqual(result['status'], 'budget_exceeded')
            self.assertEqual((original_model.calls, original_tool.calls), (1, 1))
            records = [json.loads(x) for x in trace.getvalue().splitlines()]
            self.assertTrue(any(x.get('decision') == 'blocked' and x.get('case_hash') == result['case_hash'] and x.get('thread_id') == result['thread_id'] for x in records))


if __name__ == '__main__': unittest.main()
