"""Private, OFFLINE future R49 report writer. Do not run during generation.

Reads only already completed/scored/exported/publicly reproduced three-stream
results and an actual DeepSeek RESULT review. It never invokes inference, a
scorer, a verifier, a tool, a network connection, or Git. All R49 outcomes are
dynamic, including negative results. Only fixed cohort and historical comparator
counts are declared below. Preparing this file creates no report or index block.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal
import json
from pathlib import Path
import re
from urllib.parse import quote


ROOT = Path(__file__).resolve().parents[1]
REPORT_REL = 'reports/cxr_online_skill_r49_20261108'
REPORT = ROOT / REPORT_REL
ARM = 'M43-IM-GT-S49'
DATASETS = ('chexbench', 'slake', 'vqarad')
SPEC = {
    'chexbench': dict(label='CheXbench', n=618, groups=488, repeats=130,
                     windows=21, baseline='M43', old_correct=466),
    'slake': dict(label='另列SLAKE', n=114, groups=30, repeats=84,
                 windows=4, baseline='M43', old_correct=108),
    'vqarad': dict(label='VQA-RAD', n=116, groups=58, repeats=58,
                  windows=4, baseline='M42', old_correct=100),
}
START = '<!-- R49_ONLINE_GT_WINDOW_SKILL_START -->'
END = '<!-- R49_ONLINE_GT_WINDOW_SKILL_END -->'
DEFAULT_ARCHIVE = 'D:/MedRAX_Experiment_Artifacts/online_skill_r49_20261108'
DEFAULT_PREP = 'local_assets/online_skill_r49_preparation'
DEFAULT_SCORE_RECEIPTS = 'local_assets/r49_dataset_score_receipts'


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def jsonl(path):
    return [json.loads(line) for line in Path(path).read_text(encoding='utf-8-sig').splitlines() if line.strip()]


def dump(value):
    return json.dumps(value, ensure_ascii=False, indent=2) + '\n'


def require(value, message):
    if not value:
        raise ValueError(message)


def zero(path):
    require(Path(path).read_text(encoding='utf-8-sig').strip() == '0', 'raw_exit_zero_required:' + str(path))


def cell(value):
    return ('空' if value is None else str(value)).replace('|', '\\|').replace('\r', '').replace('\n', '<br>')


def pct(value):
    return '不适用／未知' if value is None else f'{value:.2f}%'


def num(value, digits=3):
    return '未知' if value is None else f'{value:.{digits}f}'


def signed(value):
    return f'{value:+d}'


def link(label, path):
    return f'[{cell(label)}]({quote(str(path).replace(chr(92), "/"), safe="/:._-#")})'


def table(headers, values):
    return '\n'.join(['| ' + ' | '.join(headers) + ' |',
                      '|' + '|'.join(['---'] * len(headers)) + '|'] +
                     ['| ' + ' | '.join(cell(value) for value in row) + ' |' for row in values])


def interval(value):
    require(isinstance(value, list) and len(value) == 2, 'saved_interval_required')
    meaning = '含0' if value[0] <= 0 <= value[1] else ('全正' if value[0] > 0 else '全负')
    return f'[{value[0]:+.4f}, {value[1]:+.4f}]pp（{meaning}）'


def members(folder, ids):
    found = {path.stem: path for path in folder.glob('*.json')}
    require(set(found) == ids, 'full_public_artifact_membership_required:' + str(folder))
    return found


def in_report(path):
    path = Path(path).resolve()
    require(path.is_relative_to(REPORT.resolve()) and path.is_file(), 'actual_public_review_file_required:' + str(path))
    return path.relative_to(REPORT.resolve()).as_posix()


def actual_review(raw_path, metadata_path, claims_path):
    """Require a real completed result review, allowing any positive/negative verdict."""
    raw_path, metadata_path, claims_path = map(Path, (raw_path, metadata_path, claims_path))
    paths = {name: in_report(path) for name, path in
             [('raw', raw_path), ('metadata', metadata_path), ('claims', claims_path)]}
    metadata = read(metadata_path)
    require(metadata.get('status') == 'completed' and not metadata.get('is_error')
            and metadata.get('session_id') and metadata.get('duration_ms', 0) > 0
            and metadata.get('turns', 0) > 0 and metadata.get('modelUsage')
            and any('deepseek' in model.lower() for model in metadata['modelUsage'])
            and len(raw_path.read_text(encoding='utf-8-sig').strip()) > 20
            and len(claims_path.read_text(encoding='utf-8-sig').strip()) > 20,
            'actual_user_selected_DeepSeek_result_review_required')
    # No requirement for a favorable verdict. An execution-only ready score
    # cannot stand in for this separately named result-review artifact.
    return dict(paths=paths, metadata=metadata, identity_assurance='CLI-reported service alias, not weight attestation',
                clinical_or_integrity_audit_claim=False, favorable_verdict_required=False)


def complete(value, ds):
    s = SPEC[ds]
    require(value.get('status') == 'generation_complete' and value.get('arm') == ARM
            and value.get('questions') == s['n'] and len(value.get('windows', [])) == s['windows']
            and value.get('fixed_main_call_limit') is None and value.get('fixed_tool_call_limit') is None
            and not value.get('known_technical_missing_ids') and not value.get('completion_mode'),
            'full_original_R49_completion_required:' + ds)


def load_completed(archive, public_summary_name):
    """Check every raw exit before opening ANY saved target score."""
    archive = Path(archive)
    zero(archive / 'jobs/controller.exitcode')
    queue = read(archive / 'jobs/queue_status.json')
    require(queue.get('state') == 'all_three_datasets_exited_zero_after_adoption_recovery'
            and queue.get('recovery') == 'adoption_1'
            and queue.get('prior_production_attempts_include_exit1') is True
            and list(queue.get('datasets', [])) == list(DATASETS), 'final_serial_controller_completion_after_preserved_dependency_failure_required')
    for ds in DATASETS:
        zero(archive / 'jobs' / (ds + '.exitcode'))
        zero(archive / 'generation' / ds / 'generation.exitcode')
        complete(read(archive / 'generation' / ds / 'complete.json'), ds)
    bundles = {}
    for ds in DATASETS:
        spec = SPEC[ds]; n = spec['n']; baseline = spec['baseline']
        evidence = REPORT / 'evidence' / ds
        summary = read(REPORT / 'results' / ds / 'summary.json')
        details = read(REPORT / 'results' / ds / 'per_question.json')
        public = read(REPORT / 'public_reproduction' / ds / public_summary_name)
        reproduced = read(REPORT / 'public_reproduction' / ds / 'per_question.json')
        require(summary.get('dataset') == ds and summary.get('arm') == ARM
                and summary.get('questions') == n and summary.get('all_questions_fresh') is True
                and summary.get('references_read_after_all_arms_adapted') is True
                and summary['arms'][baseline]['correct'] == spec['old_correct']
                and public.get('matches_published_primary_scores_and_extractions') is True
                and public.get('matches_published_resources') is True
                and public.get('new_inference_calls') == 0
                and public.get('image_or_file_digests_checked') is False
                and public.get('private_run_paths_required') is False,
                'completed_and_publicly_reproduced_score_required:' + ds)
        for field in ('dataset', 'arm', 'questions', 'all_questions_fresh', 'arms', 'comparisons',
                      'skill_hit_questions', 'same_image_hit_questions', 'windows', 'resources',
                      'references_read_after_all_arms_adapted'):
            require(summary.get(field) == public.get(field), 'public_summary_disagrees:' + ds + ':' + field)
        require(len(details) == len(reproduced), 'public_saved_per_question_count:' + ds)
        for private_row, public_row in zip(details, reproduced):
            for field in ('question_id', 'window', 'skill_hit', 'same_image_hit', 'subset', 'reference'):
                require(private_row.get(field) == public_row.get(field), 'public_saved_question_disagrees:' + ds + ':' + field)
            require(set(private_row['arms']) == set(public_row['arms']), 'public_saved_arm_membership:' + ds)
            for name in private_row['arms']:
                # Export deliberately rewrites path bookkeeping for portability;
                # metrics, candidates and all extraction fields remain identical.
                keep = lambda value: {key: item for key, item in value.items() if key not in ('archive_call', 'reuse_chain')}
                require(keep(private_row['arms'][name]) == keep(public_row['arms'][name]),
                        'public_saved_answer_disagrees:' + ds + ':' + private_row['question_id'] + ':' + name)
        require(set(summary['comparisons']) == set(summary['arms']) - {ARM}
                and set(summary['comparisons']) == ({baseline, 'R47_online_GT'} if ds == 'chexbench' else {baseline}),
                'fixed_full_historical_comparators_required:' + ds)
        if ds == 'chexbench':
            require(summary['arms']['R47_online_GT']['correct'] == 468, 'fixed_secondary_R47_common_count_changed')
        manifest = read(evidence / 'manifest.json')
        inputs = jsonl(evidence / 'inputs.jsonl'); ids = [row['question_id'] for row in inputs]
        require(manifest.get('dataset') == ds and manifest.get('arm') == ARM
                and manifest.get('initial_repo') == 'empty' and len(ids) == n and len(set(ids)) == n
                and [item['question_id'] for item in manifest['order']] == ids
                and [row['question_id'] for row in details] == ids,
                'full_cold_start_input_order_required:' + ds)
        order = manifest['order']
        require(len({item['image_key'] for item in order}) == spec['groups']
                and sum(bool(item['previous_ids']) for item in order) == spec['repeats'],
                'declared_image_group_partition_changed:' + ds)
        publication = read(evidence / 'publication_manifest.json')
        require(publication.get('schema') == 'r49_semantic_public_evidence_v1'
                and publication.get('scope') == 'complete_scored_online_stream'
                and publication.get('dataset') == ds and publication.get('arm') == ARM
                and publication.get('questions') == n and publication.get('raw_generation_exit') == 0
                and publication.get('new_inference_calls') == 0
                and publication.get('all_question_predictions_are_fresh') is True
                and publication.get('cross_dataset_feedback_shared') is False
                and publication.get('official_SOTA_or_causal_Skill_claim') is False,
                'full_semantic_public_export_required:' + ds)
        zero(evidence / 'generation.exitcode'); complete(read(evidence / 'complete.json'), ds)
        files = {part: members(evidence / part / (ARM if part == 'predictions' else ''), set(ids))
                 for part in ('predictions', 'contexts', 'steps', 'prediction_events', 'feedback', 'reference_vault')}
        windows = sorted(path for path in (evidence / 'windows').iterdir() if path.is_dir())
        require(len(windows) == spec['windows']
                and read(windows[0] / 'read_snapshot.json').get('skills') == {}, 'empty_first_window_snapshot_required:' + ds)
        for row in inputs:
            for name in row['images']:
                image = (evidence / name).resolve()
                require(image.is_relative_to(ROOT.resolve()) and image.is_file(), 'published_original_image_missing:' + str(image))
        for name, compared in summary['arms'].items():
            require(compared['n'] == n, 'full_compared_denominator_required:' + ds + ':' + name)
        for name, comparison in summary['comparisons'].items():
            require(comparison['net'] == comparison['corrected'] - comparison['harmed']
                    and comparison['net'] == summary['arms'][ARM]['correct'] - summary['arms'][name]['correct'],
                    'saved_comparison_arithmetic:' + ds + ':' + name)
        require(summary['resources']['tools']['failed_or_unknown_tools'] == 0, 'healthy_full_generation_tools_required:' + ds)
        tools = summary['resources']['tools']
        require(tools['registered_failed_historical_attempts'] == tools['failed_backend_attempts'] == 2 * int(ds == 'chexbench')
                and tools['registered_cuda_failed_attempts'] == tools['registered_phrase_failed_attempts'] == int(ds == 'chexbench')
                and tools['unknown_backend_attempts'] == 0
                and tools['fresh_backend_attempts'] == tools['healthy_backend_attempts'] + tools['failed_backend_attempts'],
                'two_registered_CheX_historical_failures_and_all_physical_attempts_required:' + ds)
        meta_resource = summary['resources']['meta_schema_repair']
        require(meta_resource['registered'] is (ds == 'chexbench')
                and meta_resource['added_meta_requests'] == int(ds == 'chexbench')
                and meta_resource['included_in_R49_META_totals'] is True
                and meta_resource['automatic_invalid_to_none'] is False,
                'registered_META_schema_repair_metered_once_in_existing_META_total:' + ds)
        second = summary['resources']['meta_schema_repair_2']
        amendment = summary['resources']['mutation_fields_amendment']
        require(second['registered'] is (ds == 'chexbench') and second['added_meta_requests'] == int(ds == 'chexbench')
                and second['included_in_R49_META_totals'] is True and second['automatic_invalid_to_none'] is False
                and amendment['active'] is True and amendment['extra_ordinary_meta_calls'] == 0,
                'registered_second_repair_and_zero_extra_call_mutation_field_amendment_required:' + ds)
        embedding = summary['resources']['embedding']; embed_repair = summary['resources']['embedding_http_recovery']
        require(embedding['registered_http_failed_attempts'] == int(ds == 'chexbench')
                and embedding['requests'] == embedding['successful_responses'] + embedding['registered_http_failed_attempts']
                and embed_repair['registered'] is (ds == 'chexbench')
                and embed_repair['new_production_embedding_requests'] == int(ds == 'chexbench')
                and embed_repair['included_in_embedding_totals'] is True,
                'registered_failed_original_and_single_healthy_embedding_retry_metered_once:'+ds)
        phrase_retry = summary['resources']['phrase_guard_retry']; phrase_amendment = summary['resources']['phrase_guard_amendment']
        require(phrase_retry['registered'] is (ds == 'chexbench')
                and phrase_retry['guarded_production_retries'] == int(ds == 'chexbench')
                and phrase_retry['diagnostic_result_reused'] is False and phrase_retry['included_in_tools_totals'] is True
                and phrase_amendment['active'] is True,
                'registered_one_guarded_retry_and_all_three_actual_MAIRA_policy_amendments_required:'+ds)
        adoption = summary['resources']['adoption_repair']; analysis_unique = summary['resources']['analysis_unique_amendment']
        require(adoption['registered'] is (ds == 'chexbench') and adoption['added_meta_requests'] == 2 * int(ds == 'chexbench')
                and adoption['included_in_R49_META_totals'] is True and adoption['original_analysis_retained_for_mutation'] is True
                and adoption['assess_only_overlay'] is True
                and adoption['manual_selection'] is False and adoption['new_evidence_written'] is False
                and all(adoption[key] == 0 for key in ('extra_agent_calls', 'extra_embedding_calls', 'extra_tool_calls'))
                and analysis_unique['active'] is True and analysis_unique['extra_ordinary_meta_calls'] == 0,
                'two_known_assess_only_representative_choices_and_zero_extra_ordinary_analysis_calls_required:'+ds)
        bundles[ds] = dict(summary=summary, details=details, evidence=evidence, manifest=manifest,
                           inputs={row['question_id']: row for row in inputs}, files=files, windows=windows)
    return bundles


def utc(value):
    result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    require(result.tzinfo is not None, 'timestamp_timezone_required')
    return result.astimezone(timezone.utc)


def supplemental(ds, bundle):
    """Describe saved evidence; never extract answers, read labels, or score."""
    evidence = bundle['evidence']; s = bundle['summary']; clock_starts = []; clock_ends = []
    usage_unknown = Counter()
    for path in (evidence / 'services').rglob('result.json'):
        if not path.parent.joinpath('started.json').is_file():
            continue
        if 'calls' not in path.parts and 'embeddings' not in path.parts:
            continue
        receipt, started = read(path), read(path.parent / 'started.json')
        category = 'embedding' if 'embeddings' in path.parts else ('R49_META' if 'R49-META' in path.parts else 'agent')
        usage = receipt.get('usage')
        fields = ('total_tokens',) if category == 'embedding' else ('prompt_tokens', 'completion_tokens')
        usage_unknown[category] += not isinstance(usage, dict) or any(usage.get(field) is None for field in fields)
        if started.get('utc'):
            clock_starts.append(utc(started['utc']))
        if receipt.get('utc'):
            clock_ends.append(utc(receipt['utc']))
    span = (max(clock_ends) - min(clock_starts)).total_seconds() if clock_starts and clock_ends else None
    statuses, tool_names, same_image_sizes, selected_sizes = Counter(), Counter(), [], []
    fresh_tool_time_unknown = 0
    for qid, path in bundle['files']['predictions'].items():
        prediction = read(path); ctx = read(bundle['files']['contexts'][qid])
        statuses[str(prediction.get('status'))] += 1
        same_image_sizes.append(len(ctx['same_image_ids'])); selected_sizes.append(len(ctx['selected_skills']))
    for path in (evidence / 'services/tool_selections/R49-AGENT').glob('*/*.json'):
        tool = read(path)
        tool_names[tool['tool']] += 1
        fresh_tool_time_unknown += not tool.get('cache_hit') and tool.get('backend_compute_seconds') is None
    require(sum(tool_names.values()) == s['resources']['tools']['logical_calls'], 'exported_tool_selection_count:' + ds)
    history = []
    for window in bundle['windows']:
        events, repo = read(window / 'events.json'), read(window / 'repo.json')
        history.append({'window': int(window.name), 'write_events': len(events['write']),
                        'write_operations': dict(Counter(str(e.get('operation', 'rejected_or_none')) for e in events['write'])),
                        'adoption_credit_events': len(events['credit']),
                        'adoption_statuses': dict(Counter(e['status'] for e in events['credit'])),
                        'governance': events['govern'], 'skill_status_counts': dict(Counter(m['status'] for m in repo['skills'].values()))})
    final = read(evidence / 'final_repo.json')
    skills = {sid: {'name': value['c']['name'], 'branch': value['c']['branch'], 'status': value['status'],
                    'utility': value['u'], 'usage': value['usage'], 'source_ids': value['source_ids'],
                    'prior_versions': len(value['versions'])} for sid, value in final['skills'].items()}
    return {'terminal_status_counts': dict(statuses), 'tool_selections_by_name': dict(tool_names),
            'max_same_image_context_entries': max(same_image_sizes, default=0),
            'max_selected_skills': max(selected_sizes, default=0), 'lifecycle_by_window': history,
            'receipt_usage_unknown_count': {key: usage_unknown[key] for key in ('agent', 'R49_META', 'embedding')},
            'active_selection_backend_time_unknown_count': fresh_tool_time_unknown,
            'fresh_tool_backend_time_unknown_count': s['resources']['tools']['backend_compute_unknown_count'],
            'final_skill_lineage': skills, 'recorded_request_span_seconds': span,
            'recorded_request_span_scope': 'Earliest recorded main/meta/embedding send to latest recorded reply; includes gaps, excludes unrecorded startup/finalization/GPU wait. Not controller or full generation wall.',
            'whole_generation_wall_seconds': None, 'controller_wall_seconds': None,
            'unrecorded_wall_times_not_inferred': True,
            'failure_record_files': [p.relative_to(evidence).as_posix() for p in evidence.rglob('*')
                                     if p.is_file() and any(part in ('failure_events', 'failure.json', 'failures.json', 'generation_failure.json', 'generation_failure_history.json') for part in p.relative_to(evidence).parts)]}


def probe(preparation):
    assessment = read(Path(preparation) / 'embedding_probe/assessment.json')
    require(assessment.get('status') == 'healthy' and assessment.get('requested_model') == 'text-embedding-v4'
            and assessment.get('returned_model') == 'text-embedding-v4'
            and assessment.get('dimensions') == 1024 and assessment.get('finite') is True
            and assessment.get('usage', {}).get('total_tokens') == 13
            and assessment.get('main_calls') == 0, 'actual_single_preexecution_embedding_probe_required')
    return {'assessment': assessment, 'scope': 'One endpoint compatibility probe, counted once outside three stream resources; no medical case.',
            'known_total_tokens': 13, 'requests': 1, 'usage_cost_cny_proxy_known': None,
            'cost_unknown_count': 1, 'provider_invoice': False, 'medical_quality_validation': False}


def offline_scoring_provenance(archive, preparation, receipt_root, public_root, bundles):
    """Bind already saved scores to their receipts; never invoke a scorer.

    Public files are explicit root-prepared copies of known control records.
    Their JSON values are compared semantically, without file/image digests.
    No input, reference, Skill, response or answer is extracted here.
    """
    archive, receipt_root, preparation = map(Path, (archive, receipt_root, preparation))
    public_root = Path(public_root).resolve()
    require(public_root.is_relative_to(REPORT.resolve()) and public_root.is_dir(), 'actual_public_reporting_provenance_directory_required')
    files = []

    def paired(source, relative):
        source, public = Path(source), public_root/relative
        value = read(source)
        require(read(public) == value, 'published_reporting_receipt_must_match_actual_control_record:'+relative)
        files.append({'private_source': str(source.resolve()), 'public': in_report(public)})
        return value

    authorization = paired(preparation/'DATASET_COMPLETION_REPORTING_AUTHORIZATION.json', 'DATASET_COMPLETION_REPORTING_AUTHORIZATION.json')
    require(authorization.get('enabled') is True and authorization.get('confirmation_source') == 'explicit_user_reply'
            and authorization.get('exact_user_reply') == '848题是这个三个数据集吧，可以做完一个数据集汇报一个数据集的准确率等成果'
            and authorization.get('datasets') == {ds: SPEC[ds]['n'] for ds in DATASETS}
            and authorization.get('report_on_each_dataset_completion') is True
            and authorization.get('partial_dataset_scoring_allowed') is False
            and authorization.get('reuse_saved_dataset_scores_at_finalization') is True
            and authorization.get('future_inference_tuned_from_report') is False
            and authorization.get('final_all_three_exit_zero_gate_unchanged') is True,
            'actual_completed_dataset_reporting_authorization_without_future_tuning_required')
    records = {}
    for ds in DATASETS:
        receipt = paired(receipt_root/(ds+'.json'), 'score_receipts/'+ds+'.json')
        started = paired(receipt_root/(ds+'.started.json'), 'score_receipts/'+ds+'.started.json')
        identity = receipt.get('identity', {}); n = SPEC[ds]['n']; failed = int(ds == 'chexbench')
        require(receipt.get('schema') == 'r49_completed_dataset_score_receipt_v1' and receipt.get('status') == 'completed'
                and receipt.get('native_score_invocations') == 1+failed
                and receipt.get('completed_metric_calculations') == 1 and receipt.get('pre_adaptation_failed_invocations') == failed
                and receipt.get('new_inference_calls') == 0 and receipt.get('references_read_after_all_arms_adapted') is True
                and receipt.get('later_dataset_policy_frozen_do_not_tune_from_interim_scores') is True
                and receipt.get('summary_snapshot') == bundles[ds]['summary']
                and receipt.get('scored_question_ids') == [row['question_id'] for row in bundles[ds]['details']]
                and receipt.get('questions') == n and identity.get('dataset') == ds,
                'saved_completed_metric_must_match_exact_once_receipt_not_be_recomputed:'+ds)
        expected_paths = {'run': archive/'generation'/ds, 'jobs': archive/'jobs',
                          'runner_exit': archive/'recovery/adoption_1'/(ds+'.exitcode'), 'out': REPORT/'results'/ds}
        require(all(Path(identity[key]).resolve() == path.resolve() for key, path in expected_paths.items()),
                'score_receipt_must_bind_final_immutable_mirror_and_existing_output:'+ds)
        exits = receipt.get('actual_raw_exit_records', [])
        expected_exits = {str(path.resolve()) for path in (archive/'generation'/ds/'generation.exitcode',
                          archive/'jobs'/(ds+'.exitcode'), archive/'recovery/adoption_1'/(ds+'.exitcode'))}
        require(len(exits) == 3 and {str(Path(item['path']).resolve()) for item in exits} == expected_exits
                and all(item.get('raw_exit') == 0 for item in exits), 'actual_three_closed_dataset_exit_records_required:'+ds)
        pull = paired(archive/'dataset_completion'/ds/'PULL_RECEIPT.json', 'dataset_completion/'+ds+'/PULL_RECEIPT.json')
        require(pull.get('status') == 'complete_immutable_dataset_pulled' and pull.get('dataset') == ds
                and pull.get('questions') == n and Path(pull['archive']).resolve() == archive.resolve()
                and pull.get('references_parsed') is False and pull.get('completion_marker_body_parsed') is False
                and pull.get('other_dataset_predictions_pulled') is False
                and pull.get('final_pull_must_preserve_this_generation_directory') is True,
                'actual_finished_dataset_pull_before_isolated_native_score_required:'+ds)
        records[ds] = {'questions': n, 'identity': identity, 'native_score_invocations': 1+failed,
                       'completed_metric_calculations': 1, 'pre_adaptation_failed_invocations': failed,
                       'scoring_started_at': receipt.get('started_at'), 'scoring_completed_at': receipt.get('completed_at'),
                       'score_receipt': in_report(public_root/'score_receipts'/(ds+'.json')),
                       'dataset_pull_receipt': in_report(public_root/'dataset_completion'/ds/'PULL_RECEIPT.json'),
                       'original_started_receipt': in_report(public_root/'score_receipts'/(ds+'.started.json')),
                       'saved_score_outputs_reused': ['results/'+ds+'/summary.json', 'results/'+ds+'/per_question.json'],
                       'new_inference_calls': 0, 'metrics_recomputed_by_writer': False}
        if ds != 'chexbench':
            require(started.get('schema') == 'r49_dataset_score_started_v1' and started.get('identity') == identity
                    and started.get('new_inference_calls') == 0, 'actual_single_normal_score_started_record_required:'+ds)
            continue
        failure = paired(receipt_root/'chexbench.pre_adaptation_failure_001.json', 'score_receipts/chexbench.pre_adaptation_failure_001.json')
        resume = paired(receipt_root/'chexbench.pre_adaptation_resume_001.started.json', 'score_receipts/chexbench.pre_adaptation_resume_001.started.json')
        source = paired(archive/'dataset_completion/chexbench/SOURCE_INPUT_PULL_RECEIPT.json', 'dataset_completion/chexbench/SOURCE_INPUT_PULL_RECEIPT.json')
        proof = receipt.get('pre_adaptation_recovery', {})
        require(proof.get('schema') == 'r49_fixed_chexbench_pre_adaptation_recovery_v1'
                and proof.get('original_started_record') == started and proof.get('failure_metadata') == failure
                and proof.get('source_pull_receipt') == source and resume.get('pre_adaptation_recovery') == proof
                and resume.get('identity') == identity and resume.get('explicit_pre_adaptation_resume') is True
                and resume.get('native_score_attempt_ordinal') == 2 and resume.get('automatic_retry') is False,
                'actual_one_explicit_named_pre_adaptation_resume_and_original_proof_must_remain')
        require(failure.get('schema') == 'r49_dataset_score_pre_adaptation_failure_v1' and failure.get('actual_cli_exit') == 1
                and failure.get('exec_chunk_id') == 'e005ad' and failure.get('exception_message') == 'manifest_semantic_input_order_changed'
                and failure.get('all_arm_adaptation_executed') is False
                and failure.get('references_or_feedback_or_complete_body_opened') is False
                and failure.get('result_directory_exists') is False and failure.get('completed_score_receipt_exists') is False
                and failure.get('native_scorer_or_metrics_modified') is False and failure.get('original_started_receipt_retained') is True,
                'first_offline_input_path_failure_must_not_be_misreported_as_a_metric_calculation')
        require(source.get('schema') == 'r49_canonical_input_source_pull_v1' and source.get('status') == 'canonical_input_copied_and_manifest_equal'
                and source.get('questions') == 618 and source.get('manifest_inputs_equal') is True and source.get('manifest_order_equal') is True
                and source.get('references_parsed') is False and source.get('model_api_calls') == 0 and source.get('hashes_computed') is False
                and source.get('generation_or_predictions_modified') is False
                and proof.get('canonical_inputs_equal_manifest') is True and proof.get('canonical_order_equal_manifest') is True
                and proof.get('all_other_input_fields_equal') is True and proof.get('changed_field_counts') == {'images': 618}
                and proof.get('original_records_overwritten_or_deleted') is False and proof.get('native_gate_or_adaptation_modified') is False,
                'exact_canonical_source_path_repair_without_scorer_relaxation_or_new_inference_required')
        require(Path(identity['data']).resolve() == Path(source['local_data']).resolve()
                and {key: value for key, value in started['identity'].items() if key != 'data'} ==
                    {key: value for key, value in identity.items() if key != 'data'},
                'known_offline_resume_must_change_only_the_input_data_directory')
        records[ds]['pre_adaptation_recovery'] = {'first_cli_exit': 1, 'first_failure_before_all_arm_adaptation_and_labels': True,
            'old_data': started['identity']['data'], 'actual_canonical_data': identity['data'],
            'remote_canonical_input_source': source['remote_source'], 'source_pull_receipt': in_report(public_root/'dataset_completion/chexbench/SOURCE_INPUT_PULL_RECEIPT.json'),
            'failure_metadata': in_report(public_root/'score_receipts/chexbench.pre_adaptation_failure_001.json'),
            'explicit_resume_started': in_report(public_root/'score_receipts/chexbench.pre_adaptation_resume_001.started.json'),
            'changed_input_field_counts': proof['changed_field_counts'], 'new_inference_calls': 0,
            'native_scorer_metrics_or_adaptation_modified': False, 'completed_metric_calculations': 1}
    final_controls = paired(archive/'dataset_completion/FINAL_CONTROL_PULL_RECEIPT.json', 'dataset_completion/FINAL_CONTROL_PULL_RECEIPT.json')
    require(final_controls.get('status') == 'final_controls_pulled' and final_controls.get('generation_directories_skipped') == list(DATASETS)
            and final_controls.get('scores_invoked') is False and final_controls.get('result_files_overwritten') is False,
            'final_control_transfer_must_preserve_all_already_scored_generation_and_results')
    actual_source = paired(archive/'actual_code_source/source_completed.json', 'supplemental_receipts/source_completed.json')
    captures = paired(archive/'supplemental_receipts/local_captures_completed.json', 'supplemental_receipts/local_captures_completed.json')
    require(actual_source.get('status') == 'actual_code_source_copied' and actual_source.get('remote_execution') is False
            and actual_source.get('model_api_calls') == 0 and actual_source.get('byte_or_pixel_or_hash_checks') is False
            and captures.get('status') == 'known_local_captures_preserved' and captures.get('remote_requests') == 0
            and captures.get('generation_writes') is False and captures.get('capture_or_diagnostic_reexecuted') is False,
            'actual_source_and_prior_capture_preservation_receipts_required_without_reexecuting_diagnostics')
    return {'datasets': records, 'files': files, 'public_proof_root': public_root.relative_to(REPORT.resolve()).as_posix(),
            'total_native_score_function_entries': sum(item['native_score_invocations'] for item in records.values()),
            'completed_metric_calculations': sum(item['completed_metric_calculations'] for item in records.values()),
            'pre_adaptation_failed_invocations': sum(item['pre_adaptation_failed_invocations'] for item in records.values()),
            'actual_deployed_source_file_count': len(actual_source.get('files', [])),
            'known_local_captures_copied': len(captures.get('copied_missing', [])),
            'known_local_captures_preserved_without_overwrite': len(captures.get('existing_preserved_without_reading_or_overwriting', [])),
            'native_metric_function_and_public_scorer_unchanged': True, 'all_private_score_outputs_reused': True,
            'scores_or_inference_reexecuted_by_writer': False, 'final_audit_must_cover_reporting_and_source_path_resume': True,
            'image_or_file_digests_checked': False}


def recorded_scoring_sources(actual, provenance):
    """Report the real source paths, including CheX's separate references file."""
    actual = dict(actual)
    for ds in DATASETS:
        identity = provenance['datasets'][ds]['identity']
        for field, identity_key in (('data', 'data'), ('references', 'references')):
            key = ds+'_'+field; recorded = identity[identity_key]
            require(actual.get(key) is None or Path(actual[key]).resolve() == Path(recorded).resolve(),
                    'explicit_report_source_must_match_completed_score_receipt:'+key)
            actual[key] = recorded
    return actual


