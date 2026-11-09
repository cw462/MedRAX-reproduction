"""Label-isolated V10 scoring: fixed inputs, seven overlapping task categories.

No inference modules are imported. Shared P0 and option plans are charged once;
branch accounting excludes both shared stages. Default reporting refuses to open
labels until generation has completed with unique terminals for every branch.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

try:
    from . import v9_metrics as base
except ImportError:
    import v9_metrics as base


GROUPS = ('V', 'VK', 'VKE')
CATEGORIES = ('detection', 'classification', 'localization', 'comparison',
              'relationship', 'diagnosis', 'characterization')


def _unique(rows, planned, *, grouped=False):
    indexed = {}
    for row in rows:
        if row.get('record_type') in ('started', 'start'):
            continue
        qid = base._qid(row)
        if qid not in planned:
            raise ValueError(f'Unplanned question: {qid}')
        group = row.get('group')
        if grouped and group not in GROUPS:
            raise ValueError(f'Unknown V10 group: {group}')
        key = (qid, group) if grouped else qid
        if key in indexed:
            raise ValueError(f'Duplicate terminal record: {key}')
        indexed[key] = row
    return indexed


def _categories(row):
    value = row.get('official_categories', row.get('official_group', []))
    if isinstance(value, str):
        value = value.split(',')
    if not isinstance(value, list) or not all(isinstance(x, str) for x in value):
        raise ValueError('Official task categories are missing or malformed')
    normalized = {x.strip().lower() for x in value}
    if normalized - set(CATEGORIES) - {'reasoning'}:
        raise ValueError('Unknown official task category')
    categories = normalized & set(CATEGORIES)
    if not categories:
        raise ValueError('Every selected question requires an official task category')
    return categories


def _paired(initial, predictions, labels, qids):
    result = base._paired(initial, predictions, labels, qids)
    # Missing baseline answers count as not correct in the planned denominator.
    # Keep those recoveries visible rather than silently excluding their gain.
    result['corrections_from_wrong_answer'] = result['corrections']
    result['question_ids']['corrections_from_wrong_answer'] = list(result['question_ids']['corrections'])
    result['corrections'] += result['recovered_from_p0_failure']
    result['question_ids']['corrections'] += result['question_ids']['recovered_from_p0_failure']
    result['net'] = result['corrections'] - result['harms']
    result['accuracy_difference'] = base._ratio(result['net'], len(qids))
    return result


def score(selection, p0_rows, candidate_rows, labels, *, shared_plans=None, allow_partial=False):
    """Pure scoring API. Synthetic smaller selections are accepted for tests."""
    rows = selection.get('rows', [])
    planned = [base._qid(row) for row in rows]
    if not planned or len(planned) != len(set(planned)):
        raise ValueError('Selection must contain unique planned questions')
    if selection.get('planned_n', len(planned)) != len(planned):
        raise ValueError('selection.planned_n differs from its rows')
    categories = {base._qid(row): _categories(row) for row in rows}
    if set(labels) != set(planned) or any(base.letter(labels[qid]) is None for qid in planned):
        raise ValueError('Labels must cover exactly the planned selection')
    labels = {qid: base.letter(labels[qid]) for qid in planned}
    p0 = _unique(p0_rows, planned)
    candidates = _unique(candidate_rows, planned, grouped=True)
    plans = _unique(shared_plans or [], planned)
    complete = len(p0) == len(planned) and len(candidates) == len(planned) * len(GROUPS)
    if not complete and not allow_partial:
        raise ValueError('Generation has incomplete terminals; do not score during inference')
    initial = {qid: base._prediction(p0.get(qid), 'initial', p0=True) for qid in planned}
    groups, events = {}, []
    for group in GROUPS:
        records = {qid: candidates[qid, group] for qid in planned if (qid, group) in candidates}
        raw = {qid: base._prediction(records.get(qid), 'candidate') for qid in planned}
        valid = {qid: raw[qid] if not (records.get(qid) or {}).get('candidate_error') else None for qid in planned}
        final = {qid: base._prediction(records.get(qid), 'final') for qid in planned}
        accepted = {qid: valid[qid] if valid[qid] is not None else initial[qid] for qid in planned}
        for qid, row in records.items():
            if base._prediction(row, 'initial') != initial[qid]:
                raise ValueError(f'Branch does not share recorded P0: {qid}/{group}')
            if final[qid] not in (initial[qid], valid[qid], None):
                raise ValueError(f'Final is neither P0 nor a valid candidate: {qid}/{group}')
        common = [qid for qid in planned if initial[qid] is not None and raw[qid] is not None and final[qid] is not None]
        groups[group] = {
            'status': '未运行' if not records else 'completed' if len(records) == len(planned) else 'incomplete',
            'terminal_records_n': len(records),
            'final': base._summary(final, labels, planned),
            'paired': _paired(initial, final, labels, planned),
            'raw_candidate': base._summary(raw, labels, planned),
            'candidate_paired': _paired(initial, raw, labels, planned),
            'valid_candidate_n': sum(x is not None for x in valid.values()),
            'policies': {
                'always_retain': {'summary': base._summary(initial, labels, planned), 'paired': _paired(initial, initial, labels, planned)},
                'always_accept': {'summary': base._summary(accepted, labels, planned), 'paired': _paired(initial, accepted, labels, planned)},
                'evidence_gate': {'summary': base._summary(final, labels, planned), 'paired': _paired(initial, final, labels, planned)}},
            'gate': base._gate_stats(records, initial, valid, final, labels, planned),
            'common_completed': {'n': len(common), 'p0': base._summary(initial, labels, common),
                                 'candidate': base._summary(raw, labels, common), 'final': base._summary(final, labels, common)},
            'resources': base._resources(records.values()),
            'observations': base._observations(records.values()),
            'injection': {'knowledge_n': sum(bool(x.get('k_ids')) for x in records.values()),
                          'experience_n': sum(bool(x.get('e_ids')) for x in records.values())},
            'categories': {category: {
                'p0': base._summary(initial, labels, [q for q in planned if category in categories[q]]),
                'final': base._summary(final, labels, [q for q in planned if category in categories[q]]),
                'paired': _paired(initial, final, labels, [q for q in planned if category in categories[q]])}
                for category in CATEGORIES}}
        for qid in planned:
            first, cand, answer, gold = initial[qid], raw[qid], final[qid], labels[qid]
            kinds = []
            for stage, value in (('candidate', cand), ('final', answer)):
                if first != gold and value == gold:
                    kinds.append(stage + ('_recovery_from_p0_failure' if first is None else '_correction'))
                elif first == gold and value != gold:
                    kinds.append(stage + ('_harm_missing' if value is None else '_harm_wrong_answer'))
            if kinds:
                row = records.get(qid) or {}
                events.append({'question_id': qid, 'group': group, 'events': kinds, 'initial': first,
                    'candidate': cand, 'final': answer, 'reference': gold,
                    'gate_decision': (row.get('gate') or {}).get('decision'),
                    'candidate_error': bool(row.get('candidate_error')), 'gate_error': bool(row.get('gate_error')),
                    'fallback': row.get('fallback'), 'changed_attributes': row.get('changed_attributes'),
                    'original_observation_refs': row.get('original_observation_refs', []),
                    'new_observation_refs': [x.get('evidence_ref') for x in row.get('new_observations', [])],
                    'evidence_refs': (row.get('gate') or {}).get('evidence_refs', []),
                    'candidate_record_present': bool(row)})
    primary = groups['VKE']
    return {'schema_version': 1, 'implementation': 'v10-accuracy',
        'created_utc': datetime.now(timezone.utc).isoformat(),
        'run_status': 'completed' if complete else 'incomplete_provisional',
        'planned_n': len(planned), 'planned_groups': list(GROUPS), 'p0_terminal_n': len(p0),
        'candidate_terminal_n': len(candidates), 'shared_plan_terminal_n': len(plans),
        'p0': base._summary(initial, labels, planned), 'groups': groups, 'case_events': events,
        'p0_resources': base._resources(p0.values()), 'shared_plan_resources': base._resources(plans.values()),
        'total_resources': base._resources([*p0.values(), *plans.values(), *candidates.values()]),
        'category_denominators': {c: sum(c in v for v in categories.values()) for c in CATEGORIES},
        'primary_decision': {'group': 'VKE', 'minimum_net_gain': 3, 'aspirational_net_gain': 6,
            'net': primary['paired']['net'] if complete else None,
            'minimum_development_goal_met': primary['paired']['net'] >= 3 if complete else None,
            'aspirational_development_goal_met': primary['paired']['net'] >= 6 if complete else None,
            'independent_main_table_goal_evaluated': False},
        'limitations': [
            'Fixed development set; not independent main-table evaluation or a stable effect estimate.',
            'Overall counts each planned question once; seven official categories overlap and are not averaged.',
            'Missing answers count as not correct; P0 failure recoveries are included in corrections and shown separately.',
            'Shared P0 and shared blind option planning are billed once; branch resource totals exclude them.',
            'The shared plan consumes one of the four logical candidate-stage model requests per branch.',
            'Exception fallback is not a successful gate rejection; unknown visual evidence quality remains unadjudicated.',
            'Logical ledger costs are assumed-rate accounting, not provider invoices.',
            'No inference-stage file has been modified by scoring.']}


def _markdown(payload):
    pct = base._percent
    n = payload['planned_n']
    p0 = payload['p0']
    lines = ['# V10 paired accuracy results', '',
        f"Run status: **{payload['run_status']}**. Planned N={n}; failures remain in the denominator.", '',
        '| Group | Correct / N | Accuracy | Corrections | Harms | Net gain | P0 failure recoveries |',
        '|---|---:|---:|---:|---:|---:|---:|',
        f"| P0 | {p0['correct']}/{n} | {pct(p0['accuracy_over_planned'])} | — | — | — | — |"]
    for group, data in payload['groups'].items():
        final, pair = data['final'], data['paired']
        status = '' if data['status'] == 'completed' else f" ({data['status']})"
        lines.append(f"| {group}{status} | {final['correct']}/{n} | {pct(final['accuracy_over_planned'])} | {pair['corrections']} | {pair['harms']} | {pair['net']:+d} | {pair['recovered_from_p0_failure']} |")
    lines += ['', '## Seven overlapping official task categories', '',
        '| Category | N | P0 | V | VK | VKE | VKE corrections | VKE harms | VKE net |',
        '|---|---:|---:|---:|---:|---:|---:|---:|---:|']
    for category in CATEGORIES:
        stats = {g: payload['groups'][g]['categories'][category] for g in GROUPS}
        c = stats['VKE']; pair = c['paired']
        cells = [category.title(), str(c['p0']['planned_n']), pct(c['p0']['accuracy_over_planned'])]
        cells += [pct(stats[g]['final']['accuracy_over_planned']) for g in GROUPS]
        cells += [str(pair['corrections']), str(pair['harms']), f"{pair['net']:+d}"]
        lines.append('| ' + ' | '.join(cells) + ' |')
    lines += ['', 'Overall uses unique questions, not the sum or average of category scores.', '',
        '## Candidate quality and gate opportunities', '',
        '| Group | Valid candidates | Correct raw candidates | Corrective candidates | Harmful candidates | Corrections retained | Harms prevented | Candidate errors | Gate errors |',
        '|---|---:|---:|---:|---:|---:|---:|---:|---:|']
    for group, data in payload['groups'].items():
        gate = data['gate']
        values = [group, data['valid_candidate_n'], data['raw_candidate']['correct'],
            gate['correction_candidates'], gate['harmful_candidates'], gate['corrections_retained'],
            gate['harms_prevented'], gate['candidate_errors'], gate['gate_errors']]
        lines.append('| ' + ' | '.join(map(str, values)) + ' |')
    lines += ['', 'Gate opportunity counts exclude P0 failures, which can recover directly from an independent candidate.', '',
        '## Time and accounting', '',
        '| Stage | Records | Elapsed total (s) | Model calls | Tool attempts | Input tokens | Output tokens | Logical CNY |',
        '|---|---:|---:|---:|---:|---:|---:|---:|']
    resources = [('Shared P0', payload['p0_resources']), ('Shared option plan', payload['shared_plan_resources'])]
    resources += [(g, payload['groups'][g]['resources']) for g in GROUPS]
    resources += [('Total (shared stages once)', payload['total_resources'])]
    for stage, res in resources:
        values = [stage, res['records_n']] + [res[k]['sum_observed'] for k in ('elapsed_s', 'model_calls', 'tool_calls', 'input_tokens', 'output_tokens', 'logical_cost_cny')]
        lines.append('| ' + ' | '.join('N/A' if x is None else str(x) for x in values) + ' |')
    lines += ['', 'Elapsed totals sum stage durations and are not a replacement for workflow wall time. See JSON for missing usage fields and injection counts.', '',
        '## Decision and limits', '']
    if payload['run_status'] == 'completed':
        decision = payload['primary_decision']
        lines += [f"Prespecified primary VKE net gain: {decision['net']:+d}/{n}. Minimum development target (+3 questions): {'met' if decision['minimum_development_goal_met'] else 'not met'}. Independent main-table evaluation: **not run in this diagnostic**.", '']
    else:
        lines += ['Provisional: incomplete groups are marked 未运行/incomplete; no efficacy or continuation decision is drawn.', '']
    lines += ['- ' + item for item in payload['limitations']]
    return '\n'.join(lines) + '\n'


def generate_report(run_dir, labels_path, *, allow_partial=False):
    run_dir = Path(run_dir)
    selection = json.loads((run_dir/'selection.json').read_text(encoding='utf-8-sig'))
    planned = [base._qid(row) for row in selection['rows']]
    p0_rows = base.read_jsonl(run_dir/'p0_results.jsonl')
    candidates = base.read_jsonl(run_dir/'candidate_results.jsonl')
    plans = base.read_jsonl(run_dir/'shared_plans.jsonl')
    p0 = _unique(p0_rows, planned)
    grouped = _unique(candidates, planned, grouped=True)
    plan_index = _unique(plans, planned)
    if not allow_partial:
        status_path = run_dir/'status.json'
        status = json.loads(status_path.read_text(encoding='utf-8-sig')) if status_path.exists() else {}
        if (status.get('status') != 'generation_complete' or len(p0) != len(planned)
                or len(grouped) != len(planned)*len(GROUPS) or len(plan_index) != len(planned)):
            raise ValueError('Generation is incomplete; isolated labels have not been opened')
    payload = score(selection, p0_rows, candidates, base._labels(labels_path, planned),
                    shared_plans=plans, allow_partial=allow_partial)
    base._atomic(run_dir/'paired_metrics.json', json.dumps(payload, ensure_ascii=False, indent=2)+'\n')
    base._atomic(run_dir/'paired_metrics.md', _markdown(payload))
    base._atomic(run_dir/'case_review.md', base._review(payload).replace('# V9 correction', '# V10 correction', 1))
    return payload


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', required=True, type=Path)
    parser.add_argument('--labels', required=True, type=Path)
    parser.add_argument('--allow-partial', action='store_true', help='Explicit provisional scoring; no efficacy decision')
    args = parser.parse_args(argv)
    result = generate_report(args.run, args.labels, allow_partial=args.allow_partial)
    print(json.dumps({'status': result['run_status'], 'planned_n': result['planned_n'],
        'p0_correct': result['p0']['correct'],
        'final_correct': {g: result['groups'][g]['final']['correct'] for g in GROUPS}}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
