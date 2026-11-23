"""R47: fixed M43 policies with online, post-save same-image dataset feedback."""
import argparse
import copy
import json
from pathlib import Path
import sys
import time

from cxr_image_memory_gt_r47 import (
    ARM, ReferenceVault, assert_no_unknown_sends, context,
    feedback_after_save, memory_entry, now, read, rows, save_once,
    tool_failure_reason, validate_frozen, validate_resume_prefix,
)


class CapturePaid:
    def __init__(self, paid):
        self.paid, self.last, self.raw = paid, None, None

    def call(self, row, arm, ordinal, messages, **kwargs):
        raw = self.paid.call(row, ARM, ordinal, messages, **kwargs)
        self.last, self.raw = copy.deepcopy(messages), raw
        return raw


class BoundTools:
    def __init__(self, tools):
        self.tools = tools

    def call(self, row, action, arm, ordinal):
        observation = self.tools.call(row, action, ARM, ordinal)
        failure = tool_failure_reason(observation)
        if failure:
            raise RuntimeError('tool_unhealthy_stop:' + failure)
        return observation


def run_episode(base, r41, completion, row, policy, data, protocol, runtime, out, paid, tools, conditioning):
    """The R45 dispatch/completion behavior, with only the new arm/prompt binding."""
    cap, bound = CapturePaid(paid), BoundTools(tools)
    saved = base.agent_system

    def system(arm):
        value = saved(arm)
        if conditioning:
            value = value.replace(
                'No cross-case skills, sibling question context or additional patient history is available.',
                'Earlier same-image model outputs and post-prediction dataset feedback annotations may be supplied. '
                'These annotations are not patient history. No other-case skills or extra patient history are supplied.')
        return value

    base.agent_system = system
    try:
        if policy == 'C41':
            result = r41.episode(base, row, 'M-C41', data, protocol, runtime, out, cap, bound, conditioning)
        elif policy == 'M':
            result = base.episode(row, 'M', data, protocol, runtime, out, cap, bound, conditioning=conditioning)
        else:
            raise ValueError('invalid_frozen_policy')
        if policy == 'M':
            inherited = dict(result, reused_historical_M=True)
            if completion.decision(row, inherited, result) == 'complete_once':
                messages = cap.last + [{'role': 'assistant', 'content': cap.raw},
                                       {'role': 'user', 'content': completion.prompt(row)}]
                ordinal = result['main_calls'] + 1
                raw = cap.call(row, 'M', ordinal, messages)
                result['main_calls'] = ordinal
                try:
                    result.update(completion.accepted_reply(row, raw))
                    result['completion_outcome'] = 'accepted'
                except (ValueError, TypeError, IndexError):
                    result['completion_outcome'] = 'invalid_retained'
        main_cap, tool_cap = (6, 4) if policy == 'C41' else (4, 2)
        if not 1 <= result['main_calls'] <= main_cap or not 0 <= result['tool_calls'] <= tool_cap:
            raise ValueError('policy_budget_exceeded')
        result['terminal_raw'] = cap.raw
        return result
    finally:
        base.agent_system = saved


def reuse_m43(frozen, qid, prediction_saved_at):
    return dict(copy.deepcopy(frozen['baseline'][qid]), question_id=qid, arm=ARM,
                main_calls=0, tool_calls=0, new_main_calls=0, new_tool_calls=0, reused_M43=True,
                prediction_saved_at=prediction_saved_at)


def generate(frozen, out, base, r41, completion, paid, tools, protocol, runtime, load_reference):
    """Sequential spine; callback execution is visibly after immutable save."""
    out = Path(out)
    validate_resume_prefix(out, frozen['order'])
    assert_no_unknown_sends(out)
    rowmap = {row['question_id']: row for row in frozen['inputs']}
    memories = {}
    for ordinal, item in enumerate(frozen['order'], 1):
        qid, image = item['question_id'], item['image_key']
        row = rowmap[qid]
        entries = memories.setdefault(image, [])
        conditioning, used = context(entries, item, ordinal, frozen['memory_max_chars'], frozen['memory_max_entries'])
        trace_path = out / 'memory_context' / (qid + '.json')
        created_at = read(trace_path)['created_at'] if trace_path.exists() else now()
        trace = {'question_id': qid, 'image_key': image, 'ordinal': ordinal,
                 'previous_ids': item['previous_ids'], 'included_ids': used,
                 'memory': conditioning,
                 'current_reference_available': False, 'created_at': created_at}
        save_once(trace_path, trace)
        destination = out / 'predictions' / ARM / (qid + '.json')
        if destination.exists():
            result = read(destination)
            if result.get('question_id') != qid or result.get('arm') != ARM:
                raise ValueError('saved_prediction_identity_changed')
            if not item['previous_ids'] and result != reuse_m43(frozen, qid, result['prediction_saved_at']):
                raise ValueError('original_M43_reuse_changed')
            if item['previous_ids'] and result.get('reused_M43') is not False:
                raise ValueError('repeat_question_must_be_fresh')
        elif not item['previous_ids']:
            result = reuse_m43(frozen, qid, now())
            save_once(destination, result)
        else:
            base.write(out / 'progress.json', {'status': 'running', 'index': ordinal, 'total': 618,
                       'question_id': qid, 'policy': frozen['policy'][qid], 'included_ids': used, 'utc': base.now()})
            tick = time.monotonic()
            try:
                result = run_episode(base, r41, completion, row, frozen['policy'][qid], Path(frozen['data']),
                                     protocol, runtime, out, paid, tools, conditioning)
            except Exception as exc:
                base.write(out / 'progress.json', {'status': 'stopped', 'index': ordinal,
                           'question_id': qid, 'error': base.safe_error(exc, getattr(paid, 'key', '')),
                           'error_type': type(exc).__name__, 'utc': base.now()})
                # A technical stop remains a stop. No prediction, feedback, retry, or failure registration.
                raise RuntimeError('image_memory_gt_generation_stopped:' + type(exc).__name__) from None
            result.update(question_id=qid, arm=ARM, reused_M43=False,
                          new_main_calls=result['main_calls'], new_tool_calls=result['tool_calls'],
                          elapsed_s=time.monotonic() - tick, utc=base.now(), prediction_saved_at=now())
            save_once(destination, result)
        event = feedback_after_save(out, item, ordinal, frozen['reference_files'], load_reference)
        entries.append(memory_entry(row, result, event))
    return memories


