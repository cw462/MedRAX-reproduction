import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

try:
    from . import v11_blindread_metrics as metrics
except ImportError:
    import v11_blindread_metrics as metrics


class V11BlindreadMetricsTests(unittest.TestCase):
    def test_stage_and_case_keys_are_s3_without_mutating_results(self):
        selection = {'planned_n': 2, 'rows': [
            {'question_id': 'a', 'official_group': 'detection'},
            {'question_id': 'b', 'official_group': 'classification'}]}
        p0 = [{'question_id': 'a', 'initial': 'A'}, {'question_id': 'b', 'initial': None}]
        source = [
            {'question_id': 'a', 'group': 'VKE', 'initial': 'A', 'candidate': 'B', 'final': 'A'},
            {'question_id': 'b', 'group': 'VKE', 'initial': None, 'candidate': 'C', 'final': 'C'}]
        rows = [dict(r, stage='S3', final=r['candidate'], route='selector' if r['initial'] else 'p0_missing',
                     accounting={'model_calls': 2 if r['initial'] else 0, 'logical_cost_cny': '.02' if r['initial'] else '0'})
                for r in source]
        before = copy.deepcopy(rows)
        previous = [dict(r, stage='S1') for r in source]
        result = metrics.score(selection, p0, source, rows, {'a': 'B', 'b': 'C'}, previous_rows=previous)
        self.assertEqual(result['stage'], 'S3')
        self.assertEqual(result['groups']['VKE']['final']['correct'], 2)
        self.assertEqual(result['groups']['VKE']['S1']['final']['correct'], 1)
        self.assertEqual(result['new_resources']['model_calls']['sum_observed'], 2)
        for key in ('case_changes', 'representative_changes'):
            self.assertEqual(result['groups']['VKE'][key][0]['S3'], 'B')
            self.assertNotIn('S2', result['groups']['VKE'][key][0])
        self.assertEqual(rows, before)
        markdown = metrics.original._markdown(result)
        self.assertIn('VKE/S3', markdown)
        self.assertNotIn('VKE/S2', markdown)

    def test_incomplete_generation_never_opens_labels(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, run = root/'source', root/'run'
            source.mkdir(); run.mkdir()
            selection = {'planned_n': 60, 'rows': [{'question_id': str(i),
                'official_group': 'detection'} for i in range(60)]}
            (source/'selection.json').write_text(json.dumps(selection), encoding='utf-8')
            rows = [{'question_id': str(i), 'group': 'VKE', 'stage': 'S3'} for i in range(60)]
            (run/'results.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows), encoding='utf-8')
            (run/'status.json').write_text('{"status":"running","planned_n":60}', encoding='utf-8')
            with patch.object(metrics.original.base, '_labels', side_effect=AssertionError('labels opened early')) as labels:
                with self.assertRaisesRegex(ValueError, 'labels have not been opened'):
                    metrics.generate_report(run, source, root/'labels.jsonl')
                labels.assert_not_called()


if __name__ == '__main__':
    unittest.main()
