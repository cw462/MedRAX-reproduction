"""Run joint inference on the frozen stage-three Q cohort."""

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
import time

from cxr_vqa_joint import SYSTEM, bind_group, joint_episode
from run_cxr_vqa_toolsets import PaidCalls, Tools, exclusive_lock, now, read, rows, safe_error, save, write


ARMS = ('D-Q', 'M-Q')


def load_groups(path, dataset, expected_digest):
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_digest:
        raise ValueError('Frozen joint cohort changed')
    manifest = json.loads(raw)
    if manifest['status'] != 'stage3_cohort_frozen' or manifest['target_labels_read'] is not False:
        raise ValueError('Joint cohort must be frozen and label blind')
    frozen = manifest['datasets'][dataset]
    groups = frozen['groups']
    ids = [qid for group in groups for qid in group['question_ids']]
    keys = {group['group_id'] for group in groups}
    if (len(groups) != frozen['q_group_count'] or len(keys) != len(groups) or
            len(ids) != frozen['q_questions'] or len(set(ids)) != len(ids) or not ids or
            any(not re.fullmatch(r'q-[0-9a-f]{24}', key) for key in keys)):
        raise ValueError('Frozen joint cohort counts differ')
    return groups, set(ids)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('config', 'data', 'out', 'cohort'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--dataset', choices=('chexbench', 'slake', 'vqarad'), required=True)
    parser.add_argument('--cohort-sha256', required=True)
    parser.add_argument('--arms', nargs='+', choices=ARMS, required=True)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--api-key-stdin', action='store_true')
    args = parser.parse_args(argv)

    cfg = read(args.config)
    protocol = read(cfg['protocol'])
    runtime = read(cfg['runtime'])
    groups, ids = load_groups(args.cohort, args.dataset, args.cohort_sha256)
    inputs = rows(args.data / 'inputs.jsonl')
    rows_by_id = {row['question_id']: row for row in inputs}
    if len(rows_by_id) != len(inputs) or len(inputs) != protocol['datasets'][args.dataset]['questions']:
        raise ValueError('Unexpected target input manifest')
    if any(set(row) - {'question_id', 'question', 'images', 'image_id', 'source', 'options'} for row in inputs):
        raise ValueError('Unexpected inference fields')
    for group in groups:
        bind_group(group, rows_by_id)
    if not args.execute:
        print(json.dumps({'status': 'offline_interface_ready', 'groups': len(groups),
                          'questions': len(ids), 'arms': args.arms, 'paid_calls': 0}))
        return

    out = args.out
    if out.name != args.dataset:
        raise ValueError('Joint predictions must use their dataset run directory')
    for name in protocol['datasets']:
        for earlier in ('M-S', 'M-E'):
            if not (out.parent / name / f'complete_{earlier}.json').is_file():
                raise ValueError(f'Missing stage-two completion receipt: {name}/{earlier}')
    key = sys.stdin.readline().strip() if args.api_key_stdin else ''
    if not key:
        raise ValueError('API key is required through stdin')

    with exclusive_lock(out / '.generation.lock'):
        paid = PaidCalls(cfg, protocol, out, key)
        tools = Tools(runtime, args.data, out)
        for arm in args.arms:
            if not runtime['arms'][arm]['ready']:
                raise ValueError(f'Arm is not ready: {arm}')
            freeze = {'arm': runtime['arms'][arm], 'tools': runtime['tools'],
                      'backend_config': runtime['backend_config'], 'cohort_sha256': args.cohort_sha256,
                      'agent_system': SYSTEM}
            receipt = out / f'runtime_full_{arm}.json'
            if receipt.is_file():
                if read(receipt) != freeze:
                    raise ValueError(f'Frozen joint runtime changed: {arm}')
            else:
                save(receipt, freeze)
            for index, group in enumerate(groups, 1):
                group_id = group['group_id']
                terminal = out / 'joint_groups' / arm / f'{group_id}.json'
                if terminal.is_file():
                    result = read(terminal)
                else:
                    progress = {'arm': arm, 'qid': group_id, 'index': index, 'total': len(groups)}
                    write(out / 'progress.json', dict(progress, status='running', utc=now()))
                    start = time.monotonic()
                    try:
                        result = joint_episode(group, rows_by_id, arm, args.data, runtime, out, paid, tools)
                    except Exception as exc:
                        write(out / 'progress.json', dict(progress, status='stopped', error=safe_error(exc, key), utc=now()))
                        raise
                    result['elapsed_s'] = time.monotonic() - start
                    save(terminal, result)
                for offset, qid in enumerate(group['question_ids']):
                    prediction = out / 'predictions' / arm / f'{qid}.json'
                    value = dict(result['answers'][qid], arm=arm, question_id=qid, group_id=group_id,
                                 image_id=rows_by_id[qid]['image_id'], main_calls=result['main_calls'] if offset == 0 else 0,
                                 tool_calls=result['tool_calls'] if offset == 0 else 0,
                                 elapsed_s=result['elapsed_s'] if offset == 0 else 0)
                    if prediction.is_file():
                        if read(prediction) != value:
                            raise ValueError(f'Joint prediction differs from its group record: {qid}')
                    else:
                        save(prediction, value)
            completion = out / f'complete_{arm}.json'
            if not completion.is_file():
                save(completion, {'status': 'generation_complete', 'questions': len(ids),
                                  'groups': len(groups), 'cohort_sha256': args.cohort_sha256, 'utc': now()})
        write(out / 'progress.json', {'status': 'requested_arms_complete', 'arms': args.arms, 'utc': now()})


if __name__ == '__main__':
    main()
