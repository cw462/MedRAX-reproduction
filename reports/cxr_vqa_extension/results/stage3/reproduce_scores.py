"""Verify strict Q scores without extracting answers from raw replies."""
import json
from pathlib import Path
import sys

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[3] / 'experiments'))
from score_cxr_vqa_extension import bootstrap, cluster_keys, grade, rows

for dataset in ('chexbench', 'slake', 'vqarad'):
    folder = HERE / dataset
    inputs = rows(folder / 'inputs.jsonl')
    refs = {r['question_id']: r['answer'] for r in rows(folder / 'references.jsonl')}
    cohort = json.loads((folder / 'joint_cohort.json').read_text(encoding='utf-8'))['datasets'][dataset]
    ids = {qid for group in cohort['groups'] for qid in group['question_ids']}
    assert ids == {r['question_id'] for r in inputs} == set(refs)
    assert len(ids) == cohort['q_questions']
    summary = json.loads((folder / 'summary.json').read_text(encoding='utf-8'))
    subsets = np.array([r.get('source', {}).get('subset', 'all') for r in inputs])
    clusters = cluster_keys(inputs)
    evaluated = {}
    for arm in ('D-Q', 'M-Q'):
        predictions = {p['question_id']: p for p in rows(folder / f'predictions_{arm}.jsonl')}
        assert set(predictions) == ids
        correct, missing = zip(*(grade(r, predictions[r['question_id']], refs[r['question_id']]) for r in inputs))
        evaluated[arm] = np.array(correct, dtype=int)
        assert sum(correct) == summary['arms'][arm]['correct']
        assert sum(missing) == summary['arms'][arm]['missing']
    delta = evaluated['M-Q'] - evaluated['D-Q']
    expected = summary['comparisons']['M-Q vs D-Q']
    assert int(sum(delta > 0)) == expected['corrections']
    assert int(sum(delta < 0)) == expected['harms']
    actual = bootstrap(delta, clusters, subsets)
    for metric in ('macro_pp', 'micro_pp'):
        assert np.allclose(actual[metric], expected['confidence'][metric], atol=1e-10)
    print(dataset, 'strict Q scores verified; format-confounded difference is not a clinical tool effect')
