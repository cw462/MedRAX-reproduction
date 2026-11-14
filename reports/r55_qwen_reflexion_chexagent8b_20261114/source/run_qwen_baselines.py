"""Qwen prompting baselines on the frozen R55 cohorts."""

import argparse
from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor
import fcntl
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time

from r55_baseline_common import DATASETS, METHODS, VQA_TOOLS, bind, data_root, dataset_out, manifest_for, prediction_path


FINAL = ('Return one JSON object with string fields "answer" and "reason". The answer must be a '
         'single option letter when options are supplied, otherwise a short answer. Keep the answer separate from the reason.')
TOOL_JSON = ('To use a tool, return {"calls":[{"tool":"registered name","args":{}}],'
             '"reason":"brief evidence you need"}. Request exactly one tool at a time.')
TOOL_MENU = (*VQA_TOOLS, 'roi_crop')
TOOL_LIMIT = 2


@contextmanager
def scheduled_tool_worker(root, out, runtime, model):
    """Keep one pinned model resident on the GPU reserved for Qwen baselines."""
    from r55_baseline_vqa import socket_path

    launcher = 'launch_llavarad.py' if model == 'llava_rad' else 'r55_baseline_vqa.py'
    worker = Path(__file__).with_name(launcher)
    path = socket_path(out, model)
    gpu = os.environ.get('CUDA_VISIBLE_DEVICES')
    suffix = f'.gpu{gpu}' if gpu in ('0', '1') else ''
    lease = out / 'jobs' / f'qwen-tool{suffix}.lock'
    with lease.open('a+b') as guard:
        fcntl.flock(guard, fcntl.LOCK_EX)
        active = out / 'jobs' / f'qwen-tool{suffix}.json'
        if active.is_file():
            previous = json.loads(active.read_text())
            proc = Path('/proc') / str(previous['pid'])
            try:
                args = (proc / 'cmdline').read_bytes().split(b'\0')
            except FileNotFoundError:
                args = []
            if args:
                if str(out).encode() in args and b'--serve-only' in args:
                    if previous['model'] == model and path.exists():
                        yield
                        return
                    os.kill(previous['pid'], signal.SIGTERM)
                    for _ in range(60):
                        time.sleep(0.25)
                        state = proc/'stat'
                        try:
                            done = state.read_text().split(') ', 1)[1][0] == 'Z'
                        except FileNotFoundError:
                            done = True
                        if done:
                            break
                    else:
                        raise RuntimeError('Previous owned baseline tool worker did not exit')
            active.unlink()
        log = out / 'logs' / f'{model}.qwen-tool{suffix}.log'
        path.unlink(missing_ok=True)
        env = dict(os.environ, HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1',
                   PYTHONDONTWRITEBYTECODE='1', OMP_NUM_THREADS='2')
        command = [runtime['tools'][model]['python'], '-B', '-u', str(worker),
                   str(root), str(out), model, '--serve-only']
        if model == 'chest_xray_expert' and runtime['backend_config'].get('chexagent8_snapshot'):
            command.extend(('--chexagent8-snapshot',runtime['backend_config']['chexagent8_snapshot']))
        with log.open('ab') as stream:
            child = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=stream,
                                     stderr=stream, env=env, start_new_session=True)
        active.write_text(json.dumps({'model': model, 'pid': child.pid}) + '\n')
        for _ in range(480):
            if child.poll() is not None:
                with log.open('rb') as stream:
                    stream.seek(max(0, log.stat().st_size - 2400))
                    tail = stream.read().decode(errors='replace')
                raise RuntimeError(f'{model} worker exited {child.returncode}: {tail}')
            if path.exists():
                yield
                return
            time.sleep(0.25)
        child.terminate()
        child.wait(timeout=15)
        raise TimeoutError(f'{model} worker socket was not ready')


