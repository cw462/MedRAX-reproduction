"""Label-blind bounded D/M/C/X execution using the existing client and money ledger.

One run directory is a frozen protocol. A saved send intent without a response is
never resent. Reference answers are not opened by this program.
"""
import argparse
import base64
from contextlib import ExitStack, contextmanager, nullcontext
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
import mimetypes
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import uuid

# Load the deployed ledger before the legacy helper modules add their own path.
from provider_ledger import LedgerIntegrityError, LedgerLocked
from v12_ledger import ConcurrentV12Ledger, LedgerReadError, LedgerSnapshotChanged, V12ProviderLedger
from run_sampled_vlm import profile_for, invoke, exclusive_lock, safe_error
from run_direct_vlm import write


def now(): return datetime.now(timezone.utc).isoformat()
def read(p): return json.loads(Path(p).read_text(encoding='utf-8'))
def rows(p): return [json.loads(s) for s in Path(p).read_text(encoding='utf-8').splitlines() if s]


def save(p, obj):
    p = Path(p); p.parent.mkdir(parents=True, exist_ok=True)
    temp=p.with_name('.'+p.name+'.'+uuid.uuid4().hex+'.tmp')
    try:
        with temp.open('x', encoding='utf-8') as f:
            json.dump(obj, f, ensure_ascii=False, indent=2); f.write('\n'); f.flush(); os.fsync(f.fileno())
        os.link(temp,p)  # Atomic publication, refuses an existing destination.
    finally:
        if temp.exists():temp.unlink()


def freeze_protocol(out, protocol):
    path = out / 'protocol.json'
    try:
        save(path, protocol)
    except FileExistsError:
        if read(path) != protocol:
            raise ValueError('protocol_changed')


@contextmanager
def tool_worker_slot(path):
    # Only tool subprocesses share the accelerator. API calls and cache hits
    # remain independent.
    with ExitStack() as stack:
        while True:
            try:
                stack.enter_context(exclusive_lock(path))
                break
            except BlockingIOError:
                time.sleep(.25)
        yield


IMAGE_DATA_URI = re.compile(r'data:(image/[a-z0-9.+-]+);base64,([A-Za-z0-9+/=]+)\Z')


def archive_request(payload, asset_dir):
    """Represent each original request image with a lossless content reference."""
    def visit(value):
        if isinstance(value, dict):
            return {k: visit(v) for k,v in value.items()}
        if isinstance(value, list):
            return [visit(item) for item in value]
        match = IMAGE_DATA_URI.fullmatch(value) if isinstance(value, str) else None
        if match:
            media_type, encoded = match.groups()
            digest = hashlib.sha256(encoded.encode('ascii')).hexdigest()
            asset = asset_dir / digest
            if not asset.is_file():
                asset_dir.mkdir(parents=True, exist_ok=True)
                temp = asset.with_name('.'+digest+'.'+uuid.uuid4().hex+'.tmp')
                try:
                    temp.write_bytes(encoded.encode('ascii'))
                    os.replace(temp, asset)
                finally:
                    temp.unlink(missing_ok=True)
            return {'cxr_request_image_base64_sha256': digest, 'media_type': media_type}
        return value
    return visit(payload)


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

MANUAL_EVIDENCE_RULES = ('do not treat classifier scores as severity, and do not infer temporal change '
                         'from a single-image report.')
M_MINUS_R_SYSTEM = AGENT_SYSTEM.replace(
    'Tool claims are unverified: inspect original pixels, ' + MANUAL_EVIDENCE_RULES,
    'Tool claims are unverified: inspect original pixels.')
M_MINUS_R_TOOL_DESCRIPTIONS = {
    'chest_xray_classifier': ('args={}. Single original CXR finding scores, never severity or localization.',
                              'args={}. Single original CXR finding scores.'),
    'chest_xray_report_generator': ('args={}. Single original CXR report; temporal claims unsupported.',
                                    'args={}. Single original CXR report.'),
}


def agent_system(arm):
    if arm == 'D-H':
        return ANSWER.replace('No prior patient history is supplied.', 'Use only the independently supplied history.')
    if arm == 'M-H':
        return AGENT_SYSTEM.replace('No cross-case skills, sibling question context or additional patient history is available.',
                                    'Use only the independently supplied history. No cross-case skills or sibling questions are available.')
    return ANSWER if arm == 'D' else M_MINUS_R_SYSTEM if arm == 'M-R' else AGENT_SYSTEM


