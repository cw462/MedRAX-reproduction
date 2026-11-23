"""Freeze one new R48 dataset arm and split annotations into a single-file vault."""
import argparse
import copy
import json
from pathlib import Path

from cxr_image_memory_gt_r48 import (
    BASELINE_FIELDS, DATASETS, SCHEMA, baseline_record, read, rows, safe_qid,
    save_once, schedule, summary, validate_frozen, validate_protocol,
)


def records(path):
    path = Path(path)
    return [read(value) for value in sorted(path.glob('*.json'))] if path.is_dir() else rows(path)


def load_value(value):
    return read(value) if isinstance(value, (str, Path)) else copy.deepcopy(value)


def prepare(dataset, data, baseline, references, protocol, runtime, config, out, *,
            r41_frozen=None, original_m=None, runtime_data=None, reference_dir=None):
    if dataset not in DATASETS:
        raise ValueError('unsupported_dataset')
    spec, data, out = DATASETS[dataset], Path(data), Path(out)
    inputs = rows(data / 'inputs.jsonl')
    order = schedule(inputs, dataset)
    ids = [safe_qid(row['question_id']) for row in inputs]
    if len(ids) != spec['questions'] or len(set(ids)) != len(ids):
        raise ValueError('full_dataset_cohort_required')
    prior_rows = records(baseline)
    prior = {row['question_id']: baseline_record(row) for row in prior_rows}
    if len(prior_rows) != len(ids) or set(prior) != set(ids):
        raise ValueError('baseline_whole_arm_cohort_mismatch')
    if any(row.get('arm') != spec['baseline_arm'] for row in prior_rows):
        raise ValueError('strongest_fixed_whole_baseline_required')
    protocol = load_value(protocol)
    validate_protocol(protocol)
    policy = {qid: {'kind': 'M', 'conditioning': None, 'selected_skill_ids': []} for qid in ids}
    if dataset == 'slake':
        if r41_frozen is None:
            raise ValueError('original_SLAKE_S41_selection_required')
        original_selection = load_value(r41_frozen)
        if set(original_selection['mask']) != set(ids):
            raise ValueError('original_S41_selection_cohort_mismatch')
        for qid in ids:
            selected = original_selection['mask'][qid]
            if selected['selected_ids']:
                policy[qid] = {'kind': 'M-S41', 'conditioning': selected['conditioning'],
                               'selected_skill_ids': copy.deepcopy(selected['selected_ids'])}
        if original_m is None:
            raise ValueError('original_M_observations_required')
        original_rows = records(original_m)
        original = {row['question_id']: row for row in original_rows}
        if len(original_rows) != len(ids) or set(original) != set(ids):
            raise ValueError('original_M_cohort_mismatch')
        # R43 preserved answer/reason/status while its published M branch lost the
        # old tool list. Restore only the same question's actual old observations.
        for qid in ids:
            if (policy[qid]['kind'] == 'M' and not prior[qid].get('observations')
                    and not prior[qid].get('inherited_observations')):
                prior[qid]['inherited_observations'] = copy.deepcopy(original[qid].get('observations', []))
    raw = rows(references)
    if len(raw) != len(ids) or {row['question_id'] for row in raw} != set(ids):
        raise ValueError('reference_cohort_mismatch')
    for row in raw:
        safe_qid(row['question_id'])
        if not isinstance(row.get('answer'), str) or not row['answer'].strip():
            raise ValueError('invalid_reference_answer')
        if 'answer_text' in row and not isinstance(row['answer_text'], str):
            raise ValueError('invalid_reference_answer_text')
    manifest = {qid: {'dataset': dataset, 'question_id': qid, 'file': qid + '.json'} for qid in ids}
    vault = out / 'reference_vault'
    frozen = {
        'schema': SCHEMA, 'dataset': dataset, 'arm': spec['arm'], 'baseline_arm': spec['baseline_arm'],
        'inputs': inputs, 'order': order, 'policy': policy, 'baseline': prior,
        'baseline_source': str(Path(baseline).resolve()),
        'data': str(runtime_data) if runtime_data is not None else str(data.resolve()),
        'protocol': {key: protocol[key] for key in ('model', 'temperature', 'top_p', 'enable_thinking', 'max_output_tokens')},
        'runtime': load_value(runtime), 'config': load_value(config),
        'reference_files': manifest,
        'reference_dir': str(reference_dir) if reference_dir is not None else str(vault.resolve()),
        'reference_read': 'preparation_only_split_to_per_question_files',
        'feedback_protocol': 'own_reference_only_after_immutable_prediction_and_prediction_event_save',
        'image_grouping': 'existing_canonical_image_id_else_ordered_relative_paths_no_image_byte_reads',
        'memory_max_chars': 12000, 'memory_max_entries': 8,
        'run_scope': 'First image-group item reuses one fixed whole baseline; only subsequent same-image items are generated.',
    }
    counts = summary(frozen)
    frozen.update(new_main_ceiling=counts['new_main_ceiling'], new_tool_ceiling=counts['new_tool_ceiling'])
    validate_frozen(frozen)
    for row in raw:
        reference = {'dataset': dataset, 'question_id': row['question_id'], 'answer': row['answer']}
        if 'answer_text' in row:
            reference['answer_text'] = row['answer_text']
        save_once(vault / (row['question_id'] + '.json'), reference)
    save_once(out / 'frozen.json', frozen)
    save_once(out / 'preparation.json', dict(counts, paid_calls=0, feedback_events_required=len(ids)))
    return frozen


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--dataset', choices=sorted(DATASETS), required=True)
    for key in ('data', 'baseline', 'references', 'protocol', 'runtime', 'config', 'out'):
        parser.add_argument('--' + key, type=Path, required=True)
    parser.add_argument('--r41-frozen', type=Path)
    parser.add_argument('--original-m', type=Path)
    parser.add_argument('--runtime-data')
    parser.add_argument('--reference-dir')
    args = parser.parse_args(argv)
    frozen = prepare(args.dataset, args.data, args.baseline, args.references, args.protocol,
                     args.runtime, args.config, args.out, r41_frozen=args.r41_frozen,
                     original_m=args.original_m, runtime_data=args.runtime_data, reference_dir=args.reference_dir)
    print(json.dumps(dict(summary(frozen), status='prepared_zero_paid_requests',
                          prepared=str(args.out / 'frozen.json')), ensure_ascii=False))


if __name__ == '__main__':
    main()