def make_offline_scoring_provenance(provenance):
    rows = [[SPEC[ds]['label'], (record := provenance['datasets'][ds])['questions'],
             record['native_score_invocations'], record['completed_metric_calculations'], record['pre_adaptation_failed_invocations'],
             link('实际score receipt', record['score_receipt']), link('完成组pull', record['dataset_pull_receipt'])] for ds in DATASETS]
    chex = provenance['datasets']['chexbench']['pre_adaptation_recovery']
    sources = [[SPEC[ds]['label'], item['identity']['data'], item['identity']['references']]
               for ds, item in provenance['datasets'].items()]
    return f'''# R49 已保存离线评分、原始失败与来源路径

{table(['数据集', '完整题数', '进入原生评分函数次数', '完整指标计算次数', '适配／标签前失败次数', '实际评分凭证', '完成组拉取凭证'], rows)}

三组保存的summary／per_question原样复用，报告编写器没有再次评分、生成答案或调用模型。公开语义独立重算单列，不冒充第二次私有指标计算。逐数据集完整结束后先报告结果的授权和原始时点标志保持；后续组的模型、提示、顺序和规则未据这些结果调整。

CheX第一次进入原生评分函数时，既有公开输入的images路径为`assets/...`，实际运行清单使用`images/...`。原严格completed_gate以manifest_semantic_input_order_changed拒绝，在ALL-arm适配、参考／feedback／complete正文读取之前退出1，没有指标或结果目录。原始started与[故障元数据]({chex['failure_metadata']})保留；没有删除started或把第一次改写为成功。

随后从实际原数据源`{chex['remote_canonical_input_source']}`只复制一次原始inputs，题号／顺序／题干／选项／image_id等保持，618条只有images字段的路径来源不同。记录于[canonical源拉取凭证]({chex['source_pull_receipt']})。独立private wrapper只为这一个已知前置失败执行一次显式接续，保留[新attempt2 started]({chex['explicit_resume_started']})；没有放宽原生gate、适配器、答案解析或指标，也没有新推理、改预测、读真值挑答案或选择有利成绩。故CheX是两次函数进入、一次完整指标计算；SLAKE／VQA各一次。三组共{provenance['total_native_score_function_entries']}次函数进入、{provenance['completed_metric_calculations']}次完整指标计算、{provenance['pre_adaptation_failed_invocations']}次适配前失败，不把失败算作又一套成绩。

{table(['数据集', '实际成功评分的input目录', '实际独立references文件'], sources)}

这些私有路径是已发生步骤的来源记录；公开复现使用各组evidence和verify_public接口，不需要本机或服务器私有目录。CheX修正后input目录只提供canonical inputs，references仍为原独立文件；不能从input目录猜测references路径。

后续最终控制拉取跳过所有已评分GEN及结果，补齐现有jobs／configs／恢复历史。实际部署源码保存{provenance['actual_deployed_source_file_count']}个记录；既有诊断／故障捕获补存{provenance['known_local_captures_copied']}份、保留未覆盖{provenance['known_local_captures_preserved_without_overwrite']}份。它们不重启任何诊断、模型或实验，不构成源码字节鉴证。所有原始控制凭证见下列明确清单，JSON语义核对未使用文件／像素摘要。

{table(['已保留公开控制记录', '对应私有来源（历史路径）'], [[link(item['public'], item['public']), item['private_source']] for item in provenance['files']])}

本页是来源与尝试次数说明，不代替实际完整结果审阅。最终审阅仍须覆盖逐数据集报告、这次来源路径前置失败／接续、请求账以及全部正负结果，不以增分或正向结论为前提。
'''


def dependency_recovery(archive, public_root, raw_review, metadata_review, bundle, *, continued_by_cuda=False):
    """Require preserved initial failure, the reviewed repair and final RAW zeros.

    No null terminal or effective-exit mechanism is accepted. The first saved
    prediction was already final before the missing local reward import failed;
    its three requests remain included ONCE in normal CheX resource totals.
    """
    private = Path(archive)/'recovery/dependency_1'; public_root = Path(public_root).resolve()
    require(public_root.is_relative_to(REPORT.resolve()) and public_root.is_dir(), 'portable_dependency_recovery_tree_required')
    public_rel = public_root.relative_to(REPORT.resolve()).as_posix()
    proof = {}
    for label, root in [('private', private), ('published', public_root)]:
        initial = root/'original'
        for name in ('controller.exitcode', 'chexbench.exitcode', 'generation.exitcode'):
            require((initial/name).read_text(encoding='utf-8-sig').strip() == '1', 'initial_dependency_raw_exit1_must_be_preserved:'+label+':'+name)
        tail = (initial/'chexbench.log').read_text(encoding='utf-8-sig', errors='replace').strip().splitlines()
        require(tail and tail[-1] == "ModuleNotFoundError: No module named 'cxr_author_alignment'", 'exact_initial_missing_dependency_evidence_required:'+label)
        initial_controller = (initial/'controller.pid').read_text(encoding='utf-8-sig').strip()
        initial_child = (initial/'chexbench.pid').read_text(encoding='utf-8-sig').strip()
        require(initial_controller == '2277353' and initial_child == '2277359', 'actual_initial_dependency_attempt_identity:'+label)
        ready = read(root/'REVIEW_READY.json'); diagnosis = read(root/'diagnosis.json')
        require(ready.get('verdict') == 'ready' and ready.get('scope_complete') is True, 'actual_dependency_delta_review_readiness:'+label)
        require(diagnosis.get('repair') == 'missing_deployed_cxr_author_alignment_only'
                and diagnosis.get('original_controller_exit') == diagnosis.get('original_chexbench_exit') == 1
                and diagnosis.get('committed_question_id') == 'chexbench_rad_restruct_0123'
                and diagnosis.get('committed_predictions') == diagnosis.get('released_feedback_events') == 1
                and diagnosis.get('closed_main_requests') == 3 and diagnosis.get('healthy_tool_selections') == 2
                and diagnosis.get('prediction_rewrites') == diagnosis.get('new_reference_reads_for_repair') == 0
                and diagnosis.get('runtime_policy_changed') is False
                and diagnosis.get('unknown_requests_reissued') is False and diagnosis.get('automatic_failure_nulls') is False,
                'known_local_postcommit_dependency_repair_only:'+label)
        for name in (('controller', 'chexbench') if continued_by_cuda else ('controller', *DATASETS)):
            expected_exit = '1' if continued_by_cuda else '0'
            require((root/(name+'.exitcode')).read_text(encoding='utf-8-sig').strip() == expected_exit,
                    'actual_intermediate_dependency_or_final_runner_exit_required:'+label+':'+name)
        proof[label] = {'initial_controller_pid': initial_controller, 'initial_chexbench_pid': initial_child,
                        'initial_controller_exit': 1, 'initial_chexbench_exit': 1, 'initial_generation_exit': 1,
                        'diagnosis': diagnosis, 'dependency_continuation_controller_exit': 1 if continued_by_cuda else 0,
                        'dependency_continuation_runner_exits': {'chexbench': 1} if continued_by_cuda else {ds: 0 for ds in DATASETS},
                        'continued_by_registered_cuda_recovery': continued_by_cuda}
    raw_review, metadata_review = Path(raw_review), Path(metadata_review)
    review_files = {'raw': in_report(raw_review), 'metadata': in_report(metadata_review),
                    'explanation': in_report(REPORT/'DEPENDENCY_RECOVERY.md')}
    meta = read(metadata_review)
    require(meta.get('status') == 'completed' and meta.get('modelUsage') and meta.get('duration_ms', 0) > 0
            and meta.get('session_id') and any('deepseek' in name.lower() for name in meta['modelUsage'])
            and len(raw_review.read_text(encoding='utf-8-sig').strip()) > 20,
            'actual_DeepSeek_dependency_delta_review_required')
    qid = 'chexbench_rad_restruct_0123'; evidence = bundle['evidence']
    pred = read(bundle['files']['predictions'][qid]); event = read(bundle['files']['prediction_events'][qid])
    feedback = read(bundle['files']['feedback'][qid])
    require(pred.get('ordinal') == 1 and pred.get('main_calls') == 3 and pred.get('tool_calls') == 2
            and event.get('saved_prediction') == pred and feedback.get('saved_prediction') == pred,
            'first_committed_prediction_not_replaced_after_dependency_repair')
    folder = evidence/'services/calls/R49-AGENT'/qid
    calls = sorted(path for path in folder.iterdir() if path.is_dir())
    require([path.name for path in calls] == ['1', '2', '3'], 'first_question_must_have_original_three_calls_only')
    receipts = []
    for call in calls:
        require(all((call/name).is_file() for name in ('request.json', 'started.json', 'response.json', 'result.json')),
                'initial_main_request_must_be_closed:'+str(call))
        receipt = read(call/'result.json')
        require(receipt.get('response_received') is True and not receipt.get('error'), 'initial_main_request_not_healthy')
        receipts.append(receipt)
    initial_tools = list((evidence/'services/tool_selections/R49-AGENT'/qid).glob('*.json'))
    require(len(initial_tools) == 2, 'initial_two_healthy_tool_selections_must_not_be_reissued')
    cost_known = [Decimal(str(r['settlement']['charged_cny'])) for r in receipts
                  if r.get('settlement', {}).get('charged_cny') is not None]
    return {'repair': 'missing deployed cxr_author_alignment dependency after q1 immutable prediction/event/feedback',
            'public_tree': public_rel, 'proof': proof, 'review_files': review_files, 'review_metadata': meta,
            'first_question': qid, 'first_question_prediction_and_reference_not_reexecuted': True,
            'first_question_closed_main_requests': 3, 'first_question_healthy_tools': 2,
            'first_question_main_usage_cost_cny_known': str(sum(cost_known, Decimal(0))),
            'first_question_main_cost_unknown_count': len(receipts)-len(cost_known),
            'first_question_main_elapsed_seconds_known': sum(r.get('elapsed_s') or 0 for r in receipts),
            'first_question_main_elapsed_unknown_count': sum(r.get('elapsed_s') is None for r in receipts),
            'cost_and_time_accounting': 'Initial three main requests and two tools already included exactly once in CheX scorer totals; no additive duplicate cost. Repair-review CLI USD separate, not invoice.',
            'initial_failure_wall_seconds': None, 'dependency_repair_wall_seconds': None,
            'unrecorded_failure_and_repair_wall_times_not_inferred': True,
            'runtime_policy_or_strategy_changed': False, 'technical_null_amendment': False,
            'all_attempts_exited_zero_claim': False, 'R48_recovered': False}


def public_asset_semantics(value, document, evidence):
    """Normalize exported relative image metadata; never inspect image bytes."""
    import os
    assets = read(evidence/'image_assets.json')
    aliases = [(os.path.relpath((evidence/item['path']).resolve(), Path(document).parent).replace('\\', '/'),
                'PUBLIC_ASSET:'+str(index)) for index, item in enumerate(assets)]
    def normalize(item):
        if isinstance(item, dict):
            return {key: normalize(child) for key, child in item.items()}
        if isinstance(item, list):
            return [normalize(child) for child in item]
        if isinstance(item, str):
            for old, new in sorted(aliases, key=lambda pair: -len(pair[0])):
                item = item.replace(old, new)
        return item
    return normalize(value)


