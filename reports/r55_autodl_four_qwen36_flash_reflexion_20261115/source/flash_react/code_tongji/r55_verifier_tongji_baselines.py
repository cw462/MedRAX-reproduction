from r55_timeout_recovery import VerifyUnavailable, timeout
from r55_top4_verify_recovery import disposition, inspect_reply
"""Model Studio DeepSeek vision transport for the shared R55 verifier."""

import json
import time
import urllib.request
from http.client import HTTPException
from urllib.error import HTTPError
from pathlib import Path

from online_memory_r49 import now, read, safe_qid, save_once

SLOT = 'R55-VERIFY'
from r55_tongji_deepseek_baselines import BASE_URL, ENDPOINT, MODEL, urlopen
CREDENTIAL_SLOT = 'tongji_agi'
MAX_TOKENS = 8192
TIMEOUT = 120


def profile():
    return {'model': MODEL, 'endpoint': ENDPOINT, 'enable_thinking': True,
            'reasoning_effort': 'high', 'max_tokens': MAX_TOKENS,
            'timeout_seconds': TIMEOUT, 'image_payload': 'original_file_bytes',
            'credential_slot': CREDENTIAL_SLOT}


class DeepSeekVerifier:
    def __init__(self, out, key):
        if not key or not key.strip():
            raise ValueError('R55 verify requires the Tongji AGI credential')
        self.out = Path(out)
        self.key = key.strip()

    def _send(self, payload):
        request = urllib.request.Request(
            ENDPOINT, data=json.dumps(payload, ensure_ascii=False).encode('utf-8'),
            headers={'Authorization': 'Bearer ' + self.key, 'Content-Type': 'application/json'},
        )
        with urlopen(request, timeout=TIMEOUT) as response:
            return json.load(response)

    def __call__(self, event, messages):
        event = safe_qid(event)
        folder = self.out / 'calls' / SLOT / event / '1'
        payload = {'model': MODEL, 'messages': messages, 'stream': False,
                   'enable_thinking': True, 'reasoning_effort': 'high',
                   'max_tokens': MAX_TOKENS}
        response = folder / 'response.json'
        started = folder / 'started.json'
        result = folder / 'result.json'
        request_id = f'r55:{SLOT}:{event}:1'
        save_once(folder / 'request.json', payload)
        save_once(folder / 'endpoint.json', {'url': ENDPOINT})
        elapsed = None
        if response.is_file():
            if not started.is_file():
                raise ValueError('saved_verifier_response_without_send_receipt')
            raw = read(response)
        else:
            if timeout(folder):
                raise VerifyUnavailable('verify_timeout_no_response')
            if started.exists():
                failure = disposition(folder)
                if failure is not None:
                    raise RuntimeError(failure['exception'])
                raise RuntimeError('unknown_r55_verifier_send_no_retry:' + event)
            save_once(started, {'request_id': request_id, 'utc': now()})
            tick = time.monotonic()
            try:
                raw = self._send(payload)
            except (OSError, HTTPException, json.JSONDecodeError, UnicodeError) as error:
                transport = {'http_status': error.code} if isinstance(error, HTTPError) else {}
                save_once(result, {'request_id': request_id, 'utc': now(),
                                   'response_received': False, 'error': type(error).__name__,
                                   'failure_stage': 'transport',
                                   'elapsed_s': time.monotonic() - tick, **transport})
                if isinstance(error, TimeoutError):
                    raise VerifyUnavailable('verify_timeout_no_response') from None
                raise RuntimeError('r55_verifier_transport_failed:' + type(error).__name__) from None
            elapsed = time.monotonic() - tick
            save_once(response, raw)
        raw, content, error = inspect_reply(raw, MODEL)
        if not result.is_file():
            save_once(result, {'request_id': request_id, 'utc': now(),
                               'response_received': True, 'error': error,
                               'model_returned': raw.get('model'), 'usage': raw.get('usage'),
                               'elapsed_s': elapsed})
        else:
            receipt = read(result)
            if (receipt.get('request_id'), receipt.get('response_received'), receipt.get('error'),
                    receipt.get('model_returned'), receipt.get('usage')) != (
                    request_id, True, error, raw.get('model'), raw.get('usage')):
                raise ValueError('r55_verifier_result_receipt_mismatch')
        if error:
            raise ValueError(error)
        return content
