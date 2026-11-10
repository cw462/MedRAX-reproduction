"""Isolated scoring for cached-candidate V11 selection experiments.

Only the completed-run entry point opens labels. No inference module or model is
imported; source V10 and V11 predictions are read without modification. Technical
failure recovery is reported separately from correction of a wrong legal answer.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path

try:
    from . import v9_metrics as base
    from .v10_metrics import CATEGORIES, _categories
except ImportError:
    import v9_metrics as base
    from v10_metrics import CATEGORIES, _categories

GROUPS = ('V', 'VK', 'VKE')


def _index(rows, planned, *, grouped=False):
    result = {}
    for row in rows:
        qid = base._qid(row)
        if qid not in planned:
            raise ValueError('Unplanned question in cached selection results')
        group = row.get('group')
        if grouped and group not in GROUPS:
            raise ValueError('Unknown selection group')
        key = (qid, group) if grouped else qid
        if key in result:
            raise ValueError('Duplicate terminal selection record')
        result[key] = row
    return result


def _paired(initial, final, labels, planned):
    pair = base._paired(initial, final, labels, planned)
    wrong = pair.pop('corrections')
    pair['corrections_from_wrong_answer'] = wrong
    pair['question_ids']['corrections_from_wrong_answer'] = pair['question_ids'].pop('corrections')
    pair['net_without_failure_recovery'] = wrong - pair['harms']
    pair['total_corrective_transitions'] = wrong + pair['recovered_from_p0_failure']
    pair['net'] = pair['total_corrective_transitions'] - pair['harms']
    pair['accuracy_difference'] = base._ratio(pair['net'], len(planned))
    return pair


def _opportunities(records, initial, candidates, final, labels, planned):
    names = ('corrective_candidates', 'harmful_candidates', 'corrections_kept_total',
             'corrections_kept_by_selection', 'corrections_kept_by_fallback',
             'corrections_rejected_by_selection', 'corrections_lost_to_error',
             'harmful_candidates_blocked_total', 'harms_blocked_by_selection',
             'harms_blocked_by_fallback', 'harmful_candidates_selected',
             'harmful_candidates_selected_by_fallback', 'selector_errors')
    ids = {name: [] for name in names}
    for q in planned:
        row = records[q]
        technical = bool(row.get('selector_error') or row.get('fallback'))
        if technical:
            ids['selector_errors'].append(q)
        first, cand, answer, gold = initial[q], candidates[q], final[q], labels[q]
        if first is None or cand is None or first == cand:
            continue
        if first != gold and cand == gold:
            ids['corrective_candidates'].append(q)
            if answer == cand:
                ids['corrections_kept_total'].append(q)
                ids['corrections_kept_by_fallback' if technical else 'corrections_kept_by_selection'].append(q)
            elif technical:
                ids['corrections_lost_to_error'].append(q)
            else:
                ids['corrections_rejected_by_selection'].append(q)
        elif first == gold and cand != gold:
            ids['harmful_candidates'].append(q)
            if answer == first:
                ids['harmful_candidates_blocked_total'].append(q)
                ids['harms_blocked_by_fallback' if technical else 'harms_blocked_by_selection'].append(q)
            elif answer == cand:
                ids['harmful_candidates_selected_by_fallback' if technical else 'harmful_candidates_selected'].append(q)
    return {**{k: len(v) for k, v in ids.items()}, 'question_ids': ids,
            'correction_retention_rate': base._ratio(len(ids['corrections_kept_total']), len(ids['corrective_candidates'])),
            'harm_blocking_rate': base._ratio(len(ids['harmful_candidates_blocked_total']), len(ids['harmful_candidates']))}


def _wall_time(rows):
    starts, ends = [], []
    for row in rows:
        timing = row.get('timing') or {}
        for key, values in [('started_utc', starts), ('ended_utc', ends)]:
            value = timing.get(key)
            if value:
                try:
                    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
                    if parsed.tzinfo:
                        values.append(parsed)
                except (ValueError, TypeError, AttributeError):
                    pass
    if not starts or not ends:
        return {'started_utc': None, 'ended_utc': None, 'elapsed_s': None}
    first, last = min(starts), max(ends)
    return {'started_utc': first.isoformat(), 'ended_utc': last.isoformat(),
            'elapsed_s': round((last-first).total_seconds(), 3)}


def score(selection, p0_rows, source_rows, result_rows, labels, *, previous_rows=None):
    """Pure scoring; small synthetic selections are accepted by this function."""
    planned = [base._qid(row) for row in selection.get('rows', [])]
    if not planned or len(planned) != len(set(planned)) or selection.get('planned_n') != len(planned):
        raise ValueError('Selection requires unique planned questions')
    categories = {base._qid(row): _categories(row) for row in selection['rows']}
    if set(labels) != set(planned) or any(base.letter(labels[q]) is None for q in planned):
        raise ValueError('Labels must cover precisely the planned selection')
    labels = {q: base.letter(labels[q]) for q in planned}
    p0 = _index(p0_rows, planned)
    source = _index(source_rows, planned, grouped=True)
    result = _index(result_rows, planned, grouped=True)
    previous = _index(previous_rows or [], planned, grouped=True)
    groups = [g for g in GROUPS if any(key[1] == g for key in result)]
    stages = {row.get('stage') for row in result_rows}
    if len(stages) != 1 or not stages <= {'S1', 'S2'}:
        raise ValueError('Each run requires exactly one stage, S1 or S2')
    stage = next(iter(stages))
    if len(p0) != len(planned) or not groups:
        raise ValueError('Incomplete fixed source or selection generation')
    initial = {q: base._prediction(p0[q], 'initial', p0=True) for q in planned}
    payload = {'schema_version': 1, 'implementation': 'v11-cached-selection',
        'created_utc': datetime.now(timezone.utc).isoformat(), 'run_status': 'completed',
        'planned_n': len(planned), 'stage': stage, 'planned_groups': groups,
        'p0': base._summary(initial, labels, planned), 'groups': {},
        'category_denominators': {c: sum(c in v for v in categories.values()) for c in CATEGORIES},
        'new_resources': base._resources(result_rows), 'wall_time': _wall_time(result_rows)}
    payload['new_resources']['cost_note'] = 'Only resources recorded by this new run are counted; cached V10 calls are not charged again. Assumed-rate ledger accounting, not provider invoices.'
    for g in groups:
        if any((q, g) not in result or (q, g) not in source for q in planned):
            raise ValueError('Incomplete selected group; full planned denominator required')
        records = {q: result[q, g] for q in planned}
        candidates = {q: base._prediction(source[q, g], 'candidate') for q in planned}
        s0 = {q: base._prediction(source[q, g], 'final') for q in planned}
        final = {q: base._prediction(records[q], 'final') for q in planned}
        for q in planned:
            row = records[q]
            if (base._prediction(row, 'initial') != initial[q]
                    or base._prediction(source[q, g], 'initial') != initial[q]
                    or base._prediction(row, 'candidate') != candidates[q]):
                raise ValueError('Result does not reuse the exact recorded P0 and candidate')
            if final[q] not in (initial[q], candidates[q], None) or s0[q] not in (initial[q], candidates[q], None):
                raise ValueError('Final answer is outside the two frozen candidates')
        data = {'S0': {'final': base._summary(s0, labels, planned), 'paired': _paired(initial, s0, labels, planned)},
            'final': base._summary(final, labels, planned), 'paired': _paired(initial, final, labels, planned),
            'raw_candidate': base._summary(candidates, labels, planned),
            'delta_correct_vs_S0': sum(final[q] == labels[q] for q in planned)-sum(s0[q] == labels[q] for q in planned),
            'selection_opportunities': _opportunities(records, initial, candidates, final, labels, planned),
            'routes': dict(Counter(str(row.get('route', 'unknown')) for row in records.values())),
            'needs_followup_n': sum((row.get('selector') or {}).get('needs_followup') is True for row in records.values()),
            'resources': base._resources(records.values()), 'wall_time': _wall_time(records.values()),
            'categories': {}, 'case_changes': []}
        p0_answered = [q for q in planned if initial[q] is not None]
        data['among_p0_answered'] = {'n': len(p0_answered), 'p0': base._summary(initial, labels, p0_answered),
            'final': base._summary(final, labels, p0_answered)}
        if previous:
            if any((q, g) not in previous for q in planned):
                raise ValueError('Previous stage requires all planned questions')
            prev = {q: base._prediction(previous[q, g], 'final') for q in planned}
            for q in planned:
                if (base._prediction(previous[q, g], 'initial') != initial[q]
                        or base._prediction(previous[q, g], 'candidate') != candidates[q]):
                    raise ValueError('Previous run uses different frozen candidates')
            data['S1'] = {'final': base._summary(prev, labels, planned), 'paired': _paired(initial, prev, labels, planned)}
            data['delta_correct_vs_S1'] = sum(final[q] == labels[q] for q in planned)-sum(prev[q] == labels[q] for q in planned)
        for category in CATEGORIES:
            subset = [q for q in planned if category in categories[q]]
            data['categories'][category] = {'p0': base._summary(initial, labels, subset),
                'S0': base._summary(s0, labels, subset), 'final': base._summary(final, labels, subset),
                'paired': _paired(initial, final, labels, subset)}
        for q in planned:
            if final[q] != s0[q]:
                data['case_changes'].append({'question_id': q, 'initial': initial[q], 'candidate': candidates[q],
                    'S0': s0[q], stage: final[q], 'S0_correct': s0[q] == labels[q],
                    'final_correct': final[q] == labels[q], 'selector_error': bool(records[q].get('selector_error')),
                    'fallback': records[q].get('fallback')})
        # Representative outcomes are selected only for reporting, after all generation.
        better = [x for x in data['case_changes'] if x['final_correct'] and not x['S0_correct']]
        worse = [x for x in data['case_changes'] if x['S0_correct'] and not x['final_correct']]
        chosen = better[:1] + worse[:1]
        chosen += [x for x in data['case_changes'] if x not in chosen][:3-len(chosen)]
        data['representative_changes'] = chosen
        payload['groups'][g] = data
    payload['limitations'] = [
        'This is a fixed development-set selection experiment, not independent main-table evaluation.',
        'P0 and raw candidates are frozen V10 outputs; no original inference requests are charged again.',
        'P0 failures remain in the full denominator; recovery is separated from correction of a legal wrong answer.',
        'Corrective/harmful candidate opportunities exclude missing P0 or candidate answers.',
        'Successful outcomes produced by technical fallback are not counted as successful adjudication.',
        'Seven official task categories overlap and must not be summed or averaged.',
        'Case examples contain identifiers and answer transitions, not patient text or claimed visual mechanisms.',
        'Reported resource costs are recorded assumed-rate estimates/settlements, not provider invoices.']
    return payload


def _markdown(payload):
    n, stage = payload['planned_n'], payload['stage']
    pct = base._percent
    lines = [f'# V11 {stage} cached-candidate selection results', '',
        f"Status: **completed**. All {n} planned questions remain in the denominator.", '',
        '| Arm | Correct / N | Accuracy | Wrong legal answers corrected | P0 failures recovered | Harms | Net vs P0 |',
        '|---|---:|---:|---:|---:|---:|---:|',
        f"| P0 | {payload['p0']['correct']}/{n} | {pct(payload['p0']['accuracy_over_planned'])} | — | — | — | — |"]
    for g, d in payload['groups'].items():
        arms = [('S0', d['S0'])]
        if 'S1' in d and stage != 'S1': arms.append(('S1', d['S1']))
        arms.append((stage, d))
        for arm, stats in arms:
            f, p = stats['final'], stats['paired']
            lines.append(f"| {g}/{arm} | {f['correct']}/{n} | {pct(f['accuracy_over_planned'])} | {p['corrections_from_wrong_answer']} | {p['recovered_from_p0_failure']} | {p['harms']} | {p['net']:+d} |")
    for g, d in payload['groups'].items():
        o = d['selection_opportunities']
        lines += ['', f'## {g}: frozen candidate opportunities', '',
            f"- Corrective candidates preserved: **{o['corrections_kept_total']}/{o['corrective_candidates']}**; normal selection {o['corrections_kept_by_selection']}, technical fallback {o['corrections_kept_by_fallback']}.",
            f"- Harmful candidates blocked: **{o['harmful_candidates_blocked_total']}/{o['harmful_candidates']}**; normal selection {o['harms_blocked_by_selection']}, technical fallback {o['harms_blocked_by_fallback']}.",
            f"- Technical selector/fallback records: {o['selector_errors']}; needs_followup: {d['needs_followup_n']}.",
            f"- Net vs P0 excluding P0-failure recovery: {d['paired']['net_without_failure_recovery']:+d}.", '',
            '### Seven overlapping categories', '', '| Category | P0 | S0 | '+stage+' |', '|---|---:|---:|---:|']
        for category, stats in d['categories'].items():
            den = stats['p0']['planned_n']
            lines.append(f"| {category} | {stats['p0']['correct']}/{den} | {stats['S0']['correct']}/{den} | {stats['final']['correct']}/{den} |")
        lines += ['', '### Representative answer changes', '',
            'Selected after scoring to illustrate outcome types; no image-based cause is inferred.', '',
            '| Question ID | P0 | Candidate | S0 | '+stage+' | S0 correct | New correct |', '|---|---|---|---|---|---|---|']
        for case in d['representative_changes']:
            cells = [case[k] for k in ('question_id', 'initial', 'candidate', 'S0', stage, 'S0_correct', 'final_correct')]
            lines.append('| '+' | '.join('missing' if x is None else str(x) for x in cells)+' |')
        if not d['representative_changes']: lines.append('| No answer changes | — | — | — | — | — | — |')
    res, wall = payload['new_resources'], payload['wall_time']
    lines += ['', '## Additional resources for this run only', '',
        '| Model calls | Tool attempts | Input tokens | Output tokens | Logical CNY | Summed stage seconds |',
        '|---:|---:|---:|---:|---:|---:|',
        '| '+' | '.join('N/A' if res[k]['sum_observed'] is None else str(res[k]['sum_observed']) for k in
            ('model_calls', 'tool_calls', 'input_tokens', 'output_tokens', 'logical_cost_cny', 'elapsed_s'))+' |', '',
        f"Observed wall time: {wall['elapsed_s']} seconds ({wall['started_utc']} to {wall['ended_utc']}).",
        'Missing usage fields and accounting caveats are retained in the JSON; this is not a provider invoice.', '',
        '## Limits', '']
    lines += ['- '+x for x in payload['limitations']]
    return '\n'.join(lines)+'\n'


def _load_completed(run_dir, planned):
    run_dir = Path(run_dir)
    status_path = run_dir/'status.json'
    status = json.loads(status_path.read_text(encoding='utf-8-sig')) if status_path.exists() else {}
    rows = base.read_jsonl(run_dir/'results.jsonl')
    indexed = _index(rows, planned, grouped=True)
    groups = {g for _, g in indexed}
    if (status.get('status') != 'generation_complete' or status.get('planned_n') != len(planned)
            or not groups or any((q, g) not in indexed for q in planned for g in groups)):
        raise ValueError('Generation is incomplete; isolated labels have not been opened')
    return rows


def generate_report(run_dir, source_run, labels_path, *, previous_run=None):
    run_dir, source_run = Path(run_dir), Path(source_run)
    selection = json.loads((source_run/'selection.json').read_text(encoding='utf-8-sig'))
    planned = [base._qid(row) for row in selection.get('rows', [])]
    if len(planned) != 60 or len(set(planned)) != 60 or selection.get('planned_n') != 60:
        raise ValueError('V11 reporting requires the original fixed sixty; isolated labels have not been opened')
    result_rows = _load_completed(run_dir, planned)
    previous_rows = _load_completed(previous_run, planned) if previous_run else None
    p0_rows = base.read_jsonl(source_run/'p0_results.jsonl')
    source_rows = base.read_jsonl(source_run/'candidate_results.jsonl')
    p0 = _index(p0_rows, planned)
    source = _index(source_rows, planned, grouped=True)
    selected_groups = {r['group'] for r in result_rows}
    if len(p0) != 60 or any((q, g) not in source for q in planned for g in selected_groups):
        raise ValueError('Incomplete fixed V10 source; isolated labels have not been opened')
    payload = score(selection, p0_rows, source_rows, result_rows,
                    base._labels(labels_path, planned), previous_rows=previous_rows)
    base._atomic(run_dir/'paired_metrics.json', json.dumps(payload, ensure_ascii=False, indent=2)+'\n')
    base._atomic(run_dir/'paired_metrics.md', _markdown(payload))
    return payload


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', required=True, type=Path)
    parser.add_argument('--source-run', required=True, type=Path)
    parser.add_argument('--labels', required=True, type=Path)
    parser.add_argument('--previous-run', type=Path)
    args = parser.parse_args(argv)
    payload = generate_report(args.run, args.source_run, args.labels, previous_run=args.previous_run)
    print(json.dumps({'status': payload['run_status'], 'stage': payload['stage'], 'planned_n': payload['planned_n'],
        'p0_correct': payload['p0']['correct'],
        'final_correct': {g: v['final']['correct'] for g, v in payload['groups'].items()}}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