def cuda_recovery(archive, public_root, raw_review, metadata_review, bundle, *, continued_by_meta_schema=False):
    """Future read-only validation of the one registered production CUDA retry."""
    import sys
    experiments = str(ROOT/'experiments')
    if experiments not in sys.path:
        sys.path.insert(0, experiments)
    # This validator reads closed tool evidence only; it does not score, invoke
    # a tool/API, or open current/future labels. Import occurs only when the
    # report writer is deliberately run AFTER all streams and scoring complete.
    from score_online_skill_r49 import registered_cuda_retry
    run = Path(archive)/'generation/chexbench'; private = Path(archive)/'recovery/cuda_1'
    checked = registered_cuda_retry(run)
    require(checked is not None, 'actual_one_closed_failed_and_healthy_registered_retry_required')
    registration = checked['registration']; old = checked['original_result']; healthy = checked['retry_result']
    public_root = Path(public_root).resolve()
    require(public_root.is_relative_to(REPORT.resolve()) and public_root.is_dir(), 'portable_cuda_recovery_tree_required')
    public_rel = public_root.relative_to(REPORT.resolve()).as_posix()
    proof = {}
    for label, root in [('private', private), ('published', public_root)]:
        for path in (root/'prior_generation.exitcode', root/'prior_jobs/controller.exitcode', root/'prior_jobs/chexbench.exitcode'):
            require(path.read_text(encoding='utf-8-sig').strip() == '1', 'prior_cuda_raw_failure_exit1_required:'+label+':'+path.name)
        for name in (('controller', 'chexbench') if continued_by_meta_schema else ('controller', *DATASETS)):
            expected_exit = '1' if continued_by_meta_schema else '0'
            require((root/(name+'.exitcode')).read_text(encoding='utf-8-sig').strip() == expected_exit,
                    'actual_intermediate_CUDA_or_final_runner_exit_required:'+label+':'+name)
        ready, scope, plan = read(root/'REVIEW_READY.json'), read(root/'SCOPE.json'), read(root/'plan.json')
        require(ready.get('verdict') == 'ready' and ready.get('scope_complete') is True
                and ready.get('recovery_id') == 'cuda_1' and ready.get('trace'), 'actual_cuda_operational_review_ready_required:'+label)
        require(scope.get('production_tool_retry_limit') == 1 and scope.get('new_diagnostic_invocations') == 0
                and scope.get('retry_current_question_main_plan') is False
                and scope.get('technical_null_fill') is False and scope.get('modify_completed_predictions') is False
                and scope.get('diagnostic_result_reused') is False
                and plan.get('main_plan_reissue') is False and plan.get('technical_null_fill') is False
                and plan.get('runtime_source_files_edited') is False,
                'exact_one_retry_scope_no_unknown_main_or_prediction_reissue:'+label)
        diagnostic = read(root/'diagnostic_evidence/status.json')
        require(diagnostic.get('status') == 'completed_healthy' and diagnostic.get('tool_invocations') == 1
                and all(diagnostic.get(key) == 0 for key in ('main_api_calls', 'meta_api_calls', 'embedding_api_calls'))
                and diagnostic.get('elapsed_s') == registration['diagnostic']['elapsed_s']
                and (root/'diagnostic_evidence/exitcode').read_text(encoding='utf-8-sig').strip() == '0',
                'actual_isolated_zero_API_diagnostic_never_used_as_production_result:'+label)
        for name in ('controller.py', 'resume_runner.py', 'original_selection.json', 'registration.json'):
            require((root/name).is_file() and (root/name).stat().st_size > 0, 'actual_cuda_recovery_source_or_record:'+label+':'+name)
        proof[label] = {'prior_controller_raw_exit': 1, 'prior_chexbench_raw_exit': 1, 'prior_generation_raw_exit': 1,
                        'cuda_continuation_controller_raw_exit': 1 if continued_by_meta_schema else 0,
                        'cuda_continuation_children_raw_exit': {'chexbench': 1} if continued_by_meta_schema else {ds: 0 for ds in DATASETS},
                        'continued_by_registered_meta_schema_recovery': continued_by_meta_schema,
                        'scope': scope, 'plan': plan, 'isolated_diagnostic_status': diagnostic}
    require(read(private/'registration.json') == registration
            and read(private/'original_selection.json') == registration['original_selection'],
            'private_shared_and_GEN_cuda_registrations_must_agree')
    evidence = bundle['evidence']; gen_path = evidence/'failure_events/cuda_1_registration.json'
    global_path = public_root/'registration.json'; archived_path = public_root/'original_selection.json'
    gen = public_asset_semantics(read(gen_path), gen_path, evidence)
    shared = public_asset_semantics(read(global_path), global_path, evidence)
    original = public_asset_semantics(read(archived_path), archived_path, evidence)
    archive_path = evidence/'failure_events/cuda_1_original_selection.json'
    require(gen == shared and gen.get('original_selection') == original
            and public_asset_semantics(read(archive_path), archive_path, evidence) == original,
            'published_shared_GEN_and_original_cuda_records_must_agree_semantically')
    active_path = evidence/'services/tool_selections/R49-AGENT'/registration['question_id']/'1.json'
    require(public_asset_semantics(read(active_path), active_path, evidence) == gen['retry_selection'],
            'published_registered_healthy_retry_must_be_active')
    for key in (registration['original_cache_key'], registration['retry_cache_key']):
        require(all((evidence/'services/tool_cache'/key/name).is_file() for name in ('started.json', 'result.json')),
                'published_old_failed_and_new_healthy_cache_must_both_be_closed')
    review_files = {'raw': in_report(raw_review), 'metadata': in_report(metadata_review),
                    'explanation': in_report(REPORT/'CUDA_PRODUCTION_RECOVERY.md'),
                    'helper': in_report(REPORT/'deployment_source/recover_cxr_online_skill_r49_cuda.py')}
    meta = read(metadata_review)
    require(meta.get('status') == 'completed' and not meta.get('is_error') and meta.get('session_id')
            and meta.get('modelUsage') and meta.get('duration_ms', 0) > 0 and meta.get('turns', 0) > 0
            and any('deepseek' in name.lower() for name in meta['modelUsage'])
            and len(Path(raw_review).read_text(encoding='utf-8-sig').strip()) > 20,
            'actual_selected_DeepSeek_cuda_operational_review_required')
    manifest = bundle['manifest']; qid = registration['question_id']
    require(manifest['inputs'][40]['question_id'] == qid, 'registered_q41_identity_required')
    failed_utc = utc(old['utc'])
    for row in manifest['inputs'][:40]:
        prediction = read(bundle['files']['predictions'][row['question_id']])
        require(utc(prediction['prediction_saved_at']) <= failed_utc, 'first40_saved_before_cuda_failure_must_be_preserved')
    call = evidence/'services/calls/R49-AGENT'/qid/'1'; started, receipt = read(call/'started.json'), read(call/'result.json')
    require(receipt.get('response_received') is True and not receipt.get('error')
            and utc(started['utc']) <= utc(receipt['utc']) <= failed_utc,
            'original_q41_plan_must_remain_closed_before_original_tool_failure')
    tool_resource = bundle['summary']['resources']['tools']
    diagnostic_resource = bundle['summary']['resources']['isolated_cuda_diagnostic']
    require(tool_resource['registered_failed_historical_attempts'] == tool_resource['failed_backend_attempts'] == 2
            and tool_resource['fresh_backend_attempts'] == tool_resource['healthy_backend_attempts']+2
            and tool_resource['unknown_backend_attempts'] == tool_resource['failed_or_unknown_tools'] == 0
            and diagnostic_resource['tool_invocations'] == 1 and diagnostic_resource['elapsed_s'] == registration['diagnostic']['elapsed_s']
            and diagnostic_resource['included_in_production_attempts'] is False
            and diagnostic_resource['result_reused_in_R49'] is False,
            'physical_failure_retry_and_separate_diagnostic_accounting_required')
    old_known_cost = receipt.get('settlement', {}).get('charged_cny')
    return {'recovery_id': 'cuda_1', 'public_tree': public_rel, 'proof': proof,
            'review_files': review_files, 'review_metadata': meta, 'registration': registration,
            'question_id': qid, 'question_ordinal': 41, 'preserved_completed_prefix_questions': 40,
            'known_q41_main_plan_before_failure_requests': 1, 'known_q41_plan_usage_cost_cny_proxy': old_known_cost,
            'known_q41_plan_cost_unknown_count': int(old_known_cost is None),
            'known_q41_plan_elapsed_seconds': receipt.get('elapsed_s'),
            'q41_plan_cost_already_in_agent_totals_once': True,
            'original_failed_attempt': old, 'healthy_production_retry': healthy,
            'isolated_diagnostic': diagnostic_resource,
            'main_requests_not_reissued': True, 'first40_predictions_not_regenerated': True,
            'diagnostic_result_reused_in_production': False, 'technical_nulls_inserted': False,
            'operational_cache_resolution_amendment': 'One original-settings production retry and exact registered backend/revision/original-path/args cache overlay.',
            'frozen_eight_inference_source_files_edited': False,
            'root_cause_fixed_claim': False, 'all_attempts_exited_zero_claim': False,
            'cost_scope': 'The original failed production tool attempt and healthy retry are already counted once in physical production totals. Diagnostic is separate; original q41 main request remains included once in agent totals.',
            'cuda_stop_and_repair_wall_seconds': None, 'unpriced_hardware_cost': None}


def meta_schema_recovery(archive, public_root, raw_review, metadata_review, bundle, explanation=None,
                         *, continued_by_mutation_fields=False):
    """Future-only proof of one fresh, same-payload META schema clarification."""
    import sys
    experiments = str(ROOT/'experiments')
    if experiments not in sys.path:
        sys.path.insert(0, experiments)
    from score_online_skill_r49 import registered_meta_schema_repair
    run = Path(archive)/'generation/chexbench'; private = Path(archive)/'recovery/meta_schema_1'
    require(registered_meta_schema_repair(run) is not None, 'actual_registered_one_META_schema_repair_required')
    registration = read(run/'failure_events/meta_schema_1_registration.json')
    expected = {'schema': 'r49_registered_meta_schema_repair_v1', 'recovery_id': 'meta_schema_1',
                'dataset': 'chexbench', 'arm': ARM, 'source_question_id': 'chexbench_slake_0004',
                'source_event': 'mutation_chexbench_slake_0004',
                'repair_event': 'mutation_chexbench_slake_0004_schema_1', 'window_index': 3,
                'same_original_payload': True, 'new_meta_calls': 1, 'extra_agent_calls': 0,
                'extra_embedding_calls': 0, 'extra_tool_calls': 0,
                'automatic_invalid_to_none': False, 'new_clinical_information': False,
                'status': 'valid_meta_schema_repair_registered'}
    require(all(registration.get(key) == value for key, value in expected.items()), 'only_known_one_case_META_schema_repair_supported')
    target = registration['target_skill_id']; old_control = registration['original_control']; new_control = registration['repair_control']
    require(target and old_control == {'operation': 'PATCH', 'patch_section': 'c', 'patch_target_id': target},
            'only_original_whole_container_patch_failure_supported')
    allowed = {'name', 'description', 'applicable_conditions', 'required_tools', 'risk_level', 'core_action'}
    require(new_control.get('operation') == 'NONE' or
            (new_control.get('operation') == 'PATCH' and new_control.get('patch_target_id') == target
             and new_control.get('patch_section') in allowed), 'actual_valid_PATCH_or_model_selected_NONE_required')
    public_root = Path(public_root).resolve()
    require(public_root.is_relative_to(REPORT.resolve()) and public_root.is_dir(), 'portable_META_schema_recovery_tree_required')
    public_rel = public_root.relative_to(REPORT.resolve()).as_posix(); proof = {}
    for label, root in [('private', private), ('published', public_root)]:
        for path in (root/'prior_generation.exitcode', root/'prior_jobs/controller.exitcode', root/'prior_jobs/chexbench.exitcode'):
            require(path.read_text(encoding='utf-8-sig').strip() == '1', 'prior_META_schema_failure_exit1_must_remain:'+label+':'+path.name)
        tail = (root/'prior_jobs/chexbench.cuda_1.log').read_text(encoding='utf-8-sig', errors='replace').strip().splitlines()
        require(tail and tail[-1] == 'ValueError: invalid_patch_section', 'exact_preserved_window4_META_schema_failure_required:'+label)
        for name in (('controller', 'chexbench') if continued_by_mutation_fields else ('controller', *DATASETS)):
            expected_exit = '1' if continued_by_mutation_fields else '0'
            require((root/(name+'.exitcode')).read_text(encoding='utf-8-sig').strip() == expected_exit,
                    'actual_intermediate_META_schema_or_final_runner_exit_required:'+label+':'+name)
        ready, scope, plan = read(root/'REVIEW_READY.json'), read(root/'SCOPE.json'), read(root/'plan.json')
        require(ready.get('recovery_id') == 'meta_schema_1' and ready.get('verdict') == 'ready'
                and ready.get('scope_complete') is True and ready.get('trace'), 'actual_META_schema_operational_readiness:'+label)
        require(scope.get('fresh_meta_repair_limit') == 1 and scope.get('extra_agent_calls') == 0
                and scope.get('extra_embedding_calls') == 0 and scope.get('extra_tool_retries') == 0
                and scope.get('new_diagnostic_invocations') == 0 and scope.get('modify_completed_records') is False
                and scope.get('allowed_sections_unchanged') is True and scope.get('target_unchanged') is True
                and scope.get('automatic_invalid_to_none') is False and scope.get('keep_cuda_cache_overlay') is True
                and plan.get('committed_questions_before') == 120 and plan.get('committed_windows_before') == 3
                and plan.get('fresh_meta_repair_limit') == 1 and plan.get('extra_agent_calls_for_repair') == 0
                and plan.get('extra_embedding_calls_for_repair') == 0 and plan.get('extra_tool_retries') == 0
                and plan.get('cuda_cache_wrapper') == 'recovery/cuda_1/resume_runner.py'
                and plan.get('automatic_invalid_to_none') is False and plan.get('target_skill_id') == target,
                'narrow_META_schema_scope_preserves_prefix_snapshots_and_CUDA_overlay:'+label)
        for name in ('controller.py', 'resume_runner.py', 'registration.json'):
            require((root/name).is_file() and (root/name).stat().st_size > 0, 'actual_META_schema_operational_record:'+label+':'+name)
        proof[label] = {'prior_CUDA_controller_raw_exit': 1, 'prior_CUDA_chexbench_raw_exit': 1,
                        'prior_generation_raw_exit': 1,
                        'meta_schema_continuation_controller_raw_exit': 1 if continued_by_mutation_fields else 0,
                        'meta_schema_continuation_children_raw_exit': {'chexbench': 1} if continued_by_mutation_fields else {ds: 0 for ds in DATASETS},
                        'continued_by_registered_mutation_fields_amendment': continued_by_mutation_fields,
                        'committed_questions_preserved': 120, 'earlier_window_repos_preserved': 3,
                        'scope': scope, 'plan': plan}
    require(read(private/'registration.json') == registration, 'private_global_META_schema_registration_must_match_GEN')
    evidence = bundle['evidence']; gen_path = evidence/'failure_events/meta_schema_1_registration.json'
    global_path = public_root/'registration.json'
    require(public_asset_semantics(read(gen_path), gen_path, evidence) ==
            public_asset_semantics(read(global_path), global_path, evidence),
            'published_global_META_schema_registration_must_match_GEN')
    review_files = {'raw': in_report(raw_review), 'metadata': in_report(metadata_review),
                    'explanation': in_report(explanation or REPORT/'META_SCHEMA_RECOVERY_PLAN.md'),
                    'helper': in_report(REPORT/'deployment_source/recover_cxr_online_skill_r49_meta_schema.py')}
    metadata = read(metadata_review)
    require(metadata.get('status') == 'completed' and not metadata.get('is_error') and metadata.get('session_id')
            and metadata.get('modelUsage') and metadata.get('duration_ms', 0) > 0 and metadata.get('turns', 0) > 0
            and any('deepseek' in name.lower() for name in metadata['modelUsage'])
            and len(Path(raw_review).read_text(encoding='utf-8-sig').strip()) > 20,
            'actual_selected_DeepSeek_META_schema_operational_review_required')
    calls = {}; receipts = {}
    for kind, field, event in [('original_invalid', 'original_call_relative', registration['source_event']),
                               ('fresh_repair', 'repair_call_relative', registration['repair_event'])]:
        relative = 'services/calls/R49-META/'+event+'/1'
        require(registration.get(field) == relative, 'exact_declared_META_event_namespace_required:'+kind)
        folder = evidence/relative
        require(all((folder/name).is_file() for name in ('request.json', 'started.json', 'response.json', 'result.json')),
                'closed_original_invalid_and_fresh_repair_META_required:'+kind)
        receipt, started = read(folder/'result.json'), read(folder/'started.json')
        require(receipt.get('response_received') is True and not receipt.get('error')
                and utc(started['utc']) <= utc(receipt['utc']), 'healthy_closed_META_transport_receipt_required:'+kind)
        require(len(list(folder.parent.glob('*/started.json'))) == 1, 'one_request_only_in_each_exact_META_event:'+kind)
        calls[kind] = {'relative': relative, 'started': started}; receipts[kind] = receipt
    require(utc(receipts['original_invalid']['utc']) <= utc(calls['fresh_repair']['started']['utc']),
            'fresh_schema_repair_must_follow_closed_original_reply')
    for row in bundle['manifest']['inputs'][:120]:
        prediction = read(bundle['files']['predictions'][row['question_id']])
        require(utc(prediction['prediction_saved_at']) <= utc(receipts['original_invalid']['utc']),
                'all120_already_committed_predictions_must_predate_META_failure')
    subset = {}
    for kind, receipt in receipts.items():
        value = receipt.get('settlement', {}).get('charged_cny')
        subset[kind] = {'requests': 1, 'charged_cny_proxy': value, 'cost_unknown_count': int(value is None),
                        'usage': receipt.get('usage'), 'elapsed_s': receipt.get('elapsed_s'),
                        'elapsed_unknown_count': int(receipt.get('elapsed_s') is None),
                        'already_in_R49_META_totals_once': True, 'add_to_totals_again': False,
                        'request_path': calls[kind]['relative']}
    metered = bundle['summary']['resources']['meta_schema_repair']
    require(metered['registered'] is True and metered['added_meta_requests'] == 1
            and metered['source_invalid_schema_response_retained'] is True
            and metered['included_in_R49_META_totals'] is True
            and metered['automatic_invalid_to_none'] is False
            and metered['fresh_model_operation'] == new_control['operation']
            and all(metered[key] == 0 for key in ('extra_agent_calls', 'extra_embedding_calls', 'extra_tool_calls'))
            and metered['repair_request_resources']['requests'] == 1,
            'actual_META_repair_resource_subset_must_match_registered_fresh_model_control')
    return {'recovery_id': 'meta_schema_1', 'public_tree': public_rel, 'proof': proof,
            'review_files': review_files, 'review_metadata': metadata, 'source_question_id': registration['source_question_id'],
            'source_event': registration['source_event'], 'repair_event': registration['repair_event'],
            'window_index': registration['window_index'], 'target_skill_id': target,
            'original_control': old_control, 'repair_control': new_control,
            'same_original_payload': True, 'schema_only_clarifier': True,
            'new_meta_calls': 1, 'extra_agent_calls': 0, 'extra_embedding_calls': 0, 'extra_tool_calls': 0,
            'automatic_invalid_to_none': False, 'new_clinical_information': False,
            'prior_committed_questions_preserved': 120, 'earlier_completed_windows_preserved': 3,
            'CUDA_overlay_preserved_without_new_CUDA_retry': True, 'frozen_evolve_validation_and_review_unchanged': True,
            'non_additive_META_cost_subsets': subset, 'root_cause_or_medical_improvement_claim': False,
            'saved_scorer_META_repair_resource_subset': metered,
            'all_attempts_exited_zero_claim': False, 'stop_and_repair_wall_seconds': None}


