"""Protected M5 services with coordinator-only Unix-socket registration."""

from __future__ import annotations

import argparse
import base64
import copy
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib
import json
import mimetypes
import os
from pathlib import Path
import secrets
import socket
import socketserver
import sys
import threading
import time
from urllib.request import Request, urlopen


class GatewayError(RuntimeError):
    pass


def validate_binding(config):
    protocol = config['protocol']
    if (protocol['model'] != 'qwen3.7-plus' or protocol['max_output_tokens'] != 2048
            or protocol['temperature'] != 0.2 or protocol['top_p'] != 0.95
            or protocol['enable_thinking'] is not False):
        raise GatewayError('original_qwen_protocol_not_bound')
    limits = config['limits']
    if limits['output_tokens'] != 2048:
        raise GatewayError('native_per_response_output_limit_changed')
    for name in ('model_calls', 'tool_calls'):
        value = limits[name]
        if value is not None and (type(value) is not int or value <= 0):
            raise GatewayError('invalid_native_call_limit')
    runtime = config['runtime']
    names = runtime['arms']['M']['tools']
    expected = {'chest_xray_expert', 'llava_med_qa', 'medgemma', 'llava_rad', 'medvlm_r1',
                'maira2_grounded_report', 'xray_phrase_grounding', 'roi_crop', 'medret', 'reflect', 'verify'}
    if len(names) != 11 or set(names) != expected:
        raise GatewayError('eleven_native_tools_required')
    if runtime['tools']['chest_xray_expert']['revision'] != '4934e91451945c8218c267aae9c34929a7677829':
        raise GatewayError('original_chexagent8b_revision_required')
    if config['deepseek_memory_profile'] != {'model': 'deepseek-flash', 'max_tokens': 2048,
                                           'temperature': 0, 'thinking': {'type': 'disabled'}}:
        raise GatewayError('native_memory_profile_changed')
    if config['deepseek_verify_profile'] != {'model': 'deepseek-flash', 'max_tokens': 8192,
                                           'reasoning_effort': 'high', 'thinking': {'type': 'enabled'}}:
        raise GatewayError('native_verifier_profile_changed')


