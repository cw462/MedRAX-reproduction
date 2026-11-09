"""Score one fully finished R49 dataset once; final publication gates are unchanged."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'experiments'))
import score_online_skill_r49 as scoring


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def exclusive_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)
        handle.write('\n')


def raw_dataset_completion(run, jobs, runner_exit, dataset):
    exits = [run/'generation.exitcode', jobs/(dataset+'.exitcode'), runner_exit]
    if runner_exit.resolve() == exits[1].resolve() or runner_exit.name != dataset+'.exitcode':
        raise ValueError('separate_actual_dataset_runner_exit_record_required')
    for path in exits:
        if not path.is_file() or path.read_text(encoding='utf-8-sig').strip() != '0':
            raise ValueError('dataset_raw_exit_zero_required:'+str(path))
    # complete.json contains learned state: do not open it before native score's
    # reference-free adaptation. Native score validates its content afterwards.
    if not (run/'complete.json').is_file():
        raise ValueError('dataset_completion_marker_required')
    return [{'path': str(path.resolve()), 'raw_exit': 0} for path in exits]


def pre_adaptation_recovery_proof(identity, receipt, *, require_unscored):
    """Only the recorded first CheX image-alias mismatch, never an unknown retry."""
    fixed_receipt = ROOT/'local_assets/r49_dataset_score_receipts/chexbench.json'
    if identity['dataset'] != 'chexbench' or receipt.resolve() != fixed_receipt.resolve():
        raise ValueError('only_named_first_CheX_pre_adaptation_failure_can_resume')
    started_path = receipt.with_name('chexbench.started.json')
    failure_path = receipt.with_name('chexbench.pre_adaptation_failure_001.json')
    old = read(started_path); failure = read(failure_path)
    old_identity = old.get('identity', {})
    old_data = ROOT/'reports/cxr_vqa_extension/results/chexbench'
    run = Path(identity['run']); expected_data = run.parent.parent/'dataset_completion/chexbench/source_data'
    if (old.get('schema') != 'r49_dataset_score_started_v1'
            or Path(old_identity.get('data', '')).resolve() != old_data.resolve()
            or identity['data'] != str(expected_data.resolve())
            or {k: v for k, v in old_identity.items() if k != 'data'} != {k: v for k, v in identity.items() if k != 'data'}
            or old.get('new_inference_calls') != 0
            or old.get('controller_exit_zero_required_for_this_interim_score') is not False):
        raise ValueError('pre_adaptation_resume_changes_more_than_known_data_alias')
    known_failure = {'schema': 'r49_dataset_score_pre_adaptation_failure_v1', 'dataset': 'chexbench',
        'started_receipt': 'local_assets/r49_dataset_score_receipts/chexbench.started.json',
        'actual_cli_exit': 1, 'exec_chunk_id': 'e005ad', 'exception_type': 'ValueError',
        'exception_message': 'manifest_semantic_input_order_changed', 'all_arm_adaptation_executed': False,
        'references_or_feedback_or_complete_body_opened': False, 'result_directory_exists': False,
        'completed_score_receipt_exists': False, 'native_scorer_or_metrics_modified': False,
        'original_started_receipt_retained': True, 'no_automatic_rescore': True}
    if (any(failure.get(k) != v for k, v in known_failure.items())
            or not any('completed_gate' in line for line in failure.get('trace_stage', []))
            or not any('raise ValueError(manifest_semantic_input_order_changed)' in line for line in failure.get('trace_stage', []))):
        raise ValueError('only_actual_closed_prereference_input_gate_failure_is_supported')
    if require_unscored and (receipt.exists() or Path(identity['out']).exists()):
        raise ValueError('pre_adaptation_recovery_requires_no_score_outputs_or_completed_receipt')
    source_path = expected_data.parent/'SOURCE_INPUT_PULL_RECEIPT.json'; source = read(source_path)
    expected_source = {'schema': 'r49_canonical_input_source_pull_v1', 'dataset': 'chexbench',
        'status': 'canonical_input_copied_and_manifest_equal',
        'remote_source': '/home/imss/cw/MedRAX_reproduction_20261027/code_cxr_vqa_extension/data/chexbench/inputs.jsonl',
        'questions': 618, 'manifest_inputs_equal': True, 'manifest_order_equal': True,
        'references_requested': False, 'references_parsed': False, 'completion_body_parsed': False,
        'generation_or_predictions_modified': False, 'shared_download_inventory_used': False,
        'model_api_calls': 0, 'hashes_computed': False}
    if (any(source.get(k) != v for k, v in expected_source.items())
            or Path(source.get('local_data', '')).resolve() != expected_data.resolve()
            or Path(source.get('local_input', '')).resolve() != (expected_data/'inputs.jsonl').resolve()):
        raise ValueError('actual_exact_canonical_source_input_pull_required')
    inputs = lambda path: [json.loads(line) for line in path.read_text(encoding='utf-8-sig').splitlines() if line.strip()]
    canonical = inputs(expected_data/'inputs.jsonl'); previous = inputs(old_data/'inputs.jsonl')
    manifest = read(run/'manifest.json'); ids = [row['question_id'] for row in canonical]
    if (len(canonical) != 618 or len(previous) != 618 or len(set(ids)) != 618
            or canonical != manifest['inputs'] or ids != [item['question_id'] for item in manifest['order']]
            or [row['question_id'] for row in previous] != ids):
        raise ValueError('canonical_618_inputs_and_declared_order_must_match_without_relaxation')
    for before, after in zip(previous, canonical):
        if (set(before) != set(after) or {k: v for k, v in before.items() if k != 'images'} != {k: v for k, v in after.items() if k != 'images'}
                or before.get('images') == after.get('images') or not isinstance(before.get('images'), list)
                or not isinstance(after.get('images'), list) or len(before['images']) != len(after['images']) or not after['images']
                or any(not isinstance(name, str) or not name.startswith('assets/') for name in before['images'])
                or any(not isinstance(name, str) or not name.startswith('images/') for name in after['images'])):
            raise ValueError('only_published_assets_to_canonical_images_path_difference_supported')
    return {'schema': 'r49_fixed_chexbench_pre_adaptation_recovery_v1', 'dataset': 'chexbench',
        'original_started_path': str(started_path.resolve()), 'original_started_record': old,
        'failure_metadata_path': str(failure_path.resolve()), 'failure_metadata': failure,
        'source_pull_receipt_path': str(source_path.resolve()), 'source_pull_receipt': source,
        'canonical_inputs_equal_manifest': True, 'canonical_order_equal_manifest': True,
        'all_other_input_fields_equal': True, 'changed_field_counts': {'images': 618},
        'original_records_overwritten_or_deleted': False, 'reference_labels_parsed_by_recovery': False,
        'native_gate_or_adaptation_modified': False}


def score_once(data, run, jobs, runner_exit, references, out, dataset, *,
               r47_frozen=None, r47_run=None, receipt=None, score_backend=None, recover_pre_adaptation_failure=False):
    if dataset not in scoring.EXPECTED:
        raise ValueError('unknown_dataset')
    data, run, jobs, runner_exit, references, out = map(Path, (data, run, jobs, runner_exit, references, out))
    receipt = Path(receipt) if receipt is not None else ROOT/'local_assets/r49_dataset_score_receipts'/(dataset+'.json')
    if (r47_frozen is None) != (r47_run is None) or (dataset == 'chexbench') != (r47_run is not None):
        raise ValueError('CheX_requires_fixed_R47_secondary_to_reuse_final_scores_others_do_not')
    raw_exits = raw_dataset_completion(run, jobs, runner_exit, dataset)
    identity = {'dataset': dataset, **{name: str(value.resolve()) for name, value in {
        'data': data, 'run': run, 'jobs': jobs, 'runner_exit': runner_exit, 'references': references, 'out': out}.items()},
        'r47_frozen': str(Path(r47_frozen).resolve()) if r47_frozen is not None else None,
        'r47_run': str(Path(r47_run).resolve()) if r47_run is not None else None}
    n, baseline, expected_baseline = scoring.EXPECTED[dataset]
    if receipt.is_file():
        saved = read(receipt)
        if (saved.get('schema') != 'r49_completed_dataset_score_receipt_v1' or saved.get('status') != 'completed'
                or saved.get('identity') != identity):
            raise ValueError('existing_score_receipt_identity_or_completion_changed')
        if saved.get('native_score_invocations') == 2:
            proof = pre_adaptation_recovery_proof(identity, receipt, require_unscored=False)
            resume = read(receipt.with_name('chexbench.pre_adaptation_resume_001.started.json'))
            if (saved.get('pre_adaptation_recovery') != proof or resume.get('pre_adaptation_recovery') != proof
                    or resume.get('identity') != identity or saved.get('completed_metric_calculations') != 1
                    or saved.get('pre_adaptation_failed_invocations') != 1):
                raise ValueError('completed_resumed_score_requires_the_same_exact_historical_proof')
        elif (saved.get('native_score_invocations') != 1 or saved.get('completed_metric_calculations') != 1
                or saved.get('pre_adaptation_failed_invocations') != 0):
            raise ValueError('unexpected_score_attempt_counts')
        summary = read(out/'summary.json'); details = read(out/'per_question.json')
        if (summary != saved['summary_snapshot'] or len(details) != n
                or [item['question_id'] for item in details] != saved['scored_question_ids']):
            raise ValueError('saved_score_outputs_no_longer_match_once_only_receipt')
        return {'dataset': dataset, 'reused_completed_score': True, 'native_score_invoked_now': False,
                'score_output': str(out.resolve()), 'receipt': str(receipt.resolve()), 'summary': summary,
                'final_audit_or_publication_complete': False}
    if out.exists():
        raise ValueError('unreceipted_existing_score_output_inspect_without_rescoring')
    if (out.resolve().is_relative_to(run.resolve()) or run.resolve().is_relative_to(out.resolve())
            or receipt.resolve().is_relative_to(out.resolve()) or receipt.resolve().is_relative_to(run.resolve())):
        raise ValueError('score_output_and_private_receipt_must_be_separate_from_generation')
    started = receipt.with_name(receipt.stem+'.started.json')
    proof = None
    if recover_pre_adaptation_failure:
        proof = pre_adaptation_recovery_proof(identity, receipt, require_unscored=True)
        started = receipt.with_name('chexbench.pre_adaptation_resume_001.started.json')
    if started.exists():
        raise ValueError('score_already_started_or_interrupted_inspect_without_automatic_rescore')
    began = datetime.now(timezone.utc).isoformat()
    exclusive_json(started, {'schema': 'r49_dataset_score_started_v1', 'identity': identity,
        'started_at': began, 'actual_raw_exit_records': raw_exits,
        'controller_exit_zero_required_for_this_interim_score': False, 'new_inference_calls': 0,
        **({'explicit_pre_adaptation_resume': True, 'pre_adaptation_recovery': proof,
            'native_score_attempt_ordinal': 2, 'automatic_retry': False} if proof else {})})
    # This unchanged native function checks the full fixed cohort, every saved
    # artifact/request/tool/recovery proof and raw exit. It adapts ALL current
    # and historical arms before opening feedback/reference annotations.
    backend = score_backend or scoring.score
    summary, details = backend(data, run, references, dataset,
                              r47_frozen=r47_frozen, r47_run=r47_run)
    ids = [item['question_id'] for item in details]
    expected_arms = {scoring.ARM, baseline} | ({'R47_online_GT'} if dataset == 'chexbench' else set())
    if (summary.get('dataset') != dataset or summary.get('arm') != scoring.ARM or summary.get('questions') != n
            or summary.get('all_questions_fresh') is not True or summary.get('references_read_after_all_arms_adapted') is not True
            or len(details) != n or len(set(ids)) != n or set(summary.get('arms', {})) != expected_arms
            or summary['arms'][baseline]['correct'] != expected_baseline
            or dataset == 'chexbench' and summary['arms']['R47_online_GT']['correct'] != 468):
        raise ValueError('native_complete_fixed_arm_scores_required')
    if proof and pre_adaptation_recovery_proof(identity, receipt, require_unscored=True) != proof:
        raise ValueError('original_failure_or_source_record_changed_during_explicit_resume')
    scoring.save_once(out/'summary.json', summary); scoring.save_once(out/'per_question.json', details)
    record = {'schema': 'r49_completed_dataset_score_receipt_v1', 'status': 'completed', 'identity': identity,
        'started_at': began, 'completed_at': datetime.now(timezone.utc).isoformat(),
        'actual_raw_exit_records': raw_exits, 'questions': n, 'scored_question_ids': ids,
        'native_score_function': 'experiments.score_online_skill_r49.score', 'native_score_invocations': 2 if proof else 1,
        'completed_metric_calculations': 1, 'pre_adaptation_failed_invocations': 1 if proof else 0,
        **({'pre_adaptation_recovery': proof} if proof else {}),
        'summary_snapshot': summary, 'references_read_after_all_arms_adapted': True,
        'new_inference_calls': 0, 'interim_completed_dataset_report': True,
        'audit_status': 'completed_dataset_offline_score_final_audit_pending',
        'online_ground_truth_feedback': True, 'causal_or_official_SOTA_claim': False,
        'later_dataset_policy_frozen_do_not_tune_from_interim_scores': True,
        'controller_exit_zero_required_for_this_interim_score': False,
        'final_three_dataset_audit_and_publication_gates_unchanged': True,
        'final_audit_or_publication_complete': False,
        'reuse_instruction': 'Reuse these exact summary/per_question files during final export/writer; do not run private scoring again. Public independent reproduction remains required.'}
    exclusive_json(receipt, record)
    return {'dataset': dataset, 'reused_completed_score': False, 'native_score_invoked_now': True,
            'score_output': str(out.resolve()), 'receipt': str(receipt.resolve()), 'summary': summary,
            'final_audit_or_publication_complete': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset', choices=scoring.EXPECTED, required=True)
    for name in ('data', 'run', 'jobs', 'runner-exit', 'references', 'out'):
        parser.add_argument('--'+name, type=Path, required=True)
    for name in ('r47-frozen', 'r47-run', 'receipt'):
        parser.add_argument('--'+name, type=Path)
    parser.add_argument('--recover-pre-adaptation-failure', action='store_true',
                        help='Explicitly resume ONLY the recorded first CheX image-alias input-gate failure, once.')
    args = parser.parse_args()
    result = score_once(args.data, args.run, args.jobs, args.runner_exit, args.references, args.out, args.dataset,
        r47_frozen=args.r47_frozen, r47_run=args.r47_run, receipt=args.receipt,
        recover_pre_adaptation_failure=args.recover_pre_adaptation_failure)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__': main()
