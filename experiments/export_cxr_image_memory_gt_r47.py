"""Allowlisted, offline publication of a fully scored R47 feedback experiment.

Uses the existing evidence publisher and public original-image assets. Never
reads credentials/weights, calls providers, regenerates answers, or pushes Git.
"""
import argparse
from pathlib import Path

from cxr_image_memory_r44 import read, rows
from export_cxr_vqa_extension import RequestEvidencePublisher, restore_images, emit_tool_results
from export_cxr_vqa_toolsets import CALL_FILES
from score_cxr_image_memory_gt_r47 import ARM, N, completed_gate


def child(root, relative):
    value = (root/relative).resolve()
    if not value.is_relative_to(root.resolve()):
        raise ValueError('export_source_outside_explicit_root')
    return value


def emit_text(publisher, target, text):
    """Existing sanitizer, with plain-text exit/job logs retained as plain text."""
    publisher.emit(target, text)
    cleaned = publisher.clean(text, target)
    target.write_text(cleaned.rstrip('\n')+'\n', encoding='utf-8')


def derived_assets(publisher, source_run, selection):
    for remote in selection.get('derived_images', []):
        if '/tool_cache/' not in remote.replace('\\', '/'):
            raise ValueError('derived_image_without_tool_cache_binding')
        suffix = remote.replace('\\', '/').split('/tool_cache/', 1)[1]
        local = child(source_run/'tool_cache', suffix)
        publisher.alias(remote, publisher.put_image(publisher.read_image(local)))


