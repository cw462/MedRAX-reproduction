"""Reproduce frozen R43 project-contract scores; no model calls or record edits."""
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'experiments'))
from score_cxr_vqa_extension import bootstrap, cluster_keys, grade, rows


def reproduce(dataset):
    folder = ROOT / 'reports/cxr_task_completion_r43_20261108/results' / dataset
    inputs = rows(folder / 'inputs.jsonl')
    refs = {x['question_id']: x['answer'] for x in rows(folder / 'references.jsonl')}
    saved = json.loads((folder / 'summary.json').read_text(encoding='utf-8'))
    details = {(x['arm'], x['question_id']): x for x in rows(folder / 'per_question.jsonl')}
    selection = json.loads((folder / 'selection.json').read_text(encoding='utf-8'))
    n = {'chexbench':618, 'slake':114}[dataset]
    assert len(inputs) == len(refs) == n
    scores, predictions = {}, {}
    for arm in ['B','M43']:
        values = rows(folder / ('predictions_' + arm + '.jsonl'))
        pred = {x['question_id']:x for x in values}
        assert len(values) == len(pred) == n and set(pred) == set(refs)
        predictions[arm] = pred
        graded = [grade(row, pred[row['question_id']], refs[row['question_id']]) for row in inputs]
        scores[arm] = np.array([v[0] for v in graded], dtype=int)
        assert int(scores[arm].sum()) == saved['arms'][arm]['correct']
        assert sum(v[1] for v in graded) == saved['arms'][arm]['missing']
        for row, outcome in zip(inputs, graded):
            detail = details[arm,row['question_id']]
            assert outcome == (detail['correct'],detail['missing'])
    selected = set(selection['selected'])
    for qid in set(refs) - selected:
        assert all(predictions['B'][qid].get(k) == predictions['M43'][qid].get(k)
                   for k in ['answer','reason','status'])
    delta = scores['M43'] - scores['B']
    pair = saved['comparisons']['M43 vs B']
    assert (int(sum(delta>0)),int(sum(delta<0)),int(delta.sum())) == (pair['corrections'],pair['harms'],pair['net'])
    ci = bootstrap(delta, cluster_keys(inputs), np.array([x.get('source',{}).get('subset','all') for x in inputs]))
    for key in ['micro_pp','macro_pp']:
        assert np.allclose(ci[key],pair['confidence'][key],rtol=0,atol=1e-9)
    return {'dataset':dataset,'questions':n,'baseline_correct':int(scores['B'].sum()),
            'M43_correct':int(scores['M43'].sum()),'exact_reuse':n-len(selected),
            'net':pair['net'],'public_score_reproduction':'passed'}


if __name__ == '__main__':
    for dataset in ['chexbench','slake']:
        print(json.dumps(reproduce(dataset)))
