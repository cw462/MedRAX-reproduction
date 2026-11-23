"""Candidate-side client for a coordinator-registered native service session."""

import base64
import json
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen


class NativeServices:
    def __init__(self, gateway_url, model, limits, seed):
        self.url = gateway_url.rstrip('/')
        self.metadata = self._request('metadata', {})
        if self.metadata['model'] != model or self.metadata['limits'] != limits:
            raise RuntimeError('native gateway model or limits differ from the registered session')
        if self.metadata['seed'] != seed:
            raise RuntimeError('native gateway seed differs from the registered session')
        self.runtime_catalog = self.metadata['runtime_catalog']
        self.protocol = self.metadata['protocol']
        self.image_views = self.metadata['image_views']

    def _request(self, operation, payload):
        request = Request(self.url + '/' + operation,
                          data=json.dumps(payload, ensure_ascii=False, allow_nan=False).encode(),
                          headers={'Content-Type': 'application/json'}, method='POST')
        try:
            with urlopen(request, timeout=900) as stream:
                result = json.load(stream)
        except HTTPError as error:
            detail = json.loads(error.read())
            raise RuntimeError('native gateway rejected request: ' + detail.get('error', 'request_failed')) from None
        if result.get('ok') is not True:
            raise RuntimeError('native gateway request failed')
        return result['result']

    def main(self, messages):
        return self._request('main', {'messages': messages})

    def memory(self, messages):
        return self._request('memory', {'messages': messages})

    def embed(self, text):
        return self._request('embed', {'text': text})

    def tool(self, row, action, ordinal):
        result = self._request('tool', {'row': row, 'action': action, 'ordinal': ordinal})
        observation = result['observation']
        paths = []
        for item in result['images']:
            name = item['name']
            if Path(name).name != name:
                raise RuntimeError('invalid native tool image name')
            target = Path('/state/tool_cache/gateway') / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(base64.b64decode(item['base64'], validate=True))
            paths.append(str(target))
        if paths or 'derived_images' in observation:
            observation['derived_images'] = paths
        return observation

    def usage_receipt(self):
        return self._request('usage', {})


def create_services(gateway_url, model, limits, seed):
    return NativeServices(gateway_url, model, limits, seed)