def export(frozen_path, run, scores, data, out, health=None, reference_dir=None):
    if out.exists():
        raise FileExistsError(out)
    if out.resolve().is_relative_to(run.resolve()) or run.resolve().is_relative_to(out.resolve()):
        raise ValueError('publication_must_be_separate_from_private_run')
    frozen = read(frozen_path)
    inputs, expected, _, completion, predictions, contexts, feedback = completed_gate(frozen, run)
    marker = read(run/'run.json')
    if any(marker.get(key) != frozen[key] for key in ('order', 'inputs', 'policy', 'baseline')):
        raise ValueError('run_plan_changed')
    summary = read(scores/'summary.json'); details = read(scores/'per_question.json')
    if (summary.get('n') != N or summary.get('arm') != ARM or summary.get('M43') != 466
            or summary.get('raw_generation_exit') != 0
            or summary.get('effective_recovery_used') is not False
            or summary.get('references_read_after_all_arms_adapted') is not True
            or len(details) != N or {r['question_id'] for r in details} != expected):
        raise ValueError('full618_isolated_scoring_required')
    originals = rows(data/'inputs.jsonl'); canonical = {r['question_id']: r for r in originals}
    if len(originals) != N or set(canonical) != expected:
        raise ValueError('canonical_input_membership')
    # Map only explicitly named original assets already published with this data.
    public_map = {name: name for row in originals for name in row['images']}
    out.mkdir(parents=True, exist_ok=False)
    publisher = RequestEvidencePublisher(out, data/'data_manifest.json', public_map=public_map, image_roots=(data,))
    for row in inputs:
        original = canonical[row['question_id']]
        if any(row.get(k) != original.get(k) for k in ('question', 'options', 'image_id')):
            raise ValueError('canonical_question_or_options_changed')
        if len(row['images']) != len(original['images']):
            raise ValueError('canonical_image_sequence_count_changed')
        for remote, source in zip(row['images'], original['images']):
            publisher.source_image(source); digest = publisher.sources[source]
            for name in (frozen['data'].rstrip('/\\')+'/'+remote,
                         str(Path(frozen['data'])/remote), remote):
                publisher.alias(name, digest)
    tools, selected = {}, []
    for path in sorted((run/'tool_selections'/ARM).glob('*/*.json')):
        value = read(path)
        selected.append(dict(value, question_id=path.parent.name, ordinal=path.stem))
        key = value['cache_key']
        derived_assets(publisher, run, value)
        if key in tools:
            continue
        folder = child(run/'tool_cache', key)
        raw, stderr = folder/'artifacts/raw.json', folder/'backend.stderr.log'
        tools[key] = {'cache_key': key, 'result': value,
                      'raw_result': read(raw) if raw.is_file() else None,
                      'backend_stderr': stderr.read_text(encoding='utf-8', errors='replace') if stderr.is_file() else None}
    for name in ('summary.json', 'per_question.json'):
        publisher.copy_json(scores/name, out/'scores'/name)
    publisher.emit(out/'fee_time.json', summary['resources'])
    for name in ('inputs.jsonl', 'references.jsonl'):
        values = rows(data/name)
        if len(values) != N or {r['question_id'] for r in values} != expected:
            raise ValueError('canonical_publication_membership:' + name)
        for value in values:
            if 'images' in value:
                value['images'] = [publisher.rel(publisher.source_image(image), out/name) for image in value['images']]
        publisher.emit(out/name, values, jsonl=True)
    if (data/'data_manifest.json').exists():
        publisher.copy_json(data/'data_manifest.json', out/'data_manifest.json')
    publisher.emit(out/'frozen.public.json', frozen)
    publisher.emit(out/'run.json', marker)
    publisher.emit(out/f'complete_{ARM}.json', completion)
    emit_text(publisher, out/'generation.exitcode', '0')
    # Per-ID vault records are now publishable post-run labels, never a model input.
    vault = reference_dir or Path(frozen['reference_dir'])
    for row in inputs:
        qid = row['question_id']; declared = frozen['reference_files'][qid]
        source = child(vault, declared['file'])
        reference = read(source)
        if reference.get('question_id') != qid:
            raise ValueError('reference_vault_identity:' + qid)
        publisher.emit(out/'reference_vault'/(qid+'.json'), reference)
        publisher.copy_json(predictions[qid], out/'predictions'/ARM/(qid+'.json'))
        publisher.copy_json(contexts[qid], out/'memory_context'/(qid+'.json'))
        publisher.copy_json(feedback[qid], out/'feedback_events'/(qid+'.json'))
        for request in sorted((run/'calls'/ARM/qid).glob('*/request.json')):
            target = out/'calls'/ARM/qid/request.parent.name
            for name in CALL_FILES:
                publisher.emit(target/name, restore_images(read(request.parent/name), run))
    publisher.emit(out/f'tool_selections_{ARM}.jsonl', selected, jsonl=True)
    for path in (run/'tool_selections'/ARM).glob('*/*.json'):
        publisher.copy_json(path, out/'tool_selections'/ARM/path.parent.name/path.name)
    emit_tool_results(publisher, out, tools.values())
    # Explicit tool evidence only; no recursive copying of runtime/model folders.
    for key in tools:
        folder = child(run/'tool_cache', key)
        for name in ('started.json', 'result.json'):
            if (folder/name).is_file():
                publisher.copy_json(folder/name, out/'tool_cache'/key/name)
    for name in ('progress.json', 'failure.json', 'failures.json', 'generation_failure.json', 'generation_failure_history.json'):
        if (run/name).is_file():
            publisher.copy_json(run/name, out/'failure_records'/name)
    for path in (run/'failure_events').glob('*.json'):
        publisher.copy_json(path, out/'failure_records/events'/path.name)
    for path in (run.parent/'jobs').glob('*'):
        if path.is_file() and path.suffix in ('.json', '.log', '.exitcode'):
            if path.suffix == '.json':
                publisher.copy_json(path, out/'job_records'/path.name)
            else:
                emit_text(publisher, out/'job_records'/path.name, path.read_text(encoding='utf-8', errors='replace'))
    if health is not None:
        probes, raw = [], []
        for path in sorted((health/'tool_selections').glob('*/*/*.json')):
            probe = read(path); probes.append(probe); derived_assets(publisher, health, probe)
            source = child(health/'tool_cache', probe['cache_key'])/'artifacts/raw.json'
            raw.append({'tool': probe['tool'], 'result': probe, 'raw_result': read(source) if source.is_file() else None})
        for name in ('assessment.json', 'kernel_witness.json', 'complete.json'):
            if (health/name).is_file():
                publisher.copy_json(health/name, out/'health'/name)
        publisher.emit(out/'health/probes.jsonl', raw, jsonl=True)
    publisher.emit(out/'reuse.json', {
        'baseline_M43': '../../cxr_task_completion_r43_20261108/README.md',
        'M_C41': '../../cxr_action_r41_20261108/FINAL_REPORT.md',
        'R45_frozen_comparison_if_scored': '../../cxr_image_memory_r45_20261108/README.md',
        'old_original_inputs_and_evidence': '../../cxr_vqa_extension/results/chexbench',
        'online_feedback_protocol': 'Earlier same-image dataset truth is released only after its own immutable prediction is saved. This is an online ground-truth-feedback advantage, not standard closed-test SOTA.',
        'privacy_note': 'Existing path/credential transformations are applied. Original and derived image bytes are preserved; keys, weights and unrelated files are not copied.'})
    publisher.emit(out/'image_assets.json', [
        {k: v for k, v in asset.items() if k != 'target'} |
        {'path': publisher.rel(asset['target'], out/'image_assets.json')}
        for asset in publisher.assets.values()])
    for document, relative, target in publisher.references:
        if (document.parent/relative).resolve() != target.resolve() or not target.is_file():
            raise ValueError('outgoing_asset_reference_missing_or_mismatched')
    publisher.emit(out/'publication_manifest.json', {
        'files': sorted({p.relative_to(out).as_posix() for p in publisher.files} | {'publication_manifest.json'}),
        'redactions': dict(publisher.redactions), 'questions': N, 'arm': ARM,
        'prediction_context_feedback_records': [N, N, N], 'reference_vault_records': N,
        'raw_generation_exit': 0, 'online_ground_truth_feedback_advantage': True,
        'standard_closed_test_SOTA_claim': False, 'raw_tool_results': 'Complete available raw.json values and model-visible structures are preserved in partitioned evidence files.',
        'public_score_verifier': 'experiments/verify_public_cxr_image_memory_gt_r47.py',
        'new_inference_calls': 0, 'private_account_ledgers_read': False})
    return {'files': len(publisher.files), 'images': len(publisher.assets), 'new_inference_calls': 0}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('frozen', 'run', 'scores', 'data', 'out'):
        parser.add_argument('--'+name, type=Path, required=True)
    parser.add_argument('--health', type=Path)
    parser.add_argument('--reference-dir', type=Path)
    args = parser.parse_args()
    print(export(args.frozen, args.run, args.scores, args.data, args.out, args.health, args.reference_dir))
