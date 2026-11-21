"""Summarize a completed OpenI60 F pair without editing the scored work directory."""

import argparse
from collections import Counter
import csv
from decimal import Decimal
import json
from pathlib import Path


ARMS = ('B0', 'L1')
SLOT = 'R49-AGENT'
TOKEN_FIELDS = ('prompt_tokens', 'completion_tokens', 'total_tokens')


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def save_json(path, value):
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False)
        stream.write('\n')


class Accounting:
    def __init__(self):
        self.calls = 0
        self.tokens = Counter()
        self.missing_usage = 0
        self.known_cost = Decimal(0)
        self.missing_cost = 0

    def add(self, receipt):
        self.calls += 1
        usage = receipt.get('usage') or {}
        if not all(type(usage.get(field)) is int for field in TOKEN_FIELDS):
            self.missing_usage += 1
        for field in TOKEN_FIELDS:
            if type(usage.get(field)) is int:
                self.tokens[field] += usage[field]
        cost = (receipt.get('settlement') or {}).get('charged_cny')
        if cost is None:
            self.missing_cost += 1
        else:
            self.known_cost += Decimal(str(cost))

    def report(self):
        return {'calls': self.calls, 'known_tokens': dict(self.tokens),
                'calls_missing_usage_fields': self.missing_usage,
                'known_reported_charged_cny': str(self.known_cost),
                'calls_missing_cost': self.missing_cost}


def arm_paths(work, arm, native_arm, qid):
    run = work / arm
    return {
        'steps': run / 'steps' / f'{qid}.json',
        'prediction': run / 'predictions' / native_arm / f'{qid}.json',
        'protocol_events': run / 'services' / 'protocol_events' / qid,
        'main_call_archive': run / 'services' / 'calls' / SLOT / qid,
        'tool_selections': run / 'services' / 'tool_selections' / SLOT / qid,
        'tool_failures': run / 'failure_observations' / qid,
        'feedback': run / 'feedback' / f'{qid}.json',
        'memory_call_archive': run / 'external_memory' / 'model_calls' / qid,
    }


def summarize_arm(work, arm, native_arm, qids):
    run = work / arm
    score = read_json(run / 'analysis' / 'summary.json')
    statuses, error_stages, error_types, error_codes = (Counter() for _ in range(4))
    selections, dispatches, failures = (Counter() for _ in range(3))
    main, repair, memory = Accounting(), Accounting(), Accounting()
    counts = Counter()
    protocol_failure_qids = []
    dispatch_gaps = []
    for qid in qids:
        paths = arm_paths(work, arm, native_arm, qid)
        prediction = read_json(paths['prediction'])
        statuses[prediction['status']] += 1
        if prediction['status'] == 'protocol_failure':
            protocol_failure_qids.append(qid)
        if prediction['protocol']['version'] != 'F':
            raise ValueError(f'{arm}/{qid} has no F prediction')
        steps = read_json(paths['steps'])
        if len(steps) != prediction['main_calls']:
            raise ValueError(f'{arm}/{qid} step count differs from prediction')
        accepted_calls = 0
        for ordinal, step in enumerate(steps, 1):
            event = read_json(paths['protocol_events'] / f'{ordinal}.json')
            if event != step['protocol'] or step['step_index'] != ordinal - 1:
                raise ValueError(f'{arm}/{qid}/{ordinal} step and protocol event differ')
            main.add(event)
            if event['repair_attempt']:
                repair.add(event)
            if event['accepted']:
                kind = event['kind']
                counts[f'accepted_{kind}_replies'] += 1
                if event['repair_attempt']:
                    counts[f'repairs_accepted_as_{kind}'] += 1
                if kind == 'calls':
                    for action in json.loads(step['response'])['calls']:
                        selections[action['tool']] += 1
                        accepted_calls += 1
            else:
                counts['rejected_replies'] += 1
                stage = event['error_stage']
                error_stages[stage] += 1
                error_types[f'{stage}/{event["error_type"]}'] += 1
                error_codes[f'{stage}/{event["error"]}'] += 1

        receipts = [read_json(path) for path in paths['tool_selections'].glob('*.json')]
        observations = prediction['observations']
        dispatched = len(receipts)
        if dispatched != prediction['tool_calls'] or dispatched != len(observations):
            raise ValueError(f'{arm}/{qid} selection receipts and observations differ')
        if dispatched != accepted_calls:
            dispatch_gaps.append({'question_id': qid, 'accepted_call_items': accepted_calls,
                                  'dispatched': dispatched, 'terminal_status': prediction['status']})
        for item in receipts:
            dispatches[item['tool']] += 1
            counts['cache_hits'] += bool(item.get('cache_hit'))
        for observation in observations:
            failure = observation.get('failure_observation')
            if failure:
                failures[observation['tool']] += 1

    if (len(qids), main.calls, sum(dispatches.values()), sum(failures.values())) != tuple(
            score[key] for key in ('questions', 'main_calls', 'tool_calls', 'failed_tool_calls')):
        raise ValueError(f'{arm} protocol counts differ from the native score summary')
    memory_root = run / 'external_memory' / 'model_calls'
    for path in memory_root.glob('*/*/*/result.json'):
        memory.add(read_json(path))
    disconnected = []
    for path in sorted((work / 'jobs' / arm).glob('attempt-*/unknown_provider_outcome/*/*/result.json')):
        receipt = read_json(path)
        disconnected.append({'path': path.relative_to(work).as_posix(),
                             'request_id': receipt.get('request_id'), 'received': receipt.get('response_received'),
                             'error': receipt.get('error'), 'billing': 'unknown'})
    return {
        'native_score': score,
        'additional_unanswered_provider_attempts': disconnected,
        'terminal_statuses': dict(statuses),
        'protocol_failure_question_ids': protocol_failure_qids,
        'main_model': main.report(),
        'repair_overhead': repair.report(),
        'memory_model_receipts': memory.report(),
        'memory_model_calls_native': read_json(run / 'memory.completed.json')['memory_model_calls'],
        'protocol_outcomes': {key: counts[key] for key in (
            'accepted_answer_replies', 'accepted_calls_replies', 'rejected_replies',
            'repairs_accepted_as_answer', 'repairs_accepted_as_calls')},
        'errors_by_stage': dict(error_stages),
        'errors_by_stage_and_exception': dict(error_types),
        'errors_by_stage_and_message': dict(error_codes),
        'tool_dispatch': {'accepted_items_by_tool': dict(selections),
                          'dispatched_by_tool': dict(dispatches), 'failed_by_tool': dict(failures),
                          'cache_hits': counts['cache_hits'], 'per_question_dispatch_gaps': dispatch_gaps},
    }