def mutation_fields_recovery(archive, public_root, raw_review, metadata_review, bundles, explanation=None,
                             *, continued_by_embedding=False):
    """Future-only exact second repair plus declared three-stream prompt amendment."""
    import sys
    experiments = str(ROOT/'experiments')
    if experiments not in sys.path:
        sys.path.insert(0, experiments)
    from score_online_skill_r49 import registered_meta_schema_repair_2, validate_mutation_fields_amendment
    run = Path(archive)/'generation/chexbench'; private = Path(archive)/'recovery/mutation_fields_2'
    checked = registered_meta_schema_repair_2(run)
    require(checked is not None, 'actual_known_second_META_schema_repair_required')
    registration = checked['registration']
    expected = {'schema': 'r49_registered_meta_schema_repair_v2', 'recovery_id': 'mutation_fields_2',
                'dataset': 'chexbench', 'arm': ARM, 'source_question_id': 'chexbench_slake_0013',
                'source_event': 'mutation_chexbench_slake_0013', 'repair_event': 'mutation_chexbench_slake_0013_schema_2',
                'window_index': 4, 'same_original_payload': True, 'new_meta_calls': 1, 'extra_agent_calls': 0,
                'extra_embedding_calls': 0, 'extra_tool_calls': 0, 'automatic_invalid_to_none': False,
                'new_clinical_information': False, 'status': 'valid_meta_schema_repair_registered'}
    require(all(registration.get(key) == value for key, value in expected.items()), 'only_exact_second_closed_META_failure_supported')
    target = registration['target_skill_id']; original = registration['original_control']; fresh = registration['repair_control']
    require(original == {'operation': 'PATCH', 'patch_section': 'content', 'patch_target_id': target},
            'original_second_failure_must_be_PATCH_content_same_target')
    allowed = {'name', 'description', 'applicable_conditions', 'required_tools', 'risk_level', 'core_action'}
    require(fresh.get('operation') == 'NONE' or (fresh.get('operation') == 'PATCH'
            and fresh.get('patch_target_id') == target and fresh.get('patch_section') in allowed),
            'actual_second_fresh_reply_must_be_valid_same_target_PATCH_or_model_NONE')
    public_root = Path(public_root).resolve()
    require(public_root.is_relative_to(REPORT.resolve()) and public_root.is_dir(), 'portable_mutation_field_amendment_recovery_required')
    public_rel = public_root.relative_to(REPORT.resolve()).as_posix(); proofs = {}
    for label, root in [('private', private), ('published', public_root)]:
        for path in (root/'prior_generation.exitcode', root/'prior_jobs/controller.exitcode', root/'prior_jobs/chexbench.exitcode'):
            require(path.read_text(encoding='utf-8-sig').strip() == '1', 'prior_150_question_schema_stop_raw1_required:'+label+':'+path.name)
        tail = (root/'prior_jobs/chexbench.meta_schema_1.log').read_text(encoding='utf-8-sig', errors='replace').strip().splitlines()
        require(tail and tail[-1] == 'ValueError: invalid_patch_section', 'actual_preserved_fifth_window_invalid_patch_section_required:'+label)
        for name in (('controller', 'chexbench') if continued_by_embedding else ('controller', *DATASETS)):
            expected_exit = '1' if continued_by_embedding else '0'
            require((root/(name+'.exitcode')).read_text(encoding='utf-8-sig').strip() == expected_exit,
                    'actual_intermediate_mutation_fields_or_final_runner_exit_required:'+label+':'+name)
        ready, scope, plan = read(root/'REVIEW_READY.json'), read(root/'SCOPE.json'), read(root/'plan.json')
        require(ready.get('recovery_id') == 'mutation_fields_2' and ready.get('verdict') == 'ready'
                and ready.get('scope_complete') is True and ready.get('trace'), 'actual_second_schema_operational_review_ready:'+label)
        require(scope.get('fresh_meta_repair_limit') == 1 and scope.get('extra_agent_calls') == 0
                and scope.get('extra_embedding_calls') == 0 and scope.get('extra_tool_retries') == 0
                and scope.get('new_diagnostic_invocations') == 0 and scope.get('modify_completed_records') is False
                and scope.get('allowed_sections_unchanged') is True and scope.get('target_unchanged') is True
                and scope.get('automatic_invalid_to_none') is False and scope.get('keep_cuda_cache_overlay') is True
                and scope.get('keep_meta_schema_1_overlay') is True and scope.get('ordinary_field_clarification_all_datasets') is True
                and scope.get('extra_meta_calls_per_ordinary_event') == 0 and scope.get('automatic_future_repair') is False
                and plan.get('committed_questions_before') == 150 and plan.get('committed_windows_before') == 4
                and plan.get('fresh_meta_repair_limit') == 1 and plan.get('extra_agent_calls_for_repair') == 0
                and plan.get('extra_embedding_calls_for_repair') == 0 and plan.get('extra_tool_retries') == 0
                and plan.get('target_skill_id') == target and plan.get('automatic_invalid_to_none') is False
                and plan.get('ordinary_field_clarification_all_datasets') is True
                and plan.get('previous_wrapper') == 'recovery/meta_schema_1/resume_runner.py',
                'bounded_one_second_repair_and_zero_extra_ordinary_call_scope_required:'+label)
        for name in ('controller.py', 'resume_runner.py', 'registration.json'):
            require((root/name).is_file() and (root/name).stat().st_size > 0, 'actual_mutation_field_operational_source_or_record:'+label+':'+name)
        proofs[label] = {'prior_meta_schema_controller_raw_exit': 1, 'prior_meta_schema_chexbench_raw_exit': 1,
                         'prior_generation_raw_exit': 1,
                         'mutation_fields_continuation_controller_raw_exit': 1 if continued_by_embedding else 0,
                         'mutation_fields_continuation_children_raw_exit': {'chexbench': 1} if continued_by_embedding else {ds: 0 for ds in DATASETS},
                         'continued_by_registered_embedding_http_recovery': continued_by_embedding,
                         'committed_questions_preserved': 150, 'completed_window_repos_preserved': 4,
                         'scope': scope, 'plan': plan}
    require(read(private/'registration.json') == registration, 'private_global_case2_registration_must_equal_GEN')
    evidence = bundles['chexbench']['evidence']; gen_path = evidence/'failure_events/meta_schema_2_registration.json'
    shared_path = public_root/'registration.json'
    require(public_asset_semantics(read(gen_path), gen_path, evidence) ==
            public_asset_semantics(read(shared_path), shared_path, evidence), 'public_case2_global_and_GEN_records_must_agree')
    amendments = {}
    for ds in DATASETS:
        stream = Path(archive)/'generation'/ds
        stats = validate_mutation_fields_amendment(stream)
        require(stats.get('active') is True and stats.get('extra_ordinary_meta_calls') == 0,
                'actual_three_stream_zero_extra_call_prompt_amendment_required:'+ds)
        declaration = stats['amendment']
        require(declaration.get('schema') == 'r49_mutation_fields_amendment_v1'
                and declaration.get('recovery_id') == 'mutation_fields_2' and declaration.get('dataset') == ds
                and declaration.get('arm') == ARM and declaration.get('status') == 'active'
                and declaration.get('committed_questions_at_activation') == (150 if ds == 'chexbench' else 0)
                and declaration.get('extra_ordinary_meta_calls') == 0 and declaration.get('automatic_future_repair') is False
                and declaration.get('new_clinical_information') is False and declaration.get('same_original_payload') is True
                and declaration.get('cached_original_or_clarified_replay') is True
                and set(declaration.get('allowed_sections', [])) == allowed,
                'exact_per_dataset_mutation_field_amendment_boundary_required:'+ds)
        require(read(private/'amendments'/(ds+'.json')) == declaration, 'private_shared_and_GEN_amendment_disagree:'+ds)
        public_declaration = read(bundles[ds]['evidence']/'failure_events/mutation_fields_2_amendment.json')
        require(public_declaration == read(public_root/'amendments'/(ds+'.json')), 'public_shared_and_GEN_amendment_disagree:'+ds)
        saved = bundles[ds]['summary']['resources']['mutation_fields_amendment']
        for field in ('active', 'ordinary_mutation_requests', 'original_system_requests', 'clarified_system_requests',
                      'protected_original_events', 'extra_ordinary_meta_calls'):
            require(saved.get(field) == stats.get(field), 'saved_prompt_variant_usage_must_match_actual_requests:'+ds+':'+field)
        amendments[ds] = stats
    review_files = {'raw': in_report(raw_review), 'metadata': in_report(metadata_review),
                    'explanation': in_report(explanation or REPORT/'MUTATION_FIELDS_RECOVERY_PLAN.md'),
                    'helper': in_report(REPORT/'deployment_source/recover_cxr_online_skill_r49_mutation_fields.py')}
    metadata = read(metadata_review)
    require(metadata.get('status') == 'completed' and not metadata.get('is_error') and metadata.get('session_id')
            and metadata.get('modelUsage') and metadata.get('duration_ms', 0) > 0 and metadata.get('turns', 0) > 0
            and any('deepseek' in name.lower() for name in metadata['modelUsage'])
            and len(Path(raw_review).read_text(encoding='utf-8-sig').strip()) > 20,
            'actual_selected_DeepSeek_mutation_field_operational_review_required')
    receipts = {}; subsets = {}
    for label, key, event in [('original_invalid', 'original_call', registration['source_event']),
                               ('fresh_repair', 'repair_call', registration['repair_event'])]:
        folder, start, receipt = checked[key]
        require(folder.relative_to(run).as_posix() == 'services/calls/R49-META/'+event+'/1'
                and receipt.get('response_received') is True and not receipt.get('error'), 'exact_closed_second_META_repair_namespace:'+label)
        receipts[label] = receipt
        cost = receipt.get('settlement', {}).get('charged_cny')
        subsets[label] = {'requests': 1, 'charged_cny_proxy': cost, 'cost_unknown_count': int(cost is None),
                          'usage': receipt.get('usage'), 'elapsed_s': receipt.get('elapsed_s'),
                          'elapsed_unknown_count': int(receipt.get('elapsed_s') is None),
                          'already_in_R49_META_totals_once': True, 'add_to_totals_again': False,
                          'request_path': folder.relative_to(run).as_posix()}
    for row in bundles['chexbench']['manifest']['inputs'][:150]:
        prediction = read(bundles['chexbench']['files']['predictions'][row['question_id']])
        require(utc(prediction['prediction_saved_at']) <= utc(receipts['original_invalid']['utc']),
                'all150_saved_predictions_must_predate_second_META_schema_failure')
    metered = bundles['chexbench']['summary']['resources']['meta_schema_repair_2']
    require(metered['registered'] is True and metered['added_meta_requests'] == 1
            and metered['source_invalid_schema_response_retained'] is True
            and metered['included_in_R49_META_totals'] is True and metered['automatic_invalid_to_none'] is False
            and metered['fresh_model_operation'] == fresh['operation']
            and all(metered[field] == 0 for field in ('extra_agent_calls', 'extra_embedding_calls', 'extra_tool_calls'))
            and metered['repair_request_resources']['requests'] == 1,
            'second_META_repair_cost_subset_and_actual_control_must_match')
    return {'recovery_id': 'mutation_fields_2', 'public_tree': public_rel, 'proof': proofs,
            'review_files': review_files, 'review_metadata': metadata,
            'source_question_id': registration['source_question_id'], 'source_event': registration['source_event'],
            'repair_event': registration['repair_event'], 'window_index': 4, 'target_skill_id': target,
            'original_control': original, 'repair_control': fresh, 'non_additive_META_cost_subsets': subsets,
            'saved_scorer_second_META_repair_resource_subset': metered, 'per_dataset_prompt_amendments': amendments,
            'same_original_payload': True, 'new_clinical_information': False, 'automatic_invalid_to_none': False,
            'new_case2_META_requests': 1, 'extra_agent_calls': 0, 'extra_embedding_calls': 0, 'extra_tool_calls': 0,
            'ordinary_prompt_clarifier_extra_calls': 0, 'automatic_future_repair': False,
            'prior_committed_questions_preserved': 150, 'earlier_window_repos_preserved': 4,
            'prior_CUDA_and_schema1_wrappers_preserved': True, 'frozen_evolve_validation_unchanged': True,
            'operational_prompt_change_confound': True, 'original_static_protocol_claim': False,
            'medical_gain_from_schema_recovery_claim': False, 'all_attempts_exited_zero_claim': False,
            'second_stop_and_repair_wall_seconds': None}


def embedding_http_recovery(archive, public_root, raw_review, metadata_review, bundles, explanation=None,
                            *, continued_by_phrase_guard=False):
    """Future-only known SDK HTTP failure, one new embedding and separate billing diagnostic."""
    import sys
    experiments = str(ROOT/'experiments')
    if experiments not in sys.path:
        sys.path.insert(0, experiments)
    from score_online_skill_r49 import registered_embedding_http_failure
    run = Path(archive)/'generation/chexbench'; private = Path(archive)/'recovery/embedding_arrearage_1'
    checked = registered_embedding_http_failure(run)
    require(checked is not None, 'actual_registered_one_embedding_HTTP_recovery_required')
    registration = checked['registration']; original = checked['original_failure']; retry = checked['retry_call']
    expected = {'schema': 'r49_registered_embedding_http_failure_v1', 'recovery_id': 'embedding_arrearage_1',
                'dataset': 'chexbench', 'arm': ARM, 'original_embedding_id': '000063',
                'retry_embedding_id': '000063_arrearage_1', 'same_original_request': True,
                'new_production_embedding_requests': 1, 'extra_agent_calls_for_repair': 0,
                'extra_meta_calls_for_repair': 0, 'extra_tool_retries': 0,
                'no_encoding_or_text_change': True, 'no_automatic_retry': True,
                'status': 'healthy_embedding_retry_registered'}
    require(all(registration.get(key) == value for key, value in expected.items()), 'only_the_one_exact_known_embedding_HTTP_recovery_supported')
    old_flags = registration['original_failure']
    require(old_flags.get('error_type') == 'BadRequestError' and old_flags.get('http_status') == 400
            and old_flags.get('http_status_evidence') == 'installed_sdk_BadRequestError_status_code_400'
            and old_flags.get('http_body_missing') is True and old_flags.get('specific_body_unknown') is True
            and old_flags.get('response_archive_absent') is True
            and original['result'].get('response_received') is False and original['result'].get('usage') is None,
            'original_HTTP_body_and_usage_must_remain_unknown_not_reconstructed_from_diagnostic')
    public_root = Path(public_root).resolve()
    require(public_root.is_relative_to(REPORT.resolve()) and public_root.is_dir(), 'portable_embedding_HTTP_recovery_tree_required')
    public_rel = public_root.relative_to(REPORT.resolve()).as_posix(); proof = {}
    for label, root in [('private', private), ('published', public_root)]:
        for path in (root/'prior_generation.exitcode', root/'prior_jobs/controller.exitcode', root/'prior_jobs/chexbench.exitcode'):
            require(path.read_text(encoding='utf-8-sig').strip() == '1', 'prior_fields2_embedding_failure_raw1_must_remain:'+label+':'+path.name)
        tail = (root/'prior_jobs/chexbench.mutation_fields_2.log').read_text(encoding='utf-8-sig', errors='replace').strip().splitlines()
        require(tail and tail[-1] == 'RuntimeError: embedding_api_failure_no_automatic_retry:BadRequestError',
                'actual_preserved_original_embedding_failure_boundary_required:'+label)
        for name in (('controller', 'chexbench') if continued_by_phrase_guard else ('controller', *DATASETS)):
            expected_exit = '1' if continued_by_phrase_guard else '0'
            require((root/(name+'.exitcode')).read_text(encoding='utf-8-sig').strip() == expected_exit,
                    'actual_intermediate_embedding_or_final_runner_exit_required:'+label+':'+name)
        ready, scope, plan, funding = (read(root/name) for name in ('REVIEW_READY.json', 'SCOPE.json', 'plan.json', 'FUNDING_CONFIRMED.json'))
        require(ready.get('recovery_id') == 'embedding_arrearage_1' and ready.get('verdict') == 'ready'
                and ready.get('scope_complete') is True and ready.get('trace'), 'actual_post_funding_embedding_operational_review_required:'+label)
        require(funding.get('recovery_id') == 'embedding_arrearage_1' and funding.get('provider') == 'aliyun_dashscope'
                and funding.get('funding_confirmed') is True and funding.get('confirmation_source') == 'explicit_user_reply'
                and funding.get('confirmed_at'), 'actual_explicit_DashScope_funding_confirmation_required:'+label)
        require(scope.get('fresh_production_embedding_limit') == 1 and scope.get('same_original_embedding_input') is True
                and scope.get('sdk_defaults_unchanged') is True and scope.get('extra_agent_calls_for_repair') == 0
                and scope.get('extra_meta_calls_for_repair') == 0 and scope.get('extra_tool_retries') == 0
                and scope.get('modify_completed_records') is False and scope.get('automatic_future_embedding_retry') is False
                and scope.get('retain_all_prior_overlays') is True and plan.get('committed_questions_before') == 150
                and plan.get('committed_windows_before') == 4 and plan.get('fresh_production_embedding_limit') == 1
                and plan.get('previous_wrapper') == 'recovery/mutation_fields_2/resume_runner.py',
                'minimal_one_embedding_same_text_model_SDK_scope_required:'+label)
        diagnostic = read(root/'diagnostic_evidence/status.json'); diagnostic_error = read(root/'diagnostic_evidence/error.json')
        require((root/'diagnostic_evidence/exitcode').read_text(encoding='utf-8-sig').strip() == '1'
                and diagnostic.get('diagnostic_id') == 'r49_embedding_400_once_20261109'
                and diagnostic.get('embedding_requests') == 1 and diagnostic.get('http_status') == 400
                and all(diagnostic.get(key) == 0 for key in ('agent_calls', 'meta_calls', 'cxr_tool_calls', 'gpu_calls'))
                and diagnostic_error.get('http_status') == 400 and diagnostic_error.get('body', {}).get('code') == 'Arrearage'
                and diagnostic.get('elapsed_s') == registration['diagnostic']['elapsed_s'],
                'neutral_billing_diagnostic_is_a_separate_failed_400_not_healthy_embedding:'+label)
        for name in ('controller.py', 'resume_runner.py', 'registration.json', 'original_failure/request.json',
                     'original_failure/started.json', 'original_failure/result.json'):
            require((root/name).is_file(), 'actual_embedding_recovery_source_and_original_failure_proof:'+label+':'+name)
        require(not (root/'original_failure/response.json').exists(), 'missing_original_HTTP_response_must_not_be_fabricated:'+label)
        proof[label] = {'prior_fields_controller_raw_exit': 1, 'prior_fields_chexbench_raw_exit': 1,
                        'prior_generation_raw_exit': 1,
                        'embedding_continuation_controller_raw_exit': 1 if continued_by_phrase_guard else 0,
                        'embedding_continuation_children_raw_exit': {'chexbench': 1} if continued_by_phrase_guard else {ds: 0 for ds in DATASETS},
                        'continued_by_registered_phrase_guard_amendment': continued_by_phrase_guard,
                        'funding_confirmation_source': funding['confirmation_source'], 'funding_confirmed_at': funding['confirmed_at'],
                        'preserved_questions': 150, 'preserved_completed_windows': 4,
                        'scope': scope, 'neutral_diagnostic': diagnostic}
    require(read(private/'registration.json') == registration
            and {name: read(private/'original_failure'/(name+'.json')) for name in ('request', 'started', 'result')} == original,
            'original_failed_embedding_semantics_must_remain_unchanged')
    evidence = bundles['chexbench']['evidence']; gen_path = evidence/'failure_events/embedding_arrearage_1_registration.json'
    shared_path = public_root/'registration.json'
    require(public_asset_semantics(read(gen_path), gen_path, evidence) == public_asset_semantics(read(shared_path), shared_path, evidence),
            'public_GEN_and_global_embedding_registration_must_match')
    archived = evidence/'failure_events/embedding_arrearage_1_original_failure.json'
    public_original = {name: read(public_root/'original_failure'/(name+'.json')) for name in ('request', 'started', 'result')}
    require(public_asset_semantics(read(archived), archived, evidence) ==
            public_asset_semantics(public_original, public_root/'original_failure/bundle.json', evidence),
            'public_original_embedding_failure_archive_must_remain_semantic_copy')
    review_files = {'raw': in_report(raw_review), 'metadata': in_report(metadata_review),
                    'explanation': in_report(explanation or REPORT/'EMBEDDING_ARREARAGE_RECOVERY_PLAN.md'),
                    'helper': in_report(REPORT/'deployment_source/recover_cxr_online_skill_r49_embedding_arrearage.py')}
    metadata = read(metadata_review)
    require(metadata.get('status') == 'completed' and not metadata.get('is_error') and metadata.get('session_id')
            and metadata.get('modelUsage') and metadata.get('duration_ms', 0) > 0 and metadata.get('turns', 0) > 0
            and any('deepseek' in name.lower() for name in metadata['modelUsage'])
            and len(Path(raw_review).read_text(encoding='utf-8-sig').strip()) > 20,
            'actual_selected_DeepSeek_embedding_recovery_review_required')
    resources = bundles['chexbench']['summary']['resources']; info = resources['embedding_http_recovery']; diag = resources['isolated_embedding_diagnostic']
    require(info['registered'] is True and info['new_production_embedding_requests'] == 1
            and info['included_in_embedding_totals'] is True and info['original_error_type'] == 'BadRequestError'
            and info['original_http_status'] == 400 and info['original_specific_body_unknown'] is True
            and info['original_usage_unknown'] is True and info['original_cost_unknown'] is True
            and diag['embedding_requests'] == 1 and diag['http_status'] == 400 and diag['error_code'] == 'Arrearage'
            and diag['usage_unknown'] is True and diag['cost_unknown'] is True
            and diag['included_in_production_embedding_totals'] is False and diag['original_error_body_reconstructed'] is False,
            'failed_original_unknown_cost_and_separate_failed_diagnostic_resource_accounting_required')
    retry_receipt = retry['result']; charge = retry_receipt.get('settlement', {}).get('charged_cny')
    return {'recovery_id': 'embedding_arrearage_1', 'public_tree': public_rel, 'proof': proof,
            'review_files': review_files, 'review_metadata': metadata,
            'original_embedding_id': '000063', 'retry_embedding_id': '000063_arrearage_1',
            'original_error': old_flags, 'original_usage': None, 'original_cost_cny': None,
            'original_cost_unknown_not_free': True, 'original_http_body_reconstructed': False,
            'neutral_diagnostic': diag, 'neutral_diagnostic_cost_unknown_count': 1,
            'same_original_request': True, 'SDK_default_encoding_preserved': True,
            'new_production_embedding_requests': 1, 'no_automatic_future_retry': True,
            'declared_runtime_closure_exception': 'Startup/final closure checks exempt only the registered immutable 000063 SDK BadRequestError failure with its original missing response; all other unknown/failed requests still stop. No response is fabricated.',
            'retry_cost_subset': {'requests': 1, 'usage': retry_receipt.get('usage'), 'charged_cny_proxy': charge,
                'cost_unknown_count': int(charge is None), 'elapsed_s': retry_receipt.get('elapsed_s'),
                'already_in_production_embedding_totals_once': True, 'add_to_totals_again': False},
            'saved_scorer_embedding_HTTP_recovery_resource_subset': info,
            '150_predictions_and_four_completed_repos_preserved': True, 'all_prior_overlays_retained': True,
            'extra_Agent_META_tools_for_repair': 0, 'model_text_encoding_or_medical_rule_changed': False,
            'all_attempts_exited_zero_claim': False, 'medical_capability_or_original_body_claim': False,
            'billing_stop_and_repair_wall_seconds': None}


