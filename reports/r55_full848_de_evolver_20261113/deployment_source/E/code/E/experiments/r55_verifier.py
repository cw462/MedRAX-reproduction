"""Model Studio DeepSeek vision transport for the shared R55 verifier."""

import json
import time
import urllib.request
from pathlib import Path

from online_memory_r49 import now, read, safe_qid, save_once

SLOT = 'R55-VERIFY'
MODEL = 'deepseek-v4.1-flash-1017'
BASE_URL = 'https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1'
ENDPOINT = BASE_URL + '/chat/completions'
CREDENTIAL_SLOT = 'token_plan'
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
            raise ValueError('R55 verify requires the shared Token Plan credential')
        self.out = Path(out)
        self.key = key.strip()

    def _send(self, payload):
        request = urllib.request.Request(
            ENDPOINT, data=json.dumps(payload, ensure_ascii=False).encode('utf-8'),
            headers={'Authorization': '[REDACTED]' + self.key, 'Content-Type': 'application/json'},
        )
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
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
            if started.exists():
                raise RuntimeError('unknown_r55_verifier_send_no_retry:' + event)
            save_once(started, {'request_id': request_id, 'utc': now()})
            tick = time.monotonic()
            try:
                raw = self._send(payload)
            except Exception as error:
                save_once(result, {'request_id': request_id, 'utc': now(),
                                   'response_received': False, 'error': type(error).__name__,
                                   'elapsed_s': time.monotonic() - tick})
                raise RuntimeError('r55_verifier_transport_failed:' + type(error).__name__) from None
            elapsed = time.monotonic() - tick
            save_once(response, raw)
        error = None
        choice = (raw.get('choices') or [{}])[0]
        message = choice.get('message') or {}
        content = message.get('content')
        if raw.get('model') != MODEL:
            error = 'r55_verifier_model_mismatch'
        elif choice.get('finish_reason') != 'stop':
            error = 'r55_verifier_incomplete_response'
        elif not isinstance(content, str) or not content.strip():
            error = 'r55_verifier_missing_content'
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
