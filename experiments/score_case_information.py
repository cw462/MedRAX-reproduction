"""Offline E0-E3 scoring. All generation must finish before labels are opened.

Only saved answers are scored. No provider client, ledger, GPU, or generation
module is imported. Batch requests are scored through their immutable child
question projection; usage is counted once from the original request units.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import random

from score_votes import (load_complete_run, read, read_labels, totals, paired,
                         vote, error_overlap, resources, quantile, write)

ARM_IDS = ['E2_Batch', 'E2_Sequential', 'E1_DeepSeek', 'E1_QwenFlash',
           'E3_Classifier', 'E3_Report', 'E3_Evidence', 'E0_Heldout']
TUNE_IDS = ARM_IDS[:-1]


def absolute(root, value):
    p = Path(value)
    return p.resolve() if p.is_absolute() else (root / p).resolve()


def accuracy_interval(predictions, labels, qids, cases, repeats=2000, seed=20261103):
    groups = defaultdict(list)
    for q in qids:
        groups[cases[q]].append(int(predictions[q] == labels[q]))
    clusters = [(sum(v), len(v)) for _, v in sorted(groups.items())]
    rng = random.Random(seed)
    values = []
    for _ in range(repeats):
        sample = [clusters[rng.randrange(len(clusters))] for _ in clusters]
        values.append(sum(x for x, _ in sample) / sum(n for _, n in sample))
    return {'method': 'case_cluster_percentile_question_weighted',
            'case_n': len(clusters), 'repeats': repeats, 'seed': seed,
            'accuracy_ci95': [quantile(values, .025), quantile(values, .975)]}


def compare_views(views, labels, rows, repeats=2000):
    qids = [str(r['question_id']) for r in rows]
    cases = {str(r['question_id']): str(r['case_id']) for r in rows}
    comparisons = {name: paired(views['D'], values, labels, qids, cases,
                                repeats, 20261103)
                   for name, values in views.items() if name != 'D'}
    for value in comparisons.values():
        value['passes_exploratory_retention_rule'] = value['bootstrap']['delta_ci95'][0] > 0
    wrong = [q for q in qids if views['D'][q] != labels[q]]
    covered = [q for q in wrong if any(views[name][q] == labels[q]
                                     for name in ('E1_DeepSeek', 'E1_QwenFlash'))]
    return {'totals': {name: totals(values, labels, qids) for name, values in views.items()},
            'comparisons_to_D': comparisons,
            'complementarity': {'D_wrong_n': len(wrong),
                'D_errors_correct_in_at_least_one_new_model': len(covered),
                'covered_question_ids': covered,
                'oracle_is_not_achieved_ensemble_accuracy': True,
                'about_15_errors_heuristic_is_diagnostic_only': True,
                'pairwise': {name: error_overlap(views['D'], views[name], labels, qids)
                            for name in ('E1_DeepSeek', 'E1_QwenFlash')}}}


def score(manifest_path, tune_labels, test_labels, out):
    manifest = read(manifest_path)
    root = Path(manifest['root']).resolve()
    out = Path(out).resolve()
    if out.exists() and any(out.iterdir()):
        raise ValueError('refusing_to_overwrite_existing_scored_report')
    specs = manifest['arms']
    if [a['id'] for a in specs] != ARM_IDS:
        raise ValueError('exact_frozen_six_arm_order_required')
    paths = {a['id']: absolute(root, a['out']) for a in specs}
    baseline_path = absolute(root, manifest['baseline_run'])
    for p in [*paths.values(), baseline_path]:
        if out == p or out.is_relative_to(p):
            raise ValueError('report_must_not_modify_generation_or_old_baseline')
    # No label file is opened until every raw arm AND child view is complete.
    raw = {name: load_complete_run(p) for name, p in paths.items()}
    runs = dict(raw)
    runs['E2_Batch'] = load_complete_run(paths['E2_Batch'] / 'question_view')
    runs['D'] = load_complete_run(baseline_path)
    rows = runs['D']['rows']
    if len(rows) != 402 or len({str(r['case_id']) for r in rows}) != 99:
        raise ValueError('fixed_D_402_questions_99_cases_required')
    for name in TUNE_IDS:
        if runs[name]['samples'] != 1 or runs[name]['rows'] != rows:
            raise ValueError('every_tune_arm_requires_identical_blind_inputs:' + name)
    test = runs['E0_Heldout']
    if len(test['qids']) != 1002 or len({str(r['case_id']) for r in test['rows']}) != 241:
        raise ValueError('fixed_heldout_1002_questions_241_cases_required')
    tune_cases = {str(r['case_id']) for r in rows}
    if tune_cases & {str(r['case_id']) for r in test['rows']}:
        raise ValueError('tune_heldout_cases_overlap')
    qids = runs['D']['qids']
    labels = read_labels(tune_labels, qids)
    held_labels = read_labels(test_labels, test['qids'])
    views = {name: {q: runs[name]['answers'][q, 1] for q in qids}
             for name in ['D', *TUNE_IDS]}
    views['E1_Ensemble'] = {q: vote([views[name][q] for name in
                         ('D', 'E1_DeepSeek', 'E1_QwenFlash')],
                         tie_answer=views['D'][q], weights=[1, 1, 1]) for q in qids}
    result = compare_views(views, labels, rows)
    held = {q: test['answers'][q, 1] for q in test['qids']}
    held_cases = {str(r['question_id']): str(r['case_id']) for r in test['rows']}
    result.update(status='completed', experiment_id=manifest['experiment_id'], plan_version=manifest['plan_version'],
        inference_performed_by_scorer=False,
        selection_rule='Exploratory: paired case-bootstrap lower CI endpoint > 0; no fixed 2.5pp count gate',
        multiple_comparisons='Six exploratory tuning views; no independent method validation',
        E0_Heldout={**totals(held, held_labels, test['qids']),
                    **accuracy_interval(held, held_labels, test['qids'], held_cases),
                    'interpretation': 'Fixed D baseline only; not validation of an E1-E3 method'},
        usage={name: resources(run['records']) for name, run in raw.items()},
        reused_D_new_requests=0, actual_token_plan_credits=None)
    result['usage']['scope_note'] = 'Original request units only; no duplicate batch costs from child-question projections.'
    write(out / 'metrics.json', result)
    write(out / 'per_question.json', {'records': [
        {'question_id': q, 'case_id': str(row['case_id']), 'reference': labels[q],
         'predictions': {name: pred[q] for name, pred in views.items()},
         'correct': {name: pred[q] == labels[q] for name, pred in views.items()}}
        for row, q in zip(rows, qids)]})
    write(out / 'heldout_per_question.json', {'records': [
        {'question_id': q, 'case_id': held_cases[q], 'reference': held_labels[q],
         'answer': held[q], 'correct': held[q] == held_labels[q]} for q in test['qids']]})
    report = '# Case information experiments: completed offline scoring\n\n'
    report += '|Arm|Correct / planned|Accuracy|Missing|\n|---|---:|---:|---:|\n'
    for name, t in result['totals'].items():
        report += f"|{name}|{t['correct']}/{t['planned_n']}|{t['accuracy']:.2%}|{t['missing']}|\n"
    report += '\n|Versus D|Corrections|Harms|Net|Case-bootstrap 95% CI (pp)|\n|---|---:|---:|---:|---|\n'
    for name, p in result['comparisons_to_D'].items():
        lo, hi = p['bootstrap']['delta_ci95_pp']
        report += f"|{name}|{p['legal_wrong_to_correct'] + p['missing_to_correct']}|{p['correct_to_legal_wrong'] + p['correct_to_missing']}|{p['net']}|{lo:.2f} to {hi:.2f}|\n"
    h = result['E0_Heldout']
    report += f"\nE0 fixed D: {h['correct']}/{h['planned_n']} ({h['accuracy']:.2%}).\n\n"
    report += ('[Full metrics, corrections/harms/missing and exact McNemar](metrics.json) · '
               '[402-question results](per_question.json) · [1,002-question E0](heldout_per_question.json).\n\n'
               'All E1-E3 comparisons are exploratory on the same tuning cases. E0 evaluates only the fixed direct '
               'baseline. Tool evidence and technical recovery are separate from model/method improvement. '
               'CNY accounting proxies are not Token Plan invoices or a Credits conversion; actual Credits are unknown.\n')
    (out / 'README.md').write_text(report, encoding='utf-8')
    write(out / 'scoring_complete.json', {'status': 'complete', 'experiment_id': manifest['experiment_id'],
                                        'all_generation_complete_before_labels': True})
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manifest', required=True, type=Path)
    p.add_argument('--tune-labels', required=True, type=Path)
    p.add_argument('--test-labels', required=True, type=Path)
    p.add_argument('--out', required=True, type=Path)
    a = p.parse_args()
    score(a.manifest, a.tune_labels, a.test_labels, a.out)
    print(json.dumps({'status': 'scoring_complete', 'new_model_requests': 0}))


if __name__ == '__main__':
    main()
