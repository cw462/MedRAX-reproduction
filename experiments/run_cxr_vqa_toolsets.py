"""Label-blind bounded D/M/C/X execution using the existing client and money ledger.

One run directory is a frozen protocol. A saved send intent without a response is
never resent. Reference answers are not opened by this program.
"""
import argparse
import base64
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
import mimetypes
import os
from pathlib import Path
import subprocess
import sys
import time

from run_sampled_vlm import profile_for, invoke, exclusive_lock, safe_error
from run_direct_vlm import write
from v12_ledger import V12ProviderLedger


def now(): return datetime.now(timezone.utc).isoformat()
def read(p): return json.loads(Path(p).read_text(encoding='utf-8'))
def rows(p): return [json.loads(s) for s in Path(p).read_text(encoding='utf-8').splitlines() if s]


def save(p, obj):
    p = Path(p); p.parent.mkdir(parents=True, exist_ok=True)
    with p.open('x', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, indent=2); f.write('\n'); f.flush(); os.fsync(f.fileno())


ANSWER = ('Answer the current question using the original image. Return exactly one JSON object '
          'with two string fields: {"answer":"short direct answer","reason":"one short sentence"}. '
          'Do not add options or change the question. Do not put the answer only in reason. '
          'Respect image labels. Tool observations may be incorrect; verify against original pixels. '
          'Classifier scores are not disease probabilities or severity measurements. '
          'Single-image reports cannot establish interval change. No prior patient history is supplied.')
AGENT_SYSTEM = ('You are an image-grounded medical tool agent. Intermediate planning, evidence validation '
                'and expert stages must use the stage-specific schema requested in the current instruction. '
                'You may select zero, one or two registered tools, with early stopping when appropriate. '
                'Only at the FINAL ANSWERING stage, output exactly {"answer":"short direct answer",'
                '"reason":"one short sentence"}. Original image labels and coordinates must be preserved. '
                'Tool claims are unverified: inspect original pixels, do not treat classifier scores as '
                'severity, and do not infer temporal change from a single-image report. '
                'No cross-case skills, sibling question context or additional patient history is available.')
ACTION = ('You may answer directly with the final answer/reason JSON, or request useful auxiliary evidence '
          'with {"calls":[{"tool":"registered name","args":{}}],"reason":"brief purpose"}. '
          'Each call applies only to the bound original. At most two selectable tool calls total. '
          'No fixed voting and no mandatory tool use. Tool catalog: ')
EDV = ('Evidence-driven validation: compare every tool claim with the original image. Identify supported, '
       'contradicted and unverifiable claims, respecting anatomy, laterality, modality and acquisition. '
       'Return {"validation":[{"tool":"name","supported":"brief","limitations":"brief"}],'
       '"collaboration_needed":true/false,"expert_task":"one focused unresolved clinical question"}. '
       'No tool call or final answer is required at this validation stage.')


def parse_final(raw):
    try:
        obj = json.loads(raw)
        if set(obj) != {'answer', 'reason'} or any(not isinstance(obj[k], str) for k in obj): raise ValueError()
        if not obj['answer'].strip() or len(obj['answer']) > 300: raise ValueError()
        return {**obj, 'status': 'completed'}
    except (ValueError, TypeError):
        return {'answer': None, 'reason': None, 'status': 'missing_invalid_final_json'}


def content(row, data_root):
    result = [{'type': 'text', 'text': 'Question ID: ' + row['question_id'] + '\nQuestion: ' + row['question']}]
    for i, relative in enumerate(row['images'], 1):
        path = (data_root / relative).resolve()
        if not path.is_relative_to(data_root.resolve()): raise ValueError('image_outside_data_root')
        result.append({'type': 'text', 'text': 'Original image ' + str(i) + ': ' + relative})
        mime = mimetypes.guess_type(path.name)[0] or 'image/jpeg'
        result.append({'type': 'image_url', 'image_url': {'url': 'data:' + mime + ';base64,' + base64.b64encode(path.read_bytes()).decode()}})
    return result