def phrase_guard_recovery(archive, public_root, raw_review, metadata_review, bundles, explanation=None,
                          *, continued_by_adoption=False):
    """Future-only saved-attempt proof for the declared MAIRA EOS-policy change.

    This function is called only after load_completed has required all three
    final raw zeros. Validators inspect saved evidence; nothing is generated,
    diagnosed, scored or repaired by this private report writer.
    """
    import sys
    experiments = str(ROOT/'experiments')
    if experiments not in sys.path:
        sys.path.insert(0, experiments)
    from score_online_skill_r49 import registered_phrase_guard_retry, validate_phrase_guard_amendment
    run = Path(archive)/'generation/chexbench'; private = Path(archive)/'recovery/phrase_guard_1'
    checked = registered_phrase_guard_retry(run)
    require(checked is not None, 'actual_known_closed_MAIRA_failure_and_healthy_guarded_retry_required')
    registration, original, retry = (checked[key] for key in ('registration', 'original_result', 'retry_result'))
    fixed = {'schema': 'r49_registered_phrase_guard_retry_v1', 'recovery_id': 'phrase_guard_1',
             'dataset': 'chexbench', 'arm': ARM, 'question_id': 'chexbench_slake_0053',
             'question_ordinal': 169, 'logical_tool_ordinal': 1, 'tool': 'xray_phrase_grounding',
             'policy_id': 'maira_unclosed_tag_eos_guard_v1', 'generation_policy_changed': True,
             'same_generation_settings': False, 'guarded_production_retry_limit': 1,
             'automatic_retry': False, 'status': 'healthy_guarded_production_retry_registered'}
    require(all(registration.get(key) == value for key, value in fixed.items()),
            'one_exact_q169_guarded_retry_under_declared_changed_policy_required')
    require(registration['retry_cache_key'] == registration['original_cache_key']+'_phrase_guard_1',
            'known_guarded_retry_namespace_must_preserve_original_cache')
    public_root = Path(public_root).resolve()
    require(public_root.is_relative_to(REPORT.resolve()) and public_root.is_dir(), 'portable_phrase_guard_recovery_tree_required')
    public_rel = public_root.relative_to(REPORT.resolve()).as_posix(); proof = {}
    expected_scope = {'recovery_id': 'phrase_guard_1', 'activation_boundary_chexbench': 168,
                      'known_failed_guarded_retry_limit': 1, 'all_new_physical_maira_calls': True,
                      'generation_policy_changed': True, 'same_generation_settings': False,
                      'clinical_prompt_changed': False, 'parser_changed': False, 'max_new_tokens': 300,
                      'extra_agent_calls_for_repair': 0, 'extra_meta_calls_for_repair': 0,
                      'extra_embedding_calls_for_repair': 0, 'automatic_tool_retry': False,
                      'modify_completed_records': False, 'retain_all_prior_overlays': True,
                      'diagnostic_result_reused': False}
    for label, root in [('private', private), ('published', public_root)]:
        for path in (root/'prior_generation.exitcode', root/'prior_jobs/controller.exitcode', root/'prior_jobs/chexbench.exitcode'):
            require(path.read_text(encoding='utf-8-sig').strip() == '1', 'prior_MAIRA_raw_failure_exit1_must_remain:'+label+':'+path.name)
        require((root/'prior_jobs/controller.pid').read_text(encoding='utf-8-sig').strip() == '2645757'
                and (root/'prior_jobs/chexbench.pid').read_text(encoding='utf-8-sig').strip() == '2645763',
                'actual_prior_embedding_attempt_identity_before_MAIRA_failure_required:'+label)
        tail = (root/'prior_jobs/chexbench.embedding_arrearage_1.log').read_text(encoding='utf-8-sig', errors='replace').strip().splitlines()
        require(tail and tail[-1] == 'RuntimeError: tool_failure_stop_no_automatic_retry:nested_backend_error',
                'actual_preserved_q169_nested_tool_failure_boundary_required:'+label)
        for name in (('controller', 'chexbench') if continued_by_adoption else ('controller', *DATASETS)):
            expected_exit = '1' if continued_by_adoption else '0'
            require((root/(name+'.exitcode')).read_text(encoding='utf-8-sig').strip() == expected_exit,
                    'actual_intermediate_phrase_guard_or_final_runner_exit_required:'+label+':'+name)
        ready, scope, plan = (read(root/name) for name in ('REVIEW_READY.json', 'SCOPE.json', 'plan.json'))
        require(ready.get('recovery_id') == 'phrase_guard_1' and ready.get('verdict') == 'ready'
                and ready.get('scope_complete') is True and ready.get('trace'), 'actual_phrase_guard_operational_review_required:'+label)
        require(all(scope.get(key) == value for key, value in expected_scope.items())
                and scope.get('authorization_basis') and scope.get('new_user_approval_claimed') is False
                and plan.get('activation_boundary_chexbench') == 168 and plan.get('committed_windows_before') == 5
                and plan.get('previous_wrapper') == 'recovery/embedding_arrearage_1/resume_runner.py'
                and plan.get('generation_policy_changed') is True and plan.get('same_generation_settings') is False,
                'explicit_generation_policy_amendment_not_original_settings_or_automatic_retry:'+label)
        diagnostic = read(root/'diagnostic_evidence/status.json')
        require((root/'diagnostic_evidence/exitcode').read_text(encoding='utf-8-sig').strip() == '1'
                and diagnostic.get('status') == 'failed' and diagnostic.get('capture_complete') is True
                and diagnostic.get('tool_invocations') == 1
                and all(diagnostic.get(key) == 0 for key in ('main_api_calls', 'meta_api_calls', 'embedding_api_calls'))
                and diagnostic.get('elapsed_s') == registration['diagnostic']['elapsed_s']
                and plan['diagnostic']['elapsed_s'] == diagnostic['elapsed_s']
                and plan['diagnostic']['result_reused_in_R49'] is False,
                'independent_MAIRA_diagnostic_must_remain_failed_separate_not_reused:'+label)
        for name in ('controller.py', 'resume_runner.py', 'maira_guard_worker.py', 'eos_guard_policy.py',
                     'registration.json', 'original_selection.json'):
            require((root/name).is_file() and (root/name).stat().st_size > 0,
                    'actual_phrase_guard_source_or_proof_required:'+label+':'+name)
        proof[label] = {'prior_embedding_controller_pid': 2645757, 'prior_embedding_chexbench_pid': 2645763,
                        'prior_controller_raw_exit': 1, 'prior_chexbench_raw_exit': 1, 'prior_generation_raw_exit': 1,
                        'phrase_guard_continuation_controller_raw_exit': 1 if continued_by_adoption else 0,
                        'phrase_guard_continuation_children_raw_exit': {'chexbench': 1} if continued_by_adoption else {ds: 0 for ds in DATASETS},
                        'continued_by_registered_adoption_recovery': continued_by_adoption,
                        'preserved_questions': 168, 'preserved_completed_windows': 5, 'scope': scope,
                        'isolated_failed_diagnostic_status': diagnostic}
    require(read(private/'registration.json') == registration
            and read(private/'original_selection.json') == registration['original_selection'],
            'private_shared_and_GEN_phrase_guard_registration_and_original_selection_must_match')
    evidence = bundles['chexbench']['evidence']; gen_path = evidence/'failure_events/phrase_guard_1_registration.json'
    shared_path = public_root/'registration.json'; archived_path = evidence/'failure_events/phrase_guard_1_original_selection.json'
    gen = public_asset_semantics(read(gen_path), gen_path, evidence)
    require(gen == public_asset_semantics(read(shared_path), shared_path, evidence)
            and gen['original_selection'] == public_asset_semantics(read(archived_path), archived_path, evidence)
            and gen['original_selection'] == public_asset_semantics(read(public_root/'original_selection.json'), public_root/'original_selection.json', evidence),
            'published_GEN_global_and_original_phrase_guard_evidence_must_match')
    active_path = evidence/'services/tool_selections/R49-AGENT'/registration['question_id']/'1.json'
    require(public_asset_semantics(read(active_path), active_path, evidence) == gen['active_selection'],
            'published_known_guarded_retry_must_be_active_not_diagnostic_output')
    for key in (registration['original_cache_key'], registration['retry_cache_key']):
        require(all((evidence/'services/tool_cache'/key/name).is_file() for name in ('started.json', 'result.json')),
                'published_old_failed_and_new_guarded_physical_attempts_must_be_closed')
    amendments = {}
    for ds in DATASETS:
        checked_amendment = validate_phrase_guard_amendment(Path(archive)/'generation'/ds)
        require(checked_amendment['active'] is True, 'actual_all_three_MAIRA_policy_amendments_required:'+ds)
        amendment = checked_amendment['amendment']; expected_activation = 168 if ds == 'chexbench' else 0
        require(amendment.get('schema') == 'r49_phrase_guard_amendment_v1' and amendment.get('recovery_id') == 'phrase_guard_1'
                and amendment.get('dataset') == ds and amendment.get('arm') == ARM
                and amendment.get('activation_committed_questions') == expected_activation
                and amendment.get('scope') == 'all_new_physical_MAIRA_calls_after_activation'
                and amendment.get('generation_policy_changed') is True and amendment.get('same_generation_settings') is False
                and amendment.get('legacy_healthy_cache_reuse') is True and amendment.get('automatic_retry') is False,
                'exact_activation_and_mixed_legacy_cache_new_physical_MAIRA_policy_required:'+ds)
        require(read(private/'amendments'/(ds+'.json')) == amendment, 'private_shared_phrase_guard_amendment_must_match:'+ds)
        pub_evidence = bundles[ds]['evidence']; pub_path = pub_evidence/'failure_events/phrase_guard_1_amendment.json'
        pub_shared = public_root/'amendments'/(ds+'.json')
        require(public_asset_semantics(read(pub_path), pub_path, pub_evidence) ==
                public_asset_semantics(read(pub_shared), pub_shared, pub_evidence),
                'published_GEN_and_shared_phrase_guard_amendments_must_match:'+ds)
        saved = bundles[ds]['summary']['resources']['phrase_guard_amendment']
        require(saved == checked_amendment, 'saved_resource_policy_counts_must_match_actual_closed_tool_evidence:'+ds)
        amendments[ds] = checked_amendment
    review_files = {'raw': in_report(raw_review), 'metadata': in_report(metadata_review),
                    'explanation': in_report(explanation or REPORT/'PHRASE_GROUNDING_EOS_GUARD_RECOVERY_PLAN.md'),
                    'helper': in_report(REPORT/'deployment_source/recover_cxr_online_skill_r49_phrase_guard.py'),
                    'policy': in_report(REPORT/'deployment_source/r49_phrase_grounding_eos_guard_candidate.py')}
    metadata = read(metadata_review)
    require(metadata.get('status') == 'completed' and not metadata.get('is_error') and metadata.get('session_id')
            and metadata.get('modelUsage') and metadata.get('duration_ms', 0) > 0 and metadata.get('turns', 0) > 0
            and any('deepseek' in name.lower() for name in metadata['modelUsage'])
            and len(Path(raw_review).read_text(encoding='utf-8-sig').strip()) > 20,
            'actual_user_selected_DeepSeek_phrase_guard_operational_review_required')
    saved_resources = bundles['chexbench']['summary']['resources']; info = saved_resources['phrase_guard_retry']
    diagnostic_resource = saved_resources['isolated_phrase_diagnostic']; tools = saved_resources['tools']
    require(info['registered'] is True and info['guarded_production_retries'] == 1
            and info['generation_policy_changed'] is True and info['same_generation_settings'] is False
            and info['diagnostic_result_reused'] is False and info['included_in_tools_totals'] is True
            and tools['registered_cuda_failed_attempts'] == tools['registered_phrase_failed_attempts'] == 1
            and tools['registered_failed_historical_attempts'] == tools['failed_backend_attempts'] == 2
            and diagnostic_resource['tool_invocations'] == 1 and diagnostic_resource['status'] == 'failed'
            and diagnostic_resource['capture_complete'] is True
            and diagnostic_resource['elapsed_s'] == registration['diagnostic']['elapsed_s']
            and diagnostic_resource['included_in_production_attempts'] is False
            and diagnostic_resource['result_reused_in_R49'] is False
            and all(diagnostic_resource[key] == 0 for key in ('main_api_calls', 'meta_api_calls', 'embedding_api_calls')),
            'known_failed_production_once_guarded_retry_once_and_separate_failed_diagnostic_accounting_required')
    qid = registration['question_id']; old_closed_at = utc(original['utc']); manifest = bundles['chexbench']['manifest']
    require(manifest['inputs'][168]['question_id'] == qid, 'actual_q169_order_identity_required')
    for row in manifest['inputs'][:168]:
        require(utc(read(bundles['chexbench']['files']['predictions'][row['question_id']])['prediction_saved_at']) <= old_closed_at,
                'first168_committed_predictions_must_precede_original_MAIRA_failure')
    old_main_prefix = []
    for call in sorted((evidence/'services/calls/R49-AGENT'/qid).iterdir()):
        started, receipt = read(call/'started.json'), read(call/'result.json')
        if utc(started['utc']) <= old_closed_at:
            require(receipt.get('response_received') is True and not receipt.get('error') and utc(receipt['utc']) <= old_closed_at,
                    'original_q169_main_prefix_must_remain_closed_not_retried')
            old_main_prefix.append({'ordinal': call.name, 'usage': receipt.get('usage'), 'elapsed_s': receipt.get('elapsed_s'),
                                    'charged_cny_proxy': receipt.get('settlement', {}).get('charged_cny'),
                                    'already_in_agent_totals_once': True, 'add_to_totals_again': False})
    require(old_main_prefix, 'known_pre_failure_q169_main_prefix_must_be_preserved')
    return {'recovery_id': 'phrase_guard_1', 'public_tree': public_rel, 'proof': proof,
            'review_files': review_files, 'review_metadata': metadata, 'question_id': qid,
            'question_ordinal': 169, 'preserved_committed_questions': 168, 'preserved_completed_windows': 5,
            'generation_policy_changed': True, 'same_generation_settings': False,
            'original_failure_elapsed_s': original.get('elapsed_s'),
            'original_failure_backend_elapsed_s': original.get('backend_compute_seconds'),
            'isolated_diagnostic': diagnostic_resource, 'per_dataset_policy_amendments': amendments,
            'original_q169_main_prefix_costs_are_non_additive': old_main_prefix,
            'original_failed_and_guarded_retry_are_in_physical_tool_totals_once': True,
            'diagnostic_result_reused_in_production': False, 'diagnostic_cost_added_to_production': False,
            'legacy_healthy_cache_policy_preserved': True, 'mixed_generation_policy_confound': True,
            'automatic_retry_or_parse_fallback': False, 'frozen_eight_inference_source_files_edited': False,
            'official_MAIRA_fix_claim': False, 'unchanged_output_semantics_claim': False,
            'medical_capability_or_Skill_causality_claim': False, 'all_attempts_exited_zero_claim': False,
            'MAIRA_stop_diagnosis_and_repair_wall_seconds': None, 'unpriced_hardware_cost': None}


def adoption_recovery(archive, public_root, bundles, final_review, explanation=None):
    """Future-only two representative choices and the user-directed final audit.

    The initial execution authorization remains an explicitly deferred audit,
    never an invented reviewer-ready artifact. A single actual final DeepSeek
    review must cover this protocol, the resource accounting and all results.
    """
    import sys
    experiments = str(ROOT/'experiments')
    if experiments not in sys.path:
        sys.path.insert(0, experiments)
    from score_online_skill_r49 import registered_adoption_repair, validate_analysis_unique_amendment
    run = Path(archive)/'generation/chexbench'; private = Path(archive)/'recovery/adoption_1'
    checked = registered_adoption_repair(run)
    require(checked is not None, 'two_actual_assess_only_adoption_representative_choices_required')
    registration = checked['registration']
    fixed = {'schema': 'r49_registered_assessment_adoption_repair_v1', 'recovery_id': 'adoption_1',
             'dataset': 'chexbench', 'arm': ARM, 'window_index': 6, 'activation_committed_questions': 210,
             'new_meta_requests': 2, 'assess_only': True, 'write_phase_analysis_unchanged': True,
             'other_analysis_fields_unchanged': True, 'automatic_retry': False,
             'status': 'two_assess_only_adoption_repairs_registered'}
    require(all(registration.get(key) == value for key, value in fixed.items()),
            'only_exact_two_assessment_representative_choices_supported')
    expected_events = {'analysis_chexbench_slake_0081', 'analysis_chexbench_slake_0082'}
    cases = registration['repairs']
    require(len(cases) == 2 and {case['source_event'] for case in cases} == expected_events
            and all(case['repair_event'] == case['source_event']+'_adoption_1' for case in cases)
            and all(type(case['selected_duplicate_index']) is int and case['selected_duplicate_index'] in (0, 1) for case in cases),
            'two_known_model_chosen_original_entry_indices_not_operator_deduplication_required')
    public_root = Path(public_root).resolve()
    require(public_root.is_relative_to(REPORT.resolve()) and public_root.is_dir(), 'portable_adoption_recovery_tree_required')
    public_rel = public_root.relative_to(REPORT.resolve()).as_posix(); proof = {}
    expected_scope = {'recovery_id': 'adoption_1', 'uses_existing_r49_authorization': True,
                      'new_user_approval_claimed': False, 'fresh_meta_repair_limit': 2, 'assess_only': True,
                      'write_phase_analysis_unchanged': True, 'representative_index_only': True,
                      'extra_agent_calls_for_repair': 0, 'extra_embedding_calls_for_repair': 0, 'extra_tool_retries': 0,
                      'analysis_clarification_all_datasets': True, 'extra_meta_calls_per_ordinary_analysis': 0,
                      'automatic_future_repair': False, 'modify_completed_records': False, 'retain_all_prior_overlays': True}
    expected_authorization = {'recovery_id': 'adoption_1', 'verdict': 'audit_deferred_until_full_generation',
                              'review_completed': False, 'scope_complete': False,
                              'exact_user_reply': '这个可以跑完再审计？', 'confirmation_source': 'explicit_user_reply',
                              'audit_before_publication': True, 'implementation_checks_passed': True}
    for label, root in [('private', private), ('published', public_root)]:
        for path in (root/'prior_generation.exitcode', root/'prior_jobs/controller.exitcode', root/'prior_jobs/chexbench.exitcode'):
            require(path.read_text(encoding='utf-8-sig').strip() == '1', 'prior_adoption_schema_failure_raw1_must_remain:'+label+':'+path.name)
        require((root/'prior_jobs/controller.pid').read_text(encoding='utf-8-sig').strip() == '2722301'
                and (root/'prior_jobs/chexbench.pid').read_text(encoding='utf-8-sig').strip() == '2722307',
                'actual_prior_phrase_guard_attempt_identity_required:'+label)
        tail = (root/'prior_jobs/chexbench.phrase_guard_1.log').read_text(encoding='utf-8-sig', errors='replace').strip().splitlines()
        require(tail and tail[-1] == 'ValueError: duplicate_skill_adoption', 'actual_preserved_assessment_failure_boundary_required:'+label)
        for name in ('controller', *DATASETS):
            zero(root/(name+'.exitcode'))
        scope, authorization, plan = (read(root/name) for name in ('SCOPE.json', 'EXECUTION_AUTHORIZATION.json', 'plan.json'))
        require(all(scope.get(key) == value for key, value in expected_scope.items()) and scope.get('authorization_basis')
                and all(authorization.get(key) == value for key, value in expected_authorization.items()),
                'truthful_initial_user_directed_audit_deferral_must_not_be_rewritten_as_ready:'+label)
        require(plan.get('window_index') == 6 and plan.get('activation_committed_questions') == 210
                and plan.get('committed_windows_before') == 6 and plan.get('new_meta_request_limit') == 2
                and plan.get('representative_index_only') is True
                and plan.get('previous_wrapper') == 'recovery/phrase_guard_1/resume_runner.py'
                and plan.get('audit_timing') == 'after_full_generation_before_publication',
                'known210_prefix_six_windows_and_deferred_full_audit_scope_required:'+label)
        for name in ('controller.py', 'resume_runner.py', 'registration.json'):
            require((root/name).is_file() and (root/name).stat().st_size > 0, 'actual_adoption_recovery_source_or_proof_required:'+label+':'+name)
        proof[label] = {'prior_phrase_guard_controller_pid': 2722301, 'prior_phrase_guard_chexbench_pid': 2722307,
                        'prior_controller_raw_exit': 1, 'prior_chexbench_raw_exit': 1, 'prior_generation_raw_exit': 1,
                        'final_adoption_controller_raw_exit': 0, 'final_adoption_children_raw_exit': {ds: 0 for ds in DATASETS},
                        'preserved_questions': 210, 'preserved_completed_windows': 6,
                        'initial_execution_authorization': authorization, 'initial_marker_claims_review_completed': False,
                        'initial_marker_rewritten_to_ready': False, 'scope': scope}
    require(read(private/'registration.json') == registration, 'private_shared_and_GEN_adoption_registration_must_match')
    require(read(private/'EXECUTION_AUTHORIZATION.json') == read(public_root/'EXECUTION_AUTHORIZATION.json'),
            'published_initial_audit_deferral_authorization_must_remain_unchanged')
    evidence = bundles['chexbench']['evidence']; gen_path = evidence/'failure_events/adoption_1_registration.json'
    shared_path = public_root/'registration.json'
    require(public_asset_semantics(read(gen_path), gen_path, evidence) == public_asset_semantics(read(shared_path), shared_path, evidence),
            'published_GEN_and_shared_adoption_registration_must_match')
    amendments = {}
    for ds in DATASETS:
        actual = validate_analysis_unique_amendment(Path(archive)/'generation'/ds)
        require(actual['active'] is True and actual['extra_ordinary_meta_calls'] == 0,
                'all_three_declared_unique_adoption_analysis_amendments_without_extra_ordinary_calls_required:'+ds)
        amendment = actual['amendment']; expected_activation = 210 if ds == 'chexbench' else 0
        require(amendment.get('schema') == 'r49_analysis_unique_adoption_amendment_v1'
                and amendment.get('recovery_id') == 'adoption_1' and amendment.get('dataset') == ds
                and amendment.get('arm') == ARM and amendment.get('activation_committed_questions') == expected_activation
                and amendment.get('automatic_future_repair') is False and amendment.get('new_clinical_information') is False,
                'exact210_or_cold_stream_analysis_clarifier_activation_required:'+ds)
        require(read(private/'amendments'/(ds+'.json')) == amendment, 'private_shared_analysis_amendment_must_match:'+ds)
        pub_evidence = bundles[ds]['evidence']; pub_path = pub_evidence/'failure_events/analysis_unique_adoption_amendment.json'
        pub_shared = public_root/'amendments'/(ds+'.json')
        require(public_asset_semantics(read(pub_path), pub_path, pub_evidence) ==
                public_asset_semantics(read(pub_shared), pub_shared, pub_evidence), 'published_analysis_amendment_must_match:'+ds)
        require(bundles[ds]['summary']['resources']['analysis_unique_amendment'] == actual,
                'saved_analysis_prompt_variant_counts_must_match_actual_closed_requests:'+ds)
        amendments[ds] = actual
    metadata = final_review['metadata']; required_audit_scope = {'adoption_protocol', 'request_resource_accounting', 'complete_results_and_claims'}
    require(metadata.get('scope_complete') is True and isinstance(metadata.get('audit_scope'), list)
            and required_audit_scope <= set(metadata['audit_scope']),
            'actual_single_final_DeepSeek_scope_must_cover_adoption_protocol_resource_accounting_and_complete_results')
    review_files = {**final_review['paths'],
                    'explanation': in_report(explanation or REPORT/'ADOPTION_RECOVERY_PLAN.md'),
                    'helper': in_report(REPORT/'deployment_source/recover_cxr_online_skill_r49_adoption.py')}
    resources = bundles['chexbench']['summary']['resources']['adoption_repair']
    require(resources['registered'] is True and resources['added_meta_requests'] == 2
            and resources['included_in_R49_META_totals'] is True and resources['original_analysis_retained_for_mutation'] is True
            and resources['assess_only_overlay'] is True and resources['repair_request_resources']['requests'] == 2
            and resources['model_selected_existing_entry_only'] is True
            and resources['manual_selection'] is False and resources['new_evidence_written'] is False,
            'two_fresh_META_choices_already_metered_once_and_original_mutation_input_preserved_required')
    cost_subsets = []; original_analysis_starts = []
    for case in cases:
        original_path, repair_path = (evidence/case[key] for key in ('original_call_relative', 'repair_call_relative'))
        require(all(path.resolve().is_relative_to(evidence.resolve()) for path in (original_path, repair_path)), 'published_adoption_call_paths_must_stay_in_evidence')
        original_receipt, repair_receipt = (read(path/'result.json') for path in (original_path, repair_path))
        original_started, repair_started = (read(path/'started.json') for path in (original_path, repair_path))
        require(all(item.get('response_received') is True and not item.get('error') for item in (original_receipt, repair_receipt)),
                'original_and_new_adoption_META_receipts_must_both_remain_closed')
        require(utc(original_started['utc']) <= utc(original_receipt['utc']) <= utc(repair_started['utc']) <= utc(repair_receipt['utc']),
                'known_original_analysis_must_remain_closed_before_fresh_representative_choice')
        original_analysis_starts.append(utc(original_started['utc']))
        cost_subsets.append({'source_event': case['source_event'], 'repair_event': case['repair_event'],
                             'selected_duplicate_index': case['selected_duplicate_index'],
                             'original': {'usage': original_receipt.get('usage'), 'elapsed_s': original_receipt.get('elapsed_s'),
                                          'charged_cny_proxy': original_receipt.get('settlement', {}).get('charged_cny')},
                             'fresh_choice': {'usage': repair_receipt.get('usage'), 'elapsed_s': repair_receipt.get('elapsed_s'),
                                              'charged_cny_proxy': repair_receipt.get('settlement', {}).get('charged_cny')},
                             'already_in_R49_META_totals_once': True, 'add_to_totals_again': False})
    manifest = bundles['chexbench']['manifest']; earliest_original_analysis = min(original_analysis_starts)
    require(read(private/'plan.json')['window_question_ids'] == [row['question_id'] for row in manifest['inputs'][180:210]],
            'known210_assessment_window_semantic_membership_must_remain')
    for row in manifest['inputs'][:210]:
        require(utc(read(bundles['chexbench']['files']['predictions'][row['question_id']])['prediction_saved_at']) <= earliest_original_analysis,
                'first210_committed_predictions_must_precede_known_adoption_analysis_failure')
    return {'recovery_id': 'adoption_1', 'public_tree': public_rel, 'proof': proof, 'review_files': review_files,
            'review_metadata': metadata, 'audit_timing': 'after_generation_before_publication',
            'single_final_review_shared_with_result_claim_review': True, 'additional_prelaunch_DeepSeek_request_required': False,
            'initial_user_directed_audit_deferral_preserved': True, 'initial_deferred_marker_is_reviewer_ready_claim': False,
            'actual_final_review_scope_complete': True, 'actual_final_review_audit_scope': metadata['audit_scope'],
            'preserved_committed_questions': 210, 'preserved_completed_windows': 6,
            'model_chosen_original_entry_indices': {case['source_event']: case['selected_duplicate_index'] for case in cases},
            'selected_original_status_step_and_evidence_unchanged': True, 'other_unique_entries_unchanged': True,
            'original_ANALYZE_and_MUTATE_inputs_preserved': True, 'assessment_only_overlay': True,
            'per_dataset_analysis_amendments': amendments, 'non_additive_META_cost_subsets': cost_subsets,
            'saved_repair_resource_subset': resources, 'new_meta_repair_requests': 2,
            'extra_Agent_embedding_tool_calls_for_repair': 0, 'extra_ordinary_analysis_calls': 0,
            'automatic_future_repair': False, 'operational_prompt_and_credit_attribution_change_confound': True,
            'unchanged_output_semantics_or_original_static_protocol_claim': False, 'clinical_or_Skill_causality_claim': False,
            'all_attempts_exited_zero_claim': False, 'adoption_stop_and_repair_wall_seconds': None}


