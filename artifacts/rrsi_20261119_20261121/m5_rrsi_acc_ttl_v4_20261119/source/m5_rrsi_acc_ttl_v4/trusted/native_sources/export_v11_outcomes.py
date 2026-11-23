"""Export completed V11 outcomes without running inference or rescoring.

Only explicit fields are published. Correctness comes from existing scored
question-ID sets. Optional original-scorer labels are opened only after every
generation and score is complete, and only the fixed sixty answers are published.
Completed V10 score-event references must agree with that input. No raw checkpoint,
credential, request header, image payload, or model file is exported. Each input
file is loaded once per invocation. Source records and metrics are unchanged.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from decimal import Decimal
import json
from pathlib import Path
import re


RUNS = {'S1': 'v11_selector60', 'S2': 'v11_followup60', 'S3': 'v11_blindread60'}
ACCOUNTING_FIELDS = ('model_calls', 'tool_calls', 'input_tokens', 'output_tokens',
    'total_tokens', 'logical_cost_cny', 'incremental_cost_cny', 'usage_complete', 'issues')


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def read_jsonl(path):
    return [json.loads(line) for line in Path(path).read_text(encoding='utf-8-sig').splitlines() if line.strip()]


def index(rows):
    result = {row['question_id']: row for row in rows}
    if len(result) != len(rows):
        raise ValueError('Duplicate completed result')
    return result


def correct_ids(pair):
    ids = pair['question_ids']
    # V10's "corrections" already includes missing-P0 recovery; use the
    # explicitly separated fields so the same rule also works for V11.
    return (set(ids['kept_correct']) | set(ids['corrections_from_wrong_answer'])
            | set(ids['recovered_from_p0_failure']))


def pair_counts(pair):
    wrong = pair['corrections_from_wrong_answer']
    recovery = pair['recovered_from_p0_failure']
    harm = pair['harms']
    return {'wrong_legal_p0_answers_corrected': wrong, 'p0_failures_recovered': recovery,
            'correct_p0_answers_harmed': harm, 'net_without_failure_recovery': wrong-harm,
            'net_including_failure_recovery': wrong+recovery-harm}


def resources(accounting, timing=None):
    accounting = accounting or {}
    timing = timing or {}
    result = {key: accounting.get(key) for key in ACCOUNTING_FIELDS}
    if not accounting:
        result.update(model_calls=0, tool_calls=0, logical_cost_cny='0', incremental_cost_cny='0', issues=[])
    result['elapsed_s'] = timing.get('elapsed_s', 0 if not timing else None)
    result['started_utc'] = timing.get('started_utc')
    result['ended_utc'] = timing.get('ended_utc')
    return result


def compact_resources(resource, wall=None):
    result = {key: (resource.get(key) or {}).get('sum_observed') for key in
              ('model_calls', 'tool_calls', 'input_tokens', 'output_tokens', 'total_tokens',
               'logical_cost_cny', 'incremental_cost_cny', 'elapsed_s')}
    result['elapsed_s'] = {'summed_record_durations': result.pop('elapsed_s'),
                           'wall_interval': (wall or {}).get('elapsed_s')}
    if wall:
        result['started_utc'], result['ended_utc'] = wall.get('started_utc'), wall.get('ended_utc')
    return result


def stage_metadata(row):
    selector = row.get('selector') or {}
    observation = row.get('blind_observation') or row.get('new_observation') or {}
    observations = selector.get('observations') or []
    return {'route': row.get('route'), 'anonymous_choice': selector.get('choice'),
        'needs_followup': selector.get('needs_followup'),
        'followup_question': selector.get('followup_question'),
        'targeted_followup_question_used': row.get('followup_question'),
        'recorded_action': row.get('action'),
        'parse_warnings': selector.get('parse_warnings', []),
        'observation_parse_warnings': observation.get('parse_warnings', []),
        'structured_selector_observation_n': len(observations),
        'selector_observation_directions': [item.get('direction') for item in observations if isinstance(item, dict)],
        'selector_error': row.get('selector_error'), 'fallback': row.get('fallback'),
        'resources_added_in_this_stage': resources(row.get('accounting'), row.get('timing'))}


def transition(before, after, correctness, qids):
    changed = [q for q in qids if before[q] != after[q]]
    first, second = correctness
    return {'answer_changed_n': len(changed),
        'wrong_to_correct_n': sum(q not in first and q in second for q in changed),
        'correct_to_wrong_n': sum(q in first and q not in second for q in changed),
        'changed_but_still_wrong_n': sum(q not in first and q not in second for q in changed),
        'net_correct_count_change': len(second)-len(first), 'question_ids': changed}


def pair_structure(qids, answers, correctness):
    first, candidate = answers['P0'], answers['VKE_candidate']
    first_correct, candidate_correct = correctness['P0'], correctness['VKE_candidate']
    agreements = [q for q in qids if first[q] is not None and first[q] == candidate[q]]
    disagreements = [q for q in qids if first[q] is not None and candidate[q] is not None and first[q] != candidate[q]]
    union = first_correct | candidate_correct
    return {'legal_answer_agreements_n': len(agreements),
        'correct_agreements_n': sum(q in first_correct for q in agreements),
        'wrong_agreements_n': sum(q not in first_correct for q in agreements),
        'legal_answer_disagreements_n': len(disagreements),
        'corrective_disagreements_n': sum(q not in first_correct and q in candidate_correct for q in disagreements),
        'harmful_disagreements_n': sum(q in first_correct and q not in candidate_correct for q in disagreements),
        'both_wrong_disagreements_n': sum(q not in union for q in disagreements),
        'p0_missing_n': sum(first[q] is None for q in qids),
        'no_correct_choice_in_frozen_pair_n': len(qids)-len(union),
        'retrospective_oracle_union_correct_n': len(union),
        'oracle_note': 'Retrospective diagnostic ceiling using completed correctness flags; not an achieved algorithm result or a generation input.'}


def error_decomposition(qids, answers, correctness, stage):
    first, candidate, final = correctness['P0'], correctness['VKE_candidate'], correctness[stage]
    return {'wrong_or_missing_final_n': len(qids)-len(final),
        'no_correct_choice_in_frozen_pair_n': sum(q not in first and q not in candidate for q in qids),
        'available_correct_candidate_rejected_n': sum(q not in first and q in candidate and q not in final for q in qids),
        'correct_p0_replaced_by_wrong_candidate_n': sum(q in first and q not in final for q in qids)}


def require_completed_generation(root):
    """Check terminal metadata before any optional label input can be opened."""
    source = read_json(root/'runs/v10_accuracy60/status.json')
    if (source.get('status') != 'generation_complete' or source.get('planned_n') != 60
            or source.get('p0_completed') != 60 or source.get('plans_completed') != 60
            or source.get('branches_completed') != 180):
        raise ValueError('V10 generation is incomplete; publication labels have not been opened')
    for stage, name in RUNS.items():
        status = read_json(root/'runs'/name/'status.json')
        if (status.get('status') != 'generation_complete' or status.get('stage') != stage
                or status.get('planned_n') != 60 or status.get('completed_n') != 60):
            raise ValueError('V11 generation is incomplete; publication labels have not been opened')


def publication_references(labels_path, qids, existing):
    """Read exact labels (or their exact fixed-60 subset) once, without scoring."""
    selected, seen = {}, set()
    for row in read_jsonl(labels_path):
        q = row.get('question_id', row.get('qid'))
        if q not in qids:
            continue
        if q in seen:
            raise ValueError('Duplicate selected publication reference')
        seen.add(q)
        match = re.fullmatch(r'\s*([A-F])[.)]?\s*', row.get('answer') or '')
        if match is None:
            raise ValueError('Invalid selected original-scorer reference answer')
        selected[q] = match.group(1)
    for q in existing.keys() & selected.keys():
        if existing[q] != selected[q]:
            raise ValueError('Original label disagrees with completed score-event reference')
    return selected


def export(root, destination, *, labels_path=None, labels_source=None):
    root, destination = Path(root), Path(destination)
    require_completed_generation(root)
    v10 = root/'runs/v10_accuracy60'
    v10_metrics = read_json(v10/'paired_metrics.json')
    if v10_metrics.get('run_status') != 'completed':
        raise ValueError('V10 score is incomplete; publication labels have not been opened')
    p0_rows = index(read_jsonl(v10/'p0_results.jsonl'))
    vke_rows = index([row for row in read_jsonl(v10/'candidate_results.jsonl') if row['group'] == 'VKE'])
    metrics, records = {}, {}
    for stage, name in RUNS.items():
        folder = root/'runs'/name
        metrics[stage] = read_json(folder/'paired_metrics.json')
        records[stage] = index(read_jsonl(folder/'results.jsonl'))
        if metrics[stage]['run_status'] != 'completed' or metrics[stage]['stage'] != stage:
            raise ValueError('Only completed, previously scored stages may be exported')
    qids = list(records['S1'])
    if len(qids) != 60 or any(set(qids) != set(r) for r in [p0_rows, vke_rows, *records.values()]):
        raise ValueError('Export requires all original sixty outcomes at every stage')
    baseline = v10_metrics['groups']['VKE']
    retrospective_answers = {}
    for event in v10_metrics.get('case_events', []):
        q, answer = event.get('question_id'), event.get('reference')
        if q in qids and isinstance(answer, str) and answer in tuple('ABCDEF'):
            if q in retrospective_answers and retrospective_answers[q] != answer:
                raise ValueError('Conflicting completed score-event reference answers')
            retrospective_answers[q] = answer
    event_answer_n = len(retrospective_answers)
    reference_sources = {q: 'completed_v10_score_event' for q in retrospective_answers}
    label_answers = publication_references(labels_path, qids, retrospective_answers) if labels_path else {}
    matched_event_n = len(retrospective_answers.keys() & label_answers.keys())
    filled_from_labels_n = len(label_answers.keys() - retrospective_answers.keys())
    retrospective_answers.update(label_answers)
    reference_sources.update({q: 'original_isolated_scorer_label_input_publication_after_completion' for q in label_answers})
    reference_provenance = {
        'source': (labels_source or 'original isolated scorer label input') if labels_path else
                  'previously completed V10 paired_metrics.json case_events[].reference',
        'publication_after_completion': True,
        'retrospective_only_not_generation_input': True,
        'original_label_input_provided': labels_path is not None,
        'completed_score_event_reference_n': event_answer_n,
        'matched_completed_event_references_n': matched_event_n,
        'filled_from_original_label_input_n': filled_from_labels_n,
        'input_scope': 'Only fixed sixty question IDs are exported; no whole label file is published.',
        'missing_policy': 'null only when absent from both supplied original label input and completed score events; never inferred from wrong predictions'}
    correctness = {
        'P0': set(baseline['paired']['question_ids']['kept_correct']) | set(baseline['paired']['question_ids']['harms']),
        'VKE_candidate': correct_ids(baseline['candidate_paired']), 'S0': correct_ids(baseline['paired'])}
    correctness.update({stage: correct_ids(m['groups']['VKE']['paired']) for stage, m in metrics.items()})
    answers = {'P0': {q: p0_rows[q]['initial'] for q in qids},
        'VKE_candidate': {q: vke_rows[q]['candidate'] for q in qids},
        'S0': {q: vke_rows[q]['final'] for q in qids}}
    answers.update({stage: {q: rows[q]['final'] for q in qids} for stage, rows in records.items()})
    category_members = {}
    for category, stats in baseline['categories'].items():
        category_members[category] = set().union(*map(set, stats['paired']['question_ids'].values()))
    outcomes = []
    for q in qids:
        for stage in RUNS:
            if records[stage][q]['initial'] != answers['P0'][q] or records[stage][q]['candidate'] != answers['VKE_candidate'][q]:
                raise ValueError('Candidate binding differs between completed runs')
        p0, old = p0_rows[q], vke_rows[q]
        report = p0.get('report') or {}
        outcomes.append({'question_id': q, 'official_categories': [c for c, ids in category_members.items() if q in ids],
            'answers': {stage: values[q] for stage, values in answers.items()},
            'correct': {stage: q in ids for stage, ids in correctness.items()},
            'reference_answer': retrospective_answers.get(q),
            'reference_answer_source': reference_sources.get(q, 'absent_from_supplied_reference_sources'),
            'publication_after_completion': True,
            'retrospective_only_not_generation_input': True,
            'p0_failed': answers['P0'][q] is None,
            'p0_execution_status': p0.get('status'), 'p0_error_type': report.get('error_type'),
            'frozen_candidate_opportunity': ('p0_failure_recovery' if answers['P0'][q] is None
                else 'corrective' if q not in correctness['P0'] and q in correctness['VKE_candidate']
                else 'harmful' if q in correctness['P0'] and q not in correctness['VKE_candidate']
                else 'agreement' if answers['P0'][q] == answers['VKE_candidate'][q] else 'both_wrong_disagreement'),
            'cached_v10_resources': {
                'P0': resources(p0.get('accounting'), p0.get('timing')),
                'VKE_candidate': resources(old.get('candidate_accounting'), old.get('candidate_timing')),
                'S0_gate': resources(old.get('gate_accounting'), old.get('gate_timing'))},
            'S0_decision': {'decision': (old.get('gate') or {}).get('decision'),
                'candidate_error': bool(old.get('candidate_error')), 'gate_error': bool(old.get('gate_error')),
                'fallback': old.get('fallback')},
            'stages': {stage: stage_metadata(rows[q]) for stage, rows in records.items()}})
    aggregates = {'P0': {'correct': len(correctness['P0']), 'planned_n': 60, 'accuracy': len(correctness['P0'])/60,
                       'missing_n': sum(value is None for value in answers['P0'].values())},
                  'VKE_candidate': {'correct': len(correctness['VKE_candidate']), 'planned_n': 60,
                       'accuracy': len(correctness['VKE_candidate'])/60,
                       'role': 'cached_raw_candidate_reference_no_new_requests'},
                  'S0': {'correct': len(correctness['S0']), 'planned_n': 60, 'accuracy': len(correctness['S0'])/60,
                       **pair_counts(baseline['paired'])}}
    for stage, m in metrics.items():
        group = m['groups']['VKE']
        aggregates[stage] = {'correct': len(correctness[stage]), 'planned_n': 60,
            'accuracy': len(correctness[stage])/60, **pair_counts(group['paired']),
            'among_legal_p0_answers': group['among_p0_answered'],
            'candidate_opportunities': {key: value for key, value in group['selection_opportunities'].items() if key != 'question_ids'},
            'routes': group['routes'], 'needs_followup_n': group['needs_followup_n'],
            'additional_resources': compact_resources(m['new_resources'], m['wall_time'])}
    s0gate = baseline['gate']
    aggregates['S0']['candidate_opportunities'] = {key: value for key, value in s0gate.items() if key not in ('question_ids', 'decisions')}
    for stage in ('S0', *RUNS):
        aggregates[stage]['fixed_pair_error_decomposition'] = error_decomposition(qids, answers, correctness, stage)
    categories = {}
    for category, ids in category_members.items():
        categories[category] = {'denominator': len(ids),
            'correct': {stage: len(ids & correct) for stage, correct in correctness.items()}}
    transitions = {f'{a}_to_{b}': transition(answers[a], answers[b], (correctness[a], correctness[b]), qids)
        for a, b in [('S0','S1'),('S0','S2'),('S0','S3'),('S1','S2'),('S1','S3'),('S2','S3')]}
    costs = [Decimal(str(metrics[stage]['new_resources']['logical_cost_cny']['sum_observed'])) for stage in RUNS]
    generated = datetime.now(timezone.utc).isoformat()
    summary = {'schema_version': 1, 'generated_utc': generated, 'title': 'Completed V11 frozen-candidate experiments',
        'status': 'completed', 'fixed_planned_n': 60, 'candidate_group': 'VKE',
        'protocol': {'model': 'qwen3-vl-plus', 'temperature': 0.2, 'top_p': 0.95,
            'requested_output_cap': 1024, 'image_detail': 'auto', 'sdk_retries': 0,
            'xy_seed': 'medrax-v11-symmetric-20261030',
            'S1': {'eligible_disagreements': 21, 'calls_per_disagreement': 1, 'agreements_inherited': 37, 'p0_missing_inherited': 2},
            'S2': {'triggered_n': 19, 'trigger': 'frozen_S1_needs_followup_and_nonempty_question_without_selector_error',
                   'model_calls_per_trigger': 3, 'maximum_observations_per_trigger': 1,
                   'recorded_actions': {'reinspect_original': 9, 'crop_original_attempts': 9, 'inspect_existing': 1}},
            'S3': {'eligible_disagreements': 21, 'calls_per_disagreement': 2,
                   'reader_input': 'question_stem_and_original_images_only',
                   'matcher_input': 'unchanged_S1_anonymous_evidence_packet_plus_reader_observation',
                   'same_model_separate_contexts_not_statistical_independence': True},
            'budget': 'Existing ledger and its actual policy cap reused; no new pool or increase.',
            'documented_implementation_commits': {'V10': '48b0da61ee76791592f4f2b47592b6120c36c950',
                'S1_S2': '7d4df54', 'S3': '505e769', 'shell_LF_attributes': '137fd75'}},
        'results': aggregates, 'seven_overlapping_categories': categories, 'answer_transitions': transitions,
        'frozen_pair_structure': pair_structure(qids, answers, correctness),
        'combined_new_resources_S1_S2_S3': {
            'model_calls': sum(int(metrics[s]['new_resources']['model_calls']['sum_observed']) for s in RUNS),
            'tool_attempts': sum(int(metrics[s]['new_resources']['tool_calls']['sum_observed']) for s in RUNS),
            'recorded_logical_cost_cny': str(sum(costs, Decimal(0))),
            'sum_of_stage_wall_intervals_s': round(sum(metrics[s]['wall_time']['elapsed_s'] for s in RUNS), 3)},
        'development_targets': {'minimum_correct': 42, 'stretch_correct': 45, 'minimum_met': False},
        'retrospective_reference_answers': {'available_n': len(retrospective_answers),
            'unknown_n': len(qids)-len(retrospective_answers),
            'unknown_question_ids': [q for q in qids if q not in retrospective_answers],
            **reference_provenance},
        'limitations': [
            'Fixed previously examined development set; no independent main-table efficacy claim.',
            'P0 and VKE candidates are frozen; S1/S2/S3 outcomes cannot establish K/E contribution without matched V/VK/VKE comparisons.',
            'P0-failure recovery is distinct from correction of a wrong legal answer.',
            'S2 and S3 add calls/observations; this is not an equal-call-budget causal comparison.',
            'Reader and matcher use the same model with isolated inputs; errors may remain correlated.',
            'Model rationales and observations are not verified clinical explanations of outcomes.',
            'Crop counts are tool attempts, not independently verified useful image returns.',
            'Costs are recorded assumed-rate accounting values, not provider invoices.',
            'Known V10 P0 context accounting omits CNY 0.027680 already charged in its ledger; original records are unchanged.',
            'Reference answers are published only after all generation and scoring completed, for retrospective case review; they were never generation inputs.',
            'Correctness flags remain from existing completed scoring reports. Optional original label loading only fills retrospective reference answers; no model calls or rescoring occur.'],
        'files': {'per_question': 'per-question-outcomes.json',
                  'S1_S2_report': '../v11-selection60-2026-10-30.md',
                  'S3_report': '../v11-blindread60-2026-10-31.md'}}
    per_question = {'schema_version': 1, 'generated_utc': generated, 'planned_n': 60, 'candidate_group': 'VKE',
        'correctness_source': 'question-ID outcome sets in previously completed isolated scoring reports',
        'disclosure_note': 'Reference answers are published after all generations and scores completed. Optional original scorer labels fill missing score-event references; existing references must agree. Only the fixed sixty are exported, with no rescoring or generation changes.',
        'reference_answer_provenance': reference_provenance,
        'publication_after_completion': True,
        'retrospective_only_not_generation_input': True,
        'resource_note': 'cached_v10_resources are historical; stages contain only resources newly recorded by that V11 stage.',
        'records': outcomes}
    destination.mkdir(parents=True, exist_ok=True)
    for name, content in [('summary.json', summary), ('per-question-outcomes.json', per_question)]:
        target = destination/name
        temporary = target.with_suffix('.json.tmp')
        temporary.write_text(json.dumps(content, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
        temporary.replace(target)
    return {'planned_n': 60, 'correct': {stage: len(ids) for stage, ids in correctness.items()},
            'reference_answer_available_n': len(retrospective_answers),
            'reference_answer_unknown_n': len(qids)-len(retrospective_answers),
            'matched_completed_event_references_n': matched_event_n,
            'written': [str(destination/'summary.json'), str(destination/'per-question-outcomes.json')]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--out', type=Path)
    parser.add_argument('--labels', type=Path, help='Optional original scorer JSONL label input or exact fixed-60 subset; read only after completion guards')
    parser.add_argument('--labels-source', help='Provenance description of original scorer input when supplying its fixed-60 subset')
    args = parser.parse_args(argv)
    result = export(args.root, args.out or args.root/'reports/v11', labels_path=args.labels, labels_source=args.labels_source)
    print(json.dumps(result))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
