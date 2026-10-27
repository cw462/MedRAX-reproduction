"""Synthetic isolated fixtures and offline evidence-integrity tests."""
from copy import deepcopy
import builtins
import io
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'experiments'))
import diagnostic_eval as diag
import multi_tool_eval as multi
from test_multi_tool_eval import runtime, tool_call
from test_diagnostic_eval import FakeModel, Message, FakeGuard, arguments, fake_messages
from .core import Boundary, FrozenPool, compile_run, freeze_pool, digest, file_hash, visible_features


def fixture(root, *, outcome=False, source_split='memory_train'):
    image = root / 'image.png'; image.write_bytes(b'SYNTHETIC IMAGE NOT FOR INFERENCE')
    rows = [{'question_id': name, 'question': 'Where is the finding?\nA. SECRET_OPTION\nB. OTHER_OPTION',
             'images': ['image.png'], 'image_sha256': [file_hash(image)], 'case_hash': case * 64, 'split': split}
            for name, case, split in [('q1', '1', source_split), ('q2', '2', 'memory_train'),
                                      ('qsame', '1', source_split), ('qval', '3', 'validation'), ('qtest', '4', 'heldout_test')]]
    boundary = Boundary.synthetic(rows)
    source = rows[:2]
    provenance = runtime(FakeModel([])).tool_provenance
    plan = {'kind': multi.KIND, 'planned_question_count': 2, 'question_ids': ['q1', 'q2'],
        'schedule': [{'question_id': x['question_id'], 'arm': 'agent'} for x in source],
        'records': [diag.inspect_input(x, root)[0] for x in source], 'tool_registry': provenance,
        'model': diag.MODEL, 'provider_base_url': 'https://example.invalid/v1', 'prompts': {'fixture': True},
        'max_output_tokens': 1024, 'max_model_calls': 4, 'max_tool_calls': 2, 'temperature': 0.2, 'top_p': 0.95,
        'provider_retries': 0, 'image_detail': 'auto', 'source_sha256': {'fixture.py': 'a' * 64},
        'package_versions': {'synthetic_fixture': 'only'}}
    journal = diag.RunJournal(root / 'run', plan)
    with (journal.output / 'trace.jsonl').open('w', encoding='utf-8') as trace:
        for row in source:
            start = journal.start(row['question_id'], 'agent')
            model = FakeModel([Message('', tool_calls=[tool_call('chest_xray_report_generator', image, 'r')]),
                               Message('SYNTHETIC_REASONING_NOT_FOR_MEMORY'), Message('A')])
            result = multi.run_arm(runtime(model), FakeGuard(), row, [image], 'agent', start,
                journal.manifest['run_id'], arguments(), trace, message_builder=fake_messages)
            journal.finish(result)
    journal.summary('complete'); journal.close()
    sidecar = None
    if outcome:
        sidecar = root / 'outcomes.json'
        sidecar.write_bytes(diag.canonical({'schema_version': 1,
            'source_run_manifest_sha256': file_hash(root / 'run/manifest.json'),
            'source_results_sha256': file_hash(root / 'run/results.jsonl'),
            'split_manifest_sha256': boundary.payload()['registry']['split_manifest_sha256'],
            'outcomes': [{'question_id': qid, 'arm': 'agent', 'task_outcome': 'correct'} for qid in ('q1', 'q2')]}))
    return root / 'run', boundary, rows, sidecar


def query(row, records):
    return {k: row[k] for k in ('question_id', 'question', 'images')} | {
        'available_tools': records[0]['available_tool_versions'], 'protocol_sha256': records[0]['protocol_sha256']}


