"""Completion-gated audit and unchanged scoring of archived M42 continuation."""
import argparse
import json
from pathlib import Path

from export_vote_phase import read
from score_cxr_vqa_extension import rows, score


def finalize(root, data, historical):
    run = root / 'vqarad'
    pid = (root / 'jobs/vqarad.pid').read_text().strip()
    assert not Path('/proc', pid).exists()
    assert (root / 'jobs/vqarad.exitcode').read_text().strip() == '0'
    inputs = rows(data / 'inputs.jsonl')
    ids = {x['question_id'] for x in inputs}
    assert len(ids) == len(inputs) == 116
    receipt = read(run / 'complete_M42.json')
    assert receipt['questions'] == 116
    predictions = {p.stem: read(p) for p in (run / 'predictions/M42').glob('*.json')}
    assert set(predictions) == ids
    baseline = {x['question_id']: x for x in rows(historical / 'predictions_M.jsonl')}
    assert set(baseline) == ids
    selection = read(run / 'selection.json')
    selected = set(selection['selected_question_ids'])
    assert len(selected) == 1
    for qid, prediction in predictions.items():
        old = baseline[qid]
        if qid not in selected:
            for field in ('answer', 'reason', 'status', 'main_calls', 'tool_calls'):
                assert prediction.get(field) == old.get(field), (qid, field)
            assert prediction['new_main_calls'] == prediction['new_tool_calls'] == 0
        else:
            assert prediction['main_calls'] == old['main_calls'] + 1 <= 4
            assert prediction['tool_calls'] == old['tool_calls'] <= 2
            assert prediction['new_main_calls'] == 1 and prediction['new_tool_calls'] == 0
    starts = list((run / 'calls/M42').glob('*/*/started.json'))
    assert len(starts) == 1 and all((p.parent / 'response.json').is_file() for p in starts)
    audit = {'questions': 116, 'effective_job_pid': pid, 'effective_job_exit': 0,
             'completion_receipt': receipt, 'selected': sorted(selected), 'exact_M_reuse': 115,
             'reused_fields_checked': ['answer', 'reason', 'status', 'main_calls', 'tool_calls'],
             'new_main_sends': 1, 'new_responses': 1, 'unknown_sent': 0, 'new_tool_calls': 0,
             'historical_plus_new_budget': '4main/2tools',
             'references_opened_after_completion_gate': True,
             'design': 'Archived-prefix exposed-development continuation, not a fresh independent rerun.'}
    out = run / 'offline_r42'
    out.mkdir(exist_ok=True)
    if not (out / 'completion_and_reuse_audit.json').exists():
        (out / 'completion_and_reuse_audit.json').write_text(json.dumps(audit, indent=2) + '\n', encoding='utf-8')
    if not (out / 'summary.json').exists():
        score(data, run, historical, out, ['M', 'M42'], [('M42', 'M')])
    return read(out / 'summary.json')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    for name in ['root', 'data', 'historical']:
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    summary = finalize(args.root, args.data, args.historical)
    print(json.dumps({'questions': summary['questions'],
                      'arms': {a: {k: v.get(k) for k in ['correct', 'missing', 'micro_pct', 'macro_pct', 'resources']}
                               for a, v in summary['arms'].items()},
                      'comparisons': summary['comparisons']}, ensure_ascii=False))
