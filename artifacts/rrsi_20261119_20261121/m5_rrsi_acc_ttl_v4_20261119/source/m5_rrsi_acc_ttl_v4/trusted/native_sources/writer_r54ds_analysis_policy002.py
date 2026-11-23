
"""One user-authorized exclusion of an already received Analysis."""
import json
from pathlib import Path

from cxr_online_primitives_r49 import read
from writer_r54ds import Services as Original, validate_writer

EVENT = 'analysis_chexbench_rad_restruct_0133'
QID = EVENT.removeprefix('analysis_')
ERROR = 'thinking_not_observed_no_silent_fallback'
ATTEMPT = Path('services/calls/R54DS-WRITER') / EVENT / '1'


def received_failure(out):
    folder = Path(out) / ATTEMPT
    request = read(folder / 'request.json')
    raw = read(folder / 'response.json')
    receipt = read(folder / 'result.json')
    choice = raw['choices'][0]
    message = choice['message']
    if not (
        (folder / 'started.json').is_file()
        and not (folder / 'validation.json').exists()
        and set(folder.parent.iterdir()) == {folder}
        and request['model'] == raw['model'] == 'deepseek-flash'
        and request['thinking'] == {'type': 'enabled'}
        and request['reasoning_effort'] == 'high'
        and request['max_tokens'] == 16384
        and choice['finish_reason'] == 'stop'
        and message['reasoning_content'] == ''
        and len(message['content']) == 2433
        and raw['usage']['completion_tokens_details']['reasoning_tokens'] == 0
        and receipt == {'response_received': True, 'error': ERROR,
                        'model_returned': raw['model'], 'usage': raw['usage']}
    ):
        raise ValueError('bound_analysis_failure_changed')
    return request


class BoundServices(Original):
    def skip_bound_analysis(self, system, payload, image_row, data):
        content = [{'type': 'text', 'text': json.dumps(payload, ensure_ascii=False)}]
        content += self.base.content(image_row, Path(data))
        expected = {
            'model': self.writer['model'],
            'messages': [{'role': 'system', 'content': system},
                         {'role': 'user', 'content': content}],
            'thinking': self.writer['thinking'], 'max_tokens': self.writer['max_tokens'],
            'stream': False, 'reasoning_effort': self.writer['reasoning_effort'],
        }
        out = self.out.parent
        if received_failure(out) != expected:
            raise ValueError('bound_analysis_request_changed')
        if read(out / ATTEMPT / 'endpoint.json') != {'base_url': self.writer['base_url']}:
            raise ValueError('bound_analysis_endpoint_changed')
        return {'event': EVENT, 'attempt': str(ATTEMPT), 'status': 'skipped_received_invalid',
                'reason': ERROR, 'window': 1, 'new_requests': 0}


class AnalysisOmitted(Exception):
    def __init__(self, receipt):
        super().__init__(receipt['reason'])
        self.receipt = receipt


def empty_thinking_receipt(root, folder, writer):
    """Identify a received Analysis rejection without interpreting its body."""
    root, folder = Path(root), Path(folder)
    event = folder.parent.name
    if (folder.parent.parent != root / 'services/calls/R54DS-WRITER'
            or not event.startswith('analysis_') or folder.name not in ('1','2')):
        return None
    if not all((folder / name).is_file() for name in
               ('request.json','started.json','response.json','result.json','endpoint.json')):
        return None
    result = read(folder / 'result.json')
    if result.get('error') != ERROR:
        return None
    request, raw, endpoint = (
        read(folder / name) for name in ('request.json','response.json','endpoint.json'))
    choices = raw.get('choices')
    if not isinstance(choices, list) or len(choices) != 1:
        return None
    choice = choices[0]
    message = choice.get('message', {})
    reasoning = message.get('reasoning_content')
    content = message.get('content')
    if not (
        request.get('model') == writer['model']
        and request.get('thinking') == writer['thinking'] == {'type':'enabled'}
        and request.get('reasoning_effort') == writer['reasoning_effort']
        and request.get('max_tokens') == writer['max_tokens']
        and endpoint == {'base_url':writer['base_url']}
        and raw.get('model') in writer['expected_returned_models']
        and choice.get('finish_reason') == 'stop'
        and isinstance(reasoning, str) and not reasoning.strip()
        and isinstance(content, str) and content.strip()
        and not (folder / 'validation.json').exists()
        and result == {'response_received':True,'error':ERROR,
                       'model_returned':raw.get('model'),'usage':raw.get('usage')}
        and (folder.name == '2' or not (folder.parent / '2').exists())
    ):
        return None
    return {'event':event,'attempt':str(folder.relative_to(root)),
            'status':'skipped_received_invalid','reason':ERROR,'new_requests':0}


class Services(BoundServices):
    def meta(self, event, system, payload, image_row=None, data=None):
        try:
            return super().meta(event, system, payload, image_row, data)
        except ValueError as exc:
            if str(exc) != ERROR or not event.startswith('analysis_'):
                raise
            root = self.out.parent
            directory = self.out / 'calls/R54DS-WRITER' / event
            folder = directory / ('2' if (directory / '2').exists() else '1')
            receipt = empty_thinking_receipt(root, folder, self.writer)
            if receipt is None:
                raise
            from online_memory_r49 import save_once
            save_once(self.out / 'analysis_skips' / (event+'.json'), receipt)
            raise AnalysisOmitted(receipt) from exc
