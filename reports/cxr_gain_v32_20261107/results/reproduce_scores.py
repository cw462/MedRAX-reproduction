"""Reproduce all published v3.2 full-cohort scores without API calls."""
import json
from pathlib import Path
import sys

import numpy as np

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[2]
sys.path.insert(0,str(REPO/'experiments'))
from analyze_cxr_gain_v32 import historical_fence
from score_cxr_vqa_extension import bootstrap,cluster_keys,grade,rows

for dataset in ['slake','vqarad','chexbench']:
    folder=HERE/dataset
    if not (folder/'summary.json').exists():continue
    inputs=rows(folder/'inputs.jsonl');refs={r['question_id']:r['answer'] for r in rows(folder/'references.jsonl')}
    ids={r['question_id'] for r in inputs};assert set(refs)==ids
    baseline=(REPO/'reports/cxr_vqa_extension/results/chexbench' if dataset=='chexbench' else REPO/'reports/cxr_vqa_toolsets/results'/dataset)
    predictions={'M':{p['question_id']:p for p in rows(baseline/'predictions_M.jsonl')}}
    for arm in ['M-AS','M-A']:predictions[arm]={p['question_id']:p for p in rows(folder/f'predictions_{arm}.jsonl')}
    subsets=np.array([r.get('source',{}).get('subset','all') for r in inputs]);clusters=cluster_keys(inputs)
    for name in ['summary.json','mechanical_sensitivity_summary.json']:
        summary=json.loads((folder/name).read_text(encoding='utf-8'));current=dict(predictions)
        if name.startswith('mechanical'):
            repaired={}
            for qid,pred in current['M'].items():
                callfile=baseline/'calls/M'/(qid+'.json')
                calls=json.loads(callfile.read_text(encoding='utf-8')) if pred['status']!='completed' and callfile.exists() else []
                repaired[qid]=historical_fence(pred,calls)[0]
            current['M']=repaired
        scored={}
        for arm,pred in current.items():
            assert set(pred)==ids
            values=[grade(r,pred[r['question_id']],refs[r['question_id']]) for r in inputs]
            scored[arm]=np.array([v[0] for v in values],dtype=int)
            assert int(scored[arm].sum())==summary['arms'][arm]['correct']
            assert sum(v[1] for v in values)==summary['arms'][arm]['missing']
        for comparison,expected in summary['comparisons'].items():
            arm,control=comparison.split(' vs ');delta=scored[arm]-scored[control]
            assert int(sum(delta>0))==expected['corrections'] and int(sum(delta<0))==expected['harms']
            assert int(delta.sum())==expected['net']
            actual=bootstrap(delta,clusters,subsets)
            for key in ['micro_pp','macro_pp']:assert np.allclose(actual[key],expected['confidence'][key],atol=1e-10)
        print(dataset,name,'complete-denominator scores and paired intervals verified')