def evidence_catalog(runtime, arm):
    catalog = {k: runtime['tools'][k]['description'] for k in runtime['arms'][arm]['tools']}
    if arm == 'M-R':
        for name, (before, after) in M_MINUS_R_TOOL_DESCRIPTIONS.items():
            if name in catalog:
                if catalog[name] != before:
                    raise ValueError('unexpected_manual_rule_catalog:' + name)
                catalog[name] = after
    return catalog


def parse_final(raw):
    try:
        obj = json.loads(raw)
        if set(obj) != {'answer', 'reason'} or any(not isinstance(obj[k], str) for k in obj): raise ValueError()
        if not obj['answer'].strip() or len(obj['answer']) > 300: raise ValueError()
        return {**obj, 'status': 'completed'}
    except (ValueError, TypeError):
        return {'answer': None, 'reason': None, 'status': 'missing_invalid_final_json'}


def content(row, data_root):
    question = 'Question ID: ' + row['question_id'] + '\nQuestion: ' + row['question']
    if 'options' in row:
        question += '\n' + '\n'.join(f'{key}. {value}' for key, value in row['options'].items())
        question += '\nUse an original option letter or the complete original option text as answer.'
    result = [{'type': 'text', 'text': question}]
    for i, relative in enumerate(row['images'], 1):
        path = (data_root / relative).resolve()
        if not path.is_relative_to(data_root.resolve()): raise ValueError('image_outside_data_root')
        result.append({'type': 'text', 'text': 'Original image ' + str(i) + ': ' + relative})
        mime = mimetypes.guess_type(path.name)[0] or 'image/jpeg'
        result.append({'type': 'image_url', 'image_url': {'url': 'data:' + mime + ';base64,' + base64.b64encode(path.read_bytes()).decode()}})
    return result


def append_observations(messages, observations, out, arm=None):
    presented = observations
    if arm == 'M-R':
        presented = []
        for item in observations:
            value = item.get('observation')
            if item['tool'] in M_MINUS_R_TOOL_DESCRIPTIONS and isinstance(value, dict):
                value = {k: v for k, v in value.items() if k != 'limitations'}
                item = dict(item, observation=value)
            presented.append(item)
    parts=[{'type':'text','text':'Bound tool observations (untrusted):\n'+json.dumps(presented,ensure_ascii=False)}]
    for observation in observations:
        for name in observation.get('derived_images',[]):
            path=Path(name).resolve()
            if not path.is_relative_to((out/'tool_cache').resolve()):raise ValueError('tool_image_outside_artifacts')
            mime=mimetypes.guess_type(path.name)[0] or 'image/png'
            parts.extend([{'type':'text','text':'Derived evidence from '+observation['tool']+'; retain original coordinate binding.'},
                {'type':'image_url','image_url':{'url':'data:'+mime+';base64,'+base64.b64encode(path.read_bytes()).decode()}}])
    messages.append({'role':'user','content':parts})