def change(row, baseline):
    before, after = row['arms'][baseline]['aligned_correct'], row['arms'][ARM]['aligned_correct']
    return '纠正' if after and not before else '误改' if before and not after else '同对' if after else '同错'


def sentence(ds, s):
    spec = SPEC[ds]; name = spec['baseline']; before, after = s['arms'][name], s['arms'][ARM]; pair = s['comparisons'][name]
    return (f"{spec['label']}：{name} {before['correct']}/{spec['n']}→R49 {after['correct']}/{spec['n']}"
            f"（{pct(before['micro_pct'])}→{pct(after['micro_pct'])}），"
            f"{pair['corrected']}纠正／{pair['harmed']}误改／净{signed(pair['net'])}；"
            f"聚簇95%微平均差区间{interval(pair['confidence']['micro_pp'])}。")


def comparison_table(s):
    return table(['比较臂', '完整分母', '正确数', '微平均／EM', '子集宏平均', 'word recall', '纠正／误改／净增', '微平均差95%簇区间'], [
        [name, arm['n'], arm['correct'], pct(arm['micro_pct']), pct(arm['macro_pct']), pct(arm['word_recall_pct']),
         ('—' if name == ARM else f"{s['comparisons'][name]['corrected']}／{s['comparisons'][name]['harmed']}／{signed(s['comparisons'][name]['net'])}"),
         ('—' if name == ARM else interval(s['comparisons'][name]['confidence']['micro_pp']))]
        for name, arm in s['arms'].items()])


def coverage_table(bundle):
    details = bundle['details']; baseline = SPEC[bundle['summary']['dataset']]['baseline']
    fields = [('首次图像题', lambda d: not d['same_image_hit']), ('此前同图记忆命中', lambda d: d['same_image_hit']),
              ('Skill命中', lambda d: d['skill_hit']), ('Skill未命中', lambda d: not d['skill_hit'])]
    result = []
    for label, predicate in fields:
        rows = [row for row in details if predicate(row)]
        corrected = sum(change(row, baseline) == '纠正' for row in rows)
        harmed = sum(change(row, baseline) == '误改' for row in rows)
        result.append([label, len(rows), sum(row['arms'][baseline]['aligned_correct'] for row in rows),
                       sum(row['arms'][ARM]['aligned_correct'] for row in rows), corrected, harmed, signed(corrected-harmed)])
    return table(['保存结果的描述分组', '完整分母', '历史正确', 'R49正确', '纠正', '误改', '净增'], result)


def make_case_index(bundles):
    lines = ['# R49全量逐题正负证据索引', '',
             '三份清单分别列出，所有题均新生成；不把848条当独立病例。不按正确性挑例，包含全部纠正、误改、同对、同错和合法重复无进展空答。此页在完整评分后含标注与正确性。', '']
    for ds in DATASETS:
        b = bundles[ds]; baseline = SPEC[ds]['baseline']; base = f'evidence/{ds}/'
        lines += ['## ' + SPEC[ds]['label'], '',
                  link('原图／派生图清单', base+'image_assets.json') + ' · ' + link('历史整臂原始终态', base+'comparison_sources.json') + ' · ' + link('逐题评分', 'results/'+ds+'/per_question.json'), '',
                  '| 顺序／题号 | 问题与全部选项 | 参考 | 历史→R49显式答案／EM | 变化／覆盖 | 原图／预测 | 上下文／时序 | 实际请求／工具／窗口 |',
                  '|---|---|---|---|---|---|---|---|']
        for ordinal, row in enumerate(b['details'], 1):
            qid = row['question_id']; input_row = b['inputs'][qid]; ctx = read(b['files']['contexts'][qid])
            options = '<br>'.join(cell(k)+'. '+cell(v) for k, v in (input_row.get('options') or {}).items())
            question = cell(input_row['question']) + ('<br>'+options if options else '')
            reference = cell(row['reference'])
            if row['reference'] in (input_row.get('options') or {}):
                reference += '. '+cell(input_row['options'][row['reference']])
            answers = cell(row['arms'][baseline]['explicit_answer'])+'→'+cell(row['arms'][ARM]['explicit_answer'])
            answers += '<br>EM '+str(int(row['arms'][baseline]['aligned_correct']))+'→'+str(int(row['arms'][ARM]['aligned_correct']))
            images = ' · '.join(link('原图'+str(i), base+name) for i, name in enumerate(input_row['images'], 1))
            pred = link('不可覆盖预测', base+f'predictions/{ARM}/{qid}.json')
            timing = ' · '.join(link(label, base+folder+'/'+qid+'.json') for label, folder in
                                [('当时Skill与同图上下文', 'contexts'), ('保存事件', 'prediction_events'), ('其后反馈', 'feedback'), ('步骤', 'steps')])
            calls = b['evidence']/'services/calls/R49-AGENT'/qid
            require(calls.is_dir(), 'all_fresh_question_actual_request_directory_required:'+qid)
            actual = link('全部实际主请求／回复／费用', base+f'services/calls/R49-AGENT/{qid}')
            tool = b['evidence']/'services/tool_selections/R49-AGENT'/qid
            if tool.is_dir():
                actual += ' · '+link('工具选择及cache键', base+f'services/tool_selections/R49-AGENT/{qid}')
            actual += ' · '+link('窗口快照／学习轨迹／事件', base+f"windows/{row['window']:04d}")
            coverage = change(row, baseline)+f"／窗口{row['window']+1}／Skill{len(ctx['selected_skills'])}／此前同图{len(ctx['same_image_ids'])}"
            lines.append('| '+' | '.join([f'{ordinal}／{cell(qid)}', question, reference, answers, coverage, images+' · '+pred, timing, actual])+' |')
        lines.append('')
    return '\n'.join(lines)+'\n'


def make_dataset(ds, b, extra):
    s = b['summary']; base = f'evidence/{ds}/'
    subset_rows = [[name, subset, value['n'], value['correct'], pct(value['accuracy_pct'])]
                   for name, arm in s['arms'].items() for subset, value in arm['subsets'].items()]
    ci_rows = [[name, interval(pair['confidence']['micro_pp']), interval(pair['confidence']['macro_pp']),
                json.dumps(pair['confidence'].get('subset_pp', {}), ensure_ascii=False)] for name, pair in s['comparisons'].items()]
    diagnostics = [[name, arm['answer_absent'], arm['domain_invalid'], arm['raw_whole_json_valid'],
                    arm['legacy_M_contract_compliant'], json.dumps(arm['extraction_counts'], ensure_ascii=False)]
                   for name, arm in s['arms'].items()]
    windows = [[w['window']+1, w['questions'], w['correct'], w['skill_hit_questions'], w['active_skills'],
                link('快照／轨迹／蒸馏／治理', base+f"windows/{w['window']:04d}")] for w in s['windows']]
    lineage = [[sid, v['name'], v['branch'], v['status'], v['utility'], v['usage'], v['prior_versions'], ', '.join(v['source_ids'])]
               for sid, v in extra['final_skill_lineage'].items()]
    lineage_text = table(['Skill', '名称', '分支', '最终状态', '效用', '采用次数', '历史版本数', '来源题号'], lineage) if lineage else '最终Skill库为空，原样报告；没有人工补卡。'
    return f'''## {SPEC[ds]['label']}：完整{SPEC[ds]['n']}题

{sentence(ds, s)}

{comparison_table(s)}

历史比较来自固定完整整臂；本轮所有题均新生成，原图首次题也可能受此前跨病例Skill影响。R47只作CheX的在线同图真值反馈次要参照；不以较弱参照替代原无反馈最好整臂。

{table(['臂', '完整子集', '分母', '正确数', '准确率'], subset_rows)}

{table(['历史比较臂', '微平均差95%簇区间', '子集宏平均差95%簇区间', '逐子集区间（pp）'], ci_rows)}

区间直接引用保存评分器的10000次配对图像／可用patient-study关联簇bootstrap；不重评分。顺序依赖、在线反馈和已曝光数据使这些区间只具描述性，不证明未见患者泛化或同期因果效应。

{coverage_table(b)}

Skill命中{s['skill_hit_questions']}/{s['questions']}，此前同图记忆命中{s['same_image_hit_questions']}/{s['questions']}；最多注入{extra['max_selected_skills']}条Skill、{extra['max_same_image_context_entries']}条同图前缀。覆盖分组和窗口分数是事后描述，不是按正确性选用的方法。窗口内使用起始快照，末窗口进化不能改变已完成预测。

{table(['窗口（1起）', '题数', '正确', 'Skill命中题', '窗口后活跃／成熟Skill', '完整证据'], windows)}

{lineage_text}

{table(['臂', '缺显式答案', '答案域冲突', '完整原生JSON', '旧M特定契约', '提取机制'], diagnostics)}

JSON为单独接口诊断，主指标使用共同显式答案与作者答案口径。无答案、冲突和重复无进展记录保留，不从reason或参考猜答。实际终态计数：{json.dumps(extra['terminal_status_counts'], ensure_ascii=False)}。

全部正负例见[CASE_INDEX](CASE_INDEX.md)；[实际资源](RESOURCE_SUMMARY.json)、[保存评分summary](results/{ds}/summary.json)、[公开语义重算](public_reproduction/{ds}/summary.json)、[全部原始证据]({base})均保留。工具名称与次数：{json.dumps(extra['tool_selections_by_name'], ensure_ascii=False)}。有记录不等于医学解释正确；同模型Skill Review和采用归因不是独立临床核实。
'''


def resource_table(bundles):
    values = []
    for ds in DATASETS:
        r = bundles[ds]['summary']['resources']
        for name, key in [('主推理', 'agent'), ('元学习／筛选／治理', 'R49_META'), ('Embedding', 'embedding')]:
            x = r[key]
            tokens = (str(x.get('prompt_tokens'))+'／'+str(x.get('completion_tokens'))) if key != 'embedding' else str(x.get('total_tokens'))
            values.append([SPEC[ds]['label'], name, x['requests'], tokens, x['usage_cost_cny_proxy_known'],
                           x['cost_unknown_count'], num(x['elapsed_seconds_known']), x['elapsed_unknown_count']])
    return table(['数据集', '独立资源类别', '实际请求', '输入／输出token或总token', '已知CNY费用代理小计', '费用未知请求', '已知请求秒数之和', '耗时未知请求'], values)