def audit_complete(frozen, out):
    out = Path(out)
    ids = {row['question_id'] for row in frozen['inputs']}
    for directory in (out / 'predictions' / ARM, out / 'feedback_events', out / 'memory_context'):
        if {path.stem for path in directory.glob('*.json')} != ids:
            raise ValueError('incomplete_artifact_membership:' + directory.name)
    sends = list((out / 'calls' / ARM).glob('*/*/started.json'))
    for sent in sends:
        folder = sent.parent
        if not (folder / 'response.json').exists() or not (folder / 'result.json').exists():
            raise ValueError('unresolved_sent_request')
        receipt = read(folder / 'result.json')
        if receipt.get('error') or receipt.get('response_received') is not True:
            raise ValueError('unhealthy_request_receipt')
    selections = list((out / 'tool_selections' / ARM).glob('*/*.json'))
    for selection in selections:
        if tool_failure_reason(read(selection)):
            raise ValueError('unhealthy_tool_selection')
    if len(sends) > frozen['new_main_ceiling'] or len(selections) > frozen['new_tool_ceiling']:
        raise ValueError('cohort_budget_exceeded')
    return {'questions': len(ids), 'status': 'generation_complete', 'feedback_events': len(ids),
            'references_read': True, 'reference_access': 'only_after_own_prediction_saved',
            'current_or_future_reference_in_current_request': False,
            'new_main_sends': len(sends), 'new_logical_tool_calls': len(selections)}


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--frozen', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--reference-dir', type=Path)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--api-key-stdin', action='store_true')
    args = parser.parse_args(argv)
    frozen = read(args.frozen)
    validate_frozen(frozen)
    data = Path(frozen['data'])
    if rows(data / 'inputs.jsonl') != frozen['inputs']:
        raise ValueError('input_records_changed')
    if not args.execute:
        print(json.dumps({'questions': 618, 'repeat_questions': 130, 'image_groups': 488,
                          'reused_M43': 488, 'feedback_events_required': 618,
                          'paid_calls': 0, 'reference_files_read': 0}))
        return
    import run_cxr_vqa_toolsets as base
    import run_cxr_action_r41 as r41
    import cxr_task_completion_r43 as completion
    if not args.api_key_stdin:
        raise ValueError('stdin_key_required')
    key = sys.stdin.readline().strip()
    if not key:
        raise ValueError('missing_key')
    protocol = copy.deepcopy(frozen['protocol'])
    protocol.update(experiment_id='m43_image_memory_gt_r47_20261108',
                    request_archive='image_base64_content_addressed_v1',
                    main_call_limits={'M': 4, 'M-C41': 6, ARM: 6},
                    tool_call_limits={'M': 2, 'M-C41': 4, ARM: 4})
    runtime = copy.deepcopy(frozen['runtime'])
    spec = runtime['arms'].get('M') or runtime['arms'].get('M-C41')
    if spec is None or not spec.get('ready'):
        raise ValueError('original_tools_not_ready')
    runtime['arms'] = {name: copy.deepcopy(spec) for name in ('M', 'M-C41', ARM)}
    reference_dir = args.reference_dir or Path(frozen['reference_dir'])
    args.out.mkdir(parents=True, exist_ok=True)
    with base.exclusive_lock(args.out / '.generation.lock'):
        marker = {'frozen_path': str(args.frozen.resolve()), 'order': frozen['order'],
                  'inputs': frozen['inputs'], 'policy': frozen['policy'], 'baseline': frozen['baseline'],
                  'protocol': protocol, 'runtime': runtime, 'reference_dir': str(reference_dir.resolve())}
        run_path = args.out / 'run.json'
        if not run_path.exists() and any(path.name != '.generation.lock' for path in args.out.iterdir()):
            raise ValueError('fresh_output_required')
        save_once(run_path, marker)
        assert_no_unknown_sends(args.out)
        paid = base.PaidCalls(frozen['config'], protocol, args.out, key)
        tools = base.Tools(runtime, data, args.out)
        vault = ReferenceVault(reference_dir, frozen['reference_files'])
        generate(frozen, args.out, base, r41, completion, paid, tools, protocol, runtime, vault.after_prediction)
        receipt = audit_complete(frozen, args.out)
        if not (args.out / ('complete_' + ARM + '.json')).exists():
            save_once(args.out / ('complete_' + ARM + '.json'), dict(receipt, utc=base.now()))
        base.write(args.out / 'progress.json', {'status': 'complete', 'questions': 618, 'utc': base.now()})
        print(json.dumps({'status': 'complete', 'questions': 618, 'feedback_events': 618}))


if __name__ == '__main__':
    main()
