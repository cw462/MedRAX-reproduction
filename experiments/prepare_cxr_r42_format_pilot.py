"""Prepare a source-only paired format-repair pilot; never calls an API."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil

from export_vote_phase import question_parts

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'reports/cxr_action_r41_20261108/results/source_learning'


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def normal(text):
    return ' '.join(text.split())


def prepare(out, count=12):
    if out.exists():
        raise FileExistsError('Prepared pilot is immutable: ' + str(out))
    source = read(SOURCE / 'source_learning_inputs.json')
    manifest = read(SOURCE / 'source_v2_manifest.json')
    assets = {x['sha256']: x for x in read(SOURCE / 'image_assets.json')}
    candidates = []
    for case in source['cases']:
        bound = manifest['images'][case['case_id']]
        if len(bound) != 1:
            continue
        for item in sorted(case['source_trajectories'], key=lambda x: x['source_id']):
            question, options = question_parts(item['question_and_options'])
            if re.search(r'follow.?up|compar(?:ed|ing|ison)|previous|initial|prior|clinical|history|serial|before|after|progression|evolut|timeline', question, re.I):
                continue
            labels = {x.lower() for x in re.findall(r'Figure\s+\d+', item['question_and_options'], re.I)}
            if not labels.issubset({x['label'].lower() for x in bound}):
                continue
            rank = hashlib.sha256(('r42-format-pilot-v1:' + item['source_id']).encode()).hexdigest()
            candidates.append((rank, case['case_id'], item, question, options, bound[0]))
            break
    assert len(candidates) >= count, 'Insufficient eligible cases; do not silently change eligibility.'
    inputs, references, roster, image_files = [], [], [], {}
    for rank, case_id, item, question, options, binding in sorted(candidates)[:count]:
        asset = assets[binding['sha256']]
        image = SOURCE / asset['path']
        data = image.read_bytes()
        assert hashlib.sha256(data).hexdigest() == binding['sha256']
        relative_image = 'images/' + image.name
        image_files[relative_image] = image
        # Source-reference binding is checked only after label-independent selection.
        matches = [letter for letter, text in options.items() if normal(text) == normal(item['reference_answer'])]
        if len(matches) != 1:
            raise ValueError('Source reference is not an exact unique option: ' + item['source_id'])
        qid = 'source_' + item['source_id']
        inputs.append({'question_id': qid, 'source_id': item['source_id'], 'source_case_id': case_id,
                       'image_id': 'source_case_' + case_id, 'subset': 'exposed_source_dev',
                       'question': 'Source image binding: image 1 = ' + binding['label'] + '.\n' + question,
                       'options': options, 'images': [relative_image], 'modality': 'CXR',
                       'answer_type': 'multiple_choice', 'source_image_label': binding['label']})
        references.append({'question_id': qid, 'reference': matches[0],
                           'source_reference_answer': item['reference_answer'],
                           'provenance': 'Previously released source trajectory; exposed development evidence.'})
        roster.append({'question_id': qid, 'source_case_id': case_id, 'rank_sha256': rank,
                       'source_image_sha256': binding['sha256'], 'source_image_label': binding['label']})
    out.mkdir(parents=True)
    for relative, source_image in image_files.items():
        target = out / relative
        target.parent.mkdir(exist_ok=True)
        shutil.copyfile(source_image, target)
    for name, values in [('inputs.jsonl', inputs), ('references.jsonl', references)]:
        (out / name).write_text('\n'.join(json.dumps(x, ensure_ascii=False) for x in values) + '\n', encoding='utf-8')
    protocol = {'experiment_id': 'format_pilot_r42_20261108', 'status': 'prepared_not_launched',
                'data_role': 'Previously exposed source/development; not an unseen test.',
                'questions_per_arm': count, 'distinct_source_case_ids': count,
                'patient_independence_verified': False,
                'arms': {'F0': 'Frozen R4.1 no-card behavior; strict parser, stop on format failure.',
                         'F1': 'Same behavior plus at most one generation-time format repair after strict JSON parse failure.'},
                'model': manifest['protocol']['model'],
                'main_call_limits': {'F0': 6, 'F1': 6}, 'tool_call_limits': {'F0': 4, 'F1': 4},
                'max_main_requests': count * 2 * 6, 'max_logical_tool_calls': count * 2 * 4,
                'repair_within_original_main_limit': True, 'repair_max_per_question': 1,
                'repair_prompt': 'Your previous message was not a single valid JSON object. Reformat your own previous answer or tool plan into exactly one JSON object using the existing schema. Do not add analysis or a fenced block. Do not introduce a new clinical conclusion.',
                'references_available_to_generation': False, 'previous_answers_or_trajectories_in_prompt': False,
                'skill_cards_in_either_arm': False, 'unknown_sent_retry': False,
                'failed_tool_observation_reused': False,
                'generation_order': 'Sequential case pairs; deterministic hash parity alternates F0/F1 first.',
                'unlaunched_reason': 'R4.1 authorization is complete. This new paid pilot requires its own explicit scope decision.',
                'eligible_cases': len(candidates), 'selection': roster}
    protocol['inputs_sha256'] = hashlib.sha256((out / 'inputs.jsonl').read_bytes()).hexdigest()
    protocol['references_sha256'] = hashlib.sha256((out / 'references.jsonl').read_bytes()).hexdigest()
    (out / 'protocol.json').write_text(json.dumps(protocol, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'status': protocol['status'], 'questions': count, 'eligible_cases': len(candidates),
                      'image_files': len(image_files), 'max_main_requests': protocol['max_main_requests'],
                      'new_paid_requests': 0, 'source_ids': [x['source_id'] for x in inputs]}, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--count', type=int, default=12)
    args = parser.parse_args()
    prepare(args.out, args.count)