class PaidCalls:
    def __init__(self, cfg, protocol, out, key, *, parallel=False):
        from openai import OpenAI
        self.cfg, self.protocol, self.out = cfg, protocol, out
        self.profile = profile_for(cfg)
        self.key = key
        self.parallel = parallel
        self.client = OpenAI(api_key=key, base_url=self.profile.base_url, max_retries=0,
                             timeout=cfg.get('request_timeout_seconds', 120))

    def open_ledger(self):
        cfg = self.cfg
        root = Path(cfg['root'])
        ledger_path = root / cfg['ledger']
        waiting_for_read = False
        while True:
            try:
                ledger_class = ConcurrentV12Ledger if self.parallel else V12ProviderLedger
                return ledger_class(ledger_path, self.profile, cap_cny=str(cfg['cap_cny']),
                                    inherit_ledger_path=root / cfg['inherit_ledger'])
            except LedgerLocked:
                # The current holder can be settling a paid call. This call
                # has made no reservation and will wait before sending.
                time.sleep(1)
            except (json.JSONDecodeError, UnicodeDecodeError, LedgerIntegrityError) as exc:
                # Wait at the pre-send boundary until the budget can be read.
                read_error = exc.__cause__ if isinstance(exc, LedgerIntegrityError) else exc
                if not isinstance(exc, LedgerReadError) and not isinstance(read_error, (json.JSONDecodeError, UnicodeDecodeError)):
                    raise
                if not waiting_for_read:
                    print('Waiting to read the shared ledger before sending.', file=sys.stderr, flush=True)
                    waiting_for_read = True
                time.sleep(10)

    def update_accounting(self, operation):
        while True:
            try:
                with self.open_ledger() as ledger:
                    return operation(ledger)
            except LedgerSnapshotChanged:
                continue
            except (LedgerReadError, KeyError) as exc:
                if isinstance(exc, KeyError) and exc.args != ('charged_cny',):
                    raise
                print('Waiting to update the shared SQLite ledger.', file=sys.stderr, flush=True)
                time.sleep(10)

    def reserve(self, ledger, request_id, arm, qid):
        return ledger.reserve(
            request_id=request_id, estimated_input_tokens=self.profile.max_input_tokens,
            max_output_tokens=2048, model=self.protocol['model'],
            metadata={'run': self.protocol['experiment_id'], 'arm': arm, 'qid': qid})

    @contextmanager
    def reserve_call(self, request_id, arm, qid):
        if self.parallel:
            # The transaction records both the request ID and its reservation.
            # Its connection is closed before entering the network call.
            reservation = self.update_accounting(lambda ledger: self.reserve(ledger, request_id, arm, qid))
            yield None, reservation
            return
        counter_path = Path(self.cfg['root']) / self.cfg['global_request_counter']
        waiting_for_charge = False
        while True:
            with self.open_ledger() as ledger:
                with exclusive_lock(str(counter_path) + '.lock'):
                    state = read(counter_path)
                    if request_id in state['request_ids']:
                        raise RuntimeError('already_claimed_no_reissue')
                    try:
                        reservation = self.reserve(ledger, request_id, arm, qid)
                    except KeyError as exc:
                        if exc.args != ('charged_cny',):
                            raise
                        # The charge calculation failed before persisting a reservation.
                        reservation = None
                    if reservation is not None:
                        state['request_ids'].append(request_id)
                        state.setdefault('scoped_request_limits', {})[self.protocol['experiment_id']] = {
                            'normal': None, 'hard': None, 'authorization': 'user_20261104_request_count_unlimited', 'monetary_cap_changed': False}
                        write(counter_path, state)
                if reservation is not None:
                    yield ledger, reservation
                    return
            if not waiting_for_charge:
                print('Waiting for the shared ledger charge field before sending.', file=sys.stderr, flush=True)
                waiting_for_charge = True
            time.sleep(10)

    def call(self, row, arm, ordinal, messages, *, api_tools=None):
        folder = self.out / 'calls' / arm / row['question_id'] / str(ordinal)
        stored_response = (folder / 'response.json').exists()
        dedup = self.protocol.get('request_archive') == 'image_base64_content_addressed_v1'
        if stored_response and not dedup:
            raw = read(folder / 'response.json')
            if not self.profile.identity_ok(raw.get('model')): raise RuntimeError('returned_model_identity_mismatch')
            message = raw['choices'][0]['message']
            return message if api_tools is not None else message['content']
        if not stored_response and (folder / 'started.json').exists(): raise RuntimeError('unknown_sent_no_reissue:' + row['question_id'])
        payload = {'model': self.protocol['model'], 'messages': messages, 'temperature': self.protocol['temperature'],
                   'top_p': self.protocol['top_p'], 'max_tokens': self.protocol['max_output_tokens'],
                   'extra_body': {'enable_thinking': False}, 'stream': False}
        if api_tools is not None:
            payload['tools'] = api_tools
        archived = archive_request(payload, self.out/'request_image_base64') if dedup else payload
        # Request saved before reservation, and send intent saved before network access.
        if not (folder / 'request.json').exists(): save(folder / 'request.json', archived)
        elif read(folder / 'request.json') != archived: raise ValueError('frozen_request_changed')
        if stored_response:
            raw = read(folder / 'response.json')
            if not self.profile.identity_ok(raw.get('model')): raise RuntimeError('returned_model_identity_mismatch')
            message = raw['choices'][0]['message']
            return message if api_tools is not None else message['content']
        request_id = f"cxrvqa:{self.protocol['experiment_id']}:{self.out.name}:{arm}:{row['question_id']}:{ordinal}"
        with self.reserve_call(request_id, arm, row['question_id']) as (ledger, reservation):
            save(folder / 'started.json', {'request_id': request_id, 'utc': now(), 'reserved': reservation})
            tick = time.monotonic(); raw = None; error = None
            try:
                raw = invoke(self.client, payload, folder)
                if not self.profile.identity_ok(raw.get('model')): raise RuntimeError('returned_model_identity_mismatch')
            except Exception as exc:
                error = exc
            def settle(current):
                return current.settle(reservation, usage=raw.get('usage') if raw else None,
                                      response_received=raw is not None, error_type=type(error).__name__ if error else None)
            if self.parallel:
                settlement = self.update_accounting(settle)
            else:
                settlement = settle(ledger)
            save(folder / 'result.json', {'request_id': request_id, 'model_returned': raw.get('model') if raw else None,
                 'usage': raw.get('usage') if raw else None, 'settlement': settlement,
                 'elapsed_s': time.monotonic() - tick, 'error': safe_error(error, self.key) if error else None,
                 'response_received': raw is not None, 'utc': now(), 'ledger_remaining_proxy_cny': settlement['remaining_cny']})
            if error: raise error
        message = raw['choices'][0]['message']
        return message if api_tools is not None else message['content']


