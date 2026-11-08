"""Bounded paired source/development Skill pilot; never reads references."""
import argparse
import json
from pathlib import Path
import sys
import time

from cxr_author_alignment import extract
from cxr_skill_probe_r44 import ARMS, messages, order, protocol, rows


def main():
    parser = argparse.ArgumentParser()
    for name in ['data','skill','out']:
        parser.add_argument('--'+name, type=Path, required=True)
    parser.add_argument('--config', type=Path)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--api-key-stdin', action='store_true')
    args = parser.parse_args()
    # Use the already deployed, frozen R4.1 transport and atomic record writer.
    from run_cxr_vqa_toolsets import PaidCalls, exclusive_lock, freeze_protocol, now, read, save
    inputs = rows(args.data/'inputs.jsonl')
    skill = args.skill.read_text(encoding='utf-8').strip()
    specification = protocol(skill, inputs)
    args.out.mkdir(parents=True, exist_ok=True)
    with exclusive_lock(args.out/'.generation.lock'):
        freeze_protocol(args.out, specification)
        snapshot = args.out/'inputs.json'
        if snapshot.exists():
            assert read(snapshot) == inputs, 'input_changed'
        else:
            save(snapshot, inputs)
        for row, arm in order(inputs):
            messages(row, arm, args.data, skill)
        if not args.execute:
            print(json.dumps({'status':'zero_paid_prepared','pairs':len(inputs),
                              'max_new_main':54,'tools':0}), flush=True)
            return
        assert args.config and args.api_key_stdin
        assert not list((args.out/'calls').glob('*/*/*/started.json')), 'new_execution_only_no_resume'
        assert not list((args.out/'predictions').glob('*/*.json')), 'new_execution_only_no_resume'
        key = sys.stdin.readline().strip(); assert key
        paid = PaidCalls(read(args.config), specification, args.out, key)
        started_at = now()
        for row, arm in order(inputs):
            qid = row['question_id']
            target = args.out/'predictions'/arm/(qid+'.json')
            if target.exists():
                continue
            # A prior interrupted/failed send is a cohort stop, even if its
            # response happened to arrive before transport validation failed.
            folder = args.out/'calls'/arm/qid/'1'
            if (folder/'started.json').exists():
                raise RuntimeError('existing_sent_without_prediction_no_automatic_recovery:'+qid)
            tick = time.monotonic()
            try:
                paid.call(row, arm, 1, messages(row, arm, args.data, skill))
            except Exception:
                save(target, {'question_id':qid,'arm':arm,'answer':None,
                     'status':'technical_stop','main_calls':1,'tool_calls':0,
                     'elapsed_s':time.monotonic()-tick,'utc':now()})
                raise
            raw = read(folder/'response.json')
            response = raw['choices'][0]
            message = response['message']
            final = (response.get('finish_reason') == 'stop'
                     and not message.get('tool_calls') and not message.get('function_call'))
            extracted = extract(message.get('content'), qid) if final else None
            answer = extracted.answer if extracted else None
            save(target, {'question_id':qid,'arm':arm,'answer':answer,
                 'status':'explicit_answer' if answer is not None else 'missing_explicit_answer',
                 'extraction':extracted.mechanism if extracted else 'nonterminal_reply',
                 'finish_reason':response.get('finish_reason'),
                 'main_calls':1,'tool_calls':0,'elapsed_s':time.monotonic()-tick,'utc':now()})
            print(json.dumps({'saved':qid,'arm':arm,'main_calls':1,'tools':0}), flush=True)
        expected = {row['question_id'] for row in inputs}
        for arm in ARMS:
            assert {p.stem for p in (args.out/'predictions'/arm).glob('*.json')} == expected
            assert len(list((args.out/'calls'/arm).glob('*/1/response.json'))) == len(expected)
            save(args.out/('complete_'+arm+'.json'), {'questions':len(expected),
                 'new_main_sends':len(expected),'new_tool_calls':0,'utc':now()})
        save(args.out/'complete.json', {'pairs':len(expected),'arms':list(ARMS),
             'new_main_sends':54,'new_tools':0,'started_at':started_at,'completed_at':now()})
        print('BOTH_R44_ARMS_GENERATED', flush=True)


if __name__ == '__main__':
    main()
