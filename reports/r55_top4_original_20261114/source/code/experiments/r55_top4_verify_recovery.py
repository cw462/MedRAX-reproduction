"""Account for terminal Verify failures and preserve the original request."""

from online_memory_r49 import read, save_once


NOTE = 'unavailable.top4.json'
LEGACY_REQUEST_ERRORS = {
    'HTTPError', 'URLError', 'TimeoutError', 'ConnectionError', 'ConnectionResetError',
    'ConnectionRefusedError', 'BrokenPipeError', 'RemoteDisconnected',
    'IncompleteRead', 'BadStatusLine', 'SSLError', 'JSONDecodeError', 'UnicodeDecodeError',
}


def inspect_reply(raw, expected_model):
    """Return the usable answer or the reason the provider reply is unusable."""
    if not isinstance(raw, dict):
        return {}, None, 'r55_verifier_invalid_response'
    if raw.get('model') != expected_model:
        return raw, None, 'r55_verifier_model_mismatch'
    choices = raw.get('choices')
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        return raw, None, 'r55_verifier_incomplete_response'
    choice = choices[0]
    if choice.get('finish_reason') != 'stop':
        return raw, None, 'r55_verifier_incomplete_response'
    message = choice.get('message')
    content = message.get('content') if isinstance(message, dict) else None
    if not isinstance(content, str) or not content.strip():
        return raw, None, 'r55_verifier_missing_content'
    return raw, content, None


def disposition(folder):
    if folder.name != '1' or folder.parent.parent.name != 'R55-VERIFY':
        return None
    result, started, request = (folder / name for name in
                                ('result.json', 'started.json', 'request.json'))
    if not all(path.is_file() for path in (result, started, request)):
        return None
    receipt = read(result)
    error = receipt.get('error')
    if not isinstance(error, str) or not error:
        return None
    identity = f'r55:R55-VERIFY:{folder.parent.name}:1'
    if receipt.get('request_id') != identity or read(started).get('request_id') != identity:
        return None
    response = folder / 'response.json'
    if receipt.get('response_received') is True and response.is_file():
        reply, _, reply_error = inspect_reply(read(response), read(request)['model'])
        if (reply_error, reply.get('model'), reply.get('usage')) != (
                error, receipt.get('model_returned'), receipt.get('usage')):
            return None
        exception = error
        reason = error.removeprefix('r55_verifier_')
        choices = reply.get('choices')
        if (error == 'r55_verifier_incomplete_response' and isinstance(choices, list)
                and choices and isinstance(choices[0], dict)
                and choices[0].get('finish_reason') == 'length'):
            reason = 'length'
    else:
        if receipt.get('response_received') is not False or response.exists():
            return None
        if not (receipt.get('failure_stage') == 'transport' and error.isidentifier()
                or error in LEGACY_REQUEST_ERRORS):
            return None
        reason = 'http' if error == 'HTTPError' else 'transport'
        exception = 'r55_verifier_transport_failed:' + error
    return {'request_id': identity, 'response_received': receipt['response_received'],
            'reason': f'verify_{reason}_no_usable_response', 'exception': exception, 'resent': False}


def account(folder, error):
    note = disposition(folder)
    if note is None or note['exception'] != str(error):
        return None
    save_once(folder / NOTE, note)
    return note['reason']


def accounted(folder, require_receipts):
    note = disposition(folder)
    if note is None:
        return False
    path = folder / NOTE
    return read(path) == note if path.is_file() else not require_receipts