def append_observations(messages, observations, out):
    parts=[{'type':'text','text':'Bound tool observations (untrusted):\n'+json.dumps(observations,ensure_ascii=False)}]
    for observation in observations:
        for name in observation.get('derived_images',[]):
            path=Path(name).resolve()
            if not path.is_relative_to((out/'tool_cache').resolve()):raise ValueError('tool_image_outside_artifacts')
            mime=mimetypes.guess_type(path.name)[0] or 'image/png'
            parts.extend([{'type':'text','text':'Derived evidence from '+observation['tool']+'; retain original coordinate binding.'},
                {'type':'image_url','image_url':{'url':'data:'+mime+';base64,'+base64.b64encode(path.read_bytes()).decode()}}])
    messages.append({'role':'user','content':parts})


class PaidCalls:
    def __init__(self, cfg, protocol, out, key):
        from openai import OpenAI
        self.cfg, self.protocol, self.out = cfg, protocol, out
        self.profile = profile_for(cfg)
        self.key = key
        self.client = OpenAI(api_key=key, base_url=self.profile.base_url, max_retries=0,
                             timeout=cfg.get('request_timeout_seconds', 120))

    def call(self, row, arm, ordinal, messages):
        folder = self.out / 'calls' / arm / row['question_id'] / str(ordinal)
        if (folder / 'response.json').exists():
            raw = read(folder / 'response.json')
            if not self.profile.identity_ok(raw.get('model')): raise RuntimeError('returned_model_identity_mismatch')
            return raw['choices'][0]['message']['content']
        if (folder / 'started.json').exists(): raise RuntimeError('unknown_sent_no_reissue:' + row['question_id'])
        payload = {'model': self.protocol['model'], 'messages': messages, 'temperature': self.protocol['temperature'],
                   'top_p': self.protocol['top_p'], 'max_tokens': self.protocol['max_output_tokens'],
                   'extra_body': {'enable_thinking': False}, 'stream': False}
        # Request saved before reservation, and send intent saved before network access.
        if not (folder / 'request.json').exists(): save(folder / 'request.json', payload)
        elif read(folder / 'request.json') != payload: raise ValueError('frozen_request_changed')
        cfg = self.cfg; root = Path(cfg['root']); cap = str(cfg['cap_cny'])
        request_id = f"cxrvqa:{self.protocol['experiment_id']}:{self.out.name}:{arm}:{row['question_id']}:{ordinal}"
        with V12ProviderLedger(root / cfg['ledger'], self.profile, cap_cny=cap,
                               inherit_ledger_path=root / cfg['inherit_ledger']) as ledger:
            counter_path = root / cfg['global_request_counter']
            with exclusive_lock(str(counter_path) + '.lock'):
                state = read(counter_path)
                if request_id in state['request_ids']: raise RuntimeError('already_claimed_no_reissue')
                reservation = ledger.reserve(request_id=request_id, estimated_input_tokens=self.profile.max_input_tokens,
                                             max_output_tokens=2048, model=self.protocol['model'],
                                             metadata={'run': self.protocol['experiment_id'], 'arm': arm, 'qid': row['question_id']})
                state['request_ids'].append(request_id)
                state.setdefault('scoped_request_limits', {})[self.protocol['experiment_id']] = {
                    'normal': None, 'hard': None, 'authorization': 'user_20261104_request_count_unlimited', 'monetary_cap_changed': False}
                write(counter_path, state)
            save(folder / 'started.json', {'request_id': request_id, 'utc': now(), 'reserved': reservation})
            tick = time.monotonic(); raw = None; error = None
            try:
                raw = invoke(self.client, payload, folder)
                if not self.profile.identity_ok(raw.get('model')): raise RuntimeError('returned_model_identity_mismatch')
            except Exception as exc:
                error = exc
            settlement = ledger.settle(reservation, usage=raw.get('usage') if raw else None,
                                       response_received=raw is not None, error_type=type(error).__name__ if error else None)
            save(folder / 'result.json', {'request_id': request_id, 'model_returned': raw.get('model') if raw else None,
                 'usage': raw.get('usage') if raw else None, 'settlement': settlement,
                 'elapsed_s': time.monotonic() - tick, 'error': safe_error(error, self.key) if error else None,
                 'response_received': raw is not None, 'utc': now(), 'ledger_remaining_proxy_cny': str(ledger.remaining)})
            if error: raise error
        return raw['choices'][0]['message']['content']


