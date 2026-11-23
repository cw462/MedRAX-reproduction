
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


class Services(Original):
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
