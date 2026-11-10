"""Local-only secondary analysis; reuse saved scores and raw observations unchanged."""
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

DEST = Path(__file__).resolve().parent
PREFIX = DEST.parent


def once(name, value):
    with (DEST / name).open('x', encoding='utf-8') as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)
        handle.write('\n')


def numeric_confidences(value):
    if isinstance(value, dict):
        for key, item in value.items():
            if 'confidence' in key.lower() and isinstance(item, (int, float)):
                yield key, item
            yield from numeric_confidences(item)
    elif isinstance(value, list):
        for item in value:
            yield from numeric_confidences(item)


def main():
    once('grounding_analysis.started.json', {'utc': datetime.now(timezone.utc).isoformat(),
        'scope': 'Existing 90 injected cases only; no SSH, model call, new grading or label-file reads.'})
    snapshot = json.loads((PREFIX / 'raw_prefix_snapshot.json').read_text(encoding='utf-8'))
    grades = {item['question_id']: item for item in json.loads((PREFIX / 'per_question.json').read_text(encoding='utf-8'))}
    summary = json.loads((DEST / 'summary.json').read_text(encoding='utf-8'))
    patterns = defaultdict(Counter)
    details = []
    confidence_count = 0
    two_initial_grounding = 0
    laterality_only = 0
    single_box_errors = []
    for case in snapshot['cases']:
        row = case['row']
        grade = grades[row['question_id']]
        if not grade['skill_injected']:
            continue
        observations = case['prediction']['observations']
        two_initial_grounding += [item.get('tool') for item in observations[:2]] == ['xray_phrase_grounding'] * 2
        normalized = {item.lower().replace('left', 'SIDE').replace('right', 'SIDE') for item in row['options'].values()}
        laterality_only += len(normalized) == 1
        groundings = []
        flags = []
        for observation in observations:
            if observation.get('tool') != 'xray_phrase_grounding':
                continue
            contents = observation['observation']
            predictions = []
            for item in contents if isinstance(contents, list) else [contents]:
                if isinstance(item, dict):
                    predictions.extend(item.get('predictions', []))
            box_count = sum(len(item.get('bounding_boxes', {}).get('image_coordinates', [])) for item in predictions)
            flags.append(box_count > 0)
            confidence_count += sum(1 for _ in numeric_confidences(contents))
            groundings.append({'query': observation['identity']['args'], 'box_count': box_count,
                'phrase_boxes': [{'phrase': item.get('phrase'), 'bounding_boxes': item.get('bounding_boxes')} for item in predictions]})
        assert len(flags) == 2
        kind = 'both_boxes' if all(flags) else 'one_boxes' if any(flags) else 'neither_boxes'
        correct = bool(grade['score']['aligned_correct'])
        patterns[kind].update(n=1, correct=int(correct), wrong=int(not correct))
        item = {'question_id': row['question_id'], 'ordinal': grade['ordinal'], 'pattern': kind,
            'correct': correct, 'choice': grade['adapted']['choice'], 'reference': grade['reference'],
            'options': row['options'], 'reason': case['prediction']['reason'], 'groundings': groundings}
        details.append(item)
        if kind == 'one_boxes' and not correct:
            single_box_errors.append(item)
    assert len(details) == two_initial_grounding == laterality_only == 90
    assert sum(item['correct'] for item in details) == 62
    result = {'utc': datetime.now(timezone.utc).isoformat(), 'n': len(details),
        'patterns': {key: dict(value, accuracy_pct=100 * value['correct'] / value['n']) for key, value in patterns.items()},
        'all_options_differ_only_in_left_vs_right': laterality_only,
        'initial_two_observations_both_grounding': two_initial_grounding,
        'returned_numeric_confidence_fields_in_grounding_observations': confidence_count,
        'single_box_errors': single_box_errors,
        'interpretation': 'The card box-presence decision rule seldom discriminates options (4/90); three of those four decisions are wrong against the saved benchmark labels. It is not a validated presence/laterality test.',
        'new_model_calls': 0, 'SSH_calls': 0, 'new_grading': False,
        'producer_or_predictions_modified': False}
    once('grounding_patterns.json', result)
    once('grounding_per_case.json', details)
    report = '''# R50 frozen-prefix Skill analysis requested by the user

This is a descriptive secondary analysis of the previously scored 420-question prefix. No new prediction, grading, label-file read, ongoing-protocol change, old R49 private scoring, or final-score receipt was performed. A separate bounded read captured five historical card/context/window files once. The prefix and all negative results remain unchanged.

| Comparison | Correct / N | Accuracy |
|---|---:|---:|
| All uninjected cases | 262 / 330 | 79.39% |
| OpenI before first injection | 68 / 92 | 73.91% |
| OpenI with this one card | 62 / 90 | 68.89% |

All 90 injected cases are consecutive OpenI fine-grained questions, ordinals331–420. Their two options differ only in left/right. The crude gap is −10.51 percentage points; within OpenI it is −5.02 points (−6.80% relative accuracy). The comparison is between different ordered cases, not a same-question intervention. There is no concurrent uninjected control. Neither a causal benefit nor causal harm is identified. Post-injection windows score19/30,24/30,19/30; this does not show a consistent improving trajectory.

The actual card s_39391f294d360026, Phrase Grounding Verification for Conflicting Binary Choices, was created from one source, chexbench_openi_0073. Its condition specifies conflicting/negative/ambiguous initial VLM or expert results. Its decisive rule chooses the option with valid grounding boxes; with two boxes it prefers higher confidence or more precise localization. The first injected context contains this exact accepted card. Its source_count1 and active status are provenance/lifecycle facts, not efficacy validation.

The first two observed tool calls are grounding for all90 injected cases;75/90 use grounding alone. In the earlier92 OpenI cases,79 used grounding, only22 had exactly two grounding calls, and18 used grounding alone. Mean main/tool calls change from3.674/2.902 to2.311/2.300. These are descriptive behavior/call-count changes; they do not establish net cost or causal efficiency because tasks differ and new embedding/META overhead is not included.

| Two grounding results | Correct / N | Consequence |
|---|---:|---|
| Both options return boxes | 49 / 70 | Box presence does not discriminate the two options |
| Neither option returns boxes | 12 / 16 | Card requires an unspecified fallback |
| Only one option returns boxes | 1 / 4 | Three wrong answers follow the claimed decisive rule |

No numeric confidence field exists in these180 grounding observations. The card's confidence branch therefore has no returned confidence value to compare. Box geometry or a plausible rationale is not a recorded confidence score or independent clinical verification. For example, chexbench_openi_0166 returns no left-base box and a right-base box; the answer chooses right (B), while the saved reference is left (A). This shows failure against the benchmark, without a fresh clinical image review or a claim of medically adjudicated truth.

Completed historical windows cover adoption attribution only for ordinals331–390:55 ADOPTED_POSITIVE include43 correct and12 wrong;5 ADOPTED_NEGATIVE are wrong. The12 wrong positive attributions receive negative numeric credit in the actual reward-based updater. Thus the positive status is a same-model process judgment, not55 corrections or55 beneficial interventions, and the implementation does not blindly give all55 positive numeric credit. The final30 cases in this frozen-prefix analysis lack completed-window attribution in the captured historical documents.

Current evidence establishes a real card, injection and a matching execution pattern. It does not establish accuracy improvement; observed accuracy is lower and the learned decision rule has concrete counterexamples. The proposed improvement direction is stricter procedural applicability, explicit non-decisive handling of boxes/absence/confidence, source-supported limits, and decision-rationale consistency checks. These are recommendations for a separately authorized method revision, not changes to the running R50 protocol. The already-approved stronger-model formation protocol addresses candidate eligibility and evidence anchoring; those changes alone do not prove this heuristic reliable. No additional ablation or third arm has been launched.

Evidence: [summary](summary.json), [grounding patterns](grounding_patterns.json), [per-case patterns](grounding_per_case.json), [actual credit bindings](credit_case_bindings.json), [original scored prefix](../per_question.json), [archived capture inventory](archived_evidence.completed.json). Original card/context/window bytes are under archived_evidence/.
'''
    with (DEST / 'ANALYSIS.md').open('x', encoding='utf-8') as handle:
        handle.write(report)
    once('grounding_analysis.completed.json', {'utc': datetime.now(timezone.utc).isoformat(),
        'status': 'completed', 'n': 90, 'correct': 62, 'new_inference_or_grading': False,
        'recommendations_implemented_in_running_protocol': False})
    print(json.dumps({'n': 90, 'patterns': result['patterns'], 'first_two_grounding': two_initial_grounding,
        'numeric_confidence_fields': confidence_count, 'report': str(DEST / 'ANALYSIS.md')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
