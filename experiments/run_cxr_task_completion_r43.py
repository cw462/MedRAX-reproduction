"""Best-whole-arm archived task completion; no references or score reads."""
import argparse
from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
import sys
import time

from cxr_task_completion_r43 import accepted_reply, decision, prompt
from export_cxr_vqa_extension import restore_images
from run_cxr_vqa_toolsets import PaidCalls, exclusive_lock, freeze_protocol, now, read, rows, save


def prepare(data, best_run, best_arm, original_run, out, dataset):
    expected = {'chexbench': 618, 'slake': 114}[dataset]
    inputs = rows(data / 'inputs.jsonl')
    best = {p.stem: read(p) for p in (best_run / 'predictions' / best_arm).glob('*.json')}
    original = {p.stem: read(p) for p in (original_run / 'predictions/M').glob('*.json')}
    ids = {x['question_id'] for x in inputs}
    assert len(ids) == len(inputs) == expected and set(best) == set(original) == ids
    assert read(best_run / ('complete_' + best_arm + '.json'))['questions'] == expected
    assert read(original_run / 'complete_M.json')['questions'] == expected
    reasons = {x['question_id']: decision(x, best[x['question_id']], original[x['question_id']]) for x in inputs}
    selected = [q for q, value in reasons.items() if value == 'complete_once']
    assert len(selected) <= {'chexbench': 10, 'slake': 1}[dataset]
    prefixes = {}
    for qid in selected:
        old = original[qid]
        folders = list((original_run / 'calls/M' / qid).glob('*'))
        assert len(folders) == old['main_calls']
        assert all((p / 'request.json').exists() and (p / 'response.json').exists() for p in folders)
        last = original_run / 'calls/M' / qid / str(old['main_calls'])
        request = restore_images(read(last / 'request.json'), original_run)
        assert request['messages'] and read(last / 'response.json')['choices'][0]['message']['content']
        prefixes[qid] = {'source': 'inherited_original_M', 'actual_main_calls': old['main_calls'],
                         'actual_tool_calls': old['tool_calls'], 'total_main_after': old['main_calls'] + 1}
    inherited = read(original_run / 'protocol.json')
    origin = read(original_run / 'origin.json') if (original_run / 'origin.json').exists() else {
        'kind': 'private_original_archive', 'public_metadata_transformations': False}
    protocol = {k: inherited[k] for k in ['model', 'temperature', 'top_p', 'enable_thinking', 'max_output_tokens']}
    protocol.update(experiment_id='task_completion_r43_20261108', dataset=dataset, questions=expected,
                    baseline_arm=best_arm, design='Strongest fixed whole arm plus reference-free unscorable-output completion.',
                    nominal_whole_strategy_limits={'main': 6, 'tools': 4},
                    actual_edited_prefix_limits={'main': 4, 'tools': 2},
                    main_call_limits={'M43': 6}, tool_call_limits={'M43': 4},
                    request_archive='image_base64_content_addressed_v1', new_main_request_ceiling=len(selected),
                    wave_new_main_ceiling=11, new_tool_calls=0, target_references_read=False,
                    benchmark_is_unseen=False, raw_prefix_source=original_run.name, prefix_origin=origin,
                    prompt_template=prompt({'question': 'Is this supported?'}),
                    prompt_mcq_template=prompt({'question': '', 'options': {'A': '', 'B': ''}}),
                    reply_acceptance='Original exactM JSON schema plus fixed reference-free task legality; no correctness selection.',
                    fallback='Retain exact baseline answer/reason/status after known invalid reply.',
                    accounting='main_calls/tool_calls are new-run counts; prefix_actual fields count historical branch.',
                    budget={'existing_shared_ledger': False, 'enforce_money_cap': False})
    out.mkdir(parents=True, exist_ok=True)
    freeze_protocol(out, protocol)
    selection = {'dataset': dataset, 'questions': expected, 'baseline_arm': best_arm,
                 'decisions': reasons, 'selected': selected, 'prefixes': prefixes,
                 'counts': dict(Counter(reasons.values())), 'references_read': False}
    path = out / 'selection.json'
    if path.exists():
        assert read(path) == selection
    else:
        save(path, selection)
    return inputs, best, original, protocol, selection


