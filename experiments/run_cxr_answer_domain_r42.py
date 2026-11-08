"""Full-denominator archived M continuation; never reads target references."""
import argparse
from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
import sys

from cxr_answer_domain_r42 import RESTATE, decision, parse_restatement
from run_cxr_vqa_toolsets import PaidCalls, exclusive_lock, freeze_protocol, now, read, rows, save
from export_cxr_vqa_extension import restore_images


def prepare(data, baseline, out):
    inputs = rows(data / 'inputs.jsonl')
    original = {p.stem: read(p) for p in (baseline / 'predictions/M').glob('*.json')}
    ids = {x['question_id'] for x in inputs}
    assert len(ids) == len(inputs) and set(original) == ids
    receipt = read(baseline / 'complete_M.json')
    assert receipt['questions'] == len(inputs)
    inherited = read(baseline / 'protocol.json')
    assert inherited['main_call_limits']['M'] == 4 and inherited['selectable_tool_limit'] == 2
    gates = {x['question_id']: decision(x, original[x['question_id']]) for x in inputs}
    selected = [q for q, value in gates.items() if value == 'continue_once']
    for qid in selected:
        old = original[qid]
        calls = baseline / 'calls/M' / qid
        folders = sorted(calls.glob('*'))
        assert len(folders) == old['main_calls']
        assert all((p / 'request.json').is_file() and (p / 'response.json').is_file() for p in folders)
        last = calls / str(old['main_calls'])
        response = read(last / 'response.json')
        assert response['choices'][0]['message']['content']
        request = restore_images(read(last / 'request.json'), baseline)
        assert request['model'] == inherited['model'] and isinstance(request['messages'], list)
    protocol = {k: inherited[k] for k in ['model', 'temperature', 'top_p', 'enable_thinking', 'max_output_tokens']}
    protocol.update(experiment_id='answer_domain_r42_20261108', design='archived_M_prefix_continuation_on_exposed_development_benchmark',
                    request_archive='image_base64_content_addressed_v1',
                    main_call_limits={'M': 4, 'M42': 4}, tool_call_limits={'M': 2, 'M42': 2},
                    new_tool_calls=0, new_main_request_ceiling=len(selected),
                    reference_free_gate=True, benchmark_is_unseen=False,
                    repair_prompt=RESTATE, fallback='Retain exact historical M answer/reason/status if known received reply is invalid.',
                    unknown_sent='Stop, preserve intent, no automatic retry.',
                    budget={'existing_shared_ledger': False, 'enforce_money_cap': False,
                            'accounting': 'Per-request usage; inherited M cost is not new spend.'})
    out.mkdir(parents=True, exist_ok=True)
    freeze_protocol(out, protocol)
    selection = {'questions': len(inputs), 'decisions': gates, 'selected_question_ids': selected,
                 'counts': dict(Counter(gates.values())), 'target_references_read': False}
    path = out / 'selection.json'
    if path.exists():
        assert read(path) == selection, 'frozen_selection_changed'
    else:
        save(path, selection)
    return inputs, original, protocol, selection


def execute(data, baseline, out, cfg, key):
    with exclusive_lock(out / '.generation.lock'):
        inputs, original, protocol, selection = prepare(data, baseline, out)
        paid = PaidCalls(cfg, protocol, out, key)
        for index, row in enumerate(inputs, 1):
            qid = row['question_id']
            target = out / 'predictions/M42' / (qid + '.json')
            if target.exists():
                continue
            prior = original[qid]
            result = deepcopy(prior)
            result.update(arm='M42', archived_prefix=True, new_main_calls=0, new_tool_calls=0,
                          continuation_gate=selection['decisions'][qid],
                          reused_historical_M=True)
            if selection['decisions'][qid] == 'continue_once':
                last = baseline / 'calls/M' / qid / str(prior['main_calls'])
                request = restore_images(read(last / 'request.json'), baseline)
                response = read(last / 'response.json')
                messages = deepcopy(request['messages'])
                messages.append({'role': 'assistant', 'content': response['choices'][0]['message']['content']})
                messages.append({'role': 'user', 'content': RESTATE})
                ordinal = prior['main_calls'] + 1
                assert ordinal <= 4
                raw = paid.call(row, 'M42', ordinal, messages)
                try:
                    repaired = parse_restatement(raw)
                except (ValueError, TypeError, IndexError):
                    result['continuation_outcome'] = 'invalid_reply_retained_M'
                else:
                    result.update(repaired, reused_historical_M=False,
                                  continuation_outcome='explicit_binary_answer_received')
                result.update(main_calls=ordinal, new_main_calls=1, utc=now())
            save(target, result)
        saved = {x.stem for x in (out / 'predictions/M42').glob('*.json')}
        assert saved == set(original)
        calls = list((out / 'calls/M42').glob('*/*/started.json'))
        assert len(calls) <= protocol['new_main_request_ceiling']
        assert all((p.parent / 'response.json').is_file() for p in calls)
        completion = out / 'complete_M42.json'
        if not completion.exists():
            save(completion, {'status': 'generation_complete', 'questions': len(inputs),
                              'new_main_requests': len(calls), 'new_tool_calls': 0, 'utc': now()})
        print(json.dumps({'status': 'generation_complete', 'questions': len(inputs),
                          'new_main_requests': len(calls), 'references_read': False}), flush=True)


def main():
    parser = argparse.ArgumentParser()
    for name in ['data', 'baseline', 'out']:
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--config', type=Path)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--api-key-stdin', action='store_true')
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    if not args.execute:
        _, _, _, selection = prepare(args.data, args.baseline, args.out)
        print(json.dumps({'status': 'prepared_no_paid_requests', **selection}), flush=True)
        return
    assert args.config and args.api_key_stdin
    key = sys.stdin.readline().strip()
    assert key
    execute(args.data, args.baseline, args.out, read(args.config), key)


if __name__ == '__main__':
    main()
