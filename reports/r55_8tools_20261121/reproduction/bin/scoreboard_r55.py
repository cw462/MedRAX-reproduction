"""Read and render the native R55 experiment scoreboard on AutoDL."""

import argparse
from collections import Counter
import json
from pathlib import Path
import sys
import time


ROOT = Path('/root/autodl-tmp/medrax_r55_top4_full848/r55_8tools_20261121_001')
sys.path.insert(0, str(ROOT / 'bin'))
import queue_r55 as queue
import r55_deepseek_rerun_runtime as runtime


DATASETS = {'slake': 114, 'chexbench': 618, 'vqarad': 116}
MODELS = {
    'flash': ('qwen3.6-flash', 'Qwen3.6-Flash', ('CRITIC', 'Reflexion', 'M2')),
    'plus': ('qwen3.7-plus', 'Qwen3.7-Plus', ('CRITIC', 'Reflexion', 'M2')),
    'deepseek': ('deepseek-flash', 'DeepSeek V4.1 Flash', ('ReAct', 'CRITIC', 'Reflexion', 'M2', 'M5')),
}
ARMS = [(model, method) for model, (_, _, methods) in MODELS.items() for method in methods]
SCOPE = {(*arm, dataset) for arm in ARMS for dataset in DATASETS}


def checked_plan():
    plan = runtime.read(queue.PLAN)
    cohorts = list(map(tuple, plan['cohorts']))
    models = {key: model[0] for key, model in MODELS.items()}
    if (plan['models'] != models or plan['datasets'] != DATASETS
            or len(cohorts) != len(SCOPE) or set(cohorts) != SCOPE):
        raise ValueError('The live plan does not match the 11 groups across three frozen datasets')
    return plan, cohorts


def public_error(value):
    if not value:
        return None
    error = str(value)
    if any(term in error.lower() for term in ('sk-', 'bearer', 'authorization', 'api_key', 'base64', '://')):
        return 'See the native cohort log for error details'
    return error[:200]


def cohort_state(item, supervisor_live):
    model, method, dataset = item
    job = queue.job_path(item)
    complete = runtime.read(job / 'complete.json')
    failed = runtime.read(job / 'failed.json')
    run = runtime.read(job / 'run.started.json')
    scorer = runtime.read(job / 'score.started.json')
    if complete:
        state = 'scored'
        saved = complete.get('questions')
    else:
        if failed:
            state = 'failed'
        elif queue.live(scorer):
            state = 'scoring'
        elif queue.live(run):
            state = 'running'
        elif run or scorer:
            state = 'finishing' if supervisor_live else 'interrupted'
        else:
            state = 'queued'
        predictions = queue.output_path(item) / 'predictions'
        saved = 0 if state == 'queued' else sum(1 for _ in predictions.rglob('*.json'))
    child = scorer if state == 'scoring' else run
    return dict(model=model, method=method, dataset=dataset, state=state,
                saved=saved, expected=DATASETS[dataset], pid=child.get('pid'),
                error=public_error(failed.get('error')), phase=failed.get('phase'),
                scored_epoch=complete.get('epoch'))


def tally(correct, questions):
    return dict(correct=correct, questions=questions, accuracy_pct=round(100 * correct / questions, 2))


def official_score(item):
    _, method, dataset = item
    output = queue.output_path(item)
    memory = method in queue.MEMORY
    receipt = runtime.read(queue.job_path(item) / 'complete.json')
    summary = runtime.read(output / ('analysis/summary.json' if memory else 'summary.json'))
    expected = DATASETS[dataset]
    arm = f'R55-{method}' if memory else method.lower()
    correct = summary.get('correct')
    if ((summary.get('arm'), summary.get('dataset'), summary.get('questions')) != (arm, dataset, expected)
            or type(correct) is not int or not 0 <= correct <= expected
            or (receipt.get('correct'), receipt.get('questions')) != (correct, expected)):
        raise ValueError(f'Native scoring receipts disagree for {"/".join(item)}')
    if sum(1 for _ in (output / 'predictions').rglob('*.json')) != expected:
        raise ValueError(f'Prediction denominator disagrees for {"/".join(item)}')
    return tally(correct, expected)


