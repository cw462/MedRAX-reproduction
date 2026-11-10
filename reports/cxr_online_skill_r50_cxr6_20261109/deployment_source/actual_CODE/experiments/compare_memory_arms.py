"""Paired comparison of two completed arms on the same frozen questions.

Reads only the private run journals and the label file; prints aggregate numbers
and writes a private JSON. Public reports must be derived from the aggregates, not
from per-question reference answers.

Usage:
  python experiments/compare_memory_arms.py --baseline runs/val40_r0_v1 \
      --compare runs/val40_r1_v1 --labels data/prepared_v2/validation.labels.jsonl \
      --report runs/val40_comparison.json
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path


def read_jsonl(path):
    return [json.loads(line) for line in Path(path).read_text(encoding='utf-8-sig').splitlines() if line.strip()]


def outcomes(run, labels, key):
    rows = {}
    for row in read_jsonl(Path(run) / 'results.jsonl'):
        if row.get('record_type') != 'terminal':
            continue
        label = labels.get(row['question_id'])
        letter = row.get(key)
        status = row.get('status')
        if label is None:
            outcome = 'unknown'
        elif status == 'completed' and letter:
            outcome = 'correct' if letter == label else 'incorrect'
        elif status in ('completed', 'invalid_answer'):
            outcome = 'invalid'
        else:
            outcome = 'error'
        rows[row['question_id']] = {'outcome': outcome, 'status': status, 'letter': letter,
                                    'model_calls': row.get('actual_model_calls'),
                                    'tool_calls': row.get('actual_tool_attempts'),
                                    'tools': row.get('selected_tool_names'),
                                    'seconds': row.get('elapsed_seconds'),
                                    'charged_cny': sum(float(s.get('charged_cny', 0))
                                                       for s in (row.get('ledger_settlements') or [])
                                                       if isinstance(s, dict))}
    return rows


def summaries(rows):
    total = len(rows)
    graded = sum(1 for r in rows.values() if r['outcome'] in ('correct', 'incorrect'))
    correct = sum(1 for r in rows.values() if r['outcome'] == 'correct')
    invalid = sum(1 for r in rows.values() if r['outcome'] == 'invalid')
    errors = sum(1 for r in rows.values() if r['outcome'] == 'error')
    calls = [r['model_calls'] for r in rows.values() if r['model_calls'] is not None]
    tools = [r['tool_calls'] for r in rows.values() if r['tool_calls'] is not None]
    seconds = [r['seconds'] for r in rows.values() if r['seconds'] is not None]
    cost = sum(r['charged_cny'] for r in rows.values())
    return {
        'questions': total, 'graded': graded, 'correct': correct, 'invalid': invalid, 'error': errors,
        'accuracy_graded': round(correct / graded, 4) if graded else None,
        'accuracy_all': round(correct / total, 4) if total else None,
        'mean_model_calls': round(sum(calls) / len(calls), 2) if calls else None,
        'mean_tool_calls': round(sum(tools) / len(tools), 2) if tools else None,
        'mean_seconds': round(sum(seconds) / len(seconds), 1) if seconds else None,
        'accounted_cny': round(cost, 5),
    }


def mcnemar_exact(b, c):
    n = b + c
    if n == 0:
        return 1.0
    tail = sum(math.comb(n, k) for k in range(0, min(b, c) + 1)) / (2 ** n)
    return min(1.0, 2 * tail)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', type=Path, required=True)
    parser.add_argument('--compare', type=Path, required=True)
    parser.add_argument('--labels', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--answer-key', default='answer_letter_relaxed')
    args = parser.parse_args(argv)

    labels = {row['question_id']: str(row['answer']).strip().upper() for row in read_jsonl(args.labels)}
    base = outcomes(args.baseline, labels, args.answer_key)
    comp = outcomes(args.compare, labels, args.answer_key)
    shared = sorted(set(base) & set(comp))
    if not shared:
        raise SystemExit('No shared questions between the two runs')

    transitions = {'both_correct': 0, 'both_wrong': 0, 'base_only': 0, 'memory_only': 0,
                   'other': 0}
    detail = []
    for qid in shared:
        b = base[qid]['outcome'] == 'correct'
        c = comp[qid]['outcome'] == 'correct'
        if b and c:
            transitions['both_correct'] += 1
        elif not b and not c:
            transitions['both_wrong'] += 1
        elif b and not c:
            transitions['base_only'] += 1
        else:
            transitions['memory_only'] += 1
        detail.append({'question_id': qid, 'baseline': base[qid]['outcome'],
                       'compare': comp[qid]['outcome'],
                       'baseline_status': base[qid]['status'], 'compare_status': comp[qid]['status']})

    retrieval = []
    path = args.compare / 'retrieval.jsonl'
    if path.exists():
        retrieval = read_jsonl(path)
    hit_rate = (sum(1 for r in retrieval if r.get('rendered', r.get('returned', 0)) > 0) / len(retrieval)
                if retrieval else None)

    report = {
        'baseline': str(args.baseline), 'compare': str(args.compare),
        'shared_questions': len(shared),
        'baseline_summary': summaries({q: base[q] for q in shared}),
        'compare_summary': summaries({q: comp[q] for q in shared}),
        'transitions': transitions,
        'mcnemar_exact_p': round(mcnemar_exact(transitions['base_only'], transitions['memory_only']), 4),
        'memory_injection': {
            'questions_queried': len(retrieval),
            'questions_with_hits': sum(1 for r in retrieval if r.get('rendered', r.get('returned', 0)) > 0),
            'hit_rate': round(hit_rate, 4) if hit_rate is not None else None,
            'mean_rendered': round(sum(r.get('rendered', 0) for r in retrieval) / len(retrieval), 2) if retrieval else None,
            'mean_chars': round(sum(r.get('injected_chars', 0) for r in retrieval) / len(retrieval), 1) if retrieval else None,
        },
        'detail': detail,
        'statistics_note': 'Exact McNemar on discordant pairs; not adjusted for case clustering.',
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    print(json.dumps({k: report[k] for k in ('shared_questions', 'baseline_summary', 'compare_summary',
                                             'transitions', 'mcnemar_exact_p', 'memory_injection')},
                     ensure_ascii=False, indent=1))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
