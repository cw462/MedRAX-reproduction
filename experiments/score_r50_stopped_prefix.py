"""Honest user-stopped prefix scoring/public reproduction with the common adapter.

Every raw terminal is adapted before opening references; an incomplete stream
never receives a fabricated complete.json or zero native exit.
"""
import json
from pathlib import Path
import random

from score_cxr_author_alignment import adapt, outcomes

ARM = 'M43-IM-GT-S50-CXR6'


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def raw_adapt(run, inputs):
    run = Path(run)
    answers = []
    for ordinal, row in enumerate(inputs, 1):
        qid = row['question_id']
        pred = read(run / 'predictions' / ARM / (qid + '.json'))
        event = read(run / 'prediction_events' / (qid + '.json'))
        assert pred['question_id'] == qid and pred['ordinal'] == ordinal and pred['arm'] == ARM
        assert event['saved_prediction'] == pred and event['ordinal'] == ordinal
        call = run / 'services/calls/R50-AGENT' / qid / str(pred['main_calls'])
        result = read(call / 'result.json')
        response = read(call / 'response.json')
        assert result['response_received'] is True and not result.get('error')
        message = response['choices'][0]['message']
        content = message.get('content')
        if isinstance(content, list):
            content = '\n'.join(item.get('text', '') for item in content if isinstance(item, dict) and item.get('type') == 'text')
        if not isinstance(content, str) or message.get('tool_calls') or message.get('function_call'):
            content = None
        source = {'raw': content, 'call_path': call.relative_to(run).as_posix(),
            'ordinal': str(pred['main_calls']), 'reuse_chain': [], 'technical_stop': False,
            'evidence_status': 'received_terminal_text' if content else 'nonfinal_or_unavailable'}
        answers.append(adapt(row, pred, source))
    return answers


def grade_saved(run, inputs, answers, references):
    # Caller must finish and persist reference-free adaptation before loading references.
    run = Path(run)
    refs = {item['question_id']: item for item in references}
    rng = random.Random(0)
    details = []
    for row, answer in zip(inputs, answers):
        qid = row['question_id']
        pred = read(run / 'predictions' / ARM / (qid + '.json'))
        feedback = read(run / 'feedback' / (qid + '.json'))
        assert feedback['saved_prediction'] == pred and feedback['reference_annotation']['answer'] == refs[qid]['answer']
        assert pred['prediction_saved_at'] <= feedback['released_at']
        value = outcomes(row, answer, refs[qid]['answer'], rng)
        details.append({'question_id': qid, 'ordinal': pred['ordinal'],
            'subset': row['source']['subset'], 'reference': refs[qid]['answer'],
            'skill_injected': bool(pred['selected_skill_ids']), 'selected_skill_ids': pred['selected_skill_ids'],
            'same_image_prior': pred['same_image_ids'], 'adapted': answer,
            'aligned_correct': bool(value['aligned_correct'])})
    def counts(values):
        correct = sum(item['aligned_correct'] for item in values)
        return {'n': len(values), 'correct': correct,
            'accuracy_pct': 100 * correct / len(values) if values else None}
    subsets = {name: counts([item for item in details if item['subset'] == name]) for name in sorted({item['subset'] for item in details})}
    summary = {'status': 'user_stopped_incomplete', 'arm': ARM, 'dataset': 'chexbench',
        'questions': len(details), **counts(details), 'intended_dataset_n': 618, 'intended_total_n': 848,
        'unanswered_total': 848 - len(details), 'subsets': subsets,
        'macro_accuracy_of_present_subsets_pct': sum(value['accuracy_pct'] for value in subsets.values()) / len(subsets),
        'skill_injected': counts([item for item in details if item['skill_injected']]),
        'no_skill_injected': counts([item for item in details if not item['skill_injected']]),
        'absent_answers': sum(item['adapted']['answer_absent'] for item in details),
        'invalid_option_answers': sum(item['adapted']['choice_domain_invalid'] for item in details),
        'raw_whole_json_valid': sum(item['adapted']['raw_whole_json_valid'] for item in details),
        'all_raw_answers_adapted_before_references': True,
        'new_inference_calls': 0, 'historical_private_score_invoked': False,
        'corrected_harmed_net_vs_same_question_Skill_off': None,
        'causal_effect_identified': False,
        'limitations': 'Ordered stopped prefix, not the complete618/848 cohort. Skill groups differ by time/source. No same-question Skill-off counterfactual. SeparateSLAKE/VQA never started.'}
    return summary, details


def verify_public(evidence, out):
    from unittest.mock import patch
    from verify_public_online_skill_r50 import asset_normalizer
    evidence, out = Path(evidence).resolve(), Path(out).resolve()
    assert not out.exists() and not out.is_relative_to(evidence) and not evidence.is_relative_to(out)
    publication = read(evidence / 'publication_manifest.json')
    assert publication['status'] == 'user_stopped_incomplete' and publication['completed_prefix'] == 435
    assert publication['full_intended_total'] == 848 and publication['remaining_unanswered'] == 413
    normalize = asset_normalizer(evidence)
    original_read = read
    inputs = [json.loads(line) for line in (evidence / 'inputs.jsonl').read_text(encoding='utf-8').splitlines() if line.strip()]
    assert len(inputs) == 435
    for row in inputs:
        for name in row['images']:
            target = (evidence / name).resolve()
            assert target.is_relative_to(evidence) and target.is_file()
    normalized_inputs = normalize(inputs, evidence / 'inputs.jsonl')
    with patch(__name__ + '.read', side_effect=lambda path: normalize(original_read(path), Path(path))):
        answers = raw_adapt(evidence, normalized_inputs)
        out.mkdir(parents=True)
        (out / 'reference_free_adaptation.json').write_text(json.dumps(answers, ensure_ascii=False, indent=2), encoding='utf-8')
        references = [json.loads(line) for line in (evidence / 'references.jsonl').read_text(encoding='utf-8').splitlines() if line.strip()]
        summary, details = grade_saved(evidence, normalized_inputs, answers, references)
    expected = original_read(evidence / 'scores/summary.json')
    previous = original_read(evidence / 'scores/per_question.json')
    assert summary == expected, 'public_stopped_prefix_summary_changed'
    assert details == previous, 'public_stopped_prefix_raw_answers_or_grades_changed'
    (out / 'summary.json').write_text(json.dumps(dict(summary, public_reproduction_passed=True,
        private_run_paths_required=False, new_model_calls=0), ensure_ascii=False, indent=2), encoding='utf-8')
    (out / 'per_question.json').write_text(json.dumps(details, ensure_ascii=False, indent=2), encoding='utf-8')
    return summary


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(verify_public(args.evidence, args.out), ensure_ascii=False))
