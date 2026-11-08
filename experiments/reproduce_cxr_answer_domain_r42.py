"""Reproduce public M42 full-denominator scores, without API or inference."""
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'experiments'))
from score_cxr_vqa_extension import bootstrap, cluster_keys, grade, rows


def main():
    folder = ROOT / 'reports/cxr_answer_domain_r42_20261108/results/vqarad'
    inputs = rows(folder / 'inputs.jsonl')
    refs = {x['question_id']: x['answer'] for x in rows(folder / 'references.jsonl')}
    saved = json.loads((folder / 'summary.json').read_text(encoding='utf-8'))
    details = {(x['arm'], x['question_id']): x for x in rows(folder / 'per_question.jsonl')}
    assert len(inputs) == len(refs) == 116
    scores = {}
    for arm in ['M', 'M42']:
        values = rows(folder / ('predictions_' + arm + '.jsonl'))
        pred = {x['question_id']: x for x in values}
        assert len(values) == len(pred) == 116 and set(pred) == set(refs)
        graded = [grade(row, pred[row['question_id']], refs[row['question_id']]) for row in inputs]
        scores[arm] = np.array([x[0] for x in graded], dtype=int)
        assert int(scores[arm].sum()) == saved['arms'][arm]['correct']
        assert sum(x[1] for x in graded) == saved['arms'][arm]['missing']
        for row, outcome in zip(inputs, graded):
            detail = details[arm, row['question_id']]
            assert outcome == (detail['correct'], detail['missing'])
    delta = scores['M42'] - scores['M']
    pair = saved['comparisons']['M42 vs M']
    assert (int(sum(delta > 0)), int(sum(delta < 0)), int(delta.sum())) == (pair['corrections'], pair['harms'], pair['net'])
    ci = bootstrap(delta, cluster_keys(inputs), np.array([x.get('source', {}).get('subset', 'all') for x in inputs]))
    for key in ['micro_pp', 'macro_pp']:
        assert np.allclose(ci[key], pair['confidence'][key], rtol=0, atol=1e-9)
    print(json.dumps({'questions': 116, 'M': int(scores['M'].sum()), 'M42': int(scores['M42'].sum()),
                      'net': pair['net'], 'public_score_reproduction': 'passed'}))


if __name__ == '__main__':
    main()
