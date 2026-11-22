"""Continue Flash Reflexion after a provider rejects an unchanged JPEG request."""

import base64
import io
import json
from pathlib import Path
import sys

import r55_deepseek_rerun_runtime as runtime


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'flash/flash_react'
DATASET = 'chexbench'
QID = 'chexbench_slake_0079'
ARM = 'reflexion_retry'
ORDINAL = 1
MODEL = 'qwen3.6-flash'
API = OUT / 'api' / DATASET
REPLAY = OUT / 'replay' / DATASET
REJECTED = API / 'calls' / ARM / QID / str(ORDINAL)
RETRY_ROLE = ARM + '_request_retry1'
RETRY = API / 'calls' / RETRY_ROLE / QID / str(ORDINAL)


def images(request):
    return [part['image_url']['url']
            for message in request['messages'] if isinstance(message['content'], list)
            for part in message['content'] if part['type'] == 'image_url']


def checkpoint():
    from PIL import Image

    receipt = runtime.read(REJECTED / 'result.json')
    reason = str(receipt.get('error'))
    if (receipt.get('response_received') is not False or (REJECTED / 'response.json').exists()
            or 'Error code: 400' not in reason or 'invalid_parameter_error' not in reason
            or 'provided URL does not appear to be valid' not in reason):
        raise ValueError('The saved case does not have the expected rejected image request')
    request = runtime.read(REJECTED / 'request.json')
    earlier = runtime.read(REPLAY / f'{QID}.json')
    refs = images(request)
    if (request.get('model') != MODEL or earlier['result'].get('model_returned') != MODEL
            or earlier['result'].get('response_received') is not True
            or len(refs) != 1 or refs[0] != images(earlier['request'])[0]
            or refs[0].get('media_type') != 'image/jpeg'):
        raise ValueError('The rejected request does not match the JPEG in the successful same-case ReAct')
    name = refs[0]['cxr_request_image_base64_sha256']
    encoded = (API / 'request_image_base64' / name).read_bytes()
    if encoded != (REPLAY / 'request_image_base64' / name).read_bytes():
        raise ValueError('Archived input bytes differ')
    with Image.open(io.BytesIO(base64.b64decode(encoded, validate=True))) as img:
        if img.format != 'JPEG':
            raise ValueError('Archived image is not a JPEG')
        img.verify()
    return request


def run():
    request = checkpoint()
    if (RETRY / 'started.json').exists():
        raise ValueError('The one identical request retry has already been attempted')
    runtime.save(RETRY / 'request.json', request)
    sys.path.insert(0, str(OUT / 'code'))
    import run_qwen_baselines as native

    original = native.Baselines.call

    def call(self, row, arm, ordinal, messages):
        if (row['question_id'], arm, ordinal) != (QID, ARM, ORDINAL):
            return original(self, row, arm, ordinal, messages)
        # PaidCalls compares the new canonical payload with the staged original before sending.
        raw = self.paid.call(row, RETRY_ROLE, ordinal, messages)
        if raw is None:
            return ''
        if not isinstance(raw, str):
            raise TypeError('Unexpected Qwen message format')
        return raw

    native.Baselines.call = call
    native.main()


if __name__ == '__main__':
    if sys.argv[1:] == ['--check', 'flash', DATASET]:
        checkpoint()
        print(json.dumps({'question': QID, 'arm': ARM, 'ordinal': ORDINAL, 'validated_jpeg': True}))
    else:
        run()