class Tools:
    """Cache complete backend results by model version, image bytes and actual args."""
    def __init__(self, runtime, data_root, out, *, worker_gate=None):
        self.runtime, self.data_root, self.out = runtime, data_root, out
        self.worker_gate = worker_gate

    def call(self, row, call, arm, ordinal):
        selection = self.out / 'tool_selections' / arm / row['question_id'] / (str(ordinal) + '.json')
        if selection.exists(): return read(selection)
        name, args = call['tool'], call.get('args', {})
        spec = self.runtime['tools'][name]
        index = call.get('image_index', 1)
        if type(index) is not int or not 1 <= index <= len(row['images']):
            raise ValueError('invalid_bound_image_index')
        image = (self.data_root / row['images'][index-1]).resolve()
        if not image.is_relative_to(self.data_root.resolve()): raise ValueError('invalid_bound_image')
        identity = {'backend': spec['backend'], 'revision': spec.get('revision'), 'image': hashlib.sha256(image.read_bytes()).hexdigest(), 'args': args}
        key = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
        folder = self.out / 'tool_cache' / key; saved = folder / 'result.json'
        gate = tool_worker_slot(self.worker_gate) if self.worker_gate and not saved.is_file() else nullcontext()
        with gate:
            result, cache_hit = self.observe(spec, args, image, identity, folder, saved)
        observation = {**result, 'tool': name, 'cache_hit': cache_hit, 'cache_key': key}
        if len(row['images']) > 1:
            observation['image_index'] = index
        save(selection, observation)
        return observation

    def observe(self, spec, args, image, identity, folder, saved):
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
                if spec.get('cpu_affinity') is not None:
                    command = ['taskset', '-c', str(spec['cpu_affinity']), *command]
                env = dict(os.environ, CUDA_VISIBLE_DEVICES=spec.get('gpu', '1'), MPLBACKEND='Agg', TOKENIZERS_PARALLELISM='false')
                env.update(spec.get('worker_env', {}))
                completed = subprocess.run(command, input=json.dumps(request), capture_output=True, text=True, env=env, timeout=spec.get('timeout', 600))
                (folder / 'backend.stderr.log').write_text(completed.stderr, encoding='utf-8')
                if completed.returncode: raise RuntimeError('backend_exit_' + str(completed.returncode))
                result = json.loads(completed.stdout.split('CXR_VQA_RESULT=')[-1])
            except Exception as exc:
                result = {'status': 'failed', 'observation': None, 'error_type': type(exc).__name__, 'error': str(exc)[:300]}
            result.update(elapsed_s=time.monotonic() - tick, backend=spec['backend'], identity=identity, utc=now())
            save(saved, result)
        return result, cache_hit


