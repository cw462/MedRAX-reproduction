"""Run or validate one frozen R55 cohort with its original memory provider."""

import argparse
from contextlib import ExitStack, contextmanager
import json
import os
from pathlib import Path
from shutil import disk_usage
import subprocess
import sys
import time

import r55_memevolve_driver003 as bridge
from run_r55_full848_dataset import ARMS, COUNTS


PROVIDERS = {'M9': 'generative', 'M2': 'expel', 'M3': 'memp', 'M7': 'mobilee'}
ARM_LABELS = {name: 'R55-'+name for name in PROVIDERS}
bridge.PROVIDERS.update(PROVIDERS)
ARMS.update(ARM_LABELS)


class BeforeFirstAnswer(Exception):
    """End a validation at the real service boundary."""


@contextmanager
def shared_gpu_slot(root):
    """Allow two simultaneous heavyweight tool workers across the four arms."""
    from run_cxr_vqa_toolsets import exclusive_lock

    with ExitStack() as stack:
        while True:
            for n in range(2):
                try:
                    stack.enter_context(exclusive_lock(root/'jobs'/f'gpu-worker.{n}.lock'))
                    break
                except BlockingIOError:
                    pass
            else:
                time.sleep(0.25)
                continue
            break
        yield


def run_dataset(root, arm, dataset, verify=False):
    code = root/'code/experiments'
    sys.path.insert(0, str(code))
    import run_online_skill_r54 as engine
    from cxr_online_primitives_r49 import rows
    from online_memory_r49 import ReferenceVault, read, save_once
    from r55_continue60_policy import bound_candidate
    from skill_services_r55 import Services, Tools

    work = root/('verification' if verify else 'generation')/arm/dataset
    work.mkdir(mode=0o700, parents=True, exist_ok=not verify)
    data = root/'data'/dataset
    runtime = root/'runtime'/('five' if arm in ('M2', 'M3') else 'expansion')
    manifest = read(root/'manifests'/arm/(dataset+'.json'))
    inputs, order = manifest['inputs'], manifest['order']
    ids = [row['question_id'] for row in inputs]
    assert len(ids) == len(set(ids)) == COUNTS[dataset]
    assert rows(data/'inputs.jsonl') == inputs and [row['question_id'] for row in order] == ids
    assert set(manifest['reference_files']) == set(ids)
    assert manifest['arm'] == ARM_LABELS[arm] and manifest['memory_provider'] == PROVIDERS[arm]
    assert manifest['memory_source'] == bridge.SOURCE and manifest['skill_enabled'] is False
    tools = manifest['runtime']['arms']['M']['tools']
    assert len(tools) == len(set(tools)) == 11 and set(tools) == set(manifest['runtime']['tools'])
    assert os.environ['R55_MEMEVOLVE_GPU'] == os.environ['CUDA_VISIBLE_DEVICES'] == '0'
    save_once(work/'manifest.json', manifest)
    engine.ARM = ARM_LABELS[arm]

    fixture = None
    if verify:
        from reference_model_fixture import completion_for, message_text

        for row in inputs:
            rendered = bridge.question(row)
            if row.get('options'):
                assert dataset == 'chexbench' and rendered.startswith(row['question']+'\nOptions: ')
                for letter, text in row['options'].items():
                    assert bound_candidate(row, letter+'. placeholder') == bridge.reference_text(row, letter) == letter+'. '+text
            else:
                assert dataset != 'chexbench' and rendered == row['question']
                candidate = 'a short free-text candidate'
                assert bound_candidate(row, candidate) == bridge.reference_text(row, candidate) == candidate

        fixture_routes = []

        def fixture(messages):
            route, response = completion_for(message_text(messages))
            assert route != 'unmapped'
            fixture_routes.append(route)
            return response

        class FirstAnswer(Services):
            def call(self, row, role, ordinal, messages):
                assert row == inputs[0] and role == 'R49-AGENT' and ordinal == 1
                assert len(messages) >= 3
                raise BeforeFirstAnswer

        class ClosedVault:
            def after_prediction(self, *_):
                raise AssertionError('validation attempted to access a reference answer')

        main_key = 'offline-validation'
        memory_key = ''
        service_class = FirstAnswer
        vault = ClosedVault()
    else:
        main_key, memory_key = [sys.stdin.readline().strip() for _ in range(2)]
        assert main_key and memory_key
        service_class = Services
        vault = ReferenceVault(root/'refs'/dataset, manifest['reference_files'])

    class GuardedTools(Tools):
        def observe(self, name, spec, args, image, identity, folder, saved):
            if saved.is_file() or name in ('roi_crop', 'medret', 'reflect', 'verify'):
                return super().observe(name, spec, args, image, identity, folder, saved)
            ready = root/'jobs'/'priority-tool-ready'/(name+'.json')
            if not ready.is_file():
                print(json.dumps({'event': 'waiting_for_backend', 'tool': name}), flush=True)
                while not ready.is_file():
                    time.sleep(5)
            with shared_gpu_slot(root):
                return super().observe(name, spec, args, image, identity, folder, saved)

    class DiskGuardedMemory(bridge.Memory):
        def retrieve(self, row):
            if disk_usage(work).free < 256 * 1024**2:
                raise RuntimeError('r55_top4_disk_below_256_mib_before_question')
            return super().retrieve(row)

    service = service_class(manifest['config'], manifest['protocol'], manifest['runtime'],
                            work/'services', main_key, manifest['embedding_model'], manifest['embedding_base_url'])
    service.tools = GuardedTools(manifest['runtime'], data, work/'services', service.call, service.verifier)
    bridge.load_runtime(runtime, work)
    memory = DiskGuardedMemory(arm, runtime, work/'external_memory', memory_key, fixture)
    try:
        engine.run_stream(inputs, order, data, work, service, vault, tools,
                          evolver=engine.disabled_evolve, external_memory=memory)
    except BeforeFirstAnswer:
        assert verify and memory.model.calls == 0
        assert not any((work/name).exists() for name in ('predictions','feedback'))
        assert not list((work/'services').rglob('started.json'))
        result = {'arm': arm, 'dataset': dataset, 'bound_questions': len(ids), 'provider': PROVIDERS[arm],
                  'first_answer_boundary': ids[0], 'new_external_model_requests': 0,
                  'fixture_routes': fixture_routes}
        save_once(work/'verified.json', result)
        return result
    assert not verify
    complete = read(work/'complete.json')
    assert complete['arm'] == ARM_LABELS[arm] and complete['questions'] == len(ids)
    for receipt in ('retrieval.json','ingest.json'):
        assert {path.parent.name for path in (work/'external_memory/episodes').glob('*/'+receipt)} == set(ids)
    result = {'arm': arm, 'dataset': dataset, 'questions': len(ids),
              'memory_model_calls': memory.model.calls, 'provider': PROVIDERS[arm]}
    save_once(work/'memory.completed.json', result)
    return result


