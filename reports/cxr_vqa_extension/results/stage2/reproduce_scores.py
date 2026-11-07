"""Verify stage-two strict scores and paired intervals using released records only."""
import json
from pathlib import Path
import sys

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / 'experiments'))
from score_cxr_vqa_extension import bootstrap, cluster_keys, grade, rows

for dataset in ('chexbench', 'slake', 'vqarad'):
    folder = HERE / dataset
    inputs = rows(folder / 'inputs.jsonl')
    refs = {r['question_id']: r['answer'] for r in rows(folder / 'references.jsonl')}
    baseline = (HERE.parent / dataset if dataset == 'chexbench' else
                REPO / 'reports/cxr_vqa_toolsets/results' / dataset)
    summary = json.loads((folder / 'summary.json').read_text(encoding='utf-8'))
    subsets = np.array([r.get('source', {}).get('subset', 'all') for r in inputs])
    clusters = cluster_keys(inputs)
    evaluated = {}
    for arm in ('M', 'M-S', 'M-E'):
        source = baseline if arm == 'M' else folder
        predictions = {p['question_id']: p for p in rows(source / f'predictions_{arm}.jsonl')}
        assert set(predictions) == {r['question_id'] for r in inputs}
        values = [grade(r, predictions[r['question_id']], refs[r['question_id']]) for r in inputs]
        correct = np.array([v[0] for v in values], dtype=int)
        assert int(correct.sum()) == summary['arms'][arm]['correct']
        assert sum(v[1] for v in values) == summary['arms'][arm]['missing']
        evaluated[arm] = correct
    for arm in ('M-S', 'M-E'):
        delta = evaluated[arm] - evaluated['M']
        expected = summary['comparisons'][arm + ' vs M']
        assert int(sum(delta > 0)) == expected['corrections']
        assert int(sum(delta < 0)) == expected['harms']
        assert int(delta.sum()) == expected['net']
        actual = bootstrap(delta, clusters, subsets)
        for metric in ('macro_pp', 'micro_pp'):
            assert np.allclose(actual[metric], expected['confidence'][metric], atol=1e-10)
    print(dataset, 'released strict scores and paired intervals verified')