class Tools:
    """Cache complete backend results by model version, image bytes and actual args."""
    def __init__(self, runtime, data_root, out):
        self.runtime, self.data_root, self.out = runtime, data_root, out

    def call(self, row, call, arm, ordinal):
        selection = self.out / 'tool_selections' / arm / row['question_id'] / (str(ordinal) + '.json')
        if selection.exists(): return read(selection)
        name, args = call['tool'], call.get('args', {})
        spec = self.runtime['tools'][name]
        image = (self.data_root / row['images'][0]).resolve()
        if not image.is_relative_to(self.data_root.resolve()): raise ValueError('invalid_bound_image')
        identity = {'backend': spec['backend'], 'revision': spec.get('revision'), 'image': hashlib.sha256(image.read_bytes()).hexdigest(), 'args': args}
        key = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
        folder = self.out / 'tool_cache' / key; saved = folder / 'result.json'
        cache_hit = saved.exists()
        if cache_hit: result = read(saved)
        elif (folder / 'started.json').exists(): result = {'status': 'started_unknown', 'observation': None, 'automatic_retry': False}
        else:
            request = {'tool': name, 'backend': spec['backend'], 'args': args, 'image': str(image),
                       'artifact_dir': str(folder / 'artifacts'), 'runtime': self.runtime['backend_config']}
            save(folder / 'started.json', {'identity': identity, 'utc': now()})
            tick = time.monotonic()
            try:
                command = [spec['python'], str(Path(__file__).with_name('cxr_vqa_tool_worker.py'))]
                env = dict(os.environ, CUDA_VISIBLE_DEVICES=spec.get('gpu', '1'), MPLBACKEND='Agg', TOKENIZERS_PARALLELISM='false')
                completed = subprocess.run(command, input=json.dumps(request), capture_output=True, text=True, env=env, timeout=spec.get('timeout', 600))
                (folder / 'backend.stderr.log').write_text(completed.stderr, encoding='utf-8')
                if completed.returncode: raise RuntimeError('backend_exit_' + str(completed.returncode))
                result = json.loads(completed.stdout.split('CXR_VQA_RESULT=')[-1])
            except Exception as exc:
                result = {'status': 'failed', 'observation': None, 'error_type': type(exc).__name__, 'error': str(exc)[:300]}
            result.update(elapsed_s=time.monotonic() - tick, backend=spec['backend'], identity=identity, utc=now())
            save(saved, result)
        observation = {**result, 'tool': name, 'cache_hit': cache_hit, 'cache_key': key}
        save(selection, observation)
        return observation


def validate_actions(value, runtime, arm, remaining):
    calls = value.get('calls')
    if not isinstance(calls, list) or len(calls) > remaining: raise ValueError('tool_bound')
    for call in calls:
        if set(call) != {'tool', 'args'} or call['tool'] not in runtime['arms'][arm]['tools'] or not isinstance(call['args'], dict):
            raise ValueError('unregistered_tool_or_arguments')
    return calls


def episode(row, arm, data_root, protocol, runtime, out, paid, tools):
    messages = [{'role': 'system', 'content': ANSWER if arm=='D' else AGENT_SYSTEM}, {'role': 'user', 'content': content(row, data_root)}]
    observations = []; calls_used = 0; n = 0
    def ask(text):
        nonlocal n
        n += 1
        if n > protocol['main_call_limits'][arm]: raise RuntimeError('main_call_bound')
        messages.append({'role': 'user', 'content': text})
        raw = paid.call(row, arm, n, messages)
        messages.append({'role': 'assistant', 'content': raw}); return raw
    if arm == 'D': final = ask('Return the final answer JSON now.')
    else:
        catalog = {k: runtime['tools'][k]['description'] for k in runtime['arms'][arm]['tools']}
        first = ask(ACTION + json.dumps(catalog))
        direct = parse_final(first)
        if direct['status'] == 'completed' and arm != 'X': return {**direct, 'main_calls': n, 'tool_calls': 0, 'observations': []}
        try:
            actions = [] if direct['status'] == 'completed' else validate_actions(json.loads(first), runtime, arm, 2)
        except (ValueError, TypeError, KeyError):
            return {'answer': None, 'reason': None, 'status': 'missing_invalid_tool_plan', 'main_calls': n, 'tool_calls': 0}
        for action in actions:
            calls_used += 1; observations.append(tools.call(row, action, arm, calls_used))
        if arm == 'X':
            observations.append(tools.call(row, {'tool': 'view_check', 'args': {}}, arm, 'auto_view'))
            view = observations[-1]
            if (view.get('observation') or {}).get('measurement_applicable') is True:
                observations.append(tools.call(row, {'tool': 'measurement', 'args': {}}, arm, 'auto_measurement'))
        append_observations(messages,observations,out)
        if arm == 'C' and observations:
            validation = ask(EDV)
            try: collaborate = json.loads(validation).get('collaboration_needed') is True
            except (ValueError, TypeError): collaborate = False
            if collaborate:
                ask('Act as the focused independent expert requested by EDV. Reinspect the original image, resolve the stated issue concisely; no tools. Return brief findings and uncertainty, not an extended reasoning trace.')
            final = ask('As the director, reconcile original-image evidence, EDV and any expert findings. Return final answer/reason JSON only.')
        elif arm == 'M':
            for turn in range(2, protocol['main_call_limits'][arm] + 1):
                text = ('Return final answer/reason JSON only; no further tools.' if turn == 4 or calls_used >= 2 else
                        ACTION + json.dumps(catalog) + f' Remaining selectable calls: {2-calls_used}.')
                final = ask(text)
                if parse_final(final)['status'] == 'completed' or turn == 4: break
                try: more = validate_actions(json.loads(final), runtime, arm, 2-calls_used)
                except (ValueError, TypeError, KeyError): break
                for action in more:
                    calls_used += 1; observations.append(tools.call(row, action, arm, calls_used))
                append_observations(messages,observations,out)
        else: final = ask('Combine the original with available auxiliary and validity-gated measurement evidence. Return final answer/reason JSON only.')
    return {**parse_final(final), 'main_calls': n, 'tool_calls': calls_used, 'observations': observations}