def main():
    p = argparse.ArgumentParser()
    for name in ['data', 'best-run', 'original-run', 'out']:
        p.add_argument('--' + name, type=Path, required=True)
    p.add_argument('--best-arm', required=True)
    p.add_argument('--dataset', choices=['chexbench', 'slake'], required=True)
    p.add_argument('--config', type=Path)
    p.add_argument('--execute', action='store_true')
    p.add_argument('--api-key-stdin', action='store_true')
    a = p.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    with exclusive_lock(a.out / '.generation.lock'):
        inputs, best, original, protocol, selected = prepare(a.data, a.best_run, a.best_arm, a.original_run, a.out, a.dataset)
        if not a.execute:
            print(json.dumps({'status': 'zero_paid_prepared', 'questions': len(inputs),
                              'selected': selected['selected'], 'prefixes': selected['prefixes']}), flush=True)
            return
        assert a.config and a.api_key_stdin
        key = sys.stdin.readline().strip()
        assert key
        paid = PaidCalls(read(a.config), protocol, a.out, key)
        for row in inputs:
            qid = row['question_id']
            target = a.out / 'predictions/M43' / (qid + '.json')
            if target.exists():
                continue
            prior = best[qid]
            result = deepcopy(prior)
            inherited_observations = result.pop('observations', [])
            result.update(arm='M43', main_calls=0, tool_calls=0, observations=[], elapsed_s=0,
                          inherited_observations=inherited_observations,
                          inherited_arm=a.best_arm, historical_reported_main_calls=prior.get('main_calls'),
                          historical_reported_tool_calls=prior.get('tool_calls'),
                          new_main_calls=0, new_tool_calls=0, reused_best=True,
                          continuation_gate=selected['decisions'][qid])
            if selected['decisions'][qid] == 'complete_once':
                old = original[qid]
                last = a.original_run / 'calls/M' / qid / str(old['main_calls'])
                request = restore_images(read(last / 'request.json'), a.original_run)
                messages = deepcopy(request['messages'])
                messages.append({'role': 'assistant', 'content': read(last / 'response.json')['choices'][0]['message']['content']})
                messages.append({'role': 'user', 'content': prompt(row)})
                ordinal = old['main_calls'] + 1
                assert ordinal <= 4 and old['tool_calls'] <= 2
                tick = time.monotonic()
                raw = paid.call(row, 'M43', ordinal, messages)
                result.update(main_calls=1, new_main_calls=1, elapsed_s=time.monotonic() - tick,
                              prefix_actual_main_calls=old['main_calls'], prefix_actual_tool_calls=old['tool_calls'],
                              total_edited_main_calls=ordinal, total_edited_tool_calls=old['tool_calls'])
                try:
                    completed = accepted_reply(row, raw)
                except (ValueError, TypeError, IndexError):
                    result['completion_outcome'] = 'invalid_reply_retained_best'
                else:
                    result.update(completed, reused_best=False, completion_outcome='accepted_task_answer')
                result['utc'] = now()
            save(target, result)
        ids = {p.stem for p in (a.out / 'predictions/M43').glob('*.json')}
        assert ids == set(best)
        starts = list((a.out / 'calls/M43').glob('*/*/started.json'))
        assert len(starts) <= protocol['new_main_request_ceiling']
        assert all((p.parent / 'response.json').exists() for p in starts)
        receipt = a.out / 'complete_M43.json'
        if not receipt.exists():
            save(receipt, {'status': 'generation_complete', 'questions': len(inputs),
                           'new_main_sends': len(starts), 'new_tool_calls': 0, 'utc': now()})
        print(json.dumps({'status': 'generation_complete', 'dataset': a.dataset, 'questions': len(inputs),
                          'new_main_sends': len(starts), 'references_read': False}), flush=True)


if __name__ == '__main__':
    main()
