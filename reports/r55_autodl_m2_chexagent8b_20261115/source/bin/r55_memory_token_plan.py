"""Token Plan transport for the AutoDL DeepSeek memory writer."""

import json
from urllib.error import HTTPError
from urllib.request import Request, urlopen


TOKEN_PLAN = 'https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1'
MODEL = 'deepseek-v4.1-flash'
LOGICAL_MODEL = 'deepseek-flash'
MARKER = 'memory-writer-token-plan.json'
ROUTE = {'transport': 'token_plan', 'endpoint': TOKEN_PLAN + '/chat/completions',
         'model_requested': MODEL, 'logical_model': LOGICAL_MODEL, 'enable_thinking': False}


def enabled(root):
    path = root / 'jobs' / MARKER
    if not path.is_file():
        return False
    if json.loads(path.read_bytes()).get('writer') != ROUTE:
        raise ValueError('Invalid recorded AutoDL memory writer route')
    return True


def wire_request(logical):
    if (logical['model'], logical['thinking'], logical['stream']) != (LOGICAL_MODEL, {'type': 'disabled'}, False):
        raise ValueError('The DeepSeek memory request no longer matches the frozen protocol')
    payload = dict(logical, model=MODEL, enable_thinking=False)
    del payload['thinking']
    return payload


def valid_response(response):
    message = response['choices'][0]['message']
    return response.get('model') == MODEL and not message.get('reasoning_content')


def probe(key):
    logical = {'model': LOGICAL_MODEL,
               'messages': [{'role': 'user', 'content': [{'type': 'text', 'text': 'Reply with just OK.'}]}],
               'stream': False, 'thinking': {'type': 'disabled'}, 'max_tokens': 32, 'temperature': 0}
    request = Request(ROUTE['endpoint'], data=json.dumps(wire_request(logical)).encode(),
                      headers={'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json'})
    try:
        with urlopen(request, timeout=20) as handle:
            response = json.load(handle)
    except HTTPError as exc:
        return {'state': 'writer_unavailable', 'http_status': exc.code, 'writer': ROUTE}
    choice = response['choices'][0]
    if not valid_response(response) or choice['finish_reason'] != 'stop' or not choice['message'].get('content'):
        raise ValueError('The Token Plan writer probe did not return a usable non-thinking response')
    return {'state': 'available', 'model_returned': response['model']}