def run_arm(root, arm):
    sys.path.insert(0, str(root/'code/experiments'))
    from online_memory_r49 import read, save_once

    job = root/'jobs'/arm
    keys = sys.stdin.buffer.read().splitlines()
    assert len(keys) == 2 and all(keys)
    scores = {}
    for dataset, count in COUNTS.items():
        output = root/'generation'/arm/dataset
        earlier = root/'jobs/priority-independent/vqarad'/arm
        if dataset == 'vqarad' and (earlier/'terminal.json').is_file():
            status = read(earlier/'terminal.json')['exit_code']
            if status:
                return status
            summary = read(output/'analysis/summary.json')
            assert summary['questions'] == count and summary['arm'] == ARM_LABELS[arm]
            scores[dataset] = summary
            continue
        stage = job/dataset
        stage.mkdir()
        tick = time.monotonic()
        command = [sys.executable, '-B', '-u', __file__, 'dataset', str(root), arm, '--dataset', dataset]
        with (stage/'runner.stdout.log').open('xb') as stdout, (stage/'runner.stderr.log').open('xb') as stderr:
            runner = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=stdout, stderr=stderr)
            (stage/'runner.pid').write_text(str(runner.pid)+'\n')
            runner.communicate(b'\n'.join(keys)+b'\n')
        (stage/'runner.exitcode').write_text(str(runner.returncode)+'\n')
        if output.is_dir():
            (output/'generation.exitcode').write_text(str(runner.returncode)+'\n')
        save_once(stage/'runtime.json', {'generation_wall_seconds': time.monotonic()-tick})
        if runner.returncode:
            return runner.returncode
        command[4] = 'score'
        with (stage/'score.stdout.log').open('xb') as stdout, (stage/'score.stderr.log').open('xb') as stderr:
            scorer = subprocess.run(command, stdout=stdout, stderr=stderr, stdin=subprocess.DEVNULL)
        (stage/'score.exitcode').write_text(str(scorer.returncode)+'\n')
        if scorer.returncode:
            return scorer.returncode
        summary = read(output/'analysis/summary.json')
        assert summary['questions'] == count and summary['arm'] == ARM_LABELS[arm]
        scores[dataset] = summary
    save_once(job/'controller.completed.json', {'arm': arm, 'datasets': scores,
              'questions': sum(value['questions'] for value in scores.values()),
              'correct': sum(value['correct'] for value in scores.values())})
    return 0