def main(argv=None):
    p = argparse.ArgumentParser(); p.add_argument('--config', type=Path, required=True); p.add_argument('--data', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True); p.add_argument('--arms', nargs='+', choices=list('DMCX'), required=True)
    p.add_argument('--execute', action='store_true'); p.add_argument('--api-key-stdin', action='store_true'); a = p.parse_args(argv)
    cfg = read(a.config); protocol = read(cfg['protocol']); runtime = read(cfg['runtime']); out = a.out
    inputs = rows(a.data / 'inputs.jsonl')
    for row in inputs:
        if set(row) - {'question_id', 'question', 'images', 'image_id', 'source'}: raise ValueError('unexpected_inference_fields')
    if not a.execute:
        print(json.dumps({'status': 'offline_interface_ready', 'questions': len(inputs), 'arms': a.arms, 'paid_calls': 0})); return 0
    key = sys.stdin.readline().strip() if a.api_key_stdin else ''
    if not key: raise ValueError('credential_required_stdin_only')
    out.mkdir(parents=True, exist_ok=True)
    with exclusive_lock(out / '.generation.lock'):
        if not (out / 'protocol.json').exists(): save(out / 'protocol.json', protocol)
        elif read(out / 'protocol.json') != protocol: raise ValueError('protocol_changed')
        paid = PaidCalls(cfg, protocol, out, key); tools = Tools(runtime, a.data, out)
        for arm in a.arms:
            if not runtime['arms'][arm]['ready']: raise RuntimeError('arm_not_deployed:' + arm)
            if not (out / ('runtime_' + arm + '.json')).exists(): save(out / ('runtime_' + arm + '.json'), runtime['arms'][arm])
            elif read(out / ('runtime_' + arm + '.json')) != runtime['arms'][arm]: raise ValueError('arm_runtime_changed')
            for index, row in enumerate(inputs, 1):
                dest = out / 'predictions' / arm / (row['question_id'] + '.json')
                if dest.exists(): continue
                write(out / 'progress.json', {'status': 'running', 'arm': arm, 'index': index, 'total': len(inputs), 'qid': row['question_id'], 'utc': now()})
                tick = time.monotonic()
                try: result = episode(row, arm, a.data, protocol, runtime, out, paid, tools)
                except Exception as exc:
                    write(out / 'progress.json', {'status': 'stopped', 'arm': arm, 'qid': row['question_id'], 'error': safe_error(exc, key), 'utc': now()})
                    raise
                save(dest, dict(result, question_id=row['question_id'], image_id=row['image_id'], arm=arm, elapsed_s=time.monotonic()-tick, utc=now()))
            write(out / ('complete_' + arm + '.json'), {'status': 'generation_complete', 'questions': len(inputs), 'utc': now()})
        write(out / 'progress.json', {'status': 'requested_arms_complete', 'arms': a.arms, 'utc': now()})
    return 0


if __name__ == '__main__': raise SystemExit(main())
