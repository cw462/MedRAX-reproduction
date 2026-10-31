"""D0: one independent, tool-free multi-image request per fixed question.

This generator accepts no label/score paths and never loads historical answers.
Only the separate comparison process reads labels after all 60 terminals exist.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

SYSTEM_PROMPT = '''You answer medical image multiple-choice questions. Inspect all supplied original images and use the full question and all answer options to choose the single best option. Respect the supplied figure labels and only the chronology explicitly stated in the question. Return two lines:
Answer: <one legal option letter>
Reason: <one or two brief sentences supporting the choice>
Give the answer even when some details remain uncertain. Do not output a long reasoning trace.'''


def now():
    return datetime.now(timezone.utc).isoformat()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def write(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.tmp')
    with temp.open('w', encoding='utf-8', newline='\n') as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2, allow_nan=False)
        handle.write('\n'); handle.flush(); os.fsync(handle.fileno())
    temp.replace(path)


def read_lines(path):
    path = Path(path)
    return [json.loads(s) for s in path.read_text(encoding='utf-8-sig').splitlines() if s.strip()] if path.exists() else []


def parse_answer(text, legal):
    """Explicit answer lines only; do not extract choices from the reason."""
    if not isinstance(text, str):
        return {'answer': None, 'status': 'invalid_answer', 'reason_missing': True}
    clean = text.replace('**', '').replace('__', '').replace('`', '').strip()
    fields = []
    for line in clean.splitlines():
        match = re.match(r'^\s*Answer\s*:\s*(.*?)\s*$', line, re.I)
        if match:
            value = match[1].strip().strip('()[] .').upper()
            fields.append(value if len(value) == 1 and value in legal else None)
    if fields:
        answer = fields[0] if None not in fields and len(set(fields)) == 1 else None
    else:
        value = clean.strip('()[] .').upper()
        answer = value if len(value) == 1 and value in legal else None
    reasons = [m[1].strip() for line in clean.splitlines()
               if (m := re.match(r'^\s*Reason\s*:\s*(.*)$', line, re.I))]
    return {'answer': answer, 'status': 'completed' if answer else 'invalid_answer',
            'reason_missing': not any(reasons)}


def request_for(row, image_root):
    from v12_evidence import build_images, multimodal_content
    images = build_images(row, image_root)
    # Metadata is built only from the original filenames/pixels. All model-derived
    # modality, chronology and object fields remain unknown, exactly as at V12 input.
    return [{'role': 'system', 'content': SYSTEM_PROMPT},
            {'role': 'user', 'content': multimodal_content(row['question'], images)}]


def estimate_tokens(messages):
    chars = sum(len(p.get('text', '')) for m in messages if isinstance(m['content'], list)
                for p in m['content'] if p.get('type') == 'text') + len(SYSTEM_PROMPT)
    images = sum(p.get('type') == 'image_url' for m in messages if isinstance(m['content'], list) for p in m['content'])
    return int(chars / 2.2) + images * 1200 + 2600


def prepare(cfg, out):
    from v12_evidence import build_images, question_parts
    root = Path(cfg['root'])
    rows = read_lines(root / cfg['input'])
    if len(rows) != 60 or len({r['question_id'] for r in rows}) != 60:
        raise ValueError('expected_original_fixed60_unique_inputs')
    if any(set(r) != {'question_id', 'question', 'images'} for r in rows):
        raise ValueError('inference_input_has_extra_fields')
    cached = [{k: r[k] for k in ('question_id','question','images')} for r in read(root/cfg['frozen_v12_selection'])['rows']]
    if rows != cached: raise ValueError('inputs_differ_from_frozen_V12_selection')
    fingerprints = []
    for row in rows:
        if not re.fullmatch(r'[A-Za-z0-9_-]+', row['question_id']): raise ValueError('unsafe_question_id')
        question_parts(row['question'])
        for image in build_images(row, root / cfg['image_root']):
            p = Path(image['path'])
            fingerprints.append({'question_id': row['question_id'], 'image_id': image['image_id'],
                                 'source_filename': image['source_filename'], 'size': image['size'],
                                 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()})
    if (cfg['max_requests'], cfg['max_extra_requests'], cfg['max_attempts_per_question']) != (66, 6, 2):
        raise ValueError('direct_request_limits_changed')
    if cfg['tools'] or cfg['retrieval'] or cfg['memory'] or cfg['judge']:
        raise ValueError('direct_group_must_be_tool_free')
    frozen = dict(cfg, implementation_commit=os.environ.get('MEDRAX_CODE_COMMIT', 'unrecorded'),
                  system_prompt=SYSTEM_PROMPT, inference_fields=['question_id', 'question', 'images'],
                  labels_loaded_by_generation=False, image_fingerprints=fingerprints,
                  implementation_sha256={n: hashlib.sha256((HERE/n).read_bytes()).hexdigest() for n in
                      ('run_direct_vlm.py', 'v12_evidence.py', 'provider_profile.py', 'provider_ledger.py', 'v12_ledger.py')})
    for name, value in [('selection.json', {'planned_n': 60, 'rows': rows}), ('protocol.json', frozen)]:
        p = out/name
        if p.exists() and read(p) != value: raise ValueError('fixed_input_or_config_conflict:' + name)
        if not p.exists(): write(p, value)
    return rows


def retryable(exc):
    return getattr(exc, 'status_code', None) in {408, 429, 500, 502, 503, 504} or type(exc).__name__ in {'APITimeoutError', 'APIConnectionError', 'TimeoutError'}


def run(args, cfg, out):
    from v12_evidence import question_parts
    rows = prepare(cfg, out); root = Path(cfg['root'])
    records = {}
    for row in rows:
        p = out/'checkpoints'/row['question_id']/'terminal.json'
        if p.exists():
            record = read(p)
            if record.get('question_id') != row['question_id']: raise ValueError('terminal_identity_conflict')
            records[row['question_id']] = record
    attempts = {str(p.parent): read(p) for p in (out/'checkpoints').glob('*/attempt_*/started.json')}
    used = len(attempts)
    extras = sum(Path(p).name != 'attempt_1' for p in attempts)
    def status(state, **extra):
        write(out/'status.json', dict(status=state, updated_utc=now(), planned_n=60,
              completed_n=len(records), valid_n=sum(r.get('answer') is not None for r in records.values()),
              requests_used=used, extra_requests_used=extras, medical_tool_calls=0, **extra))
    if used > 66 or extras > 6: raise ValueError('persistent_request_limit_exceeded')
    if args.prepare_only:
        status('prepared'); print(json.dumps({'status': 'prepared', 'planned_n': 60, 'new_model_calls': 0})); return 0
    if len(records) == 60:
        (out/'predictions.jsonl').write_text(''.join(json.dumps(records[r['question_id']], ensure_ascii=False)+'\n' for r in rows),encoding='utf-8')
        status('generation_complete'); return 0
    key = sys.stdin.readline().strip() if args.api_key_stdin else ''
    if not key: raise ValueError('missing_api_key_on_stdin')
    from langchain_openai import ChatOpenAI
    from provider_profile import get_profile
    from v12_ledger import V12ProviderLedger
    profile = get_profile(cfg['model'])
    model = ChatOpenAI(model=profile.model, base_url=profile.base_url, api_key=key,
                       temperature=cfg['temperature'], top_p=cfg['top_p'], max_tokens=cfg['max_output_tokens'],
                       max_retries=0, timeout=cfg['request_timeout_seconds'])
    del key
    ledger_path = root/cfg['ledger']
    # Read the existing cap once. The inherited interface opens/locks the existing
    # ledger; no fresh budget, byte-drift check, or additional ledger scan is added.
    state = read(ledger_path)
    if state.get('blocked'): raise ValueError('existing_ledger_blocked')
    cap = state['policy']['cap_cny']
    with V12ProviderLedger(ledger_path, profile, cap_cny=cap, inherit_ledger_path=root/cfg['inherit_ledger']) as ledger:
        if not (out/'ledger_start.json').exists():
            write(out/'ledger_start.json', {'committed_cny': str(Decimal(cap)-ledger.remaining), 'cap_cny': cap, 'utc': now()})
        def finish_ledger():
            start = Decimal(read(out/'ledger_start.json')['committed_cny'])
            end = Decimal(cap)-ledger.remaining
            write(out/'ledger_final_summary.json', {'run_increment_cny': str(end-start),
                  'price_basis': profile.price_basis, 'provider_invoice': False, 'utc': now()})
        for index, row in enumerate(rows, 1):
            qid = row['question_id']; folder = out/'checkpoints'/qid
            if qid in records: continue
            started = now(); began = time.monotonic(); messages = request_for(row, root/cfg['image_root'])
            legal = question_parts(row['question'])[1]
            write(folder/'request.json', {'model': profile.model, 'temperature': cfg['temperature'],
                  'top_p': cfg['top_p'], 'max_tokens': cfg['max_output_tokens'], 'messages': messages})
            terminal = {'question_id': qid, 'answer': None, 'status': 'request_failed',
                        'reason_missing': True, 'attempts': [], 'medical_tool_calls': 0, 'started_utc': started}
            stop = None
            for number in (1, 2):
                attempt_dir = folder/f'attempt_{number}'
                start_path = attempt_dir/'started.json'; result_path = attempt_dir/'result.json'
                if result_path.exists():
                    attempt = read(result_path)
                elif start_path.exists():
                    # Never repeat an ambiguous in-flight paid call on resume.
                    if (attempt_dir/'response.json').exists():
                        raw = read(attempt_dir/'response.json')
                        attempt = dict(read(start_path), response_received=True, raw_content=raw.get('content'),
                                       parsed=parse_answer(raw.get('content'), legal),
                                       recovery='saved_response_reused_no_new_request', settlement=None,
                                       error_type=None, elapsed_s=None)
                    else:
                        attempt = dict(read(start_path), response_received=False, error_type='InterruptedUnknown',
                                       retryable=False, elapsed_s=None, settlement=None)
                    write(result_path, attempt)
                else:
                    if used >= 66 or (number == 2 and extras >= 6): break
                    request_id = f'{out.name}:{qid}:{number}'
                    try:
                        reservation = ledger.reserve(request_id=request_id, estimated_input_tokens=min(estimate_tokens(messages), profile.max_input_tokens),
                            max_output_tokens=cfg['max_output_tokens'], model=profile.model,
                            metadata={'question_id': qid, 'arm': 'D0', 'phase': 'direct', 'model_call': number})
                    except Exception as exc:
                        stop = type(exc).__name__ + ':' + str(exc)
                        write(folder/f'reserve_error_{number}.json', {'error_type': type(exc).__name__, 'message': str(exc), 'utc': now(), 'request_sent': False})
                        break
                    used += 1; extras += int(number == 2)
                    attempt = {'question_id': qid, 'ordinal': number, 'request_id': request_id,
                               'started_utc': now(), 'response_received': False}
                    write(start_path, attempt)
                    status('running', active_index=index, active_question=qid, active_started_utc=attempt['started_utc'])
                    tick = time.monotonic(); response = None; usage = None; error = None
                    try:
                        response = model.invoke(messages)
                        raw = response.model_dump(mode='json')
                        write(attempt_dir/'response.json', raw)  # Save before parsing or settlement.
                        usage = getattr(response, 'usage_metadata', None)
                        attempt.update(response_received=True, raw_content=response.content,
                                       response_metadata=response.response_metadata, usage=usage,
                                       parsed=parse_answer(response.content, legal))
                        returned = response.response_metadata.get('model_name')
                        if not profile.identity_ok(returned):
                            error = RuntimeError('returned_model_identity_mismatch'); stop = str(error)
                    except Exception as exc:
                        error = exc
                        attempt.update(error_type=type(exc).__name__, error_message=str(exc)[:1600],
                                       status_code=getattr(exc, 'status_code', None), retryable=retryable(exc))
                        if not retryable(exc): stop = type(exc).__name__
                    finally:
                        attempt['elapsed_s'] = round(time.monotonic()-tick, 3)
                        billed = {'prompt_tokens': usage['input_tokens'], 'completion_tokens': usage['output_tokens']} if usage and 'input_tokens' in usage and 'output_tokens' in usage and error is None else None
                        try:
                            attempt['settlement'] = ledger.settle(reservation, usage=billed,
                                response_received=response is not None, error_type=type(error).__name__ if error else None)
                        except Exception as exc:
                            attempt['settlement_error'] = {'error_type': type(exc).__name__, 'message': str(exc)}
                            stop = type(exc).__name__ + ':' + str(exc)
                        write(result_path, attempt)
                terminal['attempts'].append(attempt)
                if attempt.get('response_received'):
                    terminal.update(attempt.get('parsed') or parse_answer(attempt.get('raw_content'), legal))
                    if stop == 'returned_model_identity_mismatch': terminal.update(answer=None, status='request_failed')
                    break  # No format/content retry after a successful response.
                if stop or not attempt.get('retryable') or number == 2: break
                time.sleep(2)
            if terminal['attempts']:
                terminal.update(ended_utc=now(), elapsed_s=round(time.monotonic()-began, 3))
                write(folder/'terminal.json', terminal); records[qid] = terminal
                print(json.dumps({'event': 'direct_terminal', 'index': index, 'status': terminal['status'],
                                  'requests_used': used, 'elapsed_s': terminal['elapsed_s']}), flush=True)
            if stop or not terminal['attempts']:
                write(out/'fatal_error.json', {'utc': now(), 'error': stop or 'request_limit', 'question_id': qid})
                status('stopped', error=stop or 'request_limit', not_run_n=60-len(records))
                finish_ledger(); return 2
            status('running')
            if index == 2:
                # The first two are formal records, not a separate trial. Only
                # transport/parse/save status is checked; no correctness access.
                print(json.dumps({'event': 'first_two_saved', 'terminal_n': len(records),
                                  'response_received_n': sum(any(a.get('response_received') for a in records[r['question_id']]['attempts']) for r in rows[:2]),
                                  'continuing_remaining': 58, 'labels_read': False}), flush=True)
        # Atomic aggregate is derived only from immutable per-question terminals.
        text = ''.join(json.dumps(records[r['question_id']], ensure_ascii=False)+'\n' for r in rows)
        (out/'predictions.jsonl').write_text(text, encoding='utf-8')
        finish_ledger(); status('generation_complete')
        return 0


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config', type=Path, required=True); p.add_argument('--out', type=Path, required=True)
    p.add_argument('--api-key-stdin', action='store_true'); p.add_argument('--prepare-only', action='store_true')
    p.add_argument('--resume', action='store_true')
    args = p.parse_args(argv); out = args.out.resolve(); out.mkdir(parents=True, exist_ok=True)
    import fcntl
    with (out/'.generation.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try: return run(args, read(args.config), out)
        except Exception as exc:
            write(out/'fatal_error.json', {'error_type': type(exc).__name__, 'message': str(exc)[:2000], 'utc': now()})
            existing = read(out/'status.json') if (out/'status.json').exists() else {}
            write(out/'status.json', dict(existing, status='stopped', updated_utc=now(), error_type=type(exc).__name__))
            print(json.dumps({'status': 'stopped', 'error_type': type(exc).__name__}), flush=True)
            return 2


if __name__ == '__main__': raise SystemExit(main())
