"""Run one R48 fixed-baseline same-image feedback arm, sequentially."""
import argparse
import copy
import json
from pathlib import Path
import sys
import time

from cxr_image_memory_gt_r48 import (
    DATASETS, POLICY_LIMITS, ReferenceVault, assert_closed_sends, context,
    feedback_after_save, memory_entry, now, read, rows, save_once,
    summary, tool_failure_reason, validate_frozen, validate_protocol, validate_resume_prefix,
)


class CapturePaid:
    def __init__(self, paid, arm):
        self.paid, self.arm, self.last, self.raw = paid, arm, None, None

    def call(self, row, arm, ordinal, messages, **kwargs):
        raw = self.paid.call(row, self.arm, ordinal, messages, **kwargs)
        self.last, self.raw = copy.deepcopy(messages), raw
        return raw


class BoundTools:
    def __init__(self, tools, arm):
        self.tools, self.arm = tools, arm

    def call(self, row, action, arm, ordinal):
        observation = self.tools.call(row, action, self.arm, ordinal)
        failure = tool_failure_reason(observation)
        if failure:
            raise RuntimeError('tool_unhealthy_stop:' + failure)
        return observation


def run_episode(base, r41, r42, completion, row, policy, dataset, arm, data,
                protocol, runtime, out, paid, tools, conditioning):
    """R41 S41 or original M, followed only by that dataset's original gate."""
    kind = policy['kind']
    if dataset not in DATASETS or (dataset == 'vqarad' and kind != 'M'):
        raise ValueError('invalid_dataset_policy')
    cap, bound = CapturePaid(paid, arm), BoundTools(tools, arm)
    saved_system = base.agent_system

    def system(name):
        value = saved_system(name)
        if conditioning:
            supplied = ('The original optional source-derived action skill may be supplied. ' if kind == 'M-S41' else '')
            value = value.replace(
                'No cross-case skills, sibling question context or additional patient history is available.',
                supplied + 'Earlier exact-same-image model outputs and post-prediction dataset feedback may be supplied. '
                'Feedback is question-specific dataset annotation, not patient history. No other-image or other-dataset memory is supplied.')
        return value

    base.agent_system = system
    try:
        if kind == 'M-S41':
            # Preserve the exact original row-specific skill before adding memory.
            combined = policy['conditioning'] + ('\n\n' + conditioning if conditioning else '')
            result = r41.episode(base, row, 'M-S41', data, protocol, runtime, out, cap, bound, combined)
            result['selected_skill_ids'] = copy.deepcopy(policy['selected_skill_ids'])
        elif kind == 'M':
            result = base.episode(row, 'M', data, protocol, runtime, out, cap, bound, conditioning=conditioning)
            if dataset == 'slake':
                gate = completion.decision(row, dict(result, reused_historical_M=True), result)
            else:
                gate = r42.decision(row, result)
            result['completion_gate'] = gate
            if gate in ('complete_once', 'continue_once'):
                if dataset == 'slake':
                    continuation_prompt, parser = completion.prompt, completion.accepted_reply
                else:
                    continuation_prompt, parser = lambda value: r42.RESTATE, lambda value, raw: r42.parse_restatement(raw)
                ordinal = result['main_calls'] + 1
                if ordinal > 4 or cap.last is None:
                    raise ValueError('original_completion_prefix_budget_exceeded')
                messages = cap.last + [{'role': 'assistant', 'content': cap.raw},
                                       {'role': 'user', 'content': continuation_prompt(row)}]
                raw = cap.call(row, 'M', ordinal, messages)
                result['main_calls'] = ordinal
                try:
                    result.update(parser(row, raw))
                    result['completion_outcome'] = 'accepted'
                except (ValueError, TypeError, IndexError):
                    result['completion_outcome'] = 'invalid_retained'
        else:
            raise ValueError('invalid_frozen_policy')
        main_cap, tool_cap = POLICY_LIMITS[kind]
        if (type(result.get('main_calls')) is not int or not 1 <= result['main_calls'] <= main_cap
                or type(result.get('tool_calls')) is not int or not 0 <= result['tool_calls'] <= tool_cap):
            raise ValueError('policy_budget_exceeded')
        for observation in result.get('observations', []):
            failure = tool_failure_reason(observation)
            if failure:
                raise RuntimeError('tool_unhealthy_stop:' + failure)
        result.update(terminal_raw=cap.raw, policy_kind=kind)
        return result
    finally:
        base.agent_system = saved_system


def reuse_baseline(frozen, qid, saved_at):
    return dict(copy.deepcopy(frozen['baseline'][qid]), question_id=qid, dataset=frozen['dataset'],
                arm=frozen['arm'], baseline_arm=frozen['baseline_arm'], reused_baseline=True,
                policy_kind=frozen['policy'][qid]['kind'], main_calls=0, tool_calls=0,
                new_main_calls=0, new_tool_calls=0, prediction_saved_at=saved_at)