def validate_actions(value, runtime, arm, remaining, images=1):
    calls = value.get('calls')
    if not isinstance(calls, list) or len(calls) > remaining: raise ValueError('tool_bound')
    for call in calls:
        keys = {'tool', 'args', 'image_index'} if images > 1 else {'tool', 'args'}
        if set(call) != keys or call['tool'] not in runtime['arms'][arm]['tools'] or not isinstance(call['args'], dict):
            raise ValueError('unregistered_tool_or_arguments')
        index = call.get('image_index', 1)
        if type(index) is not int or not 1 <= index <= images:
            raise ValueError('invalid_bound_image_index')
    return calls


def resolve_action(call, observations):
    if call['tool']=='roi_crop' and call['args'].get('box_from')=='region_parse':
        if 'box' in call['args']:raise ValueError('ambiguous_crop_coordinates')
        prior=next((x for x in reversed(observations) if x.get('tool')=='region_parse'
                    and x.get('image_index',1)==call.get('image_index',1)),None)
        box=((prior or {}).get('observation') or {}).get('combined_box_normalized')
        if box is None:raise ValueError('prior_region_box_unavailable')
        return dict(call,args={'box':box})
    return call


def episode(row, arm, data_root, protocol, runtime, out, paid, tools, *, conditioning=None):
    messages = [{'role': 'system', 'content': agent_system(arm)}, {'role': 'user', 'content': content(row, data_root)}]
    if conditioning:
        messages.append({'role': 'user', 'content': conditioning})
    observations = []; calls_used = 0; n = 0
    images = len(row['images'])
    action_prompt = ACTION
    if images > 1:
        action_prompt = ACTION.replace('"args":{}', '"args":{},"image_index":1').replace(
            'Each call applies only to the bound original.', 'Select the numbered original for each call via image_index.')
    def ask(text):
        nonlocal n
        n += 1
        if n > protocol['main_call_limits'][arm]: raise RuntimeError('main_call_bound')
        messages.append({'role': 'user', 'content': text})
        raw = paid.call(row, arm, n, messages)
        messages.append({'role': 'assistant', 'content': raw}); return raw
    if arm in ('D', 'D-H'): final = ask('Return the final answer JSON now.')
    else:
        catalog = evidence_catalog(runtime, arm)
        first = ask(action_prompt + json.dumps(catalog))
        direct = parse_final(first)
        if direct['status'] == 'completed' and arm != 'X': return {**direct, 'main_calls': n, 'tool_calls': 0, 'observations': []}
        try:
            actions = [] if direct['status'] == 'completed' else validate_actions(json.loads(first), runtime, arm, 2, images)
        except (ValueError, TypeError, KeyError):
            return {'answer': None, 'reason': None, 'status': 'missing_invalid_tool_plan', 'main_calls': n, 'tool_calls': 0}
        for action in actions:
            calls_used += 1
            try: actual=resolve_action(action,observations)
            except ValueError as exc:
                observations.append({'tool':action['tool'],'status':'invalid_arguments','observation':None,'error':str(exc),'backend_invoked':False});continue
            observations.append(tools.call(row, actual, arm, calls_used))
        if arm == 'X':
            for index in range(1, images+1):
                suffix = '' if images==1 else f'_{index}'
                binding = {} if images==1 else {'image_index': index}
                view = tools.call(row, dict(tool='view_check', args={}, **binding), arm, 'auto_view'+suffix)
                observations.append(view)
                if (view.get('observation') or {}).get('measurement_applicable') is True:
                    observations.append(tools.call(row, dict(tool='measurement', args={}, **binding), arm, 'auto_measurement'+suffix))
        append_observations(messages,observations,out,arm)
        if arm == 'C' and observations:
            validation = ask(EDV)
            try: collaborate = json.loads(validation).get('collaboration_needed') is True
            except (ValueError, TypeError): collaborate = False
            if collaborate:
                ask('Act as the focused independent expert requested by EDV. Reinspect the original image, resolve the stated issue concisely; no tools. Return brief findings and uncertainty, not an extended reasoning trace.')
            final = ask('As the director, reconcile original-image evidence, EDV and any expert findings. Return final answer/reason JSON only.')
        elif arm in ('M', 'M-R', 'M-S', 'M-E', 'M-H'):
            for turn in range(2, protocol['main_call_limits'][arm] + 1):
                text = ('Return final answer/reason JSON only; no further tools.' if turn == 4 or calls_used >= 2 else
                        action_prompt + json.dumps(catalog) + f' Remaining selectable calls: {2-calls_used}.')
                final = ask(text)
                if parse_final(final)['status'] == 'completed' or turn == 4: break
                try: more = validate_actions(json.loads(final), runtime, arm, 2-calls_used, images)
                except (ValueError, TypeError, KeyError): break
                for action in more:
                    calls_used += 1; observations.append(tools.call(row, action, arm, calls_used))
                append_observations(messages,observations,out,arm)
        else: final = ask('Combine the original with available auxiliary and validity-gated measurement evidence. Return final answer/reason JSON only.')
    return {**parse_final(final), 'main_calls': n, 'tool_calls': calls_used, 'observations': observations}