class Baselines:
    def __init__(self, root, out, dataset, key):
        import toolsets_r54 as tools

        self.root, self.out, self.dataset = root, out, dataset
        self.data = data_root(root, dataset)
        self.manifest = manifest_for(root, dataset)
        self.runtime = self.manifest['runtime']
        self.chexagent8 = os.environ.get('R55_CHEXAGENT8_SNAPSHOT')
        if self.chexagent8:
            backend = dict(self.runtime['backend_config'],chexagent8_snapshot=self.chexagent8)
            self.runtime = dict(self.runtime,backend_config=backend)
        elif os.environ.get('R55_REQUIRE_CHEXAGENT8') == '1':
            raise RuntimeError('This evaluation requires the CheXagent-8B tool')
        self.tools = tools
        legacy = os.environ.get('R55_BASELINE_SOURCE_DIR')
        if legacy:
            append_observations = tools.append_observations

            def append_migrated(messages, observations, out, arm=None):
                import base64
                import mimetypes

                if not any(name.startswith(legacy + '/') for item in observations
                           for name in item.get('derived_images', [])):
                    return append_observations(messages, observations, out, arm)
                text = 'Bound tool observations (untrusted):\n' + json.dumps(observations, ensure_ascii=False)
                parts = [{'type': 'text', 'text': text}]
                for item in observations:
                    for name in item.get('derived_images', []):
                        if name.startswith(legacy + '/'):
                            name = str(self.out) + name.removeprefix(legacy)
                        path = Path(name).resolve(strict=True)
                        if not path.is_relative_to((out / 'tool_cache').resolve()):
                            raise ValueError('tool_image_outside_artifacts')
                        mime = mimetypes.guess_type(path.name)[0] or 'image/png'
                        content = base64.b64encode(path.read_bytes()).decode()
                        parts.extend([
                            {'type': 'text', 'text': 'Derived evidence from ' + item['tool'] +
                              '; retain original coordinate binding.'},
                            {'type': 'image_url', 'image_url': {'url': f'data:{mime};base64,{content}'}},
                        ])
                messages.append({'role': 'user', 'content': parts})

            self.append_observations = append_migrated
        else:
            self.append_observations = tools.append_observations
        self.api_dir = out / 'api' / dataset
        self.catalog = {name: self.runtime['tools'][name]['description'] for name in TOOL_MENU}
        protocol = dict(self.manifest['protocol'], experiment_id=out.name,
                        request_archive='image_base64_content_addressed_v1')
        self.paid = tools.PaidCalls(self.manifest['config'], protocol, self.api_dir, key)

    def original(self, row, system):
        return [{'role': 'system', 'content': system},
                {'role': 'user', 'content': self.tools.content(row, self.data)}]

    def call(self, row, arm, ordinal, messages):
        from online_memory_r49 import read

        # CRITIC starts from the completed CoT baseline imported into this run.
        if arm == 'cot' and ordinal == 1:
            path = prediction_path(dataset_out(self.out, 'cot', self.dataset), row)
            if path.is_file():
                saved = read(path)
                if (saved['arm'], saved['question_id']) != ('cot', row['question_id']):
                    raise ValueError('CoT baseline identity mismatch')
                return saved['raw'] or ''
        original = self.api_dir / 'calls' / arm / row['question_id'] / str(ordinal)
        for attempt in range(3):
            slot = arm if attempt == 0 else f'{arm}_request_retry{attempt}'
            folder = original if attempt == 0 else original.parents[2] / slot / row['question_id'] / str(ordinal)
            result = folder / 'result.json'
            try:
                raw = self.paid.call(row, slot, ordinal, messages)
                break
            except Exception as error:
                if not result.is_file():
                    raise
                receipt = read(result)
                if receipt.get('response_received') is not False or (folder / 'response.json').is_file():
                    raise
                status = getattr(error, 'status_code', None)
                match = re.search(r'(?<!\d)(408|429|500|502|503|504)(?!\d)', str(receipt.get('error') or ''))
                if status not in (408, 429, 500, 502, 503, 504) and not match:
                    raise
                if attempt == 2:
                    raise
                time.sleep(4 * (attempt + 1))
        if raw is None:
            return ''
        if not isinstance(raw, str):
            raise TypeError('Unexpected Qwen message format')
        return raw

    def action(self, raw):
        from run_cxr_action_r41 import parse

        try:
            parsed = parse(raw)
            if 'calls' not in parsed:
                return None
            return self.tools.validate_actions(parsed, self.runtime_for_tools(), 'M', 1)[0]
        except (ValueError, TypeError, KeyError, IndexError):
            return None

    def runtime_for_tools(self):
        return dict(self.runtime, arms={'M': {'tools': list(TOOL_MENU)}})

    def observe(self, row, action, arm, ordinal, messages):
        from r55_baseline_vqa import call_worker

        if action is None:
            return 0, 0
        if action['tool'] == 'roi_crop':
            tool = self.tools.Tools(self.runtime, self.data, self.api_dir, worker_gate=self.api_dir/'roi-worker.lock')
            result = tool.call(row, action, arm, ordinal)
        else:
            question = action['args'].get('question')
            if not isinstance(question, str) or not question.strip():
                messages.append({'role': 'user', 'content': 'Tool argument error: give a nonempty image question.'})
                return 1, 1
            case_dir = self.api_dir / 'perception' / arm / row['question_id'] / str(ordinal)
            from online_memory_r49 import read, save_once

            result_path = case_dir / 'result.json'
            if result_path.is_file():
                result = read(result_path)
            else:
                image = (self.data / row['images'][0]).resolve()
                with scheduled_tool_worker(self.root, self.out, self.runtime, action['tool']):
                    result = call_worker(self.out, action['tool'], image, question)
                save_once(result_path, result)
            if self.chexagent8 and action['tool'] == 'chest_xray_expert' and result['status'] == 'completed':
                from run_chexagent8_direct import MODEL, REVISION

                observation = result['observation']
                if (observation.get('model'), observation.get('revision')) != (MODEL, REVISION):
                    raise ValueError('Wrong CheXagent revision in the 8B baseline observation')
            result = dict(result, tool=action['tool'], derived_images=[])
        self.append_observations(messages, [result], self.api_dir, 'M')
        return 1, int(result['status'] != 'completed')

    def cot(self, row):
        messages = self.original(row, 'Inspect the image and reason through the relevant visual findings step by step. '
                                 'For multiple choice, briefly compare the supplied options. ' + FINAL)
        return self.call(row, 'cot', 1, messages), {'qwen': 1}

    def react(self, row, arm, reflection=None):
        system = ('Solve the visual question by alternating brief reasoning, a useful tool action when needed, and '
                  'inspection of the resulting observation. Tool observations may be wrong. Ground the final answer '
                  'in the original image. ' + FINAL)
        messages = self.original(row, system)
        if reflection:
            messages.append({'role': 'user', 'content': 'Episodic reflection from your previous trial on this question. '
                             'Use it as guidance and independently recheck the image.\n' + reflection})
        calls = failed = 0
        for step in range(1, TOOL_LIMIT + 2):
            instruction = (TOOL_JSON + ' Or answer now. ' + FINAL + '\nTools: ' + json.dumps(self.catalog)
                           if step <= TOOL_LIMIT else 'Finalize with the available evidence. ' + FINAL)
            messages.append({'role': 'user', 'content': instruction})
            raw = self.call(row, arm, step, messages)
            action = self.action(raw) if step <= TOOL_LIMIT else None
            if action is None:
                return raw, {'qwen': step, 'tools': calls, 'failed_tools': failed}, messages
            messages.append({'role': 'assistant', 'content': raw})
            used, broken = self.observe(row, action, arm, step, messages)
            calls += used
            failed += broken

    def reflexion(self, row):
        first, initial_counts, trajectory = self.react(row, 'react')
        messages = list(trajectory)
        messages.extend([
            {'role': 'assistant', 'content': first},
            {'role': 'user', 'content': 'Act as a self-evaluator. Review your previous trial using the original image '
             'and the observations. Identify a possible error or unsupported inference, and write one short reflection '
             'with a specific recheck for your next attempt. If the answer is supported, say what to preserve. '
             'The reference answer is unavailable.'},
        ])
        reflection = self.call(row, 'reflexion_evaluator', 1, messages)
        final, counts, _ = self.react(row, 'reflexion_retry', reflection)
        counts['qwen'] += initial_counts['qwen'] + 1
        counts['tools'] += initial_counts['tools']
        counts['failed_tools'] += initial_counts['failed_tools']
        return final, counts

    def critic(self, row):
        first, _ = self.cot(row)
        new_cot_calls = int(not prediction_path(dataset_out(self.out, 'cot', self.dataset), row).is_file())
        messages = self.original(row, 'Check an initial visual answer using an external tool and the original image. '
                                 'Consider the tool observation critically before keeping or revising the answer. ' + FINAL)
        messages.append({'role': 'user', 'content': 'Initial candidate reply:\n' + first + '\n'
                         'Identify the most important check. ' + TOOL_JSON + '\nTools: ' + json.dumps(self.catalog)})
        action_raw = self.call(row, 'critic', 1, messages)
        messages.append({'role': 'assistant', 'content': action_raw})
        action = self.action(action_raw)
        if action is None:
            return first, {'qwen': 1 + new_cot_calls, 'tools': 0, 'failed_tools': 1}
        used, broken = self.observe(row, action, 'critic', 1, messages)
        if broken:
            return first, {'qwen': 1 + new_cot_calls, 'tools': used, 'failed_tools': broken}
        messages.append({'role': 'user', 'content': 'State whether the observation supports or challenges the '
                         'candidate. Retain or revise the answer according to the evidence. ' + FINAL})
        return self.call(row, 'critic', 2, messages), {'qwen': 2 + new_cot_calls, 'tools': used, 'failed_tools': broken}

    def predict(self, row, method):
        from online_memory_r49 import save_once

        folder = dataset_out(self.out, method, self.dataset)
        path = prediction_path(folder, row)
        if path.is_file():
            return
        start = time.monotonic()
        if method == 'react':
            raw, counts, _ = self.react(row, 'react')
        else:
            raw, counts = getattr(self, method)(row)
        save_once(path, {'question_id': row['question_id'], 'arm': method, 'raw': raw,
                         'calls': counts, 'elapsed_s': time.monotonic() - start})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root', type=Path)
    parser.add_argument('out', type=Path)
    parser.add_argument('method', choices=METHODS)
    parser.add_argument('--workers', type=int, default=3)
    parser.add_argument('--prepare', action='store_true')
    args = parser.parse_args()
    bind(args.root)
    from online_memory_r49 import save_once
    from r55_baseline_common import score_dataset
    from toolsets_r54 import exclusive_lock

    if args.prepare:
        for dataset in DATASETS:
            manifest = manifest_for(args.root, dataset)
            print(dataset, len(manifest['inputs']), manifest['protocol']['model'])
        return
    key = sys.stdin.readline().strip()
    if not key:
        raise ValueError('The existing Qwen credential must be supplied through stdin')
    with exclusive_lock(args.out / f'{args.method}.lock'):
        save_once(args.out / f'{args.method}.protocol.json', {
            'method': args.method, 'cohorts': DATASETS, 'model': 'qwen3.7-plus',
            'tool_menu': list(TOOL_MENU) if args.method != 'cot' else [],
            'tools_per_react_trial': TOOL_LIMIT, 'reflexion_trials': 2,
            'critic_checks': 1, 'feedback': 'self-evaluation only for Reflexion',
            'cohort_reference_available_to_generation': False,
            'critic_initial_answer': 'reuse frozen CoT prediction when available',
            **({'chexagent': 'StanfordAIMI/CheXagent-8b'} if os.environ.get('R55_CHEXAGENT8_SNAPSHOT') else {}),
        })
        for dataset in ('slake', 'vqarad', 'chexbench'):
            session = Baselines(args.root, args.out, dataset, key)
            rows = session.manifest['inputs']
            with ThreadPoolExecutor(max_workers=args.workers) as pool:
                pending = {}
                try:
                    for index, row in enumerate(rows, 1):
                        pending[index] = pool.submit(session.predict, row, args.method)
                        done = index - args.workers + 1
                        if done in pending:
                            pending.pop(done).result()
                            if done % 20 == 0:
                                print(f'{args.method} {dataset} {done}/{len(rows)}', flush=True)
                    for future in pending.values():
                        future.result()
                except BaseException:
                    for future in pending.values():
                        future.cancel()
                    raise
            score_dataset(args.root, args.out, args.method, dataset)


if __name__ == '__main__':
    main()
