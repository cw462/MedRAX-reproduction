"""Offline full-denominator scoring for a complete extension phase."""

import argparse
from collections import defaultdict
import json
from pathlib import Path

import numpy as np

from score_cxr_vqa_toolsets import normalize


def rows(path):
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line]


def grade(row, prediction, reference):
    answer = prediction.get('answer')
    if prediction['status'] != 'completed' or not isinstance(answer, str):
        return False, True
    answer = normalize(answer)
    options = row.get('options')
    if not options:
        return answer is not None and answer == normalize(reference), answer is None
    if answer and answer.upper() in options:
        return answer.upper() == reference, False
    matching = [letter for letter, text in options.items() if answer == normalize(text)]
    return len(matching) == 1 and matching[0] == reference, len(matching) != 1


def bootstrap(delta, clusters, subsets):
    unique_clusters, ci = np.unique(clusters, return_inverse=True)
    subset_names, si = np.unique(subsets, return_inverse=True)
    shape = (len(unique_clusters), len(subset_names))
    sums, sizes = np.zeros(shape), np.zeros(shape)
    np.add.at(sums, (ci, si), delta)
    np.add.at(sizes, (ci, si), 1)
    rng = np.random.default_rng(20261105)
    weights = rng.multinomial(len(unique_clusters), np.full(len(unique_clusters), 1/len(unique_clusters)), size=10000)
    numerator, denominator = weights @ sums, weights @ sizes
    valid = np.all(denominator > 0, axis=1)
    by_subset = numerator[valid] / denominator[valid]
    micro = numerator.sum(axis=1) / denominator.sum(axis=1)
    interval = lambda x: (100*np.quantile(x, [.025, .975])).tolist()
    return {'micro_pp': interval(micro), 'macro_pp': interval(by_subset.mean(axis=1)),
            'subset_pp': {name: interval(by_subset[:,i]) for i,name in enumerate(subset_names)},
            'macro_resamples': int(sum(valid))}


def cluster_keys(inputs):
    parents = {}

    def root(key):
        while key in parents:
            key = parents[key]
        return key

    first = []
    for row in inputs:
        source = row.get('source', {})
        keys = ['image:'+x for x in source.get('image_pixel_ids', [row['image_id']])]
        for field in ('official_patient_id', 'official_study_id'):
            if source.get(field) is not None:
                keys.append(field+':'+str(source[field]))
        for key in keys[1:]:
            a, b = root(keys[0]), root(key)
            if a != b:
                parents[b] = a
        first.append(keys[0])
    return [root(key) for key in first]


def resources(run, arm, predictions):
    calls = [json.loads(p.read_text()) for p in (run/'calls'/arm).glob('*/*/result.json')]
    selections = [json.loads(p.read_text()) for p in (run/'tool_selections'/arm).glob('*/*.json')]
    input_tokens = sum((c.get('usage') or {}).get('prompt_tokens', 0) or 0 for c in calls)
    output_tokens = sum((c.get('usage') or {}).get('completion_tokens', 0) or 0 for c in calls)
    return dict(main_sends=len(list((run/'calls'/arm).glob('*/*/started.json'))),
                model_ids=sorted({c['model_returned'] for c in calls if c.get('model_returned')}),
                graph_steps=sum(p.get('graph_steps', 0) for p in predictions),
                selected=sum(p.get('tool_calls', 0) for p in predictions),
                backend_records=len(selections), cache_hits=sum(s.get('cache_hit', False) for s in selections),
                fresh_backend_attempts=sum(not s.get('cache_hit') and s.get('status') != 'started_unknown' for s in selections),
                backend_failures=sum(s.get('status') == 'failed' for s in selections),
                completed_model_events=sum(e['status']=='completed' for s in selections if not s.get('cache_hit')
                                           for e in s.get('actual_model_events', [])),
                backend_compute_seconds=sum(s.get('backend_compute_seconds', 0) or 0 for s in selections if not s.get('cache_hit')),
                episode_seconds=sum(p.get('elapsed_s', 0) for p in predictions),
                input_tokens=input_tokens, output_tokens=output_tokens,
                proxy_cny=(input_tokens*4+output_tokens*12)/1e6)


