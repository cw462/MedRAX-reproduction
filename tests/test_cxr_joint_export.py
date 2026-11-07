"""Q evidence uses group episodes and only the frozen eligible question subset."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'experiments'))
from export_cxr_vqa_extension import export


class JointExportTest(unittest.TestCase):
    def fixture(self, root):
        data, run, scored = [root / name for name in ('data', 'run', 'score')]
        def put(path, value, jsonl=False):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('\n'.join(json.dumps(v) for v in value) if jsonl else json.dumps(value), encoding='utf-8')
        data.mkdir()
        Image.new('RGB', (1, 1)).save(data / 'original.png')
        put(data / 'manifest.json', {'questions': 3})
        put(data / 'inputs.jsonl', [dict(question_id=q, image_id='im', question='A question', images=['original.png']) for q in ('a', 'b', 'singleton')], True)
        put(data / 'references.jsonl', [dict(question_id=q, answer='yes') for q in ('a', 'b', 'singleton')], True)
        gid = 'q-' + '0' * 24
        cohort = root / 'cohort.json'
        put(cohort, dict(status='stage3_cohort_frozen', target_labels_read=False, datasets={'slake': dict(q_group_count=1, q_questions=2, groups=[dict(group_id=gid, question_ids=['a', 'b'])])}))
        digest = hashlib.sha256(cohort.read_bytes()).hexdigest()
        put(run / 'protocol.json', {})
        put(scored / 'summary.json', dict(questions=2, arms={'D-Q': {}, 'M-Q': {}}))
        put(scored / 'per_question.jsonl', [dict(question_id='a')], True)
        for arm in ('D-Q', 'M-Q'):
            put(run / f'complete_{arm}.json', dict(cohort_sha256=digest))
            put(run / f'runtime_full_{arm}.json', {})
            for q in ('a', 'b'):
                put(run / 'predictions' / arm / (q + '.json'), dict(question_id=q, group_id=gid, answer='yes', status='completed'))
            put(run / 'joint_groups' / arm / (gid + '.json'), dict(group_id=gid, answers={'a': {'answer': 'yes'}, 'b': {'answer': 'yes'}}))
            put(run / 'calls' / arm / gid / '1/request.json', {'group_request_marker': gid})
            put(run / 'calls' / arm / gid / '1/response.json', {'content': 'group response'})
        return data, run, scored, cohort, gid

    def test_subset_and_group_requests_are_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            data, run, scored, cohort, gid = self.fixture(root)
            out = root / 'public'
            export(data, run, scored, out, ['D-Q', 'M-Q'], 'https://example.com/previous', cohort=cohort, dataset='slake')
            for name in ('inputs.jsonl', 'references.jsonl'):
                values = [json.loads(line) for line in (out / name).read_text().splitlines()]
                self.assertEqual({v['question_id'] for v in values}, {'a', 'b'})
            for arm in ('D-Q', 'M-Q'):
                self.assertTrue((out / 'joint_groups' / arm / (gid + '.json')).exists())
                calls = json.loads((out / 'calls' / arm / (gid + '.json')).read_text())
                self.assertEqual(calls[0]['request']['group_request_marker'], gid)
                self.assertFalse((out / 'calls' / arm / 'a.json').exists())

    def test_receipt_from_different_cohort_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            data, run, scored, cohort, _ = self.fixture(root)
            (run / 'complete_D-Q.json').write_text(json.dumps({'cohort_sha256': 'wrong'}))
            with self.assertRaisesRegex(ValueError, 'different joint cohort'):
                export(data, run, scored, root / 'public', ['D-Q', 'M-Q'], 'https://example.com/previous', cohort=cohort, dataset='slake')


if __name__ == '__main__':
    unittest.main()