def generate(frozen, out, base, r41, r42, completion, paid, tools, protocol, runtime, load_reference):
    validate_frozen(frozen)
    validate_protocol(protocol)
    out, arm = Path(out), frozen['arm']
    validate_resume_prefix(out, frozen['order'], arm)
    assert_closed_sends(out, arm)
    rowmap = {row['question_id']: row for row in frozen['inputs']}
    memories = {}
    for ordinal, item in enumerate(frozen['order'], 1):
        qid, image = item['question_id'], item['image_key']
        row, entries = rowmap[qid], memories.setdefault((item['dataset'], image), [])
        conditioning, used = context(entries, item, ordinal, frozen['memory_max_chars'], frozen['memory_max_entries'])
        trace_path = out / 'memory_context' / (qid + '.json')
        created_at = read(trace_path)['created_at'] if trace_path.exists() else now()
        trace = {'dataset': frozen['dataset'], 'arm': arm, 'question_id': qid, 'image_key': image,
                 'ordinal': ordinal, 'previous_ids': item['previous_ids'], 'included_ids': used,
                 'memory': conditioning, 'current_reference_available': False, 'created_at': created_at}
        save_once(trace_path, trace)
        destination = out / 'predictions' / arm / (qid + '.json')
        if destination.exists():
            result = read(destination)
            if (result.get('question_id') != qid or result.get('arm') != arm
                    or result.get('dataset') != frozen['dataset']):
                raise ValueError('saved_prediction_identity_changed')
            if not item['previous_ids'] and result != reuse_baseline(frozen, qid, result['prediction_saved_at']):
                raise ValueError('original_whole_arm_baseline_reuse_changed')
            if item['previous_ids'] and result.get('reused_baseline') is not False:
                raise ValueError('repeat_question_must_be_fresh')
        elif not item['previous_ids']:
            result = reuse_baseline(frozen, qid, now())
            save_once(destination, result)
        else:
            base.write(out / 'progress.json', {'status': 'running', 'dataset': frozen['dataset'],
                       'index': ordinal, 'total': len(frozen['inputs']), 'question_id': qid,
                       'policy': frozen['policy'][qid]['kind'], 'included_ids': used, 'utc': base.now()})
            tick = time.monotonic()
            try:
                result = run_episode(base, r41, r42, completion, row, frozen['policy'][qid],
                                     frozen['dataset'], arm, Path(frozen['data']), protocol, runtime,
                                     out, paid, tools, conditioning)
                assert_closed_sends(out, arm)
            except Exception as exc:
                base.write(out / 'progress.json', {'status': 'stopped', 'dataset': frozen['dataset'],
                           'index': ordinal, 'question_id': qid,
                           'error': base.safe_error(exc, getattr(paid, 'key', '')),
                           'error_type': type(exc).__name__, 'utc': base.now()})
                raise RuntimeError('image_memory_gt_generation_stopped:' + type(exc).__name__) from None
            result.update(question_id=qid, dataset=frozen['dataset'], arm=arm,
                          baseline_arm=frozen['baseline_arm'], reused_baseline=False,
                          new_main_calls=result['main_calls'], new_tool_calls=result['tool_calls'],
                          elapsed_s=time.monotonic() - tick, utc=base.now(), prediction_saved_at=now())
            save_once(destination, result)
        # The callback cannot run until both immutable artifacts exist.
        event = feedback_after_save(out, arm, item, ordinal, frozen['reference_files'], load_reference)
        entries.append(memory_entry(row, result, event))
    return memories


def audit_complete(frozen, out):
    validate_frozen(frozen)
    out, arm = Path(out), frozen['arm']
    ids = set(row['question_id'] for row in frozen['inputs'])
    for directory in (out / 'predictions' / arm, out / 'prediction_events', out / 'feedback_events', out / 'memory_context'):
        if {path.stem for path in directory.glob('*.json')} != ids:
            raise ValueError('incomplete_artifact_membership:' + directory.name)
    assert_closed_sends(out, arm)
    sends = list((out / 'calls' / arm).glob('*/*/started.json'))
    selections = list((out / 'tool_selections' / arm).glob('*/*.json'))
    for selection in selections:
        if tool_failure_reason(read(selection)):
            raise ValueError('unhealthy_tool_selection')
    if len(sends) > frozen['new_main_ceiling'] or len(selections) > frozen['new_tool_ceiling']:
        raise ValueError('cohort_budget_exceeded')
    # Reconstruct the model-facing prefix from committed semantic records only.
    memories, total_main, total_tools = {}, 0, 0
    for ordinal, item in enumerate(frozen['order'], 1):
        qid = item['question_id']
        result = read(out / 'predictions' / arm / (qid + '.json'))
        if not item['previous_ids'] and result != reuse_baseline(frozen, qid, result['prediction_saved_at']):
            raise ValueError('original_whole_arm_baseline_reuse_changed')
        if item['previous_ids']:
            main_cap, tool_cap = POLICY_LIMITS[frozen['policy'][qid]['kind']]
            if (result.get('reused_baseline') is not False or result.get('policy_kind') != frozen['policy'][qid]['kind']
                    or not 1 <= result.get('main_calls', 0) <= main_cap
                    or not 0 <= result.get('tool_calls', -1) <= tool_cap):
                raise ValueError('saved_fresh_prediction_policy_changed')
        total_main += result['new_main_calls']
        total_tools += result['new_tool_calls']
        entries = memories.setdefault((item['dataset'], item['image_key']), [])
        prompt, used = context(entries, item, ordinal, frozen['memory_max_chars'], frozen['memory_max_entries'])
        trace = read(out / 'memory_context' / (qid + '.json'))
        if (trace.get('memory') != prompt or trace.get('included_ids') != used
                or trace.get('current_reference_available') is not False or trace.get('dataset') != frozen['dataset']):
            raise ValueError('saved_context_semantic_binding_changed')
        event = feedback_after_save(out, arm, item, ordinal, frozen['reference_files'],
                                    lambda *args: (_ for _ in ()).throw(ValueError('committed_feedback_required')))
        row = next(row for row in frozen['inputs'] if row['question_id'] == qid)
        entries.append(memory_entry(row, result, event))
    if total_main != len(sends) or total_tools != len(selections):
        raise ValueError('prediction_receipt_accounting_mismatch')
    return dict(summary(frozen), status='generation_complete', feedback_events=len(ids),
                prediction_events=len(ids), references_read=True,
                reference_access='own_single_file_only_after_prediction_and_event_saved',
                current_or_future_reference_in_current_request=False,
                new_main_sends=len(sends), new_logical_tool_calls=len(selections))


