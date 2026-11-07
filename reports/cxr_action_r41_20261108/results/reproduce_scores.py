"""Reproduce completed public R4.1 scores without inference or credentials."""
import argparse
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'experiments'))
from score_cxr_vqa_extension import bootstrap, cluster_keys, grade, rows


def check(dataset):
    folder = Path(__file__).resolve().parent / dataset
    inputs = rows(folder / 'inputs.jsonl')
    refs = {r['question_id']: r['answer'] for r in rows(folder / 'references.jsonl')}
    saved = json.loads((folder / 'summary.json').read_text(encoding='utf-8'))
    details = {(v['arm'], v['question_id']): v for v in rows(folder / 'per_question.jsonl')}
    ids = {r['question_id'] for r in inputs}
    assert set(refs) == ids and len(ids) == len(inputs)
    subsets = np.array([r.get('source', {}).get('subset', 'all') for r in inputs])
    correct = {}
    for arm in ('M', 'M-S41', 'M-C41'):
        values = rows(folder / ('predictions_' + arm + '.jsonl'))
        predictions = {v['question_id']: v for v in values}
        assert len(values) == len(inputs) and set(predictions) == ids
        graded = [grade(r, predictions[r['question_id']], refs[r['question_id']]) for r in inputs]
        correct[arm] = np.array([v[0] for v in graded], dtype=int)
        missing = sum(v[1] for v in graded)
        assert int(correct[arm].sum()) == saved['arms'][arm]['correct']
        assert missing == saved['arms'][arm]['missing']
        for row, (c, m) in zip(inputs, graded):
            detail = details[arm, row['question_id']]
            assert bool(c) == detail['correct'] and bool(m) == detail['missing']
        macro = np.mean([correct[arm][subsets == s].mean() * 100 for s in set(subsets)])
        assert abs(macro - saved['arms'][arm]['macro_pct']) < 1e-9
        assert abs(correct[arm].mean() * 100 - saved['arms'][arm]['micro_pct']) < 1e-9
    delta = correct['M-S41'] - correct['M-C41']
    pair = saved['comparisons']['M-S41 vs M-C41']
    assert (int(sum(delta > 0)), int(sum(delta < 0)), int(delta.sum())) == (pair['corrections'], pair['harms'], pair['net'])
    ci = bootstrap(delta, cluster_keys(inputs), subsets)
    for k in ('micro_pp', 'macro_pp'):
        assert np.allclose(ci[k], pair['confidence'][k], rtol=0, atol=1e-9)
    print(json.dumps({'dataset': dataset, 'questions': len(inputs), 'correct': {a: int(v.sum()) for a, v in correct.items()}, 'primary_net': pair['net'], 'public_score_reproduction': 'passed'}))


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--dataset', choices=['chexbench', 'slake', 'vqarad'])
    a = p.parse_args()
    datasets = [a.dataset] if a.dataset else [v.name for v in Path(__file__).resolve().parent.iterdir() if (v / 'r41_target_export_complete.json').is_file()]
    for dataset in datasets:
        check(dataset)
