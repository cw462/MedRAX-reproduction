"""Offline complete-denominator scoring; guarded until all four arms finish."""
import argparse
import json
from pathlib import Path
import unicodedata
import numpy as np


def normalize(value):
    if not isinstance(value, str): return None
    value = unicodedata.normalize('NFKC', value).lower()
    value = ''.join(' ' if unicodedata.category(c).startswith('P') else c for c in value)
    value = ' '.join(value.split())
    return {'true': 'yes', 'false': 'no'}.get(value, value) or None


def paired_ci(values, clusters):
    groups = sorted(set(clusters)); rng = np.random.default_rng(20261105)
    sums = np.array([sum(v for v, c in zip(values, clusters) if c == g) for g in groups])
    counts = np.array([clusters.count(g) for g in groups])
    sampled = rng.integers(0, len(groups), size=(10000, len(groups)))
    estimates = sums[sampled].sum(axis=1) / counts[sampled].sum(axis=1) * 100
    return np.quantile(estimates, [.025, .975]).tolist()


def score(data, out, dest):
    inputs = [json.loads(x) for x in (data / 'inputs.jsonl').read_text(encoding='utf-8').splitlines() if x]
    refs = {x['question_id']: x for x in [json.loads(s) for s in (data / 'references.jsonl').read_text(encoding='utf-8').splitlines() if s]}
    predictions = {}; accuracy = {}; changes = []; clusters = [r['image_id'] for r in inputs]
    for arm in 'DMCX':
        if not (out / ('complete_' + arm + '.json')).exists(): raise ValueError('generation_not_complete:' + arm)
        predictions[arm] = [json.loads((out / 'predictions' / arm / (r['question_id'] + '.json')).read_text(encoding='utf-8')) for r in inputs]
        accuracy[arm] = [int(p['status'] == 'completed' and normalize(p.get('answer')) == normalize(refs[r['question_id']]['answer'])) for p, r in zip(predictions[arm], inputs)]
    summary = {'questions': len(inputs), 'clusters': len(set(clusters)), 'cluster_unit': 'image', 'arms': {}, 'bootstrap': {'n':10000,'seed':20261105,'paired':True},
               'interpretation': 'Adapted whole workflows. Small sample; image-level intervals cannot establish patient-independent generalization.'}
    for arm in 'DMCX':
        y = accuracy[arm]; delta = [a-d for a,d in zip(y, accuracy['D'])]
        counts = {'correct': sum(y), 'total': len(y), 'accuracy_pct': sum(y)/len(y)*100,
                  'missing': sum(p['status'] != 'completed' for p in predictions[arm]), 'accuracy_cluster_ci_pct': paired_ci(y,clusters),
                  'corrections_vs_D': sum(a==1 and d==0 for a,d in zip(y,accuracy['D'])),
                  'harms_vs_D': sum(a==0 and d==1 for a,d in zip(y,accuracy['D'])),
                  'net_vs_D': sum(delta), 'delta_pp': sum(delta)/len(y)*100, 'delta_cluster_ci_pp': paired_ci(delta,clusters)}
        calls = [json.loads(p.read_text(encoding='utf-8')) for p in (out/'calls'/arm).glob('*/*/result.json')]
        selections = [json.loads(p.read_text(encoding='utf-8')) for p in (out/'tool_selections'/arm).glob('*/*.json')]
        counts['resources'] = {'main_calls': len(list((out/'calls'/arm).glob('*/*/started.json'))),
            'input_tokens': sum((c.get('usage') or {}).get('prompt_tokens',0) for c in calls),
            'output_tokens': sum((c.get('usage') or {}).get('completion_tokens',0) for c in calls),
            'logical_tool_selections': len([s for p in (out/'tool_selections'/arm).glob('*/*.json') if not p.stem.startswith('auto_') for s in [p]]),
            'automatic_backend_selections': len(list((out/'tool_selections'/arm).glob('*/auto_*.json'))),
            'cache_hits': sum(s.get('cache_hit',False) for s in selections),
            'fresh_backend_attempts': sum(not s.get('cache_hit',False) and s.get('status')!='started_unknown' for s in selections),
            'episode_elapsed_seconds': sum(p.get('elapsed_s',0) for p in predictions[arm]),
            'proxy_cny_from_usage': (sum((c.get('usage') or {}).get('prompt_tokens',0) for c in calls)*4 + sum((c.get('usage') or {}).get('completion_tokens',0) for c in calls)*12)/1e6,
            'cost_note': 'Token-based 4/12 CNY proxy, not actual Credits or provider invoice. Shared cache ownership follows first execution.'}
        summary['arms'][arm] = counts
        for i, row in enumerate(inputs):
            changes.append({'question_id':row['question_id'],'image_id':row['image_id'],'arm':arm,'reference':refs[row['question_id']]['answer'],
                'answer':predictions[arm][i].get('answer'),'correct':bool(y[i]),'D_correct':bool(accuracy['D'][i]),
                'change':'correction' if delta[i]>0 else 'harm' if delta[i]<0 else 'unchanged','status':predictions[arm][i]['status']})
    dest.mkdir(parents=True,exist_ok=True)
    (dest/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (dest/'changes.jsonl').write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in changes),encoding='utf-8')
    return summary


if __name__ == '__main__':
    p=argparse.ArgumentParser();p.add_argument('--data',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--dest',type=Path,required=True)
    a=p.parse_args();print(json.dumps(score(a.data,a.out,a.dest),ensure_ascii=False))