def score_rows(datasets, arms=ARMS):
    rows = []
    for model, method in arms:
        scores = {dataset: official_score((model, method, dataset)) for dataset in datasets}
        row = dict(model=model, model_label=MODELS[model][1], method=method, scores=scores)
        if len(scores) == len(DATASETS):
            row['total'] = tally(sum(score['correct'] for score in scores.values()),
                                 sum(score['questions'] for score in scores.values()))
        rows.append(row)
    return rows


def watcher(name):
    raw = runtime.read(queue.JOBS / name)
    if not raw:
        return None
    keys = ('phase', 'state', 'epoch', 'updated_epoch', 'controller_pid', 'run_pid', 'score_pid',
            'pid', 'target', 'supervisor_cap', 'repair_pid', 'updated_at', 'heartbeat_epoch',
            'native_cap', 'active', 'waiting')
    receipt = {key: raw[key] for key in keys if key in raw}
    pid = raw.get('controller_pid') or raw.get('pid')
    if type(pid) is int and pid > 0:
        receipt['live'] = bool(runtime.native(pid))
    if raw.get('error'):
        receipt['error'] = public_error(raw['error'])
    return receipt


def collect(mode):
    plan, cohorts = checked_plan()
    supervisor = runtime.read(queue.JOBS / 'supervisor.started.json')
    live = queue.live(supervisor)
    states = [cohort_state(item, live) for item in cohorts]
    by_dataset = {
        dataset: dict(Counter(row['state'] for row in states if row['dataset'] == dataset))
        for dataset in DATASETS
    }
    counts = dict(Counter(row['state'] for row in states))
    repair = watcher('repair-m5-slot.json')
    observer = watcher('timeout-watch.json')
    cap = plan['max_active_cohorts']
    reserved = bool(cap == 2 and repair and repair.get('live')
                    and repair.get('phase') in ('waiting_for_slot', 'running', 'scoring'))
    if observer and observer.get('live') and observer.get('phase') in ('waiting', 'running'):
        reserved = min(2, len(observer.get('active', [])) + len(observer.get('waiting', [])))
    hold = runtime.read(queue.JOBS / 'gpu-hold.json')
    gpu = runtime.read(queue.JOBS / 'gpu.json')
    status = dict(root=str(ROOT), observed_epoch=time.time(), supervisor=supervisor, live=live,
                  cohorts=states, counts=counts, by_dataset=by_dataset, repair=repair, observer=observer,
                  slots=dict(scheduler=cap, effective=min(3, cap + reserved),
                             active=counts.get('running', 0) + counts.get('scoring', 0)),
                  gpu_hold={key: hold[key] for key in ('mode', 'epoch') if key in hold},
                  gpu={key: gpu[key] for key in ('epoch', 'free_mib', 'healthy') if key in gpu},
                  slake_ready=by_dataset['slake'].get('scored', 0) == len(ARMS),
                  all_ready=counts.get('scored', 0) == len(SCOPE), slake_scores=None, all_scores=None)
    if mode in ('auto', 'all') and status['all_ready']:
        status['all_scores'] = score_rows(DATASETS)
    if mode in ('auto', 'slake') and status['slake_ready']:
        matrix = status['all_scores']
        status['slake_scores'] = (
            [dict(model=row['model'], model_label=row['model_label'], method=row['method'],
                  scores={'slake': row['scores']['slake']}) for row in matrix]
            if matrix is not None else score_rows(('slake',))
        )
    if mode == 'vqarad' and by_dataset['vqarad'].get('scored', 0) == len(ARMS):
        status['vqarad_scores'] = score_rows(('vqarad',))
    if mode == 'chexbench':
        completed = {(row['model'], row['method']) for row in states
                     if row['dataset'] == mode and row['state'] == 'scored'}
        status['chexbench_scores'] = score_rows((mode,), [arm for arm in ARMS if arm in completed])
    return status


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scores', choices=('auto', 'none', 'slake', 'vqarad', 'chexbench', 'all'), default='auto')
    args = parser.parse_args()
    print(json.dumps(collect(args.scores), ensure_ascii=False, separators=(',', ':')))
