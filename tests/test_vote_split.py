import contextlib
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest

from data_tools.make_heldout import build, collect_history, decode_history_manifest, main, ordered_images, read_rows


def row(case, number=0, **extra):
    value = {'question_id': f'{case}_{1000000000000 + number}',
             'case_id': str(case), 'question': 'Choose A or B from Figure 1.',
             'images': [f'figures/{case}/figure_1.jpg'], 'answer': 'A'}
    value.update(extra)
    return value


def history(*cases):
    return {'excluded_case_ids': [str(c) for c in cases], 'unresolved_references': []}


class HeldoutSplitTests(unittest.TestCase):
    def test_whole_case_selection_and_determinism_without_prefix_inference(self):
        rows = [row(c, n) for c in range(10, 18) for n in range(2)]
        rows[0]['case_id'] = 'case-not-qid-prefix'
        rows[1]['case_id'] = 'case-not-qid-prefix'
        a, _, m = build(rows, history('case-not-qid-prefix'), tune_questions=3, test_questions=3)
        b, _, _ = build(rows, history('case-not-qid-prefix'), tune_questions=3, test_questions=3)
        self.assertEqual(a, b)
        self.assertEqual(m['split_question_counts'], {'tune': 4, 'test': 4})
        self.assertFalse({r['case_id'] for r in a['tune']} & {r['case_id'] for r in a['test']})
        self.assertNotIn('case-not-qid-prefix', m['assignment'])
        for c in m['assignment']:
            self.assertEqual(sum(r['case_id'] == c for group in a.values() for r in group), 2)

    def test_pool_metadata_inventory_is_not_exposure_but_real_candidates_are(self):
        rows = [row(10), row(11), row(12)]
        boundary = {'entries': [{'question_id': r['question_id'],
                                'case_hash': hashlib.sha256(r['case_id'].encode()).hexdigest(),
                                'features': ['vqa']} for r in rows],
                    'registry': {'rows': [{'question_id': r['question_id'], 'split': 'train'} for r in rows]}}
        with tempfile.TemporaryDirectory() as d:
            Path(d, 'pool.json').write_text(json.dumps({'payload': {'boundary': boundary, 'records': [
                {'source_question_id': rows[0]['question_id'], 'candidate_not_injected': True,
                 'question': 'An actual training memory item'}]}}), encoding='utf-8')
            h = collect_history(rows, d)
            self.assertEqual(h['excluded_case_ids'], ['10'])
            self.assertEqual(len(h['metadata_only_inventories_not_exposure']), 1)
            boundary['actual_question'] = rows[1]['question_id']
            Path(d, 'pool.json').write_text(json.dumps({'boundary': boundary}), encoding='utf-8')
            self.assertEqual(set(collect_history(rows, d)['excluded_case_ids']), {'10', '11', '12'})

    def test_isolated_label_storage_not_usage_and_unknown_history_blocks(self):
        rows = [row(10), row(11), row(12)]
        with tempfile.TemporaryDirectory() as d:
            Path(d, 'train.labels.jsonl').write_text(json.dumps({'question_id': rows[0]['question_id'], 'answer': 'A'}))
            Path(d, 'feedback.json').write_text(json.dumps({'question_id': rows[1]['question_id'], 'answer': 'A'}))
            h = collect_history(rows, d)
            self.assertEqual(h['excluded_case_ids'], ['11'])
            self.assertEqual(len(h['isolated_reference_stores_not_exposure']), 1)
            Path(d, 'unknown.json').write_text(json.dumps({'question_id': 'unmapped-historical-question'}))
            h = collect_history(rows, d)
            self.assertTrue(h['unresolved_references'])
            with self.assertRaisesRegex(ValueError, 'unresolved historical'):
                build(rows, h, tune_questions=1, test_questions=1)

    def test_qid_resolves_legacy_alias_only_with_local_explicit_context(self):
        rows = [row(10), row(11)]
        with tempfile.TemporaryDirectory() as d:
            Path(d, 'trace.jsonl').write_text('\n'.join(map(json.dumps, [
                {'question_id': rows[0]['question_id'], 'case_hash': 'old-content-hash'},
                {'case_hash': 'unknown-next-record'}])))
            h = collect_history(rows, d)
            self.assertEqual(h['excluded_case_ids'], ['10'])
            self.assertEqual(len(h['qid_linked_legacy_case_aliases']), 1)
            self.assertEqual(h['unresolved_references'][0][2], 'unknown-next-record')

    def test_same_image_source_case_closure_and_missing_images(self):
        rows = [row(c) for c in range(10, 19)]
        rows[0]['image_source_urls'] = ['https://source.example/shared.jpg']
        rows[1]['image_source_urls'] = ['https://source.example/shared.jpg']
        rows[2]['images'] = []
        inputs, _, m = build(rows, history(10), tune_questions=2, test_questions=2)
        self.assertEqual(m['exact_image_component_extra_excluded_cases'], ['11'])
        self.assertEqual(m['incomplete_image_cases_excluded'], ['12'])
        self.assertFalse({'10', '11', '12'} & set(m['assignment']))
        self.assertTrue(all(r['images'] for xs in inputs.values() for r in xs))

    def test_figure_binding_preserves_explicit_order_without_timepoint_guess(self):
        r = row(10, question='Compare Figure 2b with Figure 1a.',
                images=['figures/10/figure_10.jpg', 'figures/10/figure_1a.jpg',
                        'figures/10/unknown.png', 'figures/10/figure_2b.jpg'])
        images, labels = ordered_images(r)
        self.assertEqual(labels[:3], ['Figure 2b', 'Figure 1a', 'Figure 10'])
        self.assertEqual(images[-1], 'figures/10/unknown.png')

    def test_cli_writes_label_free_inputs_and_isolated_references(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            meta, hist = root / 'meta.jsonl', root / 'history.json'
            meta.write_text('\n'.join(json.dumps(row(c, explanation='private reference explanation')) for c in range(10, 18)))
            hist.write_text(json.dumps(history()))
            argv = ['--metadata', str(meta), '--history-manifest', str(hist), '--out', str(root / 'inputs'),
                    '--labels-out', str(root / 'scorer_only'), '--tune-questions', '2', '--test-questions', '2']
            with contextlib.redirect_stdout(io.StringIO()):
                main(argv)
            for split in ['tune', 'test']:
                inputs = read_rows(root / 'inputs' / (split + '.inputs.jsonl'))
                self.assertTrue(all(set(r) == {'question_id', 'case_id', 'question', 'images', 'figure_labels'} for r in inputs))
                refs = json.loads((root / 'scorer_only' / (split + '.labels.json')).read_text())['records']
                self.assertEqual([r['question_id'] for r in inputs], [r['question_id'] for r in refs])
            with self.assertRaisesRegex(ValueError, 'outside generation'):
                main(argv[:argv.index('--labels-out') + 1] + [str(root / 'inputs' / 'labels')] + argv[argv.index('--labels-out') + 2:])
            with self.assertRaisesRegex(ValueError, 'no overwrite'):
                main(argv)

    def test_metadata_truncation_fails_with_line_without_exposing_content(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'metadata.jsonl'
            p.write_text(json.dumps(row(10)) + '\n{"answer":')
            with self.assertRaisesRegex(ValueError, 'line 2'):
                read_rows(p)

    def test_public_schema2_history_cli_decodes_losslessly_and_rejects_bad_index(self):
        packed = dict(history(10), schema_version=2,
                      source_files=['reports/train/trace.jsonl', 'archive/train.labels.jsonl'],
                      case_source_indices={'10': [0]},
                      qid_linked_legacy_case_aliases=[[0, 'case_hash', 'old-content-hash', ['10']]],
                      metadata_only_inventories_not_exposure=[],
                      isolated_reference_stores_not_exposure=[{'source_file_index': 1, 'record_count': 8}])
        decoded = decode_history_manifest(packed)
        self.assertEqual(decoded['case_sources'], {'10': ['reports/train/trace.jsonl']})
        self.assertEqual(decoded['qid_linked_legacy_case_aliases'],
                         [['reports/train/trace.jsonl', 'case_hash', 'old-content-hash', ['10']]])
        self.assertEqual(decoded['isolated_reference_stores_not_exposure'],
                         [{'source': 'archive/train.labels.jsonl', 'record_count': 8}])
        self.assertEqual(packed['schema_version'], 2)  # decoding does not mutate the published file
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / 'metadata.jsonl').write_text('\n'.join(json.dumps(row(c)) for c in range(10, 18)))
            (root / 'public.json').write_text(json.dumps(packed))
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                main(['--metadata', str(root / 'metadata.jsonl'), '--history-manifest', str(root / 'public.json'),
                      '--history-out', str(root / 'decoded.json'), '--preview', '--tune-questions', '2', '--test-questions', '2'])
            self.assertEqual(json.loads(output.getvalue())['seen_case_n'], 1)
            self.assertEqual(json.loads((root / 'decoded.json').read_text()), decoded)
        packed['case_source_indices']['10'] = [-1]
        with self.assertRaisesRegex(ValueError, 'source_file_index'):
            decode_history_manifest(packed)


if __name__ == '__main__':
    unittest.main()