def main(argv=None, *, arms=('D', 'M', 'C', 'X'), episode_fn=episode, system_fn=agent_system, extra_input_fields=()):
    p = argparse.ArgumentParser(); p.add_argument('--config', type=Path, required=True); p.add_argument('--data', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True); p.add_argument('--arms', nargs='+', choices=arms, required=True)
    p.add_argument('--execute', action='store_true'); p.add_argument('--api-key-stdin', action='store_true')
    p.add_argument('--parallel', action='store_true'); a = p.parse_args(argv)
    cfg = read(a.config); protocol = read(cfg['protocol']); runtime = read(cfg['runtime']); out = a.out
    inputs = rows(a.data / 'inputs.jsonl')
    for row in inputs:
        if set(row) - {'question_id', 'question', 'images', 'image_id', 'source', 'options', *extra_input_fields}: raise ValueError('unexpected_inference_fields')
    if not a.execute:
        print(json.dumps({'status': 'offline_interface_ready', 'questions': len(inputs), 'arms': a.arms, 'paid_calls': 0})); return 0
    key = sys.stdin.readline().strip() if a.api_key_stdin else ''
    if not key: raise ValueError('credential_required_stdin_only')
    out.mkdir(parents=True, exist_ok=True)
    paid = PaidCalls(cfg, protocol, out, key, parallel=a.parallel)
    tools = Tools(runtime, a.data, out, worker_gate=out.parent / '.tool-worker.lock' if a.parallel else None)
    for arm in a.arms:
        lock = out / (f'.generation_{arm}.lock' if a.parallel else '.generation.lock')
        progress = out / (f'progress_{arm}.json' if a.parallel else 'progress.json')
        with exclusive_lock(lock):
            freeze_protocol(out, protocol)
            completion = out / f'complete_{arm}.json'
            if completion.is_file():
                continue
            if not runtime['arms'][arm]['ready']: raise RuntimeError('arm_not_deployed:' + arm)
            full={'arm':runtime['arms'][arm], 'tools':{k:runtime['tools'][k] for k in runtime['arms'][arm]['tools']},
                  'backend_config':runtime['backend_config'] if arm!='D' else {},
                  'agent_system':system_fn(arm)}
            full_path=out/('runtime_full_'+arm+'.json')
            if not full_path.exists():save(full_path,full)
            elif read(full_path)!=full:raise ValueError('frozen_tool_or_agent_configuration_changed')
            if not (out / ('runtime_' + arm + '.json')).exists(): save(out / ('runtime_' + arm + '.json'), runtime['arms'][arm])
            elif read(out / ('runtime_' + arm + '.json')) != runtime['arms'][arm]: raise ValueError('arm_runtime_changed')
            for index, row in enumerate(inputs, 1):
                dest = out / 'predictions' / arm / (row['question_id'] + '.json')
                if dest.exists(): continue
                write(progress, {'status': 'running', 'arm': arm, 'index': index, 'total': len(inputs), 'qid': row['question_id'], 'utc': now()})
                tick = time.monotonic()
                try: result = episode_fn(row, arm, a.data, protocol, runtime, out, paid, tools)
                except Exception as exc:
                    write(progress, {'status': 'stopped', 'arm': arm, 'qid': row['question_id'], 'error': safe_error(exc, key), 'utc': now()})
                    raise
                save(dest, dict(result, question_id=row['question_id'], image_id=row['image_id'], arm=arm, elapsed_s=time.monotonic()-tick, utc=now()))
            save(completion, {'status': 'generation_complete', 'questions': len(inputs), 'utc': now()})
            write(progress, {'status': 'requested_arms_complete', 'arms': [arm], 'utc': now()})
    return 0


if __name__ == '__main__': raise SystemExit(main())
