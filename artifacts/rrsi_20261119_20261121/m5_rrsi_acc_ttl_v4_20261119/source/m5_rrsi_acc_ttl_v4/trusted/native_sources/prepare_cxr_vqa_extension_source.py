"""Screen candidate source cases and enumerate paired-input evaluation groups."""

import argparse
from collections import defaultdict
import json
from pathlib import Path

from prepare_chexbench_extension import image_fingerprints
from score_cxr_vqa_extension import cluster_keys, rows


def eligibility(data):
    inputs = rows(data/'inputs.jsonl')
    groups = defaultdict(list)
    for key, row in zip(cluster_keys(inputs), inputs):
        groups[key].append(row['question_id'])
    groups = [sorted(qids) for qids in groups.values() if len(qids)>1]
    return {'history_eligible': sum(set(row.get('history') or {}) >= {'age','sex','clinical_history'} for row in inputs),
            'joint_groups': sorted(groups), 'joint_questions': sum(map(len, groups)), 'all_questions': len(inputs)}


def candidates(source, target_dirs):
    target_pixels = set()
    target_ids = set()
    for data in target_dirs:
        for row in rows(data/'inputs.jsonl'):
            target_pixels.update((data/image).resolve() for image in row['images'])
            meta = row.get('source', {})
            target_ids.update(str(meta[k]) for k in ('official_patient_id','official_study_id') if meta.get(k) is not None)
    target_pixels = {image_fingerprints(p)[1] for p in target_pixels}
    case_file = source/'cases.json'
    cases = json.loads(case_file.read_text(encoding='utf-8'))['rows']
    case_images = defaultdict(set)
    case_rows = defaultdict(list)
    pixel_cache = {}
    for row in cases:
        case = row['case_id']
        case_rows[case].append(row['question_id'])
        for img in row['native_images']:
            path = (case_file.parent/img['image']).resolve()
            if path not in pixel_cache:
                pixel_cache[path] = image_fingerprints(path)[1]
            case_images[case].add(pixel_cache[path])
    overlap = {case for case, imgs in case_images.items() if imgs & target_pixels or str(case) in target_ids}
    checks = ['released_after_all_case_predictions', 'context_has_complete_questions_and_options',
              'context_has_old_and_correct_option_text', 'completed_tool_observation_exists']
    valid = {}
    for fold in ('A','B'):
        for file in (source/'reflection_contexts'/fold).glob('*.json'):
            trajectory = json.loads(file.read_text(encoding='utf-8'))
            steps = trajectory['steps']
            if not steps or steps[0].get('action')!='source_feedback_context':
                continue
            context = steps[0]['action_input']
            if not all(context.get(k) for k in ('full_question_and_options','options','old_answer_text','correct_answer_text')):
                continue
            if not any(o.get('status') == 'returned' and o.get('usable') is True
                       for o in context.get('tool_observations', []) if isinstance(o,dict)):
                continue
            valid[file.stem] = fold
    eligible = {}
    for fold in ('A','B'):
        for file in (source/'feedback_releases'/fold).glob('*.json'):
            release = json.loads(file.read_text(encoding='utf-8'))
            case = release['case_id']
            if case in overlap or not release['all_case_predictions_saved']:
                continue
            qids = [qid for qid in release['prediction_ids'] if valid.get(qid)==fold]
            if qids:
                eligible.setdefault(case, set()).update(qids)
    return {'candidate_dataset': 'ChestAgentBench SkeMex tools-v2 source trajectories', 'source_development': 'Previously used across development rounds',
            'stage': 'candidate_screen', 'all_target_manifests_present': any('chexbench' in data.name.lower() for data in target_dirs),
            'case_count': len(case_rows), 'question_count': len(cases), 'checks': checks,
            'excluded_matching_cases': sorted(overlap), 'eligible_source_questions_by_case': {k:sorted(v) for k,v in sorted(eligible.items())},
            'isolation_scope': 'Exact decoded RGB and available explicit IDs. Patient linkage across source datasets requires provenance review.',
            'target_labels_read': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--targets', type=Path, nargs='+', required=True)
    parser.add_argument('--dest', type=Path, required=True)
    args = parser.parse_args()
    result = candidates(args.source, args.targets)
    result['paired_input_eligibility'] = {d.name:eligibility(d) for d in args.targets}
    args.dest.parent.mkdir(parents=True, exist_ok=True)
    with args.dest.open('x', encoding='utf-8') as file:
        json.dump(result, file, ensure_ascii=False, indent=2)
