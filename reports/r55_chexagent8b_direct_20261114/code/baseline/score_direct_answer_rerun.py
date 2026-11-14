"""Score explicit direct answers, keeping the historical exact-match metric."""

import argparse
import json
import re
from pathlib import Path

from r55_baseline_common import bind, DATASETS, manifest_for, prediction_path, score_dataset


MODELS = ('medvlm_r1', 'llava_rad', 'chest_xray_expert', 'llava_med_qa')
PREFIX = re.compile(
    r'^(?:\*{1,2}\s*)?(?:'
    r'(?:final\s+answer|answer|correct\s+(?:option|answer)|best\s+option|option)\s*[:：]\s*'
    r'|(?:the\s+)?(?:best\s+option|correct\s+(?:option|answer)|answer)'
    r'(?:\s+for\s+(?:this|the)\s+[^:\n]{1,80})?\s+is\s*[:：]?\s*'
    r'|option\s+(?=[A-Z]\b))', re.I,
)
LETTER_WITH_TEXT = re.compile(r'^\(?([A-Z])(?:\)\s*[.:：]?|[.:：]|\s+[-–—])\s*(.+)$', re.I | re.S)
POLAR = re.compile(r'^(yes|no)(?=\s*(?:[.,:;!–—-]|$)|\s+(?:because|as|there|it|the|this)\b)', re.I)
POLAR_QUESTION = re.compile(
    r'^\s*(?:is|are|was|were|do|does|did|can|could|has|have|had|will|would|should)\b', re.I,
)
EXPLANATION = re.compile(r'\s+(?:because|since)\b|[.;!?](?:\s+|$)|\n|\s*[–—]\s*', re.I)
SECOND_POLAR = re.compile(r'(?:^|[.!?;])\s*(yes|no)(?=\s*[,.:;!–—-]|\s*$)', re.I)


def normalize(text):
    from cxr_author_alignment import m4cxr_normalize

    return ' '.join(m4cxr_normalize(text.strip().strip('*`').strip('!?;:')).split())


def compact_answer(raw, row):
    from cxr_author_alignment import choice, extract

    options = row.get('options') or {}
    if isinstance(raw, str):
        tags = re.findall(r'<answer>\s*(.*?)\s*</answer>', raw, flags=re.I | re.S)
        if tags:
            raw = '\n'.join('Answer: ' + ' '.join(value.split()) for value in tags)
        elif re.search(r'<\s*/?\s*(?:think|answer)\b', raw, re.I):
            return None, 'structured_reply_without_final_answer'
    extracted = extract(raw, row['question_id'], options)
    if extracted.answer is None:
        return None, extracted.mechanism
    answer = PREFIX.sub('', extracted.answer.strip().strip('*`')).strip().strip('*`')
    if options:
        legal = choice(answer, options)
        if legal:
            return legal, 'explicit_choice'
        folded_options = {k: normalize(v) for k, v in options.items()}
        value = normalize(answer)
        matches = [k for k, v in folded_options.items() if v == value]
        if len(matches) == 1:
            return matches[0], 'choice_text'
        match = LETTER_WITH_TEXT.fullmatch(answer)
        if not match or match[1].upper() not in options:
            return None, 'no_explicit_choice'
        letter, text = match[1].upper(), match[2].lstrip('*` ')
        # Requiring agreement prevents a letter in abnormal text from being scored.
        if folded_options[letter] == normalize(text):
            return letter, 'letter_and_option_text'
        polarity = POLAR.match(text)
        if polarity and polarity[1].lower() == folded_options[letter]:
            return letter, 'letter_and_option_polarity'
        return None, 'unresolved_letter_and_text'

    polarity = POLAR.match(answer)
    if POLAR_QUESTION.match(row['question']) and polarity:
        later = SECOND_POLAR.findall(answer[polarity.end():])
        if any(value.lower() != polarity[1].lower() for value in later):
            return None, 'conflicting_polarity'
        return polarity[1].lower(), 'explicit_polarity'
    if extracted.mechanism != 'plain_reply' or answer != extracted.answer.strip():
        answer = EXPLANATION.split(answer, maxsplit=1)[0]
    return normalize(answer) or None, 'short_text'


def evaluate(root, raw_dir, out, arm, dataset):
    from online_memory_r49 import read, save_once

    exact = score_dataset(root, raw_dir, arm, dataset)
    if exact is None:
        raise ValueError(f'Incomplete predictions for {arm}/{dataset}')
    directory = raw_dir / arm / dataset
    outcomes = {r['question_id']: r['correct'] for r in read(directory / 'per_question.json')}
    cohort = manifest_for(root, dataset)
    cases = []
    for row in cohort['inputs']:
        qid = row['question_id']
        record = read(prediction_path(directory, row))
        answer, mechanism = compact_answer(record['raw'], row)
        ref = read(root / 'refs' / dataset / cohort['reference_files'][qid]['file'])
        if ref['question_id'] != qid:
            raise ValueError(f'Reference identity changed for {qid}')
        expected = ref['answer'] if row.get('options') else normalize(ref['answer'])
        cases.append({'question_id': qid, 'answer': answer, 'extraction': mechanism,
                      'expected': expected, 'exact_correct': bool(outcomes[qid]), 'correct': answer == expected})
    correct = sum(row['correct'] for row in cases)
    summary = {'arm': arm, 'dataset': dataset, 'questions': len(cases), 'correct': correct,
               'accuracy_pct': 100 * correct / len(cases), 'exact_correct': exact['correct'],
               'exact_accuracy_pct': exact['accuracy_pct'], 'explicit_answers': sum(r['answer'] is not None for r in cases),
               'recovered_correct': sum(r['correct'] and not r['exact_correct'] for r in cases),
               'lost_correct': sum(not r['correct'] and r['exact_correct'] for r in cases),
               'failed_tool_calls': exact['failed_tool_calls']}
    save_once(out / arm / dataset / 'per_question.json', cases)
    save_once(out / arm / dataset / 'summary.json', summary)
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root', type=Path)
    parser.add_argument('predictions', type=Path)
    parser.add_argument('results', type=Path)
    parser.add_argument('model', choices=MODELS)
    args = parser.parse_args()
    bind(args.root)
    for ds in DATASETS:
        print(json.dumps(evaluate(args.root, args.predictions, args.results, args.model, ds)), flush=True)