def score(data, run, reused, dest, arms, comparisons):
    inputs = rows(data/'inputs.jsonl')
    if not inputs:
        raise ValueError('Empty frozen evaluation')
    ids = [row['question_id'] for row in inputs]
    predictions, costs = {}, {}
    for arm in arms:
        if reused and arm in 'DMCX':
            if not (reused/f'complete_{arm}.json').is_file():
                raise ValueError('Missing original completion receipt: '+arm)
            values = rows(reused/f'predictions_{arm}.jsonl')
            original = json.loads((reused/'summary.json').read_text())
            costs[arm] = dict(original['arms'][arm]['resources'], reused=True)
        else:
            if not (run/f'complete_{arm}.json').is_file():
                raise ValueError('Phase generation incomplete: '+arm)
            values = [json.loads((run/'predictions'/arm/(qid+'.json')).read_text()) for qid in ids]
            costs[arm] = resources(run, arm, values)
        predictions[arm] = {p['question_id']: p for p in values}
        if len(values) != len(ids) or set(predictions[arm]) != set(ids):
            raise ValueError('Prediction cohort mismatch: '+arm)

    refs = {r['question_id']: r['answer'] for r in rows(data/'references.jsonl')}
    if set(refs) != set(ids) or len(set(ids)) != len(ids):
        raise ValueError('Reference cohort mismatch')
    subsets = np.array([row.get('source', {}).get('subset', 'all') for row in inputs])
    clusters = cluster_keys(inputs)
    results = dict(questions=len(inputs), clusters=len(set(clusters)), arms={}, comparisons={})
    scored = {}
    detail = []
    for arm in arms:
        evaluated = [grade(r, predictions[arm][r['question_id']], refs[r['question_id']]) for r in inputs]
        correct, missing = (np.array(v, dtype=int) for v in zip(*evaluated))
        scored[arm] = correct
        groups = {}
        for subset in sorted(set(subsets)):
            mask = subsets == subset
            groups[subset] = dict(correct=int(correct[mask].sum()), n=int(mask.sum()),
                                  accuracy_pct=float(100*correct[mask].mean()), missing=int(missing[mask].sum()))
        results['arms'][arm] = dict(correct=int(correct.sum()), missing=int(missing.sum()), subsets=groups,
                                    micro_pct=float(100*correct.mean()),
                                    macro_pct=float(np.mean([g['accuracy_pct'] for g in groups.values()])), resources=costs[arm])
        for idx,qid in enumerate(ids):
            detail.append(dict(arm=arm, question_id=qid, answer=predictions[arm][qid].get('answer'),
                               correct=bool(correct[idx]), missing=bool(missing[idx]), reference=refs[qid]))
    for arm, baseline in comparisons:
        delta = scored[arm] - scored[baseline]
        results['comparisons'][arm+' vs '+baseline] = dict(
            corrections=int(sum(delta>0)), harms=int(sum(delta<0)), net=int(delta.sum()),
            micro_delta_pp=float(delta.mean()*100), macro_delta_pp=float(np.mean([delta[subsets==s].mean() for s in set(subsets)])*100),
            confidence=bootstrap(delta, clusters, subsets),
            changes=[dict(question_id=qid, delta=int(v)) for qid,v in zip(ids,delta) if v])
    dest.mkdir(parents=True, exist_ok=True)
    with (dest/'summary.json').open('x', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    with (dest/'per_question.jsonl').open('x', encoding='utf-8') as f:
        for row in detail:
            f.write(json.dumps(row, ensure_ascii=False)+'\n')
    return results


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    for arg in ('data', 'run', 'dest'):
        parser.add_argument('--'+arg, type=Path, required=True)
    parser.add_argument('--reuse-published', type=Path)
    parser.add_argument('--arms', nargs='+', default=['D','M','C','X','O','M-R'])
    parser.add_argument('--compare', action='append', nargs=2)
    args = parser.parse_args()
    score(args.data, args.run, args.reuse_published, args.dest, args.arms,
          args.compare or [('M','D'),('M','O'),('M','M-R'),('C','D'),('X','D')])