def make_readme(bundles, extras, resource, review):
    sentences = '\n\n'.join(sentence(ds, bundles[ds]['summary']) for ds in DATASETS)
    tool_rows = [[SPEC[ds]['label'], (r := bundles[ds]['summary']['resources']['tools'])['logical_calls'], r['cache_hits'],
                  r['fresh_backend_attempts'], r['healthy_backend_attempts'], r['registered_failed_historical_attempts'],
                  num(r['backend_compute_seconds_known']), extras[ds]['fresh_tool_backend_time_unknown_count'], r['failed_or_unknown_tools'],
                  num(extras[ds]['recorded_request_span_seconds'])] for ds in DATASETS]
    m = review['metadata']; probe_value = resource['separate_embedding_probe']; repair = resource['dependency_recovery']; cuda = resource['cuda_recovery']; schema = resource['meta_schema_recovery']; fields = resource['mutation_fields_recovery']; embed = resource['embedding_http_recovery']; phrase = resource['phrase_guard_recovery']; adoption = resource['adoption_recovery']; scoring_provenance = resource['offline_scoring_provenance']
    variants = [[SPEC[ds]['label'], (v := fields['per_dataset_prompt_amendments'][ds])['ordinary_mutation_requests'],
                 v['original_system_requests'], v['clarified_system_requests'], len(v['protected_original_events']),
                 v['extra_ordinary_meta_calls']] for ds in DATASETS]
    embedding_rows = [[SPEC[ds]['label'], (e := bundles[ds]['summary']['resources']['embedding'])['requests'],
                       e['successful_responses'], e['registered_http_failed_attempts'], e['usage_unknown_count'],
                       e['total_tokens'], e['cost_unknown_count']] for ds in DATASETS]
    phrase_rows = [[SPEC[ds]['label'], (p := phrase['per_dataset_policy_amendments'][ds])['amendment']['activation_committed_questions'],
                    p['legacy_saved_selections'], p['legacy_healthy_cache_selections'], p['guarded_new_selections'],
                    p['guarded_cache_selections'], p['guarded_physical_attempts'], p['masked_eos_steps']] for ds in DATASETS]
    analysis_rows = [[SPEC[ds]['label'], (a := adoption['per_dataset_analysis_amendments'][ds])['amendment']['activation_committed_questions'],
                      a['ordinary_analysis_requests'], a['original_system_requests'], a['clarified_system_requests'],
                      len(a['protected_original_events']), a['extra_ordinary_meta_calls']] for ds in DATASETS]
    sections = '\n\n'.join(make_dataset(ds, bundles[ds], extras[ds]) for ds in DATASETS)
    score_attempt_rows = [[SPEC[ds]['label'], (s := scoring_provenance['datasets'][ds])['native_score_invocations'],
                           s['completed_metric_calculations'], s['pre_adaptation_failed_invocations'],
                           link('原始凭证', s['score_receipt'])] for ds in DATASETS]
    return f'''# R49：同图真值反馈＋在线窗口Skill，全量三清单结果

{sentences}

以上保留实际正负结果，无增分也不改变运行记录。三份清单分别报告：618、114、116，共848个新生成题目级记录，不合成848个独立病例的总体准确率。最终原runner的三组实际原始退出均为0，最后一次adoption_1接续controller也退出0；首次依赖故障、后续CUDA、两次元学习schema、Embedding、MAIRA及采用归因校验中断的原始退出1与日志全部保留，不能说所有尝试都退出0。冻结运行源文件未改，但下文列明操作wrapper、提示、故障闭合例外、MAIRA生成策略及采用归因接口修订；完整生成后统一答案口径评分、导出和公开语义重算，没有靠评分解析放宽或历史答案填充获得结果。

## 已完成组的离线评分与来源

用户要求每组完整结束后先报告该组结果，后续数据集照冻结方案继续。各组summary／per_question已保存后在此原样复用，没有第二次私有指标计算或据此改后续推理。CheX首次进入原生评分函数在输入路径门槛失败：公开别名`assets/...`与真实运行清单的`images/...`不一致，发生于ALL-arm适配、参考／feedback／complete正文读取之前，未产生分数。保存原始started／退出1故障元数据后，只复制一次实际canonical源inputs并显式接续同一已知前置失败；原生gate、解析和指标不改，预测不改，模型调用0。故函数进入次数与完整指标计算次数分别报告，不能把首个失败称另一套已完成成绩。

{table(['数据集', '原生评分函数进入次数', '完整指标计算次数', '适配／标签前失败', '已保存score receipt'], score_attempt_rows)}

来源路径、原始失败／显式接续、逐组pull／score与最终控制拉取凭证见[离线评分来源说明](OFFLINE_SCORING_PROVENANCE.md)。CheX实际成功评分的input目录与references文件为两个独立来源，复现页从真实receipt记录读取，未由目录命名猜测。公开语义重算另列，不更改历史私有成绩。

## 信息条件与方法

唯一新方法`{ARM}`，所有题新生成，各数据集空Skill／空同图记忆冷启动。主与元调用qwen3.7-plus，.2／.95／2048／thinking=false；主／工具调用次数无固定上限，以合法终答、三次重复无进展、技术异常终止。窗口30、buffer20、三分支top6、每两窗口治理。过去同图原模型答案／理由／健康工具证据保持原样，预测及保存事件完成后才揭示本题标注，供后续同图题和窗口学习。没有当前／未来真值或其他数据集的Skill／病例传入。

R49为R47式在线记忆与SkeMex启发的项目适配，非官方SkeMex、Evo-MedAgent或历史M43执行器的完整复现。解除了旧预算并改变循环，没有同期无Skill对照。历史记录、信息优势、调用资源、采样／时段共同变化，差值不能单独归因Skill；同模型Analysis／Review和采用信用不证明临床正确或因果归因。[方案](PLAN.md) · [实际协议](PROTOCOL.json) · [来源与限制](METHOD_AND_LIMITS.md)。

CheX保留488图组／130后续题，五跨子集同图组十题；另列SLAKE30图组、VQA58图组。SLAKE114与CheX-SLAKE123同源共享17图、64相同图像＋措辞题，114中73题位于共享图像；没有论文精确114题号核验。VQA同图复述按图聚簇。三清单已有反复开发暴露，不称未见测试、闭卷SOTA、同预算因果收益或稳定医学泛化。原无在线反馈最好完整记录466／108／100仍按原条件单列，R47在线GT468/618也保持独立记录。

{sections}

## 实际费用、时间与未知项

{resource_table(bundles)}

{table(['数据集', '生产Embedding物理请求', '成功向量回复', '已登记SDK400失败', 'usage未知请求', '已知token小计', '费用未知请求'], embedding_rows)}

生产Embedding保留原000063的失败和新000063_arrearage_1的健康回复，分别计一次；旧失败没有usage或已保存HTTPbody，不能把表中的已知token／CNY小计读作其用量或费用为0。新健康回复已经在生产Embedding请求和费用中，不再附加一份“恢复费用”。

{table(['数据集', '逻辑工具', 'cache命中', '物理生产尝试', '健康物理尝试', '已登记历史失败尝试', '已知生产后端计算秒', '后端耗时未知尝试', '活跃失败／未知工具', '已记录请求时段秒'], tool_rows)}

Embedding请求未定价的条目按未知列出，已知小计0不能读作免费。另有唯一开跑前接口探针，text-embedding-v4／1024维，{probe_value['known_total_tokens']}tokens、{num(probe_value['assessment'].get('elapsed_s'))}秒、0医学题／0主请求；仅计一次，不混入三个流的请求。该探针费用未提供，保持未知，不另估单价。医学工具用时没有币价则保持未定价，缓存命中不重复计算后端尝试。

R49_META费用／请求总量保留两次原无效schema回复及各自一次独立新澄清回复，每份实际请求各计一次；下文两次故障所列费用只是该总量的非附加子集，不能再次加费。普通MUTATE字段提示不新增普通事件调用，其提示token仍按实际用量计费。没有把无效旧回复改记免费，也没有把额外学习调用漏报为主Agent免费能力。

CheX物理工具尝试包含原始已关闭CUDA失败和本次MAIRA未闭合格式失败，各一次；两份登记的健康生产尝试已在活跃健康cache中分别计数，不能再加一次。逻辑工具仍按题目选择槽位计数，未来同身份健康cache复用只计命中。活跃失败工具为0不代表所有历史物理尝试都成功。另有一次隔离CUDA诊断，实际{cuda['isolated_diagnostic']['tool_invocations']}次工具、{num(cuda['isolated_diagnostic']['elapsed_s'], 6)}秒，主／元／Embedding API均0，诊断输出没有进入生产推理，且不计入物理生产尝试；其硬件成本未知，独立披露。

本次MAIRA原失败生产尝试耗时{num(phrase['original_failure_elapsed_s'], 9)}秒，其中保存的后端计算时间{num(phrase['original_failure_backend_elapsed_s'], 8)}秒，已在生产物理尝试账内一次计入。独立MAIRA格式诊断另有{phrase['isolated_diagnostic']['tool_invocations']}次工具调用、{num(phrase['isolated_diagnostic']['elapsed_s'], 6)}秒，实际失败；其输出仅供故障定位，没有进入生产上下文、不计入生产尝试，主／元／Embedding API均0，硬件费用未知。诊断不是一次成功工具结果，也不与健康生产尝试合并或重复计算主模型费用。

另有一次中性Embedding欠费诊断：{embed['neutral_diagnostic']['embedding_requests']}次请求、HTTP{embed['neutral_diagnostic']['http_status']}、错误码{embed['neutral_diagnostic']['error_code']}、{num(embed['neutral_diagnostic']['elapsed_s'], 6)}秒；它失败退出1，没有健康向量，usage和费用均未知，不计入生产Embedding总数，也不替代原000063的缺失HTTPbody。主Agent／META／胸片工具／本地GPU调用均0。该次诊断与早先13token健康接口探针是两次不同的调用，分别记录，不能混称健康探针。

主／元／Embedding已知CNY代理小计总和为{resource['resource_totals_only']['usage_cost_cny_proxy_known']}；尚有{resource['resource_totals_only']['cost_unknown_count_including_probe_and_billing_diagnostic']}条未定价请求（包含早先健康接口探针与单独失败欠费诊断），所以不提供虚假的完整总费用。token表沿评分器已知字段求和；缺失usage的请求数量在RESOURCE_SUMMARY逐组另列，0不能补作已知用量。工具硬件成本、供应商发票、未记录GPU等待／controller总墙钟均未知。各类请求耗时之和不是墙钟；“已记录请求时段”只指最早发送到最晚回复，不能冒充完整生成时长。完整原字段、状态、Skill谱系、窗口事件与未知口径均见[RESOURCE_SUMMARY](RESOURCE_SUMMARY.json)。

## 审阅、故障与复现边界

首次controller2277353／CheX进程2277359在第一题`{repair['first_question']}`的预测、保存事件及自身反馈均完成后，于已完成题的学习奖励适配处报`ModuleNotFoundError: cxr_author_alignment`，原始退出1。此时只有第一题，3次主请求全部闭合、2次工具健康，尚无元学习／Embedding请求或第二题。原因是部署只复制了推理依赖，缺少在线奖励使用的既有答案适配模块；按原样补齐该模块，未修改runner、Skill规则、模型、配置、题序、标签或已保存输出。独立窄范围DeepSeek接续审阅就绪后使用单次守卫恢复，同一输出目录读取第一题既有预测／事件／反馈，构建其轨迹再继续，不重新作答或重复读取第一题标注。该次依赖接续后来又因下面的CUDA问题退出1，作为中间失败保留；最终原始退出0来自后续登记操作恢复，不是把依赖接续本身改记成功。

[依赖故障与恢复说明]({repair['review_files']['explanation']}) · [实际接续审阅原文]({repair['review_files']['raw']}) · [接续审阅元数据]({repair['review_files']['metadata']}) · [完整恢复树]({repair['public_tree']}) · [首次退出1／日志／原manifest]({repair['public_tree']}/original)。恢复后各组仍由原冻结runner完整运行至实际原始退出0，没有effective exit、自动技术空答或吞任意异常；首次失败不被改记成功。第一题3次主请求费用代理已知小计{repair['first_question_main_usage_cost_cny_known']}CNY、费用未知{repair['first_question_main_cost_unknown_count']}条，已知主请求时间合计{num(repair['first_question_main_elapsed_seconds_known'])}秒、时间未知{repair['first_question_main_elapsed_unknown_count']}条；它们和2次工具均已包含在CheX资源总量中一次，不能再加算。窄范围接续审阅实际{repair['review_metadata']['duration_ms']}ms、CLI估算USD={repair['review_metadata'].get('CLI_estimated_USD')}，与主模型CNY分列，不冒充发票。失败前后完整墙钟及部署修复墙钟若没有独立时间记录则保持未知；跨中断的请求时段仍按其实际跨度披露。

随后已完成前{cuda['preserved_completed_prefix_questions']}题和一个窗口，第{cuda['question_ordinal']}题`{cuda['question_id']}`在原主计划回复后，expert工具产生已关闭的`CUDA error: device kernel image is invalid`失败，当前题尚未保存预测或揭示自身真值。一次隔离debug诊断健康，但结果仅用于诊断，未写入生产cache或作为推理证据。实际DeepSeek操作审阅后，针对这一确定失败进行了恰好一次原始生产参数复试，关闭debug环境标志；仅复试健康后登记`r49_registered_cuda_retry_v1`并将当前工具槽位解析到`<oldkey>_cuda_1`健康cache。原坏cache和原选择归档保持不变，未来只有同后端／revision／原图路径／参数的精确登记身份可复用该健康cache。冻结八份推理源文件未改，但一次生产复试和登记cache解析覆盖属于明确的操作协议修订，不应说执行完全没有变化。

[CUDA操作修订说明]({cuda['review_files']['explanation']}) · [实际操作审阅]({cuda['review_files']['raw']}) · [元数据]({cuda['review_files']['metadata']}) · [操作helper源码]({cuda['review_files']['helper']}) · [完整恢复树／原始失败与诊断]({cuda['public_tree']}) · [GEN登记](evidence/chexbench/failure_events/cuda_1_registration.json) · [原失败选择归档](evidence/chexbench/failure_events/cuda_1_original_selection.json)。操作审阅实际{cuda['review_metadata']['duration_ms']}ms、CLI估算USD={cuda['review_metadata'].get('CLI_estimated_USD')}，单独报告。前40个预测不重生成，第41题既有主计划只复用已保存的第一条回复，不重发；该主请求费用代理{cuda['known_q41_plan_usage_cost_cny_proxy']}CNY、耗时{num(cuda['known_q41_plan_elapsed_seconds'])}秒，若缺失则未知，均已在主模型总量中一次计入。工具失败与复试的已知计算／经过时间及未知项沿实际资源原字段保留，隔离诊断另列。debug成功或生产复试健康均不能确定根因，更不能声称CUDA问题永久修复。未知发送、其他失败和新增错误不在这一登记例外内；没有自动技术空答或未登记重试。

CUDA接续在第4个窗口、120个已保存预测与反馈之后再次停止：`{schema['source_event']}`返回PATCH，但`patch_section="c"`表示整个内容容器，不在原六个允许的单字段集合内，冻结进化代码因此报`ValueError: invalid_patch_section`。前120题、前三个已完成窗口及此前CUDA登记仍保留，尚未产生第121题上下文或作答。此处旧回复已收到、付费凭证闭合，属于已知元学习schema失败，不是未知发送，也不是模型题目答案被判错后重答。

经实际窄范围DeepSeek审阅后，只为这一已知事件新增一次独立META请求`{schema['repair_event']}`：使用完全相同的已完成历史payload，追加schema说明，没有新病例、当前／未来真值或额外临床信息；PATCH只能保留同一目标并选择原六个合法字段，也允许模型依据原证据真实返回NONE，不由操作方把无效响应强制改成NONE。本次实际新控制输出为{json.dumps(schema['repair_control'], ensure_ascii=False)}。冻结evolve的合法性验证／质量审查不改，只有这一事件的服务路由增加明确登记的schema澄清；随后仍接受原Review，不借此跳过后续失败。

[META恢复方案与边界]({schema['review_files']['explanation']}) · [真实操作审阅]({schema['review_files']['raw']}) · [元数据]({schema['review_files']['metadata']}) · [helper源码]({schema['review_files']['helper']}) · [完整恢复树／原始失败]({schema['public_tree']}) · [GEN登记](evidence/chexbench/failure_events/meta_schema_1_registration.json)。实际操作审阅{schema['review_metadata']['duration_ms']}ms、CLI估算USD={schema['review_metadata'].get('CLI_estimated_USD')}，与主／元模型CNY分列。原无效回复和新回复的实际token／费用／耗时分别见RESOURCE_SUMMARY的`non_additive_META_cost_subsets`；二者都已包含在R49_META总账一次。额外主Agent／Embedding／医学工具调用均0，不重新生成120题、重复揭示其标签或重跑前三个窗口；原CUDA cache覆盖继续生效，未再次运行CUDA生产复试。该次meta_schema_1接续后来在150题后的第五窗口再次因下述schema失配退出1，也作为中间失败保留；最终完整0不来自把这一尝试改记成功。学习接口格式恢复不算医学正确率增益，不能据此声称改进稳定性或临床能力已证明。

在150个已提交预测／反馈、四个完整窗口之后，`{fields['source_event']}`再次给出PATCH，但字段为`content`而不是原六个允许字段，冻结校验仍以`invalid_patch_section`停止。实际操作审阅通过后，仅为这一已知、已闭合事件独立新增一次同历史payload、同一目标的schema澄清请求`{fields['repair_event']}`；实际新控制为{json.dumps(fields['repair_control'], ensure_ascii=False)}，只能是合法单字段PATCH或模型真实NONE，不能操作方强行NONE。原无效回复、两份请求回复及两份费用均保留；不重生成150题、重读其标签或重跑前四个已提交窗口，不重新执行此前CUDA生产复试。

这次操作还在三个数据集的普通MUTATE边界明确原六字段，禁止把`c`／`content`整个容器当字段。仅当事件名精确等于`mutation_`＋既有payload轨迹题号且原system为MUTATE时应用；原payload、模型参数和临床规则不变。已缓存的原提示变体按冻结保护清单回放，后续未缓存普通事件只增加固定字段说明，没有额外调用。CheX在150题处激活，另列SLAKE和VQA从各自冷启动时激活；不是把CheX Skill库传给后两组。任何后续新无效输出仍然停止，没有自动修复循环。这是明确的运行中操作提示变更，不能再称整个流自始至终遵循同一原始静态提示，收益归因更受混杂限制。

{table(['数据集', '实际普通MUTATE请求', '原始system请求', '澄清system请求', '保护原缓存事件数', '提示澄清额外调用'], variants)}

[字段修订方案]({fields['review_files']['explanation']}) · [实际操作审阅]({fields['review_files']['raw']}) · [元数据]({fields['review_files']['metadata']}) · [helper源码]({fields['review_files']['helper']}) · [完整恢复树／150题失败边界]({fields['public_tree']}) · [第二次特定事件登记](evidence/chexbench/failure_events/meta_schema_2_registration.json)。各组`failure_events/mutation_fields_2_amendment.json`保留激活点、提示全文与保护事件清单，恢复树`amendments`下保留相同声明。实际操作审阅{fields['review_metadata']['duration_ms']}ms、CLI估算USD={fields['review_metadata'].get('CLI_estimated_USD')}，单独报告。第二次旧／新META用量与费用在RESOURCE_SUMMARY的独立非附加子集中显示，已在R49_META总量一次计入。该次字段修订接续后来在同一150题边界遇到下面的Embedding失败，其controller／CheX原始退出1同样保留；最终完整0不来自改写这一尝试。提示接口恢复不证明医学能力或稳定涨点，也不意味着CUDA根因已修复。

上述字段修订实际取得第二次合法PATCH回复后，在同一150题边界的Embedding000063又因SDK `BadRequestError`停止，fields2 controller／CheX原始退出1也保留。原记录没有response.json、HTTPbody或usage；400仅来自已安装SDK异常类别的状态码约定。后来一次中性诊断返回400／Arrearage，只能证明该次诊断时账户欠费，不能把它的body冒充原000063响应或据此重建原请求的具体服务器原因。

用户明确确认DashScope充值且实际新操作审阅就绪后，仅为原000063相同input／model／端点，以安装SDK的原缺省参数新增一次生产Embedding请求000063_arrearage_1。没有修改文本、模型、encoding_format参数或临床规则；收到真实有限1024维健康向量后，只为登记的精确身份建立别名，诊断结果从未用作向量。原失败请求／started／result和缺失body保持原样；不制造旧response.json。启动及最终闭合校验也只有这一份明确登记、已封存的SDK400失败例外，其它未知发送／失败仍立即停止，不能说原来的所有闭合规则完全未变。150个预测、前四个完整repo和此前CUDA／两次META包装器均保留；生产Agent／META／医学工具没有因这次修复新增调用。

[Embedding恢复方案]({embed['review_files']['explanation']}) · [实际充值后操作审阅]({embed['review_files']['raw']}) · [元数据]({embed['review_files']['metadata']}) · [helper源码]({embed['review_files']['helper']}) · [完整恢复树／原失败／单独诊断／充值标记]({embed['public_tree']}) · [GEN登记](evidence/chexbench/failure_events/embedding_arrearage_1_registration.json) · [原失败语义归档](evidence/chexbench/failure_events/embedding_arrearage_1_original_failure.json)。操作审阅{embed['review_metadata']['duration_ms']}ms、CLI估算USD={embed['review_metadata'].get('CLI_estimated_USD')}，仍与生产CNY分列。原失败费用未知，健康新请求已包含在生产Embedding总量一次；单独失败诊断的费用也未知。该次embedding_arrearage_1接续后来在168题／5个完整窗口处遇到MAIRA未闭合格式错误，其controller2645757／CheX2645763原始退出1同样保留。恢复可用性和接口成功不算医学正确率增益，也不证明原错误具体原因、后续资金持续充足或CUDA根因已解决。

## MAIRA未闭合格式与显式生成策略修订

第169题`{phrase['question_id']}`的原MAIRA生产调用已明确失败。独立诊断在原设置下实际生成13token即EOS，生成后缀含`<obj>`而没有`</obj>`；两者在原tokenizer中都不是special，结束标签未曾生成，不能归因于decode过滤。13token未达到原max300上限，原processor严格断言拒绝。诊断用于定位这一机制，不能补标签、补box、猜阴性，不能当作同图医学观察，也未复用其输出。

实际新操作审阅通过后，`phrase_guard_1`对CheX第168个已提交预测、5个完整窗口之后的全部**新物理MAIRA调用**统一启用EOS守卫；另列SLAKE和VQA从各自冷启动启用。只根据新生成后缀的obj／box未闭合状态屏蔽EOS，其余logit不改，原input／model／量化／主prompt／max300与严格原parser保持；不强制生成标签、box、发现或阴性，不作解析回退。若守卫后仍未闭合、未正常EOS或原parser拒绝，继续技术停止，没有自动重试循环。第169题仅一次新guarded生产尝试，旧失败cache／旧selection与其原始耗时完整保留；此前168题及五个完整窗口、该题已保存主调用均没有重做，所有先前恢复包装器继续保留。

旧健康cache和已有选择保持legacy policy，不改写为新策略产物。新策略仅覆盖激活后的新物理调用，因而全流混合旧／新生成策略；本次是**自定义generation-policy amendment**，不是官方MAIRA修复，也不是与原设置相同的重试。EOS屏蔽可能改变后续文本、坐标、调用耗时和正确性，不能声称语义不受影响、医学能力获得独立验证，或把在线反馈／Skill／预算／提示／生成策略混合变化的差值作单一因果归因。

{table(['数据集', '激活前已提交题数', '保留旧MAIRA selection', '复用legacy健康cache选择', '新guarded选择', '复用guarded cache选择', 'guarded物理尝试', '实际屏蔽EOS步数'], phrase_rows)}

[EOS守卫恢复方案]({phrase['review_files']['explanation']}) · [实际操作审阅]({phrase['review_files']['raw']}) · [元数据]({phrase['review_files']['metadata']}) · [helper源码]({phrase['review_files']['helper']}) · [EOS policy源码]({phrase['review_files']['policy']}) · [完整恢复树／168题失败边界／独立失败诊断]({phrase['public_tree']}) · [GEN复试登记](evidence/chexbench/failure_events/phrase_guard_1_registration.json) · [旧selection归档](evidence/chexbench/failure_events/phrase_guard_1_original_selection.json)。操作审阅{phrase['review_metadata']['duration_ms']}ms、CLI估算USD={phrase['review_metadata'].get('CLI_estimated_USD')}，与生产CNY分列。该次phrase_guard_1继续至210个已提交预测／反馈、六个完整窗口后，因下述采用归因校验停止；controller2722301／CheX2722307原始退出1同样保留，不将此中间尝试改记0。

## 两次采用归因代表项选择与完成后审计

窗口0006的两个原ANALYZE事件`analysis_chexbench_slake_0081`／`analysis_chexbench_slake_0082`，分别为同一个已注入Skill给出了两条同为ADOPTED_POSITIVE、但step_index和evidence不同的采用项。这些不是完全相同的重复记录；原assess的唯一Skill约束以`duplicate_skill_adoption`停止，尚无第211题，也没有该窗口已提交repo／events。原回复、请求、费用、210题及前六个完整窗口保持。

只对这两个已闭合已知事件，各新增一次独立META请求。模型只能返回`selected_duplicate_index`为0或1，选择该事件原来的两个重复项之一；不是操作方择优，也不重写任何status、step或evidence。实际选择为{json.dumps(adoption['model_chosen_original_entry_indices'], ensure_ascii=False)}。effective adoption只留下模型选中的完整原项，其余唯一项原样保持；该有效列表仅在原assess边界使用。原ANALYZE原文及MUTATE使用的分析保持，未重跑原窗口的生成／标签揭示或已缓存普通ANALYZE／MUTATE调用。两次新请求与两份原付费回复均已在R49_META总账一次计入，RESOURCE_SUMMARY的adoption_recovery.non_additive_META_cost_subsets仅作拆分、不再相加；无额外主Agent／Embedding／工具调用。

对后续未缓存普通ANALYZE，只在原system／精确事件名边界增加“每个注入skill_id最多一个采用项”的固定说明，原payload和模型配置保留，每次普通事件仍只有一次调用。旧缓存原提示按声明保护清单回放。CheX在210题处激活，另列SLAKE／VQA各自空库冷启动时激活，记忆及Skill仍逐数据集隔离。后续新的不合法采用分析继续停止，不形成自动修复循环。此操作会改变采用证据代表项、信用分配及后续Skill效用轨迹，不能称输出语义不变，或把差值单独归因记忆／Skill的医学能力。

{table(['数据集', '激活前已提交题数', '普通ANALYZE请求', '原system请求', '澄清system请求', '保护原缓存事件数', '普通澄清额外调用'], analysis_rows)}

用户明确指示“这个可以跑完再审计？”。因此本次初始`EXECUTION_AUTHORIZATION.json`如实记录`audit_deferred_until_full_generation`、review_completed=false、scope_complete=false、explicit_user_reply及完成后发布前审计要求；它不冒充外部审阅ready，也不在完成后改写成曾经预审通过。实现检查完成后按现有实验授权继续，所有技术停止条件保留。最终完整848题之后的**同一次**实际DeepSeek结果审阅覆盖adoption_protocol、request_resource_accounting、complete_results_and_claims，scope_complete来自真实审阅结论；这里与下文RESULT_CLAIM审阅是同一次，不额外增加或重复计费。负结果可以如实发布，审阅已完成及范围覆盖不能由性能好坏替代。

[采用项恢复方案]({adoption['review_files']['explanation']}) · [实际完成后的统一审计]({adoption['review_files']['raw']}) · [审计元数据]({adoption['review_files']['metadata']}) · [helper源码]({adoption['review_files']['helper']}) · [完整恢复树／210题失败边界／原始后审授权]({adoption['public_tree']}) · [GEN两次选择登记](evidence/chexbench/failure_events/adoption_1_registration.json)。各组`failure_events/analysis_unique_adoption_amendment.json`保留实际激活点、原提示／说明及保护事件清单。只有最后adoption_1的controller与三组原runner实际原始退出0，全部历史1保持；没有技术空答或effective-exit。

实际用户指定DeepSeek原生Claude Code结果审阅已完成：[原文]({review['paths']['raw']}) · [元数据]({review['paths']['metadata']}) · [结果到声明]({review['paths']['claims']})。CLI返回别名{', '.join(m['modelUsage'])}，{m['duration_ms']}ms／{m['turns']}轮，CLI估算USD={m.get('CLI_estimated_USD')}，不是发票，也不与CNY代理相加。服务别名不构成权重身份鉴证；保留任何负向或部分支持结论，执行ready分数不代替结果审阅。不存在独立完整性／临床审计通过声明。

R48的63题后MAIRA嵌套失败和原始退出1保持独立，不把R49视为其恢复、不填失败题／清缓存／重试旧请求。[全部逐题与窗口证据](CASE_INDEX.md) · [公开复现与实际路径](REPRODUCTION.md)。公开语义重算使用保存的请求回复和统一答案适配，0新推理、无新字节／哈希／像素校验；本地复算不是第三方医学审计。图片／数据来源与适用条件见各组证据，代码许可证不重新许可数据。

本页生成不等于GitHub发布完成；只有实际推送且main核验成功后才报告发布完成。
'''


