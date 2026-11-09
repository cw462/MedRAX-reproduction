"""Allowlisted, offline export of R49 online learning and actual evidence.

Uses the existing publisher's sanitizer and image storage unchanged. This
module performs no inference, Git operations or new byte/hash validation.
"""
import argparse
from pathlib import Path

from analyze_cxr_author_alignment import predictions as historical_predictions, terminal
from export_cxr_image_memory_gt_r47 import child, derived_assets, emit_text
from export_cxr_vqa_extension import RequestEvidencePublisher, restore_images
from online_memory_r49 import read
from run_online_skill_r49 import ARM
from score_online_skill_r49 import EXPECTED, completed_gate, rows


def baseline_sources(dataset, inputs, names, r47_frozen=None, r47_run=None):
    """Portable actual raw terminals, with no correctness flags or label access."""
    baseline_name = EXPECTED[dataset][1]
    old = historical_predictions(dataset, baseline_name)
    ids = {row['question_id'] for row in inputs}
    if set(old) != ids:
        raise ValueError('historical_full_arm_membership')
    result = {baseline_name: {qid: {'prediction': old[qid], 'source': terminal(dataset, baseline_name, qid)} for qid in ids}}
    if 'R47_online_GT' in names:
        if dataset != 'chexbench' or r47_frozen is None or r47_run is None:
            raise ValueError('scored_R47_comparison_requires_actual_archives')
        from score_cxr_image_memory_gt_r47 import completed_gate as old_gate, request_evidence
        frozen = read(r47_frozen)
        original, _, order, _, paths, _, _ = old_gate(frozen, r47_run)
        if original != inputs:
            raise ValueError('R47_original_semantic_input_order_changed')
        values = {}
        for row in inputs:
            qid = row['question_id']; prediction = read(paths[qid])
            if order[qid]['previous_ids']:
                source, _ = request_evidence(r47_run, qid, prediction)
            else:
                if any(prediction.get(k) != old[qid].get(k) for k in ('answer', 'reason', 'status')):
                    raise ValueError('R47_whole_baseline_reuse_changed')
                source = result[baseline_name][qid]['source']
            values[qid] = {'prediction': prediction, 'source': source}
        result['R47_online_GT'] = values
    if set(result) != set(names):
        raise ValueError('historical_compared_arm_names_changed')
    return result


def tool_assets(publisher, run, manifest):
    """Register explicit original/derived image names before cleaning documents."""
    by_id = {row['question_id']: row for row in manifest['inputs']}
    services = run/'services'
    for path in sorted((services/'tool_selections/R49-AGENT').glob('*/*.json')):
        selection = read(path); row = by_id.get(path.parent.name)
        if row is None:
            raise ValueError('tool_selection_outside_declared_cohort')
        index = selection.get('image_index', 1)
        if type(index) is not int or not 1 <= index <= len(row['images']):
            raise ValueError('invalid_original_image_index')
        name = row['images'][index-1]
        publisher.alias(selection.get('original_image'), publisher.sources[name])
        derived_assets(publisher, services, selection)


def copy_records(publisher, source, destination, *, jsonl=True):
    if source.suffix in ('.json', '.jsonl'):
        publisher.copy_json(source, destination)
    else:
        emit_text(publisher, destination, source.read_text(encoding='utf-8', errors='replace'))


