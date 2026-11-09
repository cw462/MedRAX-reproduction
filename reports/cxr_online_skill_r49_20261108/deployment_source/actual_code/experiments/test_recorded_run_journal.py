import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

try:
    from .recorded_run_journal import RecordedRunJournal
except ImportError:
    from recorded_run_journal import RecordedRunJournal


def plan(version):
    return {'planned_question_count': 2, 'question_ids': ['q1', 'q2'],
            'schedule': [{'question_id': q, 'arm': 'agent'} for q in ('q1', 'q2')],
            'source_sha256': {'runner.py': version}, 'input_sha256': version}


class JournalTests(unittest.TestCase):
    def test_changed_hash_resumes_without_rewriting_manifest_or_completed_results(self):
        with TemporaryDirectory() as temp:
            root = Path(temp) / 'run'
            journal = RecordedRunJournal(root, plan('a' * 64))
            start = journal.start('q1', 'agent')
            journal.finish(dict(start, status='completed'))
            journal.close()
            original_manifest = (root / 'manifest.json').read_bytes()
            previous_results = (root / 'results.jsonl').read_bytes()
            resumed = RecordedRunJournal(root, plan('b' * 64), resume=True)
            self.assertIn(('q1', 'agent'), resumed.terminals)
            self.assertEqual((root / 'manifest.json').read_bytes(), original_manifest)
            self.assertEqual((root / 'results.jsonl').read_bytes(), previous_results)
            history = json.loads((root / 'plan_history.jsonl').read_text())
            self.assertEqual(history['plan']['source_sha256']['runner.py'], 'b' * 64)
            resumed.close()

    def test_changed_question_set_still_cannot_replay_or_mix_outcomes(self):
        with TemporaryDirectory() as temp:
            root = Path(temp) / 'run'
            journal = RecordedRunJournal(root, plan('a')); journal.close()
            changed = plan('b')
            changed['schedule'][1]['question_id'] = 'new-case'
            with self.assertRaises(ValueError):
                RecordedRunJournal(root, changed, resume=True)

    def test_started_unfinished_arm_is_not_charged_again_on_resume(self):
        with TemporaryDirectory() as temp:
            root = Path(temp) / 'run'
            journal = RecordedRunJournal(root, plan('a'))
            journal.start('q1', 'agent'); journal.close()
            resumed = RecordedRunJournal(root, plan('b'), resume=True)
            self.assertEqual(resumed.terminals['q1', 'agent']['status'], 'interrupted_no_retry')
            resumed.close()


if __name__ == '__main__':
    unittest.main()