class PipelineTests(unittest.TestCase):
    def test_real_execution_shape_compiles_without_inventing_outcomes_or_clinical_credit(self):
        with TemporaryDirectory() as temp:
            run, boundary, _, _ = fixture(Path(temp))
            records, report = compile_run(run, boundary)
            self.assertEqual(report['compiled_trajectories'], 2)
            self.assertEqual(report['compiled_actual_tool_steps'], 2)
            self.assertEqual(report['task_outcomes'], {'unknown': 2})
            for record in records:
                self.assertEqual(record['steps'][0]['execution'], 'returned_valid')
                self.assertEqual(record['clinical_evidence'], 'unknown')
                self.assertIsNone(record['steps'][0]['step_credit'])
            text = json.dumps(records)
            for secret in ('SECRET_OPTION', 'SYNTHETIC_REASONING', 'SYNTHETIC_REPORT_PROSE', 'answer_letter', 'correct_answer', 'explanation'):
                self.assertNotIn(secret, text)

    def test_validation_and_heldout_source_runs_rejected(self):
        for split in ('validation', 'heldout_test'):
            with self.subTest(split=split), TemporaryDirectory() as temp:
                run, boundary, _, _ = fixture(Path(temp), source_split=split)
                with self.assertRaises(ValueError): compile_run(run, boundary)

    def test_same_case_all_questions_excluded_and_unknown_pool_has_no_success_hits(self):
        with TemporaryDirectory() as temp:
            run, boundary, rows, sidecar = fixture(Path(temp), outcome=True)
            unknown, _ = compile_run(run, boundary)
            pool = freeze_pool(boundary, unknown, family='multitool_original', version=1, allow_synthetic=True)
            self.assertEqual(pool.search(query(rows[3], unknown)), [])
            records, _ = compile_run(run, boundary, outcomes=sidecar)
            pool = freeze_pool(boundary, records, family='multitool_original', version=2, previous_sha256=pool.sha256, allow_synthetic=True)
            hits = pool.search(query(rows[2], records), min_score=0)
            self.assertEqual(len(hits), 1)
            self.assertEqual(hits[0]['memory_id'], records[1]['memory_id'])
            context = json.dumps(hits)
            for forbidden in ('source_question_id', 'source_case_hash', 'source_thread_id', 'task_outcome'):
                self.assertNotIn(forbidden, context)

    def test_label_fields_and_modified_visible_query_rejected(self):
        with TemporaryDirectory() as temp:
            run, boundary, rows, sidecar = fixture(Path(temp), outcome=True)
            payload = json.loads(sidecar.read_text()); payload['outcomes'][0]['correct_answer'] = 'A'
            sidecar.write_bytes(diag.canonical(payload))
            with self.assertRaises(ValueError): compile_run(run, boundary, outcomes=sidecar)
            records, _ = compile_run(run, boundary)
            pool = freeze_pool(boundary, records, family='multitool_original', version=1, allow_synthetic=True)
            altered = query(rows[3], records); altered['question'] += '\nANSWER: A'
            with self.assertRaises(ValueError): pool.search(altered)
            altered = query(rows[3], records); altered['explanation'] = 'secret'
            with self.assertRaises(ValueError): pool.search(altered)
            altered = query(rows[3], records); altered['images'] = ['foreign_case.png']
            with self.assertRaises(ValueError): pool.search(altered)

    def test_missing_or_forged_tool_execution_and_version_are_rejected(self):
        for mutation in ('no_tool', 'wrong_version', 'wrong_image'):
            with self.subTest(mutation=mutation), TemporaryDirectory() as temp:
                run, boundary, _, _ = fixture(Path(temp))
                trace = [json.loads(line) for line in (run / 'trace.jsonl').read_text().splitlines()]
                if mutation == 'no_tool': trace = [x for x in trace if x.get('node') != 'tool']
                else:
                    step = next(x for x in trace if x.get('node') == 'tool')
                    step['tool_version_sha256' if mutation == 'wrong_version' else 'image_sha256'] = 'f' * 64
                (run / 'trace.jsonl').write_bytes(b''.join(diag.canonical(x) for x in trace))
                with self.assertRaises(ValueError): compile_run(run, boundary)

    def test_source_manifest_cannot_substitute_other_case_image_with_same_count(self):
        with TemporaryDirectory() as temp:
            run, boundary, _, _ = fixture(Path(temp))
            manifest = json.loads((run / 'manifest.json').read_text())
            summary = json.loads((run / 'summary.json').read_text())
            manifest['plan']['records'][0]['images'][0]['sha256'] = 'b' * 64
            manifest['plan_sha256'] = digest(manifest['plan'])
            summary['plan_sha256'] = manifest['plan_sha256']
            (run / 'manifest.json').write_bytes(diag.canonical(manifest))
            (run / 'summary.json').write_bytes(diag.canonical(summary))
            with self.assertRaises(ValueError): compile_run(run, boundary)

    def test_incomplete_or_summary_mismatched_run_rejected(self):
        with TemporaryDirectory() as temp:
            run, boundary, _, _ = fixture(Path(temp))
            summary = json.loads((run / 'summary.json').read_text()); summary['stop_reason'] = 'running'
            (run / 'summary.json').write_bytes(diag.canonical(summary))
            with self.assertRaises(ValueError): compile_run(run, boundary)
            summary['stop_reason'] = 'complete'; summary['question_results'][0]['actual_tool_attempts'] = 9
            (run / 'summary.json').write_bytes(diag.canonical(summary))
            with self.assertRaises(ValueError): compile_run(run, boundary)

    def test_family_protocol_and_available_version_must_match(self):
        with TemporaryDirectory() as temp:
            run, boundary, rows, sidecar = fixture(Path(temp), outcome=True)
            with self.assertRaises(ValueError): compile_run(run, boundary, family='historical_classifier')
            records, _ = compile_run(run, boundary, outcomes=sidecar)
            with self.assertRaises(ValueError): freeze_pool(boundary, records, family='historical_classifier', version=1, allow_synthetic=True)
            pool = freeze_pool(boundary, records, family='multitool_original', version=1, allow_synthetic=True)
            bad = query(rows[3], records); bad['protocol_sha256'] = 'f' * 64
            with self.assertRaises(ValueError): pool.search(bad)
            bad = query(rows[3], records); bad['available_tools'] = {'chest_xray_classifier': 'f' * 64}
            self.assertEqual(pool.search(bad), [])
            bad = query(rows[3], records); bad['available_tools'] = {**bad['available_tools'], 'chest_xray_segmentation': 'f' * 64}
            self.assertEqual(pool.search(bad), [])

    def test_unknown_is_not_promoted_even_when_task_correct_and_context_is_rule_labelled(self):
        with TemporaryDirectory() as temp:
            run, boundary, rows, sidecar = fixture(Path(temp), outcome=True)
            records, _ = compile_run(run, boundary, outcomes=sidecar)
            pool = freeze_pool(boundary, records, family='multitool_original', version=1, allow_synthetic=True)
            hit = pool.search(query(rows[3], records), summary_mode=True)[0]
            self.assertEqual(hit['context']['representation'], 'deterministic_execution_rule_summary_not_llm')
            self.assertEqual(hit['context']['clinical_evidence'], 'unknown')
            for value in (0, 1.0):
                changed = deepcopy(records); changed[0]['steps'][0]['step_credit'] = value
                changed[0]['memory_id'] = digest({k:v for k,v in changed[0].items() if k != 'memory_id'})
                with self.assertRaises(ValueError): freeze_pool(boundary, changed, family='multitool_original', version=2, allow_synthetic=True)

    def test_observation_free_text_cannot_be_smuggled_into_context(self):
        with TemporaryDirectory() as temp:
            run, boundary, _, _ = fixture(Path(temp)); records, _ = compile_run(run, boundary)
            records[0]['steps'][0]['observation_shape']['answer'] = 'A'
            records[0]['memory_id'] = digest({k:v for k,v in records[0].items() if k != 'memory_id'})
            with self.assertRaises(ValueError): freeze_pool(boundary, records, family='multitool_original', version=1, allow_synthetic=True)

    def test_snapshot_external_hash_deep_immutability_and_heldout_disabled(self):
        with TemporaryDirectory() as temp:
            root = Path(temp); run, boundary, rows, sidecar = fixture(root, outcome=True)
            records, _ = compile_run(run, boundary, outcomes=sidecar)
            with self.assertRaises(ValueError): freeze_pool(boundary, records, family='multitool_original', version=1)
            pool = freeze_pool(boundary, records, family='multitool_original', version=1, allow_synthetic=True)
            before = pool.sha256; records[0]['features'].append('leak')
            self.assertEqual(pool.sha256, before)
            path = root / 'pool.json'; pool.save(path)
            self.assertEqual(FrozenPool.load(path, expected_sha256=before).sha256, before)
            with self.assertRaises(FileExistsError): pool.save(path)
            with self.assertRaises(ValueError): pool.search(query(rows[4], pool.payload()['records']))
            raw = json.loads(path.read_text()); raw['payload']['pool_version'] = 99
            raw['sha256'] = digest(raw['payload']); path.write_bytes(diag.canonical(raw))
            with self.assertRaises(ValueError): FrozenPool.load(path, expected_sha256=before)

    def test_split_boundary_never_reads_label_files_and_case_quarantine_is_enforced(self):
        with TemporaryDirectory() as temp:
            root = Path(temp); run, boundary, rows, _ = fixture(root)
            splits = root / 'splits'; splits.mkdir()
            audit = [{k: row[k] for k in ('question_id', 'split', 'case_hash')} for row in rows]
            (splits / 'audit_index.jsonl').write_bytes(b''.join(diag.canonical(x) for x in audit))
            for split in ('memory_train', 'validation', 'heldout_test'):
                (splits / (split + '.inputs.jsonl')).write_bytes(b''.join(diag.canonical({k:r[k] for k in ('question_id', 'question', 'images')}) for r in rows if r['split'] == split))
                (splits / (split + '.labels.jsonl')).write_text('FORBIDDEN REFERENCE CONTENT')
            artifacts = {x.name:file_hash(x) for x in splits.glob('*.jsonl') if '.labels.' not in x.name}
            (splits / 'manifest.json').write_bytes(diag.canonical({'artifact_sha256': artifacts}))
            exclusions = root / 'exclusions.json'
            (root / 'image_audit.jsonl').write_bytes(diag.canonical({'dataset_image_path': 'image.png',
                'question_ids': [r['question_id'] for r in rows], 'case_hashes': sorted({r['case_hash'] for r in rows}),
                'splits': ['memory_train', 'validation', 'heldout_test'], 'status': 'readable',
                'sha256': file_hash(root / 'image.png')}))
            exclusions.write_bytes(diag.canonical({'schema_version': 1, 'heldout_labels_or_outputs_used': False,
                'source_image_audit_sha256': file_hash(root / 'image_audit.jsonl'),
                'phash_used_for_exclusion': False, 'excluded_case_hashes_by_split':
                {'memory_train': ['1' * 64], 'validation': [], 'heldout_test': []}}))
            original_builtin, original_io = builtins.open, io.open
            def checked(original):
                def opened(file, *args, **kwargs):
                    if isinstance(file, (str, Path)) and '.labels.' in str(file):
                        raise AssertionError('Reference labels must not be opened')
                    return original(file, *args, **kwargs)
                return opened
            with patch.object(builtins, 'open', checked(original_builtin)), patch.object(io, 'open', checked(original_io)):
                real_boundary = Boundary.from_split_directory(splits, exclusions, expected_exclusions_sha256=file_hash(exclusions))
                records, report = compile_run(run, real_boundary)
            self.assertEqual(len(records), 1)
            self.assertEqual(records[0]['source_question_id'], 'q2')
            self.assertEqual(report['skipped'], {'quarantined_case': 1})


if __name__ == '__main__':
    unittest.main()