def make_reproduction(actual, review, repair, cuda, schema, fields, embed, phrase, adoption, scoring_provenance):
    sections = ['# R49公开语义复现与实际路径', '',
                '本页由完成后的实际记录生成；编写器不启动推理、评分、验证器、网络或Git。生成、评分、导出已完成时不重复运行。', '',
                '## 便携公开复算', '',
                '完整公开证据含原始终态、完整输入／标注、窗口快照／学习轨迹、Skill版本、逐请求工具与原图派生图。验证器从公开路径重算已冻结主指标和逐题提取；不需私有run或账户账本，0新推理、无文件／像素摘要门槛。', '']
    for ds in DATASETS:
        sections += [f'```powershell\npython -X utf8 experiments/verify_public_online_skill_r49.py --evidence {REPORT_REL}/evidence/{ds} --out <new-empty-verification-directory-{ds}>\n```', '']
    sections += ['## 实际私有归档与一次性离线步骤', '',
                 '以下路径直接来自完成组的真实score receipt；原始score output原样复用，不授权再次评分／导出或重跑旧基线。实际使用private once-wrapper，所有臂先参考无关适配再读评分标签。下列原生接口仅解释等价参数，不表示又执行了一遍评分。CheX首个前置路径失败与唯一显式接续、以及独立references来源见OFFLINE_SCORING_PROVENANCE.md。', '',
                 '```json\n'+dump(actual).rstrip()+'\n```', '']
    for ds in DATASETS:
        optional = ' --r47-frozen <actual-r47-frozen> --r47-run <actual-r47-generation>' if ds == 'chexbench' else ''
        sections += [f'```powershell\npython -X utf8 experiments/score_online_skill_r49.py --dataset {ds} --data "{actual[ds+"_data"]}" --run "{actual["archive_root"]}/generation/{ds}" --references "{actual[ds+"_references"]}" --out <new-empty-score-directory>{optional}\n```', '']
    sections += ['## 已发生的依赖故障与接续', '',
                 '首次CheX／controller原始退出1，第一题预测／事件／反馈已保存。补齐既有答案适配依赖，经实际窄范围审阅和守卫后从同一已提交前缀继续。第一题3次主请求和2工具没有重做，费用已在主表中一次计入；依赖接续在40题后遇到CUDA故障再次退出1，保留为中间失败。最终完整原runner退出0不抹去这些失败。没有技术空答、effective-exit或R48恢复。', '',
                 link('恢复说明', repair['review_files']['explanation'])+' · '+link('恢复树与初始原始证明', repair['public_tree'])+' · '+link('接续审阅', repair['review_files']['raw'])+' · '+link('实际元数据', repair['review_files']['metadata']), '',
                 '## 一次登记CUDA生产复试', '',
                 'GEN/failure_events的登记与原失败选择、旧坏cache、健康新cache、独立诊断和共享恢复树均保留。只有这一已关闭失败被登记一次原设置生产复试；原40个预测和第41题已有主计划不重做。旧失败另加为一个物理生产尝试，健康复试已包含活跃cache，不重复加算；debug诊断不进入生产尝试或推理上下文。不是根因修复证明。', '',
                 link('操作修订', cuda['review_files']['explanation'])+' · '+link('实际审阅', cuda['review_files']['raw'])+' · '+link('元数据', cuda['review_files']['metadata'])+' · '+link('完整CUDA恢复树', cuda['public_tree']), '',
                 '## 一次META schema澄清与完整恢复链', '',
                 'CUDA接续在120个预测／反馈、3个完整窗口后因已关闭mutation回复PATCH/c停止。保持原无效回复，独立新增一个同历史payload＋schema说明的META事件；只能原目标合法单字段PATCH或模型真实NONE，不能操作方强制NONE。旧、新META均正常计费一次，Agent／Embedding／工具均无额外修复调用。前120题／前三窗口不重跑，恢复wrapper叠加既有CUDAcache路由而不再执行其controller或生产复试。全部先前原始退出1保留，最终完成0不抹去历史失败。', '',
                 link('META方案', schema['review_files']['explanation'])+' · '+link('实际META操作审阅', schema['review_files']['raw'])+' · '+link('META恢复树与原始日志', schema['public_tree']), '',
                 '## 第二次特定事件与普通MUTATE字段提示修订', '',
                 'meta_schema_1在150题／4个完整窗口后遇到PATCH/content再次原始退出1，完整保留。只对这一已知闭合事件新增一份独立schema澄清回复；后续普通MUTATE增加固定原六字段提示，不增加普通事件调用，不改变历史payload或临床规则。三个流均有独立激活声明，CheX旧缓存提示按保护清单回放，SLAKE／VQA各自冷启动。不重做150题／前四窗口，不重新运行CUDA复试；新失败停止，无自动循环。旧、新费用已在META总数中一次计入。', '',
                 link('字段修订方案', fields['review_files']['explanation'])+' · '+link('实际操作审阅', fields['review_files']['raw'])+' · '+link('150题失败与完整新恢复树', fields['public_tree']), '',
                 '## 已知SDK400、独立欠费诊断与一次生产Embedding恢复', '',
                 '原000063仅留SDK BadRequestError类别、started和失败receipt，HTTPbody／usage缺失；不制造原response，也不把后来中性诊断的Arrearage body当原错误。用户确认DashScope充值并经实际新操作审阅后，原input/model/defaultSDK参数只新增000063_arrearage_1一次，真实健康向量才可供精确身份别名。启动／最终闭合检查对这一已封存SDK400作明确登记例外，其它未知或失败仍停止。旧失败和新健康尝试均已在生产Embedding总量一次计入，单独失败欠费诊断另计且费用未知。150题／4repo／此前所有包装器保留，fields2退出1保持；Embedding接续又在168题／5repo后因MAIRA未闭合格式退出1，其controller2645757／CheX2645763的失败原样保留，不能将中间尝试改记0。', '',
                 link('Embedding方案', embed['review_files']['explanation'])+' · '+link('实际操作审阅', embed['review_files']['raw'])+' · '+link('原失败／诊断／充值证明／完整恢复树', embed['public_tree']), '',
                 '## MAIRA格式失败与EOS生成策略修订', '',
                 '原第169题工具生成在13token正常EOS时留下未闭合obj，原closing token非special且根本未生成，未到max300；原parser严格拒绝。独立原设置诊断也失败，其结果不进入生产。保留原坏cache／selection、此前168题／5repo及本题已保存主计划；只登记这一已知闭合失败一次新guarded生产尝试。CheX168后全部新物理MAIRA、另两组冷启动后的全部新物理MAIRA统一在后缀obj／box未闭合时屏蔽EOS；旧健康cache／selection保留legacy。该自定义生成策略可能改变文本／坐标／耗时／正确性，不能称官方方案、原设置相同或语义无影响。没有补标签、强制box、猜阴性或解析回退；max后不完整、未正常EOS或原parser失败仍停止。新生产尝试包含在实际物理工具总量一次，原坏尝试另计一次，独立失败诊断仅单列硬件时间，0主／元／Embedding调用，不重复计算此前主费用。', '',
                 link('EOS守卫恢复方案', phrase['review_files']['explanation'])+' · '+link('实际操作审阅', phrase['review_files']['raw'])+' · '+link('168题失败／独立失败诊断／完整新恢复树', phrase['public_tree'])+' · '+link('实际guard源码', phrase['review_files']['policy']), '',
                 'phrase_guard_1又在210题／六个完整窗口后因duplicate_skill_adoption停止，controller2722301／CheX2722307原始退出1完整保留；原MAIRA守卫及所有更早恢复包装器继续保留。', '',
                 '## 210题采用项代表选择、唯一项提示与完成后统一审计', '',
                 '两个已闭合ANALYZE事件各为同一注入Skill输出两份不同step／evidence的POSITIVE项，不按完全相同重复静默删除。只各新增一次META，返回selected_duplicate_index为0或1；原完整所选项及第三个唯一项原样保留，有效列表只供assess使用。原分析、MUTATE输入、210题／六窗口、缓存请求与全部付费记录保持，不由操作方择优、不重写证据／状态。后续未缓存普通ANALYZE在原事件边界加每Skill至多一项的固定提示，原payload不改、无额外普通调用；新错误继续停。原／新META均已在总量一次计入，非附加拆分不重复加费。', '',
                 '用户明确选择跑完再审计，EXECUTION_AUTHORIZATION.json保留真实deferred verdict、review_completed=false和scope_complete=false，不改写为预审ready。完整848之后，同一次实际RESULT_CLAIM DeepSeek审阅涵盖adoption协议、逐请求资源账与完整结果声明，并有真实scope_complete及audit_scope结论；此处不新增另一份预执行审阅要求。', '',
                 link('采用项恢复方案', adoption['review_files']['explanation'])+' · '+link('完成后实际统一审计', adoption['review_files']['raw'])+' · '+link('实际审计元数据', adoption['review_files']['metadata'])+' · '+link('初始后审授权／210题失败／完整恢复树', adoption['public_tree']), '',
                 '只有最后adoption_1 controller与三组原runner均有实际原始退出0，所有初始／中间1记录均保留；没有effective-exit、技术空答或全尝试健康的主张。', '',
                 '## 解释限制', '',
                 '848题为三个独立重置的题目流，不是848个独立病例；SLAKE同源重叠、CheX跨子集同图与VQA复述保留。历史比较不是同期无Skill反事实。线上学习可在已保存预测后读取自身标签，闭卷准确率、在线反馈准确率与JSON合规分开。最后窗口新Skill不改善本轮既有分数。', '',
                 link('实际结果审阅', review['paths']['raw'])+' · '+link('结果声明', review['paths']['claims'])+' · '+link('完整资源原字段', 'RESOURCE_SUMMARY.json'), '']
    sections += ['## 保存的评分尝试与原始控制记录', '',
                 f"已记录{scoring_provenance['total_native_score_function_entries']}次原生评分函数进入、{scoring_provenance['completed_metric_calculations']}次完整指标计算、{scoring_provenance['pre_adaptation_failed_invocations']}次适配前失败。这里没有评分调用，已保存summary／per_question全部复用。", '',
                 link('真实来源、首个失败／接续及公开凭证清单', 'OFFLINE_SCORING_PROVENANCE.md'), '']
    return '\n'.join(sections)


def replace_block(path, block):
    text = path.read_text(encoding='utf-8-sig')
    wrapped = START+'\n'+block.rstrip()+'\n'+END
    if START in text or END in text:
        pattern = re.compile(re.escape(START)+r'.*?'+re.escape(END), re.S)
        require(text.count(START) == text.count(END) == 1 and len(pattern.findall(text)) == 1,
                'ambiguous_existing_R49_index_block:'+str(path))
        return pattern.sub(lambda _: wrapped, text)
    return text.rstrip()+'\n\n'+wrapped+'\n'


def index_blocks(bundles):
    results = '\n\n'.join(sentence(ds, bundles[ds]['summary']) for ds in DATASETS)
    limits = ('三个流均全部新生成、各自空Skill／同图记忆；此前真值只在原预测保存后释放。在线反馈、解除调用上限、执行循环和运行中MUTATE字段提示修订共同存在，'
              '没有同期无Skill对照，不单独归因Skill。848为题目记录总量，不是独立病例总体；SLAKE17共享图／64匹配题、CheX五跨子集同图组十题及VQA复述均披露。'
              '原无反馈最好466／108／100和R47在线GT468/618原条件保留，不改旧表／旧预测，不称未见测试或官方SOTA。')
    readme = f'**R49：在线同图真值反馈＋窗口Skill，不同信息条件单列（2026-11-08）。**\n\n{results}\n\n{limits} [完整正负结果与证据]({REPORT_REL}/README.md)。'
    findings = f'## 2026-11-08 — R49：三清单在线反馈与窗口Skill\n\n{results}\n\n{limits} [完整逐题正负案例]({REPORT_REL}/CASE_INDEX.md) · [资源与局限]({REPORT_REL}/README.md)。'
    rows = []
    for ds in DATASETS:
        s = bundles[ds]['summary']; before = s['arms'][SPEC[ds]['baseline']]; after = s['arms'][ARM]; p = s['comparisons'][SPEC[ds]['baseline']]
        rows.append([SPEC[ds]['label'], s['questions'], f"{before['correct']}→{after['correct']}",
                     pct(before['micro_pct'])+'→'+pct(after['micro_pct']), pct(after['macro_pct']), pct(after['word_recall_pct']),
                     f"{p['corrected']}／{p['harmed']}／{signed(p['net'])}", interval(p['confidence']['micro_pp'])])
    tables = '## 不同信息与资源条件单列：R49在线GT＋窗口Skill\n\n'+table(
        ['数据集', '完整分母／全新生成', '历史整臂→R49正确', '微平均／EM旧→新', 'R49子集宏', 'R49 recall', '纠正／误改／净增', '微差95%簇区间'], rows)
    tables += f'\n\n{limits} 本块不并入原公平条件排行榜。[完整证据](../cxr_online_skill_r49_20261108/README.md)。'
    manifest = '## R49：已完成在线真值反馈与窗口Skill产物\n\n'
    manifest += '三清单分别完整报告，不合并独立病例准确率；全部848题新生成。下列记录保留正负结果与不同信息条件。\n\n'
    manifest += table(['产物', '范围'], [
        [link('完整结果', REPORT_REL+'/README.md'), '全量宏微、子集、纠正／误改／区间、方法限制'],
        [link('逐题正负证据', REPORT_REL+'/CASE_INDEX.md'), '全部848题各自原图、预测、反馈时序、请求与窗口'],
        [link('实际资源', REPORT_REL+'/RESOURCE_SUMMARY.json'), '主／元／Embedding／工具分账、未知费用与时间'],
        [link('复现说明', REPORT_REL+'/REPRODUCTION.md'), '公开语义复算、0新推理、无新字节门槛'],
        *[[link(SPEC[ds]['label']+'证据', REPORT_REL+'/evidence/'+ds+'/publication_manifest.json'),
           link('公开重算', REPORT_REL+'/public_reproduction/'+ds+'/summary.json')] for ds in DATASETS],
    ])
    return readme, findings, tables, manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--actual-archive-root', default=DEFAULT_ARCHIVE)
    parser.add_argument('--actual-preparation-root', default=DEFAULT_PREP)
    parser.add_argument('--actual-score-receipts-root', default=DEFAULT_SCORE_RECEIPTS)
    parser.add_argument('--actual-public-reporting-provenance-root', default=str(REPORT/'deployment_source/reporting_provenance'))
    parser.add_argument('--public-reproduction-summary-name', default='summary.json')
    parser.add_argument('--result-review', type=Path, default=REPORT/'RESULT_CLAIM_REVIEW.md')
    parser.add_argument('--result-review-metadata', type=Path, default=REPORT/'RESULT_CLAIM_METADATA.json')
    parser.add_argument('--claims', type=Path, default=REPORT/'CLAIMS_FROM_RESULTS.md')
    parser.add_argument('--actual-public-recovery-root', default=str(REPORT/'evidence/recovery/dependency_1'))
    parser.add_argument('--dependency-review', type=Path, default=REPORT/'DEPENDENCY_REPAIR_REVIEW.md')
    parser.add_argument('--dependency-review-metadata', type=Path, default=REPORT/'DEPENDENCY_REPAIR_METADATA.json')
    parser.add_argument('--actual-public-cuda-recovery-root', default=str(REPORT/'evidence/recovery/cuda_1'))
    parser.add_argument('--cuda-review', type=Path, default=REPORT/'CUDA_PRODUCTION_RECOVERY_REVIEW.md')
    parser.add_argument('--cuda-review-metadata', type=Path, default=REPORT/'CUDA_PRODUCTION_RECOVERY_METADATA.json')
    parser.add_argument('--actual-public-meta-schema-recovery-root', default=str(REPORT/'evidence/recovery/meta_schema_1'))
    parser.add_argument('--meta-schema-review', type=Path, default=REPORT/'META_SCHEMA_RECOVERY_REVIEW.md')
    parser.add_argument('--meta-schema-review-metadata', type=Path, default=REPORT/'META_SCHEMA_RECOVERY_METADATA.json')
    parser.add_argument('--meta-schema-explanation', type=Path, default=REPORT/'META_SCHEMA_RECOVERY_PLAN.md')
    parser.add_argument('--actual-public-mutation-fields-recovery-root', default=str(REPORT/'evidence/recovery/mutation_fields_2'))
    parser.add_argument('--mutation-fields-review', type=Path, default=REPORT/'MUTATION_FIELDS_RECOVERY_REVIEW.md')
    parser.add_argument('--mutation-fields-review-metadata', type=Path, default=REPORT/'MUTATION_FIELDS_RECOVERY_METADATA.json')
    parser.add_argument('--mutation-fields-explanation', type=Path, default=REPORT/'MUTATION_FIELDS_RECOVERY_PLAN.md')
    parser.add_argument('--actual-public-embedding-recovery-root', default=str(REPORT/'evidence/recovery/embedding_arrearage_1'))
    parser.add_argument('--embedding-review', type=Path, default=REPORT/'EMBEDDING_ARREARAGE_RECOVERY_REVIEW.md')
    parser.add_argument('--embedding-review-metadata', type=Path, default=REPORT/'EMBEDDING_ARREARAGE_RECOVERY_METADATA.json')
    parser.add_argument('--embedding-explanation', type=Path, default=REPORT/'EMBEDDING_ARREARAGE_RECOVERY_PLAN.md')
    parser.add_argument('--actual-public-phrase-guard-recovery-root', default=str(REPORT/'evidence/recovery/phrase_guard_1'))
    parser.add_argument('--phrase-guard-review', type=Path, default=REPORT/'PHRASE_GUARD_RECOVERY_REVIEW.md')
    parser.add_argument('--phrase-guard-review-metadata', type=Path, default=REPORT/'PHRASE_GUARD_RECOVERY_METADATA.json')
    parser.add_argument('--phrase-guard-explanation', type=Path, default=REPORT/'PHRASE_GROUNDING_EOS_GUARD_RECOVERY_PLAN.md')
    parser.add_argument('--actual-public-adoption-recovery-root', default=str(REPORT/'evidence/recovery/adoption_1'))
    parser.add_argument('--adoption-explanation', type=Path, default=REPORT/'ADOPTION_RECOVERY_PLAN.md')
    for ds in DATASETS:
        parser.add_argument('--actual-'+ds+'-data', default=None)
        parser.add_argument('--actual-'+ds+'-references', default=None)
    args = parser.parse_args()
    actual = {key.removeprefix('actual_'): value for key, value in vars(args).items() if key.startswith('actual_')}
    # All actual completion and review checks precede the first outgoing write.
    bundles = load_completed(actual['archive_root'], args.public_reproduction_summary_name)
    review = actual_review(args.result_review, args.result_review_metadata, args.claims)
    scoring_provenance = offline_scoring_provenance(actual['archive_root'], actual['preparation_root'],
        actual['score_receipts_root'], actual['public_reporting_provenance_root'], bundles)
    actual = recorded_scoring_sources(actual, scoring_provenance)
    repair = dependency_recovery(actual['archive_root'], actual['public_recovery_root'],
                                 args.dependency_review, args.dependency_review_metadata, bundles['chexbench'], continued_by_cuda=True)
    cuda = cuda_recovery(actual['archive_root'], actual['public_cuda_recovery_root'],
                         args.cuda_review, args.cuda_review_metadata, bundles['chexbench'], continued_by_meta_schema=True)
    schema = meta_schema_recovery(actual['archive_root'], actual['public_meta_schema_recovery_root'],
                                  args.meta_schema_review, args.meta_schema_review_metadata, bundles['chexbench'], args.meta_schema_explanation,
                                  continued_by_mutation_fields=True)
    fields = mutation_fields_recovery(actual['archive_root'], actual['public_mutation_fields_recovery_root'],
                                      args.mutation_fields_review, args.mutation_fields_review_metadata, bundles,
                                      args.mutation_fields_explanation, continued_by_embedding=True)
    embed = embedding_http_recovery(actual['archive_root'], actual['public_embedding_recovery_root'],
                                    args.embedding_review, args.embedding_review_metadata, bundles,
                                    args.embedding_explanation, continued_by_phrase_guard=True)
    phrase = phrase_guard_recovery(actual['archive_root'], actual['public_phrase_guard_recovery_root'],
                                    args.phrase_guard_review, args.phrase_guard_review_metadata, bundles,
                                    args.phrase_guard_explanation, continued_by_adoption=True)
    adoption = adoption_recovery(actual['archive_root'], actual['public_adoption_recovery_root'], bundles, review,
                                  args.adoption_explanation)
    single_probe = probe(actual['preparation_root'])
    extras = {ds: supplemental(ds, bundles[ds]) for ds in DATASETS}
    known, unknown = Decimal(0), single_probe['cost_unknown_count'] + embed['neutral_diagnostic_cost_unknown_count']
    resource_totals = Counter()
    for ds in DATASETS:
        resources = bundles[ds]['summary']['resources']
        for key in ('agent', 'R49_META', 'embedding'):
            value = resources[key]
            known += Decimal(str(value['usage_cost_cny_proxy_known'])); unknown += value['cost_unknown_count']
            resource_totals[key+'_requests'] += value['requests']
        resource_totals['logical_tool_calls'] += resources['tools']['logical_calls']
        resource_totals['fresh_tool_attempts'] += resources['tools']['fresh_backend_attempts']
        resource_totals['registered_failed_production_attempts'] += resources['tools']['registered_failed_historical_attempts']
        resource_totals['isolated_cuda_diagnostic_invocations'] += resources['isolated_cuda_diagnostic']['tool_invocations']
        resource_totals['isolated_failed_MAIRA_diagnostic_invocations'] += resources['isolated_phrase_diagnostic']['tool_invocations']
    resource = {'scope': 'Three fresh R49 streams, resource totals only; no pooled accuracy or historical cost replay.',
                'datasets': {ds: {'resources': bundles[ds]['summary']['resources'], 'supplemental': extras[ds]} for ds in DATASETS},
                'resource_totals_only': dict(resource_totals, fresh_questions=848, windows=29,
                    usage_cost_cny_proxy_known=str(known), cost_unknown_count_including_probe_and_billing_diagnostic=unknown,
                    complete_usage_cost_cny=None if unknown else str(known),
                    separate_preexecution_embedding_probe_requests=1, separate_failed_embedding_billing_diagnostic_requests=1,
                    separate_failed_MAIRA_diagnostic_tool_invocations=1,
                    fixed_main_call_limit=None, fixed_tool_call_limit=None),
                'separate_embedding_probe': single_probe, 'actual_result_review': review,
                'offline_scoring_provenance': scoring_provenance,
                'execution_review_metadata': read(REPORT/'CODE_REVIEW_METADATA.json') if (REPORT/'CODE_REVIEW_METADATA.json').is_file() else None,
                'actual_paths': actual, 'final_recovery_controller_raw_exit': 0, 'final_full_runner_raw_dataset_exits': {ds: 0 for ds in DATASETS},
                'dependency_recovery': repair, 'initial_controller_raw_exit': 1, 'initial_chexbench_raw_exit': 1,
                'cuda_recovery': cuda, 'raw_controller_exit': 0, 'raw_dataset_exits': {ds: 0 for ds in DATASETS},
                'meta_schema_recovery': schema,
                'mutation_fields_recovery': fields,
                'embedding_http_recovery': embed,
                'phrase_guard_recovery': phrase,
                'adoption_recovery': adoption,
                'raw_exit_alias_scope': 'These zero aliases describe ONLY the final complete adoption_1 controller/runner attempt; all initial dependency, dependency-continuation, CUDA-continuation, schema1-continuation, fields2-continuation, embedding-continuation and phrase-guard-continuation exit1 records are preserved separately.',
                'META_schema_repair_costs_are_non_additive_subsets': True,
                'second_META_schema_repair_costs_are_non_additive_subsets': True,
                'ordinary_MUTATE_field_prompt_adds_extra_calls': 0,
                'operational_prompt_change_confound': True, 'original_static_prompt_protocol_claim': False,
                'MAIRA_generation_policy_amended_after_activation': True, 'same_original_MAIRA_generation_settings_claim': False,
                'mixed_legacy_healthy_cache_and_new_guarded_MAIRA_policy_confound': True,
                'new_MAIRA_guarded_retry_is_official_fix_claim': False, 'unchanged_output_semantics_claim': False,
                'adoption_repair_META_costs_are_non_additive_subsets': True,
                'ordinary_ANALYZE_uniqueness_clarifier_extra_calls': 0,
                'adoption_credit_attribution_and_prompt_change_confound': True,
                'initial_audit_deferral_control_rewritten_as_ready': False,
                'single_actual_result_and_adoption_audit_after_generation_before_publication': True,
                'all_attempts_exited_zero_claim': False,
                'controller_wall_seconds': None, 'unpriced_tool_hardware_cost': None,
                'whole_generation_wall_times_not_inferred_from_file_mtime': True,
                'new_health_probes': 0, 'historical_costs_recounted': False, 'provider_invoice': False,
                'pooled_independent_848_case_accuracy_claim': False, 'same_budget_causal_Skill_claim': False,
                'official_SOTA_claim': False, 'clinical_verification_or_integrity_audit_claim': False,
                'image_or_file_digests_checked': False, 'new_inference_calls_by_writer': 0,
                'new_score_or_verifier_calls_by_writer': 0, 'remote_or_git_actions_by_writer': 0}
    readme_block, findings_block, tables_block, manifest_block = index_blocks(bundles)
    outgoing = {
        REPORT/'README.md': make_readme(bundles, extras, resource, review),
        REPORT/'CASE_INDEX.md': make_case_index(bundles),
        REPORT/'RESOURCE_SUMMARY.json': dump(resource),
        REPORT/'REPRODUCTION.md': make_reproduction(actual, review, repair, cuda, schema, fields, embed, phrase, adoption, scoring_provenance),
        REPORT/'OFFLINE_SCORING_PROVENANCE.md': make_offline_scoring_provenance(scoring_provenance),
        ROOT/'README.md': replace_block(ROOT/'README.md', readme_block),
        ROOT/'findings.md': replace_block(ROOT/'findings.md', findings_block),
        ROOT/'MANIFEST.md': replace_block(ROOT/'MANIFEST.md', manifest_block),
        ROOT/'reports/cxr_author_alignment_20261108/TABLES.md': replace_block(ROOT/'reports/cxr_author_alignment_20261108/TABLES.md', tables_block),
    }
    for path, content in outgoing.items():
        path.write_text(content.rstrip()+'\n', encoding='utf-8')
    print(dump({'report_written': True, 'cases_by_dataset': {ds: len(bundles[ds]['details']) for ds in DATASETS},
                'files_written': [path.relative_to(ROOT).as_posix() for path in outgoing],
                'inference_calls': 0, 'scoring_calls': 0, 'verifier_calls': 0, 'remote_actions': 0, 'git_actions': 0}).strip())


if __name__ == '__main__':
    main()