def recovery_records(publisher, source, destination, *, partial=False):
    """Preserve operational attempt history once in the shared evidence tree."""
    if destination.exists():
        raise ValueError('shared_recovery_evidence_already_exists_preserve_it')
    source, destination = source.resolve(), destination.resolve()
    files = []
    for path in sorted(source.rglob('*')):
        if not path.is_file():
            continue
        if not path.resolve().is_relative_to(source):
            raise ValueError('recovery_record_outside_explicit_archive')
        relative = path.relative_to(source)
        if any(part in ('.secrets', 'hf_modules', '__pycache__') for part in relative.parts):
            continue
        if partial and ('reference_vault' in relative.parts or path.name == 'references.jsonl'):
            continue
        if path.suffix not in ('.json', '.jsonl', '.txt', '.log', '.py', '.md', '.pid', '.exitcode') and path.name != 'exitcode':
            continue
        target = destination/relative
        if path.name == 'request.json':
            publisher.emit(target, restore_images(read(path), source))
        else:
            copy_records(publisher, path, target)
        files.append(target)
    publisher.emit(destination/'publication_manifest.json', {
        'scope': 'Actual preserved dependency, tool, META, embedding and declared policy operational history, not another experiment arm.',
        'files': sorted(path.relative_to(destination).as_posix() for path in files),
        'initial_nonzero_attempt_preserved': True,
        'current_final_zero_does_not_mean_all_attempts_zero': True,
        'archived_requests_already_in_current_stream_totals_not_additional_charges': True,
        'unknown_requests_reissued': False, 'technical_nulls_inserted': False,
        'new_inference_calls_by_exporter': 0})
    return destination