def execution_protocol(frozen):
    protocol = copy.deepcopy(frozen['protocol'])
    protocol.update(experiment_id='image_memory_gt_r48_' + frozen['dataset'] + '_20261108',
                    # Native inline archives avoid content-addressed image binding.
                    request_archive='inline_original_images_semantic_restart_r48',
                    main_call_limits={'M': 4, 'M-S41': 6, frozen['arm']: 6 if frozen['dataset'] == 'slake' else 4},
                    tool_call_limits={'M': 2, 'M-S41': 4, frozen['arm']: 4 if frozen['dataset'] == 'slake' else 2},
                    budget={'existing_shared_ledger': False, 'enforce_money_cap': False})
    return protocol


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
        raise ValueError('input_semantic_records_changed')
    if not args.execute:
        print(json.dumps(dict(summary(frozen), paid_calls=0, reference_files_read=0)))
        return
    import run_cxr_vqa_toolsets as base
    import run_cxr_action_r41 as r41
    import cxr_answer_domain_r42 as r42
    import cxr_task_completion_r43 as completion
    if not args.api_key_stdin:
        raise ValueError('stdin_key_required')
    key = sys.stdin.readline().strip()
    if not key:
        raise ValueError('missing_key')
    protocol, runtime = execution_protocol(frozen), copy.deepcopy(frozen['runtime'])
    arms = runtime['arms']
    if not arms.get('M', {}).get('ready'):
        raise ValueError('original_M_tools_not_ready')
    if frozen['dataset'] == 'slake' and not arms.get('M-S41', {}).get('ready'):
        raise ValueError('original_S41_tools_not_ready')
    # Transport artifacts have a distinct arm; tool catalog dispatch retains M/S41.
    runtime['arms'][frozen['arm']] = copy.deepcopy(arms['M'])
    reference_dir = args.reference_dir or Path(frozen['reference_dir'])
    args.out.mkdir(parents=True, exist_ok=True)
    with base.exclusive_lock(args.out / '.generation.lock'):
        marker = {'frozen_path': str(args.frozen.resolve()), 'dataset': frozen['dataset'], 'arm': frozen['arm'],
                  'order': frozen['order'], 'inputs': frozen['inputs'], 'policy': frozen['policy'],
                  'baseline': frozen['baseline'], 'protocol': protocol, 'runtime': runtime,
                  'reference_dir': str(reference_dir.resolve())}
        if not (args.out / 'run.json').exists() and any(path.name != '.generation.lock' for path in args.out.iterdir()):
            raise ValueError('fresh_output_required')
        save_once(args.out / 'run.json', marker)
        paid = base.PaidCalls(frozen['config'], protocol, args.out, key)
        tools = base.Tools(runtime, data, args.out)
        vault = ReferenceVault(reference_dir, frozen['dataset'], frozen['arm'], frozen['reference_files'])
        generate(frozen, args.out, base, r41, r42, completion, paid, tools, protocol, runtime, vault.after_prediction)
        receipt = audit_complete(frozen, args.out)
        completion_path = args.out / ('complete_' + frozen['arm'] + '.json')
        if not completion_path.exists():
            save_once(completion_path, dict(receipt, utc=base.now()))
        base.write(args.out / 'progress.json', {'status': 'complete', 'dataset': frozen['dataset'],
                   'questions': len(frozen['inputs']), 'utc': base.now()})
        print(json.dumps(receipt))


if __name__ == '__main__':
    main()
