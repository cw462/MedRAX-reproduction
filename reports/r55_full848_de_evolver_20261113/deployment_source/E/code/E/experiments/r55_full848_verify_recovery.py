"""Preserve at most two Verify attempts and continue when evidence is unavailable."""

import json
from pathlib import Path
import time
from urllib.error import HTTPError, URLError

from online_memory_r49 import now, read, safe_qid, save_once
from r55_verifier import DeepSeekVerifier as OriginalVerifier, ENDPOINT, MAX_TOKENS, MODEL, SLOT


FIRST_RETRY = 'verify_chexbench_openi_0012_4'
DISPOSITION = 'recovery.full848.json'
TRANSIENT_HTTP = {408, 429, 500, 502, 503, 504}


class VerifyUnavailable(Exception):
    """The recorded Verify attempts produced no usable tool observation."""


def request_id(folder):
    return f'r55:{SLOT}:{folder.parent.name}:{folder.name}'


def failure(folder, *, pending=False):
    if folder.parent.parent.name != SLOT or folder.name not in ('1', '2'):
        return None
    started = folder/'started.json'
    result = folder/'result.json'
    if not started.is_file():
        return None
    if read(started)['request_id'] != request_id(folder):
        raise ValueError('verify_send_receipt_id_changed')
    if not result.is_file():
        if pending and not (folder/'response.json').exists():
            return 'verify_interrupted_without_saved_response'
        return None
    receipt = read(result)
    if (receipt['request_id'] != request_id(folder)
            or receipt['response_received'] != (folder/'response.json').is_file()):
        raise ValueError('verify_attempt_receipt_changed')
    return receipt.get('error')


def accounted_verify_failure(folder, require_receipts):
    error = failure(folder, pending=not require_receipts)
    if not error:
        return False
    if not all((folder/name).is_file() for name in ('request.json', 'endpoint.json', 'started.json')):
        return False
    if read(folder/'endpoint.json') != {'url': ENDPOINT}:
        raise ValueError('verify_endpoint_changed')
    if folder.name == '2' and read(folder/'request.json') != read(folder.parent/'1/request.json'):
        raise ValueError('verify_retry_payload_changed')
    note = folder.parent/DISPOSITION
    if not note.is_file():
        # The active question can replay a recorded failure before its observation is saved.
        return not require_receipts
    disposition = read(note)
    return disposition['attempt_errors'].get(folder.name) == error


def retryable(folder, error):
    receipt = read(folder/'result.json')
    if error == 'HTTPError':
        return (receipt.get('http_status') in TRANSIENT_HTTP
                or (folder.parent.name == FIRST_RETRY and receipt.get('http_status') is None))
    return error in ('URLError', 'TimeoutError', 'ConnectionError', 'ConnectionResetError',
                     'ConnectionAbortedError', 'BrokenPipeError')


class RecoverableVerifier(OriginalVerifier):
    def _attempt(self, folder, payload):
        save_once(folder/'request.json', payload)
        save_once(folder/'endpoint.json', {'url': ENDPOINT})
        started, response, result = (folder/f'{name}.json' for name in ('started', 'response', 'result'))
        identity = request_id(folder)
        elapsed = None
        if response.is_file():
            if not started.is_file() or read(started)['request_id'] != identity:
                raise ValueError('saved_verifier_response_without_matching_send_receipt')
            raw = read(response)
        elif started.is_file():
            error = failure(folder, pending=True)
            if error is None:
                raise ValueError('verify_started_without_terminal_failure')
            if not result.is_file():
                save_once(result, {'request_id': identity, 'utc': now(), 'response_received': False,
                                   'error': error, 'elapsed_s': None})
            return None, error
        else:
            save_once(started, {'request_id': identity, 'utc': now()})
            tick = time.monotonic()
            try:
                raw = self._send(payload)
            except (URLError, TimeoutError, ConnectionError, json.JSONDecodeError) as exc:
                error = type(exc).__name__
                metadata = {}
                if isinstance(exc, HTTPError):
                    metadata['http_status'] = exc.code
                    try:
                        metadata['error_body'] = exc.read().decode('utf-8', errors='replace')
                    except OSError:
                        metadata['error_body'] = None
                    finally:
                        exc.close()
                save_once(result, {'request_id': identity, 'utc': now(), 'response_received': False,
                                   'error': error, 'elapsed_s': time.monotonic()-tick, **metadata})
                return None, error
            elapsed = time.monotonic()-tick
            save_once(response, raw)

        metadata = raw if isinstance(raw, dict) else {}
        choices = metadata.get('choices')
        choice = choices[0] if isinstance(choices, list) and choices and isinstance(choices[0], dict) else {}
        message = choice.get('message')
        content = message.get('content') if isinstance(message, dict) else None
        error = None
        if metadata.get('model') != MODEL:
            error = 'r55_verifier_model_mismatch'
        elif choice.get('finish_reason') != 'stop':
            error = 'r55_verifier_incomplete_response'
        elif not isinstance(content, str) or not content.strip():
            error = 'r55_verifier_missing_content'
        fields = {'request_id': identity, 'response_received': True, 'error': error,
                  'model_returned': metadata.get('model'), 'usage': metadata.get('usage')}
        if result.is_file():
            receipt = read(result)
            if any(receipt.get(key) != value for key, value in fields.items()):
                raise ValueError('r55_verifier_result_receipt_mismatch')
        else:
            save_once(result, {**fields, 'utc': now(), 'elapsed_s': elapsed})
        return (None, error) if error else (content, None)

    def __call__(self, event, messages):
        root = self.out/'calls'/SLOT/safe_qid(event)
        payload = {'model': MODEL, 'messages': messages, 'stream': False,
                   'enable_thinking': True, 'reasoning_effort': 'high', 'max_tokens': MAX_TOKENS}
        first = root/'1'
        content, error = self._attempt(first, payload)
        if not error:
            return content
        errors = {'1': error}
        selected = '1'
        if retryable(first, error):
            selected = '2'
            content, error = self._attempt(root/selected, read(first/'request.json'))
            if error:
                errors[selected] = error
        save_once(root/DISPOSITION, {'attempt_errors': errors, 'terminal_attempt': selected,
                                    'usable': error is None})
        if error:
            raise VerifyUnavailable(error)
        return content


def terminal_receipt(first_attempt):
    event = Path(first_attempt).parent
    note = event/DISPOSITION
    attempt = read(note)['terminal_attempt'] if note.is_file() else '1'
    return event/attempt/'result.json'