def export(data, run, scores, references, reference_dir, out, dataset, *,
           r47_frozen=None, r47_run=None, probe_root=None, jobs=None, partial=False,
           recovery_root=None, recovery_out=None):
    data, run, out = Path(data), Path(run), Path(out)
    if out.exists() or out.resolve().is_relative_to(run.resolve()) or run.resolve().is_relative_to(out.resolve()):
        raise ValueError('new_publication_directory_separate_from_private_run_required')
    n, baseline_name, expected_baseline = EXPECTED[dataset]
    manifest = read(run/'manifest.json'); inputs = manifest['inputs']; ids = [row['question_id'] for row in inputs]
    if (manifest.get('dataset') != dataset or manifest.get('arm') != ARM
            or len(ids) != n or len(set(ids)) != n):
        raise ValueError('manifest_fixed_dataset_identity')
    summary = details = comparison = None
    if not partial:
        if scores is None or references is None or reference_dir is None:
            raise ValueError('full_export_requires_scores_references_and_original_reference_vault')
        completed_inputs, _, _ = completed_gate(data, run, n)
        if completed_inputs != inputs:
            raise ValueError('completed_input_semantics_changed')
        summary, details = read(scores/'summary.json'), read(scores/'per_question.json')
        if (summary.get('dataset') != dataset or summary.get('arm') != ARM or summary.get('questions') != n
                or summary.get('references_read_after_all_arms_adapted') is not True
                or summary['arms'][baseline_name]['correct'] != expected_baseline
                or len(details) != n or {row['question_id'] for row in details} != set(ids)):
            raise ValueError('complete_isolated_R49_scores_required')
        comparison = baseline_sources(dataset, inputs, summary['comparisons'], r47_frozen, r47_run)
    elif not (run/'generation.exitcode').is_file() or (run/'generation.exitcode').read_text().strip() == '0':
        raise ValueError('partial_failure_export_requires_preserved_nonzero_raw_exit')

    originals = rows(data/'inputs.jsonl')
    if [row['question_id'] for row in originals] != ids:
        raise ValueError('canonical_public_image_input_order_changed')
    out.mkdir(parents=True, exist_ok=False)
    # The publisher owns ordinary asset naming/deduplication. No experimental
    # original-run checksum or pixel grouping gate is added here.
    publisher = RequestEvidencePublisher(out, data/'manifest.json', image_roots=(data,))
    data_aliases = [str(data), str(data.resolve())]
    for row, original in zip(inputs, originals):
        if any(row.get(k) != original.get(k) for k in ('question', 'options', 'image_id', 'source')) or len(row['images']) != len(original['images']):
            raise ValueError('canonical_question_options_or_image_sequence_changed')
        for name, source in zip(row['images'], original['images']):
            publisher.source_image(source); key = publisher.sources[source]
            publisher.alias(name, key)
            publisher.sources[name] = key
            for root in data_aliases:
                publisher.alias(root.rstrip('/\\')+'/'+name, key)
    tool_assets(publisher, run, manifest)

    # Register original paths found next to explicitly identified image blocks.
    # This uses saved metadata; requests are never regenerated or resent.
    for path in (run/'services/calls').glob('*/*/*/request.json'):
        request = restore_images(read(path), run/'services')
        for message in request.get('messages', []):
            content = message.get('content')
            if not isinstance(content, list):
                continue
            for block in content:
                text = block.get('text', '') if isinstance(block, dict) else ''
                if text.startswith('BOUND CURRENT IMAGE: '):
                    import json
                    metadata = json.loads(text[len('BOUND CURRENT IMAGE: '):])
                    name = metadata.get('source_filename')
                    if name in publisher.sources:
                        publisher.alias(metadata.get('path'), publisher.sources[name])

    publisher.emit(out/'inputs.jsonl', inputs, jsonl=True)
    publisher.emit(out/'manifest.json', manifest)
    source_manifest = next((data/name for name in ('data_manifest.json', 'manifest.json') if (data/name).is_file()), None)
    if source_manifest is not None:
        publisher.copy_json(source_manifest, out/'data_manifest.json')
    publisher.emit(out/'source_attribution.json', {
        'dataset': dataset,
        'question_image_sources': 'Original source metadata is retained in each inputs.jsonl source field.',
        'original_data_manifest': 'data_manifest.json' if source_manifest is not None else None,
        'historical_comparators': 'M43/M42 complete published archives; R47 online-GT only when separately scored.',
        'scope': 'Exposed online feedback experiment; source dataset terms and attribution continue to apply.'})
    if comparison is not None:
        publisher.emit(out/'comparison_sources.json', comparison)
        publisher.copy_json(scores/'summary.json', out/'scores/summary.json')
        publisher.copy_json(scores/'per_question.json', out/'scores/per_question.json')
        publisher.emit(out/'fee_time.json', summary['resources'])
        ref_rows = rows(references); ref_map = {row['question_id']: row for row in ref_rows}
        if len(ref_rows) != len(ref_map) or set(ref_map) != set(ids):
            raise ValueError('full_public_scoring_reference_membership')
        publisher.emit(out/'references.jsonl', [ref_map[qid] for qid in ids], jsonl=True)
        for qid in ids:
            value = read(child(reference_dir, qid+'.json'))
            if value.get('question_id') != qid or value.get('answer') != ref_map[qid]['answer']:
                raise ValueError('actual_vault_reference_identity')
            publisher.emit(out/'reference_vault'/(qid+'.json'), value)

    for name in ('complete.json', 'final_repo.json', 'progress.json', 'failure.json', 'failures.json',
                 'generation_failure.json', 'generation_failure_history.json'):
        if (run/name).is_file():
            publisher.copy_json(run/name, out/name)
    emit_text(publisher, out/'generation.exitcode', (run/'generation.exitcode').read_text(encoding='utf-8'))
    for folder in ('predictions', 'contexts', 'steps', 'prediction_events', 'feedback', 'windows', 'failure_events'):
        for path in sorted((run/folder).rglob('*.json')):
            publisher.copy_json(path, out/path.relative_to(run))
    # Explicit generated-record roots only; no environment, ledger, key, model
    # weight or unrelated directory is traversed.
    for folder in ('calls', 'embeddings', 'tool_selections', 'tool_cache'):
        root = run/'services'/folder
        for path in sorted(root.rglob('*')):
            if not path.is_file() or any(part in ('hf_modules', '__pycache__') for part in path.relative_to(root).parts):
                continue
            if path.suffix not in ('.json', '.jsonl', '.txt', '.log'):
                continue
            target = out/'services'/folder/path.relative_to(root)
            if folder == 'calls' and path.name == 'request.json':
                publisher.emit(target, restore_images(read(path), run/'services'))
            else:
                copy_records(publisher, path, target)
    if jobs is None:
        candidates = [run.parent/'jobs', run.parent.parent/'jobs']
        jobs = next((path for path in candidates if path.is_dir()), None)
    if jobs is not None:
        for path in sorted(jobs.iterdir()):
            if path.is_file() and path.suffix in ('.json', '.log', '.exitcode', '.pid'):
                copy_records(publisher, path, out/'job_records'/path.name)
    shared_recovery = None
    queue = read(jobs/'queue_status.json') if jobs is not None and (jobs/'queue_status.json').is_file() else {}
    known_repair = queue.get('recovery') in ('dependency_1', 'cuda_1', 'meta_schema_1', 'mutation_fields_2', 'embedding_arrearage_1', 'phrase_guard_1', 'adoption_1')
    recovery_root = recovery_root or (run.parent.parent/'recovery' if dataset == 'chexbench' else None)
    recovery_out = recovery_out or out.parent/'recovery'
    if not recovery_out.resolve().is_relative_to(out.parent.resolve()) or recovery_out.resolve() == out.resolve():
        raise ValueError('shared_recovery_output_must_be_within_the_public_evidence_tree')
    if dataset == 'chexbench' and recovery_root is not None and recovery_root.is_dir():
        shared_recovery = recovery_records(publisher, recovery_root, recovery_out, partial=partial)
    elif known_repair:
        required = {'cuda_1': 'cuda_1/registration.json', 'meta_schema_1': 'meta_schema_1/registration.json',
                    'mutation_fields_2': 'mutation_fields_2/registration.json',
                    'embedding_arrearage_1': 'embedding_arrearage_1/registration.json',
                    'phrase_guard_1': 'phrase_guard_1/registration.json',
                    'adoption_1': 'adoption_1/registration.json',
                    'dependency_1': 'dependency_1/diagnosis.json'}[queue['recovery']]
        if not (recovery_out/required).is_file():
            raise ValueError('known_operational_recovery_history_must_be_exported_with_CheXbench_first')
        shared_recovery = recovery_out
    if probe_root is not None:
        count = 0
        for name in ('assessment.json', 'request.json', 'started.json', 'response.json', 'result.json'):
            source = probe_root/name
            if source.is_file():
                publisher.copy_json(source, out/'embedding_probe'/name); count += 1
        if not (probe_root/'assessment.json').is_file() or count < 3:
            raise ValueError('explicit_embedding_probe_assessment_and_actual_records_required')
        publisher.emit(out/'embedding_probe/scope.json', {
            'separate_from_stream_resources': True,
            'shared_preflight_probe_count_once_across_three_dataset_reports': True,
            'purpose': 'Actual endpoint/model compatibility probe before online learning; not a training example.',
            'usage_and_elapsed_are_in_actual_response_and_assessment': True,
            'result_file_optional_when_probe_assessment_is_its_actual_receipt': True,
            'provider_invoice': False})
    publisher.emit(out/'image_assets.json', [{key: value for key, value in asset.items() if key != 'target'} |
                                           {'path': publisher.rel(asset['target'], out/'image_assets.json')}
                                           for asset in publisher.assets.values()])
    for document, relative, target in publisher.references:
        if (document.parent/relative).resolve() != target.resolve() or not target.is_file():
            raise ValueError('public_document_image_reference_missing')
    publisher.emit(out/'publication_manifest.json', {
        'schema': 'r49_semantic_public_evidence_v1', 'dataset': dataset, 'arm': ARM, 'questions': n,
        'scope': 'partial_failure_evidence_no_full_score' if partial else 'complete_scored_online_stream',
        'saved_predictions': len(list((run/'predictions'/ARM).glob('*.json'))),
        'released_feedback': len(list((run/'feedback').glob('*.json'))),
        'agent_started': len(list((run/'services/calls/R49-AGENT').glob('*/*/started.json'))),
        'agent_responses': len(list((run/'services/calls/R49-AGENT').glob('*/*/response.json'))),
        'files': sorted({path.relative_to(out).as_posix() for path in publisher.files if path.is_relative_to(out)} | {'publication_manifest.json'}),
        'redactions': dict(publisher.redactions), 'new_inference_calls': 0,
        'raw_generation_exit': int((run/'generation.exitcode').read_text().strip()),
        'all_question_predictions_are_fresh': True, 'cross_dataset_feedback_shared': False,
        'online_feedback_and_changed_executor_advantage': True, 'official_SOTA_or_causal_Skill_claim': False,
        'historical_raw_terminals': 'comparison_sources.json' if comparison is not None else None,
        'public_score_verifier': 'experiments/verify_public_online_skill_r49.py',
        'source_code': ['experiments/'+name for name in manifest.get('implementation_files', [])],
        'images': 'Original and listed derived images use the unchanged publisher asset store.',
        'shared_recovery_evidence': str(Path('..')/'recovery').replace('\\', '/') if shared_recovery is not None else None,
        'initial_attempt_nonzero_preserved': known_repair or shared_recovery is not None,
        'all_attempts_exit_zero_claim': False if known_repair or shared_recovery is not None else None,
        'registered_cuda_tool_retry': (run/'failure_events/cuda_1_registration.json').is_file(),
        'original_failed_cache_and_selection_retained': (run/'failure_events/cuda_1_original_selection.json').is_file(),
        'diagnostic_output_used_as_production_result': False,
        'registered_meta_schema_repair': (run/'failure_events/meta_schema_1_registration.json').is_file(),
        'registered_meta_schema_repair_2': (run/'failure_events/meta_schema_2_registration.json').is_file(),
        'ordinary_mutation_fields_amendment': (run/'failure_events/mutation_fields_2_amendment.json').is_file(),
        'automatic_invalid_META_to_NONE': False,
        'registered_embedding_http_failure': (run/'failure_events/embedding_arrearage_1_registration.json').is_file(),
        'original_embedding_specific_body_unknown': (run/'failure_events/embedding_arrearage_1_registration.json').is_file(),
        'original_embedding_error_body_reconstructed_from_diagnostic': False,
        'registered_phrase_guard_retry': (run/'failure_events/phrase_guard_1_registration.json').is_file(),
        'declared_phrase_generation_policy_amendment': (run/'failure_events/phrase_guard_1_amendment.json').is_file(),
        'same_MAIRA_generation_settings_claim': False,
        'phrase_diagnostic_output_reused_in_R49': False,
        'registered_assessment_adoption_repair': (run/'failure_events/adoption_1_registration.json').is_file(),
        'analysis_unique_adoption_amendment': (run/'failure_events/analysis_unique_adoption_amendment.json').is_file(),
        'original_analysis_changed_for_mutation': False,
        'automatic_future_adoption_repair': False,
        'invalid_adoption_silently_ignored': False,
        'embedding_probe': 'embedding_probe/scope.json' if probe_root is not None else None})
    return {'dataset': dataset, 'scope': 'partial' if partial else 'complete',
            'files': len(publisher.files), 'images': len(publisher.assets), 'new_inference_calls': 0}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('data', 'run', 'out'):
        parser.add_argument('--'+name, type=Path, required=True)
    for name in ('scores', 'references', 'reference-dir', 'r47-frozen', 'r47-run', 'probe-root', 'jobs', 'recovery-root', 'recovery-out'):
        parser.add_argument('--'+name, type=Path)
    parser.add_argument('--dataset', choices=EXPECTED, required=True)
    parser.add_argument('--partial', action='store_true')
    args = parser.parse_args()
    print(export(args.data, args.run, args.scores, args.references, args.reference_dir, args.out, args.dataset,
                 r47_frozen=args.r47_frozen, r47_run=args.r47_run, probe_root=args.probe_root,
                 jobs=args.jobs, partial=args.partial, recovery_root=args.recovery_root, recovery_out=args.recovery_out))
