"""One same-request retry for the saved EvolveR SLAKE provider rejection."""

from hashlib import sha256
import json
from pathlib import Path
import time

from online_memory_r49 import now, read, save_once


QID = 'slake_12393'
ROLE = 'R49-AGENT'
ORDINAL = 2
REVISION = 'slake_main_retry001'
ORIGINAL_SHA = 'e29915182372f570a39ad59fae25b75b01a24aad69d0e0c47e46877b47f75606'
TARGET = Path('calls') / ROLE / QID / str(ORDINAL)


class MainUnavailable(Exception):
    """The authorized replacement was sent and yielded no usable response."""


def history(service_root):
    return Path(service_root) / 'main_call_recovery' / QID / str(ORDINAL)


def matches(run, folder):
    run = Path(run)
    return run.name == 'slake' and run.parent.name == 'E' and folder == run/'services'/TARGET


def validate_attempt(folder, *, first):
    request = (folder/'request.json').read_bytes()
    if sha256(request).hexdigest() != ORIGINAL_SHA:
        raise ValueError('slake_main_retry_request_bytes_changed')
    started = read(folder/'started.json')
    result = read(folder/'result.json')
    response = (folder/'response.json').is_file()
    request_id = started['request_id']
    if result['request_id'] != request_id or result['response_received'] is not response:
        raise ValueError('slake_main_retry_receipts_changed')
    if first:
        error = result.get('error') or ''
        if (response or request_id.endswith(':retry2') or 'Error code: 500' not in error
                or 'StatusCode=503' not in error or 'QpsLimitExceeded' not in error):
            raise ValueError('slake_main_retry_original_failure_changed')
    elif not request_id.endswith(':retry2'):
        raise ValueError('slake_main_retry_request_identity_changed')
    return request, result


def validate_payload(service, messages, original):
    protocol = service.paid.protocol
    candidate = {'model': protocol['model'], 'messages': messages, 'temperature': protocol['temperature'],
                 'top_p': protocol['top_p'], 'max_tokens': protocol['max_output_tokens'],
                 'extra_body': {'enable_thinking': False}, 'stream': False}
    encoded = (json.dumps(candidate, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
    if encoded != original:
        raise ValueError('slake_main_retry_replayed_request_bytes_changed')
    return candidate


def retry_main(service, messages):
    from openai import APIError
    from run_cxr_vqa_toolsets import invoke, safe_error, save

    paid = service.paid
    folder = service.out/TARGET
    lineage = history(service.out)
    first = lineage/'1'
    original, _ = validate_attempt(first, first=True)
    payload = validate_payload(service, messages, original)
    if paid.uses_shared_ledger:
        raise ValueError('slake_main_retry_unexpected_shared_ledger')
    request_id = read(first/'started.json')['request_id'] + ':retry2'
    start, response, result = (folder/f'{name}.json' for name in ('started', 'response', 'result'))
    if start.is_file():
        if not result.is_file():
            raise RuntimeError('slake_main_retry_second_send_unknown_no_reissue')
        _, receipt = validate_attempt(folder, first=False)
        raw = read(response) if response.is_file() else None
        error = receipt['error']
    else:
        if response.exists() or result.exists():
            raise ValueError('slake_main_retry_response_without_send_receipt')
        folder.mkdir(exist_ok=True)
        if not (folder/'request.json').exists():
            with (folder/'request.json').open('xb') as handle:
                handle.write(original)
        if (folder/'request.json').read_bytes() != original:
            raise ValueError('slake_main_retry_second_archive_bytes_changed')
        save(start, {'request_id': request_id, 'utc': now(), 'reserved': None})
        tick = time.monotonic()
        raw, error = None, None
        try:
            raw = invoke(paid.client, payload, folder)
        except APIError as exc:
            error = safe_error(exc, paid.key)
        if raw is not None and not usable(paid, raw):
            error = 'retry_returned_unusable_model_or_content'
        settlement = paid.response_cost(raw)
        save(result, {'request_id': request_id, 'model_returned': raw.get('model') if raw else None,
             'usage': raw.get('usage') if raw else None, 'settlement': settlement,
             'elapsed_s': time.monotonic()-tick, 'error': error, 'response_received': raw is not None,
             'utc': now(), 'ledger_remaining_proxy_cny': settlement['remaining_cny']})
        validate_attempt(folder, first=False)
    if error:
        disposition = 'unanswered_after_two_attempts'
    elif usable(paid, raw):
        disposition = 'usable_replacement'
    else:
        raise ValueError('slake_main_retry_unaccounted_unusable_response')
    save_once(lineage/'outcome.json', {'schema': REVISION, 'question_id': QID, 'logical_ordinal': ORDINAL,
              'first_attempt': str(first.relative_to(service.out)),
              'second_attempt': str(TARGET), 'request_sha256': ORIGINAL_SHA, 'disposition': disposition})
    if error:
        raise MainUnavailable
    return raw['choices'][0]['message']['content']


def usable(paid, raw):
    if not isinstance(raw, dict) or not paid.profile.identity_ok(raw.get('model')):
        return False
    choices = raw.get('choices')
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        return False
    message = choices[0].get('message')
    return (isinstance(message, dict) and isinstance(message.get('content'), str)
            and bool(message['content'].strip()))


def accounted_main_failure(run, folder, require_receipts, *, offline_original=False):
    if not matches(run, folder):
        return False
    lineage = history(Path(run)/'services')
    first = lineage/'1'
    if offline_original and not first.exists():
        validate_attempt(folder, first=True)
        return not require_receipts
    if not first.exists():
        return False
    validate_attempt(first, first=True)
    _, result = validate_attempt(folder, first=False)
    if not result.get('error'):
        return False
    outcome = lineage/'outcome.json'
    return ((outcome.is_file() and read(outcome)['disposition'] == 'unanswered_after_two_attempts')
            or not require_receipts)


def unanswered_source(run, qid, prediction):
    if qid != QID or prediction.get('status') != 'main_response_unavailable_after_retry':
        return None
    folder = Path(run)/'services'/TARGET
    if (not accounted_main_failure(run, folder, True) or prediction.get('answer') is not None
            or prediction.get('terminal_raw') is not None or prediction['main_calls'] != ORDINAL):
        raise ValueError('slake_main_unanswered_evidence_mismatch')
    return {'raw': None, 'call_path': str(folder), 'ordinal': folder.name, 'reuse_chain': [],
            'technical_stop': True, 'evidence_status': 'unanswered_after_two_attempts'}


def original_results(run, role):
    service_root = Path(run)/'services'
    first = history(service_root)/'1'
    if role != ROLE or not matches(run, service_root/TARGET) or not first.is_dir():
        return []
    return [validate_attempt(first, first=True)[1]]
