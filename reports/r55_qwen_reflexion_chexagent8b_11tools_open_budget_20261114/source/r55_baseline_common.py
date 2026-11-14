"""Shared cohort and answer scoring for the R55 baselines."""

import json
from pathlib import Path
import random
import re
import sys


DATASETS = {'chexbench': 618, 'slake': 114, 'vqarad': 116}
VQA_TOOLS = ('medgemma', 'medvlm_r1', 'llava_rad', 'chest_xray_expert', 'llava_med_qa')
METHODS = ('cot', 'react', 'reflexion', 'critic')


def bind(root):
    sys.path[:0] = [str(root / 'code/experiments'), str(root / 'bin')]


def data_root(root, dataset):
    return (root / 'data' / dataset).resolve()


def manifest_for(root, dataset):
    manifest = json.loads((root / 'manifests/M2' / f'{dataset}.json').read_text())
    rows = manifest['inputs']
    ids = {row['question_id'] for row in rows}
    if len(ids) != len(rows) or len(rows) != DATASETS[dataset] or ids != set(manifest['reference_files']):
        raise ValueError(f'Unexpected frozen cohort: {dataset}')
    if any(len(row['images']) != 1 for row in rows):
        raise ValueError('This benchmark expects one original image per question')
    return manifest


def prompt_for(row):
    text = row['question']
    if row.get('options'):
        text += '\n' + '\n'.join(f'{letter}. {value}' for letter, value in row['options'].items())
        return text + '\nGive only the letter of the best option as the answer.'
    return (text + '\nReply with only the shortest answer, without explanation or extra sentences. '
            'For a yes/no question, reply only Yes or No. Keep any required side, number or qualifier.')


def dataset_out(out, arm, dataset):
    return out / arm / dataset


def prediction_path(out, row):
    from online_memory_r49 import safe_qid

    return out / 'predictions' / f'{safe_qid(row["question_id"])}.json'


def score_dataset(root, out, arm, dataset):
    from cxr_author_alignment import choice, extract
    from online_memory_r49 import read, save_once
    from r54_author_metrics import outcomes

    manifest = manifest_for(root, dataset)
    folder = dataset_out(out, arm, dataset)
    if (folder / 'summary.json').is_file():
        summary = read(folder / 'summary.json')
        if (summary['arm'], summary['dataset'], summary['questions']) != (arm, dataset, len(manifest['inputs'])):
            raise ValueError(f'Saved score identity changed for {arm}/{dataset}')
        return summary
    predictions = [prediction_path(folder, row) for row in manifest['inputs']]
    if not all(path.is_file() for path in predictions):
        return None
    cases = []
    rng = random.Random(0)
    for row, path in zip(manifest['inputs'], predictions, strict=True):
        qid = row['question_id']
        record = read(path)
        if record['question_id'] != qid or record['arm'] != arm:
            raise ValueError(f'Wrong prediction identity: {path}')
        source = record['raw']
        if arm == 'medvlm_r1' and source:
            matches = re.findall(r'<answer>\s*(.*?)\s*</answer>', source, flags=re.S | re.I)
            if matches:
                source = '\n'.join('Answer: ' + ' '.join(value.split()) for value in matches)
            elif '</think>' in source:
                source = source.rsplit('</think>', 1)[1].strip()
            elif '<think>' in source or '<answer>' in source:
                source = None
        options = row.get('options', {})
        adapted = {'explicit_answer': extract(source, qid, options).answer}
        answer = adapted['explicit_answer']
        adapted['choice'] = choice(answer, options) if answer is not None and options else None
        ref_path = root / 'refs' / dataset / manifest['reference_files'][qid]['file']
        reference = read(ref_path)
        if reference['question_id'] != qid:
            raise ValueError(f'Wrong reference identity: {ref_path}')
        measures = outcomes(row, adapted, reference['answer'], rng)
        cases.append({
            'question_id': qid, 'question': row['question'], 'options': options, 'images': row['images'],
            'answer': answer, 'choice': adapted['choice'], 'reference': reference['answer'],
            'correct': measures['aligned_correct'], 'word_recall': measures['word_recall'],
            'explicit_scorable': answer is not None and (not options or adapted['choice'] is not None),
            'elapsed_s': record['elapsed_s'], 'calls': record.get('calls', {}),
        })
    correct = sum(case['correct'] for case in cases)
    summary = {
        'arm': arm, 'dataset': dataset, 'questions': len(cases), 'correct': correct,
        'accuracy_pct': 100 * correct / len(cases),
        'explicit_scorable': sum(case['explicit_scorable'] for case in cases),
        'qwen_calls': sum(case['calls'].get('qwen', 0) for case in cases),
        'tool_calls': sum(case['calls'].get('tools', 0) for case in cases),
        'failed_tool_calls': sum(case['calls'].get('failed_tools', 0) for case in cases),
        'elapsed_case_seconds': round(sum(case['elapsed_s'] for case in cases), 2),
    }
    save_once(folder / 'per_question.json', cases)
    save_once(folder / 'summary.json', summary)
    print(json.dumps(summary, ensure_ascii=False), flush=True)
    return summary