def collect(work, output):
    work, output = work.resolve(), output.resolve()
    if output.is_relative_to(work):
        raise ValueError('Write report files to a separate output directory')
    paired_dir = work / 'paired_analysis'
    paired = read_json(paired_dir / 'summary.json')
    with (paired_dir / 'paired_results.csv').open(encoding='utf-8-sig', newline='') as stream:
        pairs = list(csv.DictReader(stream))
    qids = [row['question_id'] for row in pairs]
    if len(qids) != paired['n'] or len(set(qids)) != len(qids):
        raise ValueError('Paired CSV denominator or question IDs differ from native summary')
    names = {arm: read_json(work / arm / 'manifest.json')['arm'] for arm in ARMS}
    arms = {arm: summarize_arm(work, arm, names[arm], qids) for arm in ARMS}
    changes = {'gain': [], 'harm': []}
    for row in pairs:
        category = row['category']
        if category not in changes:
            continue
        qid = row['question_id']
        trajectory = {'question_id': qid, 'pair': row, 'arms': {}}
        for arm in ARMS:
            paths = arm_paths(work, arm, names[arm], qid)
            trajectory['arms'][arm] = {key: path.relative_to(work).as_posix()
                                       for key, path in paths.items() if path.exists()}
        changes[category].append(trajectory)
    if (len(changes['gain']), len(changes['harm'])) != (paired['gains_G'], paired['harms_H']):
        raise ValueError('Gain/harm counts differ from the native paired report')
    output.mkdir(parents=True, exist_ok=True)
    summary = {'work': str(work), 'paired_summary': paired, 'arms': arms,
               'accounting_note': 'Per-request recorded CNY is a usage proxy. Missing settlement is unpriced usage.'}
    save_json(output / 'protocol_cost_summary.json', summary)
    save_json(output / 'gain_harm_trajectories.json', {'paths_relative_to': str(work), **changes})
    print(json.dumps({
        'n': paired['n'], 'B0_correct': paired['B0_correct'], 'L1_correct': paired['L1_correct'],
        'gains': paired['gains_G'], 'harms': paired['harms_H'],
        'arms': {arm: {'repair_calls': arms[arm]['repair_overhead']['calls'],
                       'protocol_failures': len(arms[arm]['protocol_failure_question_ids']),
                       'tool_calls': arms[arm]['native_score']['tool_calls']} for arm in ARMS},
        'outputs': str(output)}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    collect(args.work, args.out)
