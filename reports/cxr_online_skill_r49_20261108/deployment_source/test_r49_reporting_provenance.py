"""Synthetic control-record integration only; no target answers, labels or scorer."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


spec = importlib.util.spec_from_file_location('r49_future_report_writer', Path(__file__).with_name('finalize_r49_report.py'))
writer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(writer)


class ReportingProvenance(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)/'project'
        self.report = self.root/'reports/r49'
        self.archive = Path(self.tmp.name)/'archive'
        self.prep = self.root/'local_assets/prep'
        self.receipts = self.root/'local_assets/score_receipts'
        self.public = self.report/'deployment_source/reporting_provenance'
        self.public.mkdir(parents=True)
        self.addCleanup(patch.stopall)
        patch.object(writer, 'ROOT', self.root).start()
        patch.object(writer, 'REPORT', self.report).start()
        self.bundles = {}; self.saved = {}
        self.pair(self.prep/'DATASET_COMPLETION_REPORTING_AUTHORIZATION.json', 'DATASET_COMPLETION_REPORTING_AUTHORIZATION.json', {
            'enabled': True, 'confirmation_source': 'explicit_user_reply',
            'exact_user_reply': '848题是这个三个数据集吧，可以做完一个数据集汇报一个数据集的准确率等成果',
            'datasets': {ds: writer.SPEC[ds]['n'] for ds in writer.DATASETS}, 'report_on_each_dataset_completion': True,
            'partial_dataset_scoring_allowed': False, 'reuse_saved_dataset_scores_at_finalization': True,
            'future_inference_tuned_from_report': False, 'final_all_three_exit_zero_gate_unchanged': True})
        for ds in writer.DATASETS:
            n = writer.SPEC[ds]['n']; ids = [ds+'_'+str(index) for index in range(n)]
            # There are no answers, references or learned contents in a fixture.
            summary = {'dataset': ds, 'questions': n, 'resources': {'unknown_cost_requests': 1}}
            self.bundles[ds] = {'summary': summary, 'details': [{'question_id': qid} for qid in ids]}
            identity = {'dataset': ds, 'run': str(self.archive/'generation'/ds), 'jobs': str(self.archive/'jobs'),
                'runner_exit': str(self.archive/'recovery/adoption_1'/(ds+'.exitcode')), 'out': str(self.report/'results'/ds),
                'data': str(self.archive/'dataset_completion/chexbench/source_data') if ds == 'chexbench' else str(self.root/'data'/ds),
                'references': str(self.root/'historical_references'/(ds+'.jsonl')), 'r47_frozen': None, 'r47_run': None}
            failed = int(ds == 'chexbench')
            receipt = {'schema': 'r49_completed_dataset_score_receipt_v1', 'status': 'completed', 'identity': identity,
                'questions': n, 'scored_question_ids': ids, 'summary_snapshot': summary,
                'native_score_invocations': 1+failed, 'completed_metric_calculations': 1, 'pre_adaptation_failed_invocations': failed,
                'new_inference_calls': 0, 'references_read_after_all_arms_adapted': True,
                'later_dataset_policy_frozen_do_not_tune_from_interim_scores': True,
                'actual_raw_exit_records': [{'path': str(path), 'raw_exit': 0} for path in (
                    self.archive/'generation'/ds/'generation.exitcode', self.archive/'jobs'/(ds+'.exitcode'),
                    self.archive/'recovery/adoption_1'/(ds+'.exitcode'))]}
            started = {'schema': 'r49_dataset_score_started_v1', 'identity': copy.deepcopy(identity), 'new_inference_calls': 0}
            if ds == 'chexbench':
                started['identity']['data'] = str(self.root/'published_alias_inputs')
                failure = {'schema': 'r49_dataset_score_pre_adaptation_failure_v1', 'actual_cli_exit': 1,
                    'exec_chunk_id': 'e005ad', 'exception_message': 'manifest_semantic_input_order_changed',
                    'all_arm_adaptation_executed': False, 'references_or_feedback_or_complete_body_opened': False,
                    'result_directory_exists': False, 'completed_score_receipt_exists': False,
                    'native_scorer_or_metrics_modified': False, 'original_started_receipt_retained': True}
                source = {'schema': 'r49_canonical_input_source_pull_v1', 'status': 'canonical_input_copied_and_manifest_equal',
                    'questions': n, 'manifest_inputs_equal': True, 'manifest_order_equal': True, 'references_parsed': False,
                    'model_api_calls': 0, 'hashes_computed': False, 'generation_or_predictions_modified': False,
                    'local_data': identity['data'], 'remote_source': '/remote/original/inputs.jsonl'}
                proof = {'schema': 'r49_fixed_chexbench_pre_adaptation_recovery_v1', 'original_started_record': started,
                    'failure_metadata': failure, 'source_pull_receipt': source, 'canonical_inputs_equal_manifest': True,
                    'canonical_order_equal_manifest': True, 'all_other_input_fields_equal': True, 'changed_field_counts': {'images': n},
                    'original_records_overwritten_or_deleted': False, 'native_gate_or_adaptation_modified': False}
                receipt['pre_adaptation_recovery'] = proof
                self.pair(self.receipts/'chexbench.pre_adaptation_failure_001.json', 'score_receipts/chexbench.pre_adaptation_failure_001.json', failure)
                self.pair(self.receipts/'chexbench.pre_adaptation_resume_001.started.json', 'score_receipts/chexbench.pre_adaptation_resume_001.started.json', {
                    'identity': identity, 'pre_adaptation_recovery': proof, 'explicit_pre_adaptation_resume': True,
                    'native_score_attempt_ordinal': 2, 'automatic_retry': False})
                self.pair(self.archive/'dataset_completion/chexbench/SOURCE_INPUT_PULL_RECEIPT.json',
                          'dataset_completion/chexbench/SOURCE_INPUT_PULL_RECEIPT.json', source)
            self.saved[ds] = copy.deepcopy(receipt)
            self.pair(self.receipts/(ds+'.json'), 'score_receipts/'+ds+'.json', receipt)
            self.pair(self.receipts/(ds+'.started.json'), 'score_receipts/'+ds+'.started.json', started)
            self.pair(self.archive/'dataset_completion'/ds/'PULL_RECEIPT.json', 'dataset_completion/'+ds+'/PULL_RECEIPT.json', {
                'status': 'complete_immutable_dataset_pulled', 'dataset': ds, 'questions': n, 'archive': str(self.archive),
                'references_parsed': False, 'completion_marker_body_parsed': False, 'other_dataset_predictions_pulled': False,
                'final_pull_must_preserve_this_generation_directory': True})
        self.pair(self.archive/'dataset_completion/FINAL_CONTROL_PULL_RECEIPT.json', 'dataset_completion/FINAL_CONTROL_PULL_RECEIPT.json', {
            'status': 'final_controls_pulled', 'generation_directories_skipped': list(writer.DATASETS),
            'scores_invoked': False, 'result_files_overwritten': False})
        self.pair(self.archive/'actual_code_source/source_completed.json', 'supplemental_receipts/source_completed.json', {
            'status': 'actual_code_source_copied', 'remote_execution': False, 'model_api_calls': 0,
            'byte_or_pixel_or_hash_checks': False, 'files': ['source_a.py', 'source_b.py']})
        self.pair(self.archive/'supplemental_receipts/local_captures_completed.json', 'supplemental_receipts/local_captures_completed.json', {
            'status': 'known_local_captures_preserved', 'remote_requests': 0, 'generation_writes': False,
            'capture_or_diagnostic_reexecuted': False, 'copied_missing': ['old_failure'],
            'existing_preserved_without_reading_or_overwriting': ['old_diagnostic']})

    def pair(self, source, relative, value):
        for path in (source, self.public/relative):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(value), encoding='utf-8')

    def inspect(self):
        return writer.offline_scoring_provenance(self.archive, self.prep, self.receipts, self.public, self.bundles)

    def test_saved_metrics_reused_and_separate_reference_source_is_reported(self):
        result = self.inspect()
        self.assertEqual((result['total_native_score_function_entries'], result['completed_metric_calculations'],
                          result['pre_adaptation_failed_invocations']), (4, 3, 1))
        self.assertFalse(result['scores_or_inference_reexecuted_by_writer'])
        actual = writer.recorded_scoring_sources({}, result)
        self.assertEqual(actual['chexbench_references'], self.saved['chexbench']['identity']['references'])
        self.assertNotEqual(Path(actual['chexbench_references']).parent, Path(actual['chexbench_data']))

    def test_mutated_saved_summary_is_not_accepted_as_the_once_score(self):
        changed = copy.deepcopy(self.saved['slake']); changed['summary_snapshot']['resources']['unknown_cost_requests'] = 0
        self.pair(self.receipts/'slake.json', 'score_receipts/slake.json', changed)
        with self.assertRaisesRegex(ValueError, 'saved_completed_metric_must_match'):
            self.inspect()

    def test_erased_failed_attempt_and_guessed_reference_path_are_rejected(self):
        changed = copy.deepcopy(self.saved['chexbench']); changed['native_score_invocations'] = 1
        self.pair(self.receipts/'chexbench.json', 'score_receipts/chexbench.json', changed)
        with self.assertRaisesRegex(ValueError, 'saved_completed_metric_must_match'):
            self.inspect()
        self.pair(self.receipts/'chexbench.json', 'score_receipts/chexbench.json', self.saved['chexbench'])
        result = self.inspect()
        wrong = str(Path(self.saved['chexbench']['identity']['data'])/'references.jsonl')
        with self.assertRaisesRegex(ValueError, 'explicit_report_source_must_match'):
            writer.recorded_scoring_sources({'chexbench_references': wrong}, result)


if __name__ == '__main__':
    unittest.main()