def store(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    pending = path.with_suffix('.pending')
    pending.write_text(json.dumps(value, ensure_ascii=False, allow_nan=False) + '\n')
    pending.replace(path)


def read_key(path):
    if isinstance(path, dict):
        lines = [line.strip() for line in Path(path['path']).read_text().splitlines() if line.strip()]
        index = path['line']
        if type(index) is not int or index < 0 or index >= len(lines):
            raise GatewayError('native_credential_line_unavailable')
        return lines[index]
    value = Path(path).read_text().strip()
    if not value:
        raise GatewayError('empty_native_credential')
    return value


def image_url(path):
    mime = mimetypes.guess_type(path.name)[0] or 'image/jpeg'
    return 'data:' + mime + ';base64,' + base64.b64encode(path.read_bytes()).decode()


def model_tokens(raw):
    usage = raw.get('usage')
    if not isinstance(usage, dict):
        raise GatewayError('missing_native_model_usage')
    total = usage.get('total_tokens')
    if total is None and all(type(usage.get(k)) is int for k in ('prompt_tokens', 'completion_tokens')):
        total = usage['prompt_tokens'] + usage['completion_tokens']
    if type(total) is not int or total < 0:
        raise GatewayError('invalid_native_model_usage')
    return total


def rebase_native_cache(root):
    """Rebind native artifact paths after the coordinator copies a snapshot."""
    root = Path(root).resolve()
    marker = root / 'cache_root.json'
    previous = json.loads(marker.read_text())['root'] if marker.is_file() else str(root)
    if previous != str(root):
        prefix = previous.rstrip(os.sep) + os.sep

        def rewrite(value, key=None):
            if isinstance(value, dict):
                return {k: rewrite(v, k) for k, v in value.items()}
            if isinstance(value, list):
                return [rewrite(v, key) for v in value]
            path_field = key in {'derived_images', 'artifact_dir', 'image', 'path'} or (key or '').endswith('_path')
            if path_field and isinstance(value, str) and value.startswith(prefix):
                return str(root) + os.sep + value[len(prefix):]
            return value

        for directory in ('tool_cache', 'tool_selections', 'calls'):
            for path in (root / directory).rglob('*.json'):
                original = json.loads(path.read_text())
                rebound = rewrite(original)
                if rebound != original:
                    store(path, rebound)
    store(marker, {'root': str(root)})


class NativeBackend:
    """Use the archived native Services and original CPU embedding model."""

    def __init__(self, config):
        self.config = config
        validate_binding(config)
        source = Path(config['source_dir']).resolve()
        if not (source / 'skill_services_r55.py').is_file():
            raise GatewayError('native_r55_services_source_missing')
        sys.path.insert(0, str(source))
        self.native = importlib.import_module('skill_services_r55')
        if Path(self.native.__file__).resolve().parent != source:
            raise GatewayError('a_different_native_services_module_is_loaded')
        self.main_key = read_key(config['key_files']['main'])
        self.deepseek_key = read_key(config['key_files']['deepseek'])
        if not Path(config['embedding_model_path']).is_dir():
            raise GatewayError('native_minilm_model_missing')
        self.embedding = None
        self.embedding_lock = threading.Lock()
        self.tool_lock = threading.Lock()
        self.tools_class = self.native.Tools
        if config.get('resident_control'):
            from native_resident_pool import tools_factory
            self.tools_class = tools_factory(self.native.Tools, config)

    def services(self, session):
        cfg = self.config
        service = self.native.Services(cfg['config'], cfg['protocol'], session.runtime,
                                       session.native_out, self.main_key, 'unused-local-embedding',
                                       cfg.get('embedding_base_url'))
        if service.paid.profile.base_url.rstrip('/') != cfg['main_base_url'].rstrip('/'):
            raise GatewayError('native_qwen_endpoint_changed')
        if 'token-plan.' not in service.paid.profile.base_url:
            raise GatewayError('original_qwen_token_plan_required')
        service.native_saved_call = service.call
        service.call = session.native_main
        service.verifier = session.native_verify
        service.tools = self.tools_class(session.runtime, session.image_root, session.native_out,
                                          service.call, service.verifier)
        return service

    def embed(self, text):
        if not isinstance(text, str):
            raise GatewayError('embedding_requires_text')
        with self.embedding_lock:
            if self.embedding is None:
                from sentence_transformers import SentenceTransformer
                os.environ.update(HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1')
                self.embedding = SentenceTransformer(self.config['embedding_model_path'], device='cpu')
            return self.embedding.encode(text).tolist()


class Session:
    def __init__(self, registry, token, request):
        self.registry, self.config, self.token = registry, registry.config, token
        self.operation = request['operation']
        self.closed = False
        self.deadline = time.monotonic() + self.config['session_timeout_seconds']
        self.lock = threading.RLock()
        self.out = Path(self.config['audit_dir']) / token
        self.out.mkdir(parents=True, exist_ok=False)
        if self.operation in ('predict', 'observe'):
            self.native_out = Path(request['state_dir']).resolve() / 'native_services'
            self.native_out.mkdir(parents=True, exist_ok=True)
            rebase_native_cache(self.native_out)
        else:
            self.native_out = self.out / 'native_services'
        self.counts = {'model_calls': 0, 'tool_calls': 0, 'total_tokens': 0, 'embedding_calls': 0}
        self.receipts = []
        self.main_ordinal = 0
        self.unknown_usage = False
        self.image_root = self.out / 'images'
        self.image_root.mkdir()
        self.allowed_images = set()
        self.runtime = copy.deepcopy(self.config['runtime'])
        self.runtime.setdefault('backend_config', {})['r54_image_views_by_path'] = {}
        self.limits = copy.deepcopy(self.config['limits'])
        if request['limits'] != self.limits:
            raise GatewayError('coordinator_limits_differ_from_gateway_configuration')
        self.row = None
        self.metadata = {'model': self.config['protocol']['model'], 'limits': self.limits,
                         'seed': request['seed'], 'operation': self.operation,
                         'protocol': {k: self.config['protocol'][k] for k in
                                      ('model', 'temperature', 'top_p', 'max_output_tokens', 'enable_thinking')},
                         'runtime_catalog': self.catalog(), 'image_views': {},
                         'native_row': None, 'order_item': request.get('order_item'),
                         'ordinal': request.get('ordinal')}
        case = request.get('case')
        if case is not None:
            self.bind_case(case, request['native_row'], request.get('image_annotations'))
        elif self.operation in ('predict', 'observe'):
            raise GatewayError('case_required_for_native_operation')
        self.service = None
        store(self.out / 'registered.json', {'operation': self.operation, 'metadata': self.metadata})

    def catalog(self):
        runtime = self.config['runtime']
        names = runtime['arms']['M']['tools']
        return {'arms': {'M': {'tools': names}}, 'tools': {
            name: {k: runtime['tools'][name][k] for k in ('description', 'revision', 'backend')
                   if k in runtime['tools'][name]} for name in names}}

    def bind_case(self, case, native_row, annotations):
        if set(native_row) - {'question_id', 'question', 'options', 'images', 'image_id', 'source'}:
            raise GatewayError('unexpected_native_case_metadata')
        expected_options = {item['label']: item['text'] for item in case['options']}
        if (native_row['question_id'] != case['id'] or native_row['question'] != case['question']
                or native_row.get('options', {}) != expected_options
                or len(native_row['images']) != len(case['images'])):
            raise GatewayError('native_case_binding_mismatch')
        if not isinstance(annotations, list) or len(annotations) != len(case['images']):
            raise GatewayError('current_original_image_annotations_required')
        self.row = copy.deepcopy(native_row)
        for i, (relative, image) in enumerate(zip(native_row['images'], case['images'])):
            target = (self.image_root / relative).resolve()
            if not target.is_relative_to(self.image_root.resolve()):
                raise GatewayError('native_image_alias_outside_case')
            source = Path(image['path']).resolve()
            pixels = source.read_bytes()
            if hashlib.sha256(pixels).hexdigest() != image['sha256']:
                raise GatewayError('registered_original_image_changed')
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(pixels)
            self.runtime['backend_config']['r54_image_views_by_path'][str(target)] = copy.deepcopy(annotations[i])
            self.allowed_images.add(image_url(target))
            self.metadata['image_views'][relative] = f'/case_images/{i}{source.suffix}'
        self.metadata['native_row'] = copy.deepcopy(native_row)

    def claim(self, kind):
        if time.monotonic() > self.deadline:
            raise GatewayError('native_session_timed_out')
        bound = self.limits.get(kind)
        if bound is not None and self.counts[kind] >= bound:
            raise GatewayError('registered_' + kind + '_limit_exhausted')
        self.counts[kind] += 1

    def check_messages(self, messages):
        if not isinstance(messages, list) or not messages:
            raise GatewayError('messages_required')
        for message in messages:
            if set(message) - {'role', 'content', 'name'} or message.get('role') not in ('system', 'user', 'assistant', 'tool'):
                raise GatewayError('invalid_native_message')
            content = message.get('content')
            if isinstance(content, str):
                continue
            if not isinstance(content, list):
                raise GatewayError('unsupported_native_message_content')
            for part in content:
                if part.get('type') == 'text' and isinstance(part.get('text'), str):
                    continue
                if part.get('type') == 'image_url' and part.get('image_url', {}).get('url') in self.allowed_images:
                    continue
                raise GatewayError('image_not_bound_to_registered_case')

    def get_service(self):
        if self.service is None:
            self.service = self.registry.backend.services(self)
        return self.service

    def record_response(self, folder, raw):
        self.counts['total_tokens'] += model_tokens(raw)
        receipt = self.out / 'model_receipts' / (str(len(self.receipts) + 1) + '.json')
        store(receipt, {'native_path': str(folder), 'model_returned': raw.get('model'), 'usage': raw['usage']})
        self.receipts.append(str(receipt.relative_to(self.out)))

    def native_main(self, row, arm, ordinal, messages):
        self.check_messages(messages)
        folder = self.native_out / 'calls' / arm / row['question_id'] / str(ordinal)
        cached = (folder / 'response.json').is_file()
        if not cached:
            self.claim('model_calls')
        try:
            result = self.get_service().native_saved_call(row, arm, ordinal, messages)
            if not cached:
                self.record_response(folder, json.loads((folder / 'response.json').read_text()))
            return result
        except Exception:
            self.unknown_usage = True
            raise

    def deepseek(self, phase, event, messages):
        self.check_messages(messages)
        self.claim('model_calls')
        if phase == 'verify':
            folder = self.native_out / 'calls' / 'R55-VERIFY' / event / '1'
        else:
            folder = self.native_out / 'deepseek' / self.token / phase / str(self.counts['model_calls'])
        folder.mkdir(parents=True)
        payload = {**copy.deepcopy(self.config['deepseek_' + phase + '_profile']),
                   'messages': messages, 'stream': False}
        store(folder / 'request.json', payload)
        store(folder / 'started.json', {'event': event, 'time': time.time()})
        request = Request('https://api.deepseek.com/chat/completions',
                          data=json.dumps(payload, ensure_ascii=False).encode(),
                          headers={'Authorization': 'Bearer ' + self.registry.backend.deepseek_key,
                                   'Content-Type': 'application/json'}, method='POST')
        try:
            with urlopen(request, timeout=180 if phase == 'memory' else 120) as response:
                raw = json.load(response)
            store(folder / 'response.json', raw)
            self.record_response(folder, raw)
            if raw.get('model') != payload['model']:
                raise GatewayError('official_deepseek_returned_model_changed')
            choice = raw['choices'][0]
            text = choice['message'].get('content')
            if choice.get('finish_reason') != 'stop' or not isinstance(text, str) or not text.strip():
                raise GatewayError('unusable_official_deepseek_response')
            store(folder / 'result.json', {'model_returned': raw['model'], 'usage': raw['usage'], 'response_received': True})
            return text
        except Exception as error:
            self.unknown_usage = True
            store(folder / 'failure.json', {'error_type': type(error).__name__, 'time': time.time()})
            raise

    def native_verify(self, event, messages):
        self.check_messages(messages)
        recovery = importlib.import_module('r55_top4_verify_recovery')
        folder = self.native_out / 'calls' / 'R55-VERIFY' / event / '1'
        payload = {**copy.deepcopy(self.config['deepseek_verify_profile']), 'messages': messages, 'stream': False}
        folder.mkdir(parents=True, exist_ok=True)
        request_id = f'r55:R55-VERIFY:{event}:1'
        request_path = folder / 'request.json'
        if request_path.is_file() and json.loads(request_path.read_text()) != payload:
            raise GatewayError('saved_native_verifier_request_changed')
        store(request_path, payload)
        store(folder / 'endpoint.json', {'url': 'https://api.deepseek.com/chat/completions'})
        response_path = folder / 'response.json'
        elapsed = None
        received_now = False
        if response_path.is_file():
            raw = json.loads(response_path.read_text())
        else:
            if (folder / 'started.json').exists():
                failure = recovery.disposition(folder)
                if failure is not None:
                    raise RuntimeError(failure['exception'])
                raise RuntimeError('unknown_r55_verifier_send_no_retry:' + event)
            self.claim('model_calls')
            store(folder / 'started.json', {'request_id': request_id, 'utc': time.time()})
            request = Request('https://api.deepseek.com/chat/completions',
                              data=json.dumps(payload, ensure_ascii=False).encode(),
                              headers={'Authorization': 'Bearer ' + self.registry.backend.deepseek_key,
                                       'Content-Type': 'application/json'}, method='POST')
            started = time.monotonic()
            try:
                with urlopen(request, timeout=120) as response:
                    raw = json.load(response)
                store(response_path, raw)
                received_now = True
            except Exception as error:
                self.unknown_usage = True
                store(folder / 'result.json', {'request_id': request_id, 'utc': time.time(),
                      'response_received': False, 'error': type(error).__name__, 'failure_stage': 'transport',
                      'elapsed_s': time.monotonic() - started,
                      **({'http_status': error.code} if hasattr(error, 'code') else {})})
                raise RuntimeError('r55_verifier_transport_failed:' + type(error).__name__) from None
            elapsed = time.monotonic() - started
        raw, content, error = recovery.inspect_reply(raw, payload['model'])
        if received_now:
            try:
                self.record_response(folder, raw)
            except GatewayError:
                self.unknown_usage = True
        store(folder / 'result.json', {'request_id': request_id, 'utc': time.time(), 'response_received': True,
              'error': error, 'model_returned': raw.get('model'), 'usage': raw.get('usage'), 'elapsed_s': elapsed})
        if error:
            raise ValueError(error)
        return content

    def tool(self, payload):
        if self.operation != 'predict' or self.row is None:
            raise GatewayError('tools_available_only_for_registered_prediction')
        if payload['row'] != self.row:
            raise GatewayError('tool_row_differs_from_registered_case')
        action, ordinal = payload['action'], payload['ordinal']
        names = self.config['runtime']['arms']['M']['tools']
        if not isinstance(action, dict) or set(action) - {'tool', 'args', 'image_index'}:
            raise GatewayError('invalid_native_tool_action')
        if action.get('tool') not in names or not isinstance(action.get('args'), dict):
            raise GatewayError('native_tool_not_registered')
        if set(action['args']) & {'url', 'path', 'file', 'runtime', 'config', 'python', 'model',
                                 'revision', 'image', 'artifact_dir'}:
            raise GatewayError('native_tool_arguments_cannot_select_files_or_backends')
        if type(ordinal) is not int or ordinal != self.counts['tool_calls'] + 1:
            raise GatewayError('native_tool_ordinal_mismatch')
        index = action.get('image_index', 1)
        if type(index) is not int or not 1 <= index <= len(self.row['images']):
            raise GatewayError('invalid_bound_image_index')
        self.claim('tool_calls')
        with self.registry.backend.tool_lock:
            observation = self.get_service().tools.call(self.row, action, 'R49-AGENT', ordinal)
        images = []
        for i, name in enumerate(observation.get('derived_images', [])):
            path = Path(name).resolve()
            if not path.is_relative_to((self.native_out / 'tool_cache').resolve()):
                raise GatewayError('native_tool_image_outside_case_artifacts')
            self.allowed_images.add(image_url(path))
            images.append({'name': f'{self.token[:12]}_{ordinal}_{i}{path.suffix}',
                           'base64': base64.b64encode(path.read_bytes()).decode()})
        result = copy.deepcopy(observation)
        result.pop('derived_images', None)
        return {'observation': result, 'images': images}

    def usage(self):
        return {**self.counts, 'usage_unknown': self.unknown_usage, 'authoritative': True,
                'receipts': list(self.receipts)}

    def dispatch(self, operation, payload):
        with self.lock:
            if self.closed:
                raise GatewayError('native_session_closed')
            if operation == 'metadata' and not payload:
                return self.metadata
            if operation == 'usage' and not payload:
                return self.usage()
            if operation in ('main', 'memory'):
                if set(payload) != {'messages'}:
                    raise GatewayError('only_messages_are_accepted')
                if self.operation not in ('predict', 'observe'):
                    raise GatewayError('model_requests_not_allowed_during_migration_or_initialization')
                if operation == 'main':
                    if self.operation != 'predict':
                        raise GatewayError('main_answer_available_only_before_feedback')
                    self.main_ordinal += 1
                    return self.native_main(self.row, 'R49-AGENT', self.main_ordinal, payload['messages'])
                return self.deepseek('memory', self.row['question_id'], payload['messages'])
            if operation == 'embed' and set(payload) == {'text'}:
                if time.monotonic() > self.deadline:
                    raise GatewayError('native_session_timed_out')
                result = self.registry.backend.embed(payload['text'])
                self.counts['embedding_calls'] += 1
                return result
            if operation == 'tool' and set(payload) == {'row', 'action', 'ordinal'}:
                return self.tool(payload)
            raise GatewayError('unsupported_native_operation')


class Registry:
    def __init__(self, config, backend=None):
        self.config = config
        self.backend = backend or NativeBackend(config)
        self.sessions = {}
        self.lock = threading.Lock()

    def control(self, request):
        with self.lock:
            if request.get('action') == 'register':
                if request.get('operation') not in ('initialize', 'predict', 'observe', 'migrate', 'check'):
                    raise GatewayError('invalid_native_session_operation')
                token = secrets.token_urlsafe(32)
                session = Session(self, token, request)
                self.sessions[token] = session
                return {'session': token, 'gateway_url': self.config['public_url'].rstrip('/') + '/v1/session/' + token}
            if request.get('action') in ('receipt', 'close'):
                session = self.sessions[request['session']]
                with session.lock:
                    receipt = session.usage()
                    if request['action'] == 'close':
                        session.closed = True
                        store(session.out / 'closed.json', receipt)
                    return receipt
            raise GatewayError('invalid_native_control_action')

    def request(self, path, payload):
        parts = path.split('/')
        if len(parts) != 5 or parts[1:3] != ['v1', 'session'] or parts[3] not in self.sessions:
            raise GatewayError('unregistered_native_session')
        return self.sessions[parts[3]].dispatch(parts[4], payload)


def control_request(socket_path, payload):
    """Coordinator-only client. This socket is never mounted in a candidate."""
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.connect(str(socket_path))
        client.sendall(json.dumps(payload, ensure_ascii=False).encode() + b'\n')
        response = json.loads(client.makefile('rb').readline())
    if not response.get('ok'):
        raise GatewayError(response.get('error', 'native_control_failed'))
    return response['result']


def serve(config):
    registry = Registry(config)

    class HTTPHandler(BaseHTTPRequestHandler):
        def do_POST(self):
            status = 200
            try:
                payload = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                response = {'ok': True, 'result': registry.request(self.path, payload)}
            except Exception as error:
                status = 400
                response = {'ok': False, 'error': str(error) if isinstance(error, GatewayError) else type(error).__name__}
            raw = json.dumps(response, ensure_ascii=False, allow_nan=False).encode()
            self.send_response(status)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def log_message(self, *_):
            pass

    class ControlHandler(socketserver.StreamRequestHandler):
        def handle(self):
            try:
                response = {'ok': True, 'result': registry.control(json.loads(self.rfile.readline()))}
            except Exception as error:
                response = {'ok': False, 'error': str(error) if isinstance(error, GatewayError) else type(error).__name__}
            self.wfile.write(json.dumps(response, ensure_ascii=False).encode() + b'\n')

    path = Path(config['control_socket'])
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise GatewayError('native_control_socket_already_exists')
    control = socketserver.ThreadingUnixStreamServer(str(path), ControlHandler)
    os.chmod(path, 0o600)
    threading.Thread(target=control.serve_forever, daemon=True).start()
    server = ThreadingHTTPServer((config['listen_host'], config['listen_port']), HTTPHandler)
    try:
        server.serve_forever()
    finally:
        control.shutdown()
        control.server_close()
        server.server_close()
        path.unlink()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True)
    args = parser.parse_args()
    serve(json.loads(args.config.read_text()))
