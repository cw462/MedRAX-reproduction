"""Completion-gated strict full-denominator comparison to fixed best arms."""
from copy import deepcopy
import json
from pathlib import Path

from export_vote_phase import read
from run_cxr_vqa_toolsets import save
from score_cxr_vqa_extension import rows, score


def finalize(root, data, historical, dataset):
    run = root / dataset
    expected = {'chexbench': 618, 'slake': 114}[dataset]
    assert (root / 'jobs/wave.exitcode').read_text().strip() == '0'
    assert (root / 'jobs' / (dataset + '.exitcode')).read_text().strip() == '0'
    pid = (root / 'jobs' / (dataset + '.pid')).read_text().strip()
    assert not Path('/proc', pid).exists()
    inputs = rows(data / 'inputs.jsonl')
    ids = {x['question_id'] for x in inputs}
    assert len(ids) == len(inputs) == expected
    receipt = read(run / 'complete_M43.json')
    assert receipt['questions'] == expected
    predictions = {p.stem: read(p) for p in (run / 'predictions/M43').glob('*.json')}
    best = {x['question_id']: x for x in rows(historical / 'predictions.jsonl')}
    assert set(predictions) == set(best) == ids
    selection = read(run / 'selection.json')
    selected = set(selection['selected'])
    assert len(selected) == {'chexbench': 10, 'slake': 1}[dataset]
    for qid, value in predictions.items():
        if qid not in selected:
            assert all(value.get(k) == best[qid].get(k) for k in ['answer', 'reason', 'status'])
            assert value['main_calls'] == value['new_main_calls'] == 0
        else:
            assert value['main_calls'] == value['new_main_calls'] == 1
            assert value['total_edited_main_calls'] == value['prefix_actual_main_calls'] + 1 <= 4
            assert value['total_edited_tool_calls'] == value['prefix_actual_tool_calls'] <= 2
        assert value['tool_calls'] == value['new_tool_calls'] == 0
    starts = list((run / 'calls/M43').glob('*/*/started.json'))
    assert len(starts) == len(selected) and all((p.parent / 'response.json').exists() for p in starts)
    # B is the entire fixed published best arm, never a per-question oracle.
    for qid, old in best.items():
        dest = run / 'predictions/B' / (qid + '.json')
        if not dest.exists():
            value = deepcopy(old)
            observations = value.pop('observations', [])
            value.update(arm='B', source_best_arm=selection['baseline_arm'], main_calls=0,
                         tool_calls=0, observations=[], inherited_observations=observations,
                         elapsed_s=0, new_main_calls=0, new_tool_calls=0)
            save(dest, value)
    if not (run / 'complete_B.json').exists():
        save(run / 'complete_B.json', {'status': 'fixed_published_baseline_reused', 'questions': expected,
                                      'source_arm': selection['baseline_arm'], 'new_requests': 0,
                                      'original_receipt': read(historical / 'complete.json')})
    audit = {'questions': expected, 'baseline': selection['baseline_arm'], 'effective_exit': 0,
             'effective_pid': pid, 'selected': sorted(selected), 'exact_baseline_reuse': expected-len(selected),
             'preserved_fields': ['answer', 'reason', 'status'], 'new_main_sends': len(starts),
             'new_responses': len(starts), 'unknown_sent': 0, 'new_tool_calls': 0,
             'actual_edited_branches_within_4main_2tools': True,
             'references_opened_only_after_complete_generation': True,
             'whole_baseline_fixed_before_generation': True}
    out = run / 'offline_r43'
    out.mkdir(exist_ok=True)
    if not (out / 'completion_and_reuse_audit.json').exists():
        (out / 'completion_and_reuse_audit.json').write_text(json.dumps(audit, indent=2)+'\n',encoding='utf-8')
    if not (out / 'summary.json').exists():
        score(data, run, None, out, ['B', 'M43'], [('M43', 'B')])
    return read(out / 'summary.json')