def score(root, arm, dataset):
    sys.path.insert(0, str(root/'code/experiments'))
    from online_memory_r49 import read, save_once
    from score_r55_full848_dataset import score_dataset

    out = root/'generation'/arm/dataset
    calls = out/'external_memory/model_calls'
    started = {path.parent for path in calls.glob('*/*/*/started.json')}
    closed = {path.parent for path in calls.glob('*/*/*/result.json')}
    assert started == closed and len(closed) == read(out/'memory.completed.json')['memory_model_calls']
    summary = score_dataset(root/'code', out)
    records = [read(p/'result.json') for p in sorted(closed)]
    save_once(out/'analysis/memory_usage.json', {
        'memory_model_calls': len(records), 'received': sum(row['response_received'] is True for row in records),
        'failed': sum(bool(row.get('error')) for row in records),
        'known_total_tokens': sum((row.get('usage') or {}).get('total_tokens') or 0 for row in records),
        'usage_unknown': sum(row.get('usage') is None for row in records),
    })
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=('verify', 'dataset', 'score', 'run'))
    parser.add_argument('root', type=Path)
    parser.add_argument('arm', choices=tuple(PROVIDERS))
    parser.add_argument('--dataset', choices=tuple(COUNTS))
    parser.add_argument('--independent-vqarad', action='store_true')
    args = parser.parse_args()
    if args.phase == 'run':
        path = args.root/'jobs'/args.arm/'controller.exitcode'
        try:
            result = run_arm(args.root, args.arm)
        except BaseException:
            path.write_text('1\n')
            raise
        path.write_text(str(result)+'\n')
        raise SystemExit(result if result >= 0 else 128-result)
    if not args.dataset:
        parser.error('--dataset is required')
    if args.dataset == 'vqarad' and not args.independent_vqarad:
        earlier = args.root/'jobs/priority-independent/vqarad'/args.arm
        if (earlier/'controller.started.json').is_file():
            while not (earlier/'terminal.json').is_file():
                time.sleep(5)
            status = json.loads((earlier/'terminal.json').read_text())['exit_code']
            if status:
                raise SystemExit(status)
            summary = args.root/'generation'/args.arm/'vqarad'/'analysis'/'summary.json'
            print(summary.read_text(), flush=True)
            raise SystemExit(0)
    result = (score(args.root, args.arm, args.dataset) if args.phase == 'score'
              else run_dataset(args.root, args.arm, args.dataset, args.phase == 'verify'))
    print(json.dumps(result, ensure_ascii=False), flush=True)
