"""Allowlisted offline publication of a complete independent-sample VLM phase.

Usage: --manifest PHASE.json --out REPORT [--image-root NATIVE_IMAGE_ROOT].
Writes REPORT/evidence, leaving scorer files alone. All runs must be complete.
No labels, credentials, provider clients, account ledgers, network or Git access.
Optional manifest.public_image_map maps source_filename to an explicitly named
existing public image (relative to manifest); exact request bytes must agree.
"""
from __future__ import annotations

import argparse
import base64
from collections import Counter
from decimal import Decimal
import hashlib
from io import BytesIO
import json
import os
from pathlib import Path, PurePosixPath
import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

try:
    from .score_votes import load_complete_run, resources
except ImportError:
    from score_votes import load_complete_run, resources


DROP_KEYS = {
    'api_key', 'apikey', 'api_token', 'authorization', 'proxy_authorization',
    'password', 'passwd', 'access_token', 'refresh_token', 'session_token',
    'private_key', 'ssh_key', 'client_secret', 'secret', 'credential', 'credentials',
    'headers', 'cookies', 'cookie', 'token', 'root', 'code_root', 'ledger',
    'inherit_ledger', 'global_request_counter', 'reservation', 'reservation_id',
    'account_balance', 'balance_cny', 'remaining_cny', 'committed_cny', 'reserved_cny',
    'start_committed_cny', 'end_committed_cny', 'private_ledgers', 'account_ledger',
}
SECRET = re.compile(r'(?i)\b(?:sk-[a-z0-9_-]{12,}|gh[pousr]_[a-z0-9]{20,}|github_pat_[a-z0-9_]{20,}|AKIA[A-Z0-9]{16})\b|\bBearer\s+[A-Za-z0-9._~+/=-]{8,}|-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----')
ASSIGNMENT = re.compile(r'(?i)\b(?:api[_-]?key|access[_-]?token|authorization|password|client[_-]?secret)\s*[=:]\s*[\"\']?[^\s\"\',;}]+')
PRIVATE_PATH = re.compile(r'(?i)(?<![\w])[a-z]:[\\/][^\r\n\"\'<>\]\},;]*|(?<![\w:/.])/(?:home|root|Users|tmp|var|mnt|workspace|private)(?:/[^\s\"\'<>\]\},;]*)?')
DATA_URI = re.compile(r'data:image/(?:png|jpeg|webp);base64,[A-Za-z0-9+/=]+', re.I)
BOUND = 'BOUND CURRENT IMAGE: '
IMAGE_SUFFIXES = {'.png', '.jpg', '.jpeg', '.webp'}
SAMPLE_FILES = ('request.json', 'image_metadata.json', 'terminal.json')
ATTEMPT_FILES = ('started.json', 'response.json', 'result.json', 'reserve_error.json', 'stream_chunks.jsonl')


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def relative_source(value):
    value = str(value).replace('\\', '/')
    path = PurePosixPath(value)
    if not value or path.is_absolute() or '..' in path.parts or ':' in value:
        raise ValueError('unsafe_relative_source')
    return value


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_.-]+', value) or value in ('.', '..'):
        raise ValueError('unsafe_public_identifier')
    return value


def source_file(run, relative):
    candidate = (run / relative).resolve()
    if not candidate.is_relative_to(run):
        raise ValueError('source_escapes_declared_run')
    return candidate


def question_parts(question):
    stem, options, current = [], {}, None
    for line in question.splitlines():
        match = re.match(r'^\s*([A-Z])[).]\s*(.*)$', line)
        if match:
            current = match[1]
            if current in options:
                raise ValueError('duplicate_option_label')
            options[current] = match[2].strip()
        elif current and line.strip():
            options[current] += '\n' + line.strip()
        elif current is None:
            stem.append(line)
    if len(options) < 2 or any(not v for v in options.values()):
        raise ValueError('complete_option_parse_failed')
    return '\n'.join(stem).strip(), options


class Publisher:
    def __init__(self, out, manifest_path, public_map=None, image_roots=()):
        self.out = out
        self.manifest_path = manifest_path
        self.image_roots = [Path(p).resolve() for p in image_roots]
        self.public_map = {relative_source(k): (manifest_path.parent / v).resolve()
                           for k, v in (public_map or {}).items()}
        self.assets, self.uri_cache, self.file_cache = {}, {}, {}
        self.sources, self.aliases, self.files, self.references = {}, {}, set(), []
        self.redactions = Counter()

    def rel(self, target, document):
        value = os.path.relpath(target, document.parent).replace('\\', '/')
        self.references.append((document, value, target))
        return value

    def inspect_image(self, data):
        from PIL import Image
        if len(data) > 100 * 1024 * 1024:
            raise ValueError('image_above_export_size_limit')
        with Image.open(BytesIO(data)) as image:
            suffix = {'PNG': '.png', 'JPEG': '.jpg', 'WEBP': '.webp'}.get(image.format)
            if not suffix:
                raise ValueError('unsupported_actual_image_format')
            size = list(image.size)
            image.verify()
        return suffix, size

    def read_image(self, path):
        if path.suffix.lower() not in IMAGE_SUFFIXES:
            raise ValueError('only_explicit_image_files_may_be_read')
        if path not in self.file_cache:
            self.file_cache[path] = path.read_bytes()
        return self.file_cache[path]

    def put_image(self, data, source=None):
        digest = hashlib.sha256(data).hexdigest()
        if source is not None:
            source = relative_source(source)
            if source in self.sources and self.sources[source] != digest:
                raise ValueError('source_filename_has_conflicting_request_bytes')
            self.sources[source] = digest
        mapped = self.public_map.get(source)
        if mapped is not None and self.read_image(mapped) != data:
            raise ValueError('public_image_mapping_does_not_match_request_bytes')
        if digest not in self.assets:
            suffix, size = self.inspect_image(data)
            target = mapped or self.out / 'assets' / (digest + suffix)
            if mapped is None:
                target.parent.mkdir(parents=True, exist_ok=True)
                if target.exists() and target.read_bytes() != data:
                    raise ValueError('existing_export_asset_conflict')
                if not target.exists():
                    target.write_bytes(data)
                self.files.add(target)
            self.assets[digest] = {'target': target, 'bytes': len(data), 'size': size,
                                   'sha256': digest, 'byte_preserving': True,
                                   'reused_existing_public_image': mapped is not None}
        return digest

    def from_uri(self, uri, source=None):
        fingerprint = hashlib.sha256(uri.encode('ascii')).hexdigest()
        if fingerprint not in self.uri_cache:
            data = base64.b64decode(uri.split(',', 1)[1], validate=True)
            digest = self.put_image(data, source)
            self.uri_cache[fingerprint] = digest
        else:
            digest = self.uri_cache[fingerprint]
            if source is not None:
                source = relative_source(source)
                if source in self.sources and self.sources[source] != digest:
                    raise ValueError('source_filename_has_conflicting_request_bytes')
                self.sources[source] = digest
                mapped = self.public_map.get(source)
                if mapped is not None and hashlib.sha256(self.read_image(mapped)).hexdigest() != digest:
                    raise ValueError('public_image_mapping_does_not_match_request_bytes')
        return digest

    def alias(self, value, digest):
        if value:
            if value in self.aliases and self.aliases[value] != digest:
                raise ValueError('private_image_alias_has_conflicting_request_bytes')
            self.aliases[value] = digest

    def bind_request(self, request, row):
        """Use metadata next to actual image bytes, never selection-list position."""
        bindings = []
        allowed = {relative_source(v) for v in row['images']}
        for mi, message in enumerate(request.get('messages', [])):
            content = message.get('content')
            if not isinstance(content, list):
                continue
            metadata = None
            for ci, block in enumerate(content):
                if block.get('type') == 'text' and str(block.get('text', '')).startswith(BOUND):
                    if metadata is not None:
                        raise ValueError('image_metadata_without_corresponding_pixels')
                    metadata = json.loads(block['text'][len(BOUND):])
                elif block.get('type') == 'image_url':
                    uri = block['image_url']
                    uri = uri.get('url') if isinstance(uri, dict) else uri
                    if not isinstance(uri, str) or not DATA_URI.fullmatch(uri) or metadata is None:
                        raise ValueError('request_image_requires_saved_pixels_and_explicit_binding')
                    source = relative_source(metadata['source_filename'])
                    if source not in allowed:
                        raise ValueError('request_image_not_in_question_selection')
                    digest = self.from_uri(uri, source)
                    asset = self.assets[digest]
                    if metadata.get('size') and list(metadata['size']) != asset['size']:
                        raise ValueError('request_metadata_size_disagrees_with_actual_bytes')
                    self.alias(metadata.get('path'), digest)
                    bindings.append({'message_index': mi, 'content_index': ci, 'source_filename': source,
                                     'image_id': metadata.get('image_id'), 'figure_label': metadata.get('figure_label'),
                                     'sha256': digest, 'size': asset['size'], 'asset': asset['target']})
                    metadata = None
            if metadata is not None:
                raise ValueError('image_metadata_without_corresponding_pixels')
        if bindings and Counter(b['source_filename'] for b in bindings) != Counter(relative_source(v) for v in row['images']):
            raise ValueError('request_original_image_coverage_mismatch')
        return bindings

    def source_image(self, source):
        source = relative_source(source)
        if source not in self.sources:
            if source in self.public_map:
                self.put_image(self.read_image(self.public_map[source]), source)
            else:
                for root in self.image_roots:
                    candidate = (root / source).resolve()
                    if candidate.is_relative_to(root) and candidate.is_file():
                        self.put_image(self.read_image(candidate), source)
                        break
                else:
                    raise FileNotFoundError('missing_native_image_supply_image_root_or_public_image_map')
        return self.assets[self.sources[source]]['target']

    def clean(self, value, document):
        if isinstance(value, dict):
            output = {}
            for key, item in value.items():
                normalized = str(key).lower().replace('-', '_')
                if normalized in DROP_KEYS or normalized.endswith(('_api_key', '_password', '_private_key', '_token')):
                    self.redactions['private_field'] += 1
                    continue
                output[key] = self.clean(item, document)
            return output
        if isinstance(value, list):
            return [self.clean(item, document) for item in value]
        if not isinstance(value, str):
            return value
        if value.startswith(BOUND):
            return BOUND + json.dumps(self.clean(json.loads(value[len(BOUND):]), document), ensure_ascii=False)
        if value.lstrip().startswith(('{', '[')):
            try:
                parsed = json.loads(value)
            except ValueError:
                pass
            else:
                return json.dumps(self.clean(parsed, document), ensure_ascii=False)
        value = DATA_URI.sub(lambda m: self.rel(self.assets[self.from_uri(m[0])]['target'], document), value)
        for alias, digest in sorted(self.aliases.items(), key=lambda pair: -len(pair[0])):
            if alias in value:
                value = value.replace(alias, self.rel(self.assets[digest]['target'], document))
        if value.startswith(('https://', 'http://')) and not any(c.isspace() for c in value):
            url = urlsplit(value)
            netloc = url.netloc.rsplit('@', 1)[-1]
            query = [(k, v) for k, v in parse_qsl(url.query, keep_blank_values=True)
                     if k.lower().replace('-', '_') not in DROP_KEYS]
            value = urlunsplit((url.scheme, netloc, url.path, urlencode(query), url.fragment))
        for pattern, label in ((SECRET, 'credential_text'), (ASSIGNMENT, 'credential_assignment'), (PRIVATE_PATH, 'private_path')):
            value, count = pattern.subn('[REDACTED]', value)
            self.redactions[label] += count
        return value

    def emit(self, path, value, jsonl=False):
        path.parent.mkdir(parents=True, exist_ok=True)
        cleaned = self.clean(value, path)
        text = ('\n'.join(json.dumps(v, ensure_ascii=False) for v in cleaned) if jsonl
                else json.dumps(cleaned, ensure_ascii=False, indent=2)) + '\n'
        if DATA_URI.search(text) or SECRET.search(text) or PRIVATE_PATH.search(text):
            raise ValueError('outgoing_text_contains_unresolved_private_content')
        path.write_text(text, encoding='utf-8')
        self.files.add(path)

    def copy_json(self, source, target):
        if source.suffix == '.jsonl':
            value = [json.loads(line) for line in source.read_text(encoding='utf-8-sig').splitlines() if line.strip()]
            self.emit(target, value, jsonl=True)
        else:
            self.emit(target, read(source))


def export_phase(manifest_path, report_out, image_roots=()):
    manifest_path, report_out = Path(manifest_path).resolve(), Path(report_out).resolve()
    manifest = read(manifest_path)
    out = report_out / 'evidence'
    runs = {}
    for arm in manifest['arms']:
        arm_id = identifier(arm['id'])
        if arm_id in runs:
            raise ValueError('duplicate_arm_id')
        run = (manifest_path.parent / arm['run']).resolve()
        if out == run or out.is_relative_to(run) or run.is_relative_to(out):
            raise ValueError('publication_must_be_separate_from_private_run')
        runs[arm_id] = load_complete_run(run)
    if not runs:
        raise ValueError('empty_phase')
    first = next(iter(runs.values()))
    rows = {identifier(str(row['question_id'])): row for row in first['rows']}
    for run in runs.values():
        if run['rows'] != first['rows']:
            raise ValueError('all_arms_must_publish_same_question_selection')
    publisher = Publisher(out, manifest_path, manifest.get('public_image_map'), image_roots)
    bindings, artifacts = {}, []
    for arm_id, run in runs.items():
        terminals = {(str(r['question_id']), r['sample_index']): r for r in run['records']}
        for row in run['rows']:
            qid = str(row['question_id'])
            for sample in range(1, run['samples'] + 1):
                prefix = f'checkpoints/{qid}/sample_{sample}'
                source = source_file(run['path'], prefix + '/request.json')
                if not source.is_file():
                    raise FileNotFoundError('completed_sample_missing_observable_request')
                request = read(source)
                binding = publisher.bind_request(request, row)
                if run['config'].get('prompt_variant') != 'text_only' and not binding:
                    raise ValueError('visual_arm_request_has_no_image_bytes')
                bindings[arm_id, qid, sample] = binding
                for name in SAMPLE_FILES:
                    source = source_file(run['path'], prefix + '/' + name)
                    if source.is_file():
                        if name == 'terminal.json' and read(source) != terminals[qid, sample]:
                            raise ValueError('checkpoint_and_aggregate_terminal_disagree')
                        artifacts.append((source, out / 'arms' / arm_id / prefix / name))
                    elif name == 'terminal.json':
                        raise FileNotFoundError('completed_sample_missing_checkpoint_terminal')
                for attempt in range(1, int(run['config'].get('max_attempts_per_sample', 2)) + 1):
                    for name in ATTEMPT_FILES:
                        relative = prefix + f'/attempt_{attempt}/' + name
                        source = source_file(run['path'], relative)
                        if source.is_file():
                            artifacts.append((source, out / 'arms' / arm_id / relative))
    # Originals for text-only arms still belong to the benchmark case archive.
    for row in rows.values():
        for source in row['images']:
            publisher.source_image(source)
    for source, target in artifacts:
        publisher.copy_json(source, target)
    cost = {}
    for arm_id, run in runs.items():
        arm_out = out / 'arms' / arm_id
        publisher.emit(arm_out / 'protocol.json', read(run['path'] / 'protocol.json'))
        publisher.emit(arm_out / 'status.json', read(run['path'] / 'status.json'))
        publisher.emit(arm_out / 'predictions.jsonl', run['records'], jsonl=True)
        cost[arm_id] = resources(run['records'])
        summary = source_file(run['path'], 'ledger_final_summary.json')
        if summary.is_file():
            saved = read(summary)
            increment = saved.get('run_increment_cny')
            cost[arm_id]['guard_run_increment_cny'] = increment
            cost[arm_id]['price_basis'] = saved.get('price_basis')
            if increment is not None:
                cost[arm_id]['guard_minus_saved_settlement_cny'] = str(Decimal(str(increment)) - Decimal(cost[arm_id]['saved_settlement_cny']))
    cases_path = out / 'cases.json'
    cases = []
    for qid, row in rows.items():
        stem, options = question_parts(row['question'])
        case = {k: row[k] for k in ('question_id', 'case_id', 'question', 'figure_labels') if k in row}
        case.update(stem=stem, options=options, native_images=[{'source_filename': source,
                    'image': publisher.rel(publisher.source_image(source), cases_path)} for source in row['images']], samples={})
        for arm_id, run in runs.items():
            samples = []
            for sample in range(1, run['samples'] + 1):
                prefix = out / 'arms' / arm_id / 'checkpoints' / qid / f'sample_{sample}'
                records = [{**{k: v for k, v in item.items() if k != 'asset'},
                            'image': publisher.rel(item['asset'], cases_path)} for item in bindings[arm_id, qid, sample]]
                samples.append({'sample_index': sample, 'request': publisher.rel(prefix / 'request.json', cases_path),
                                'terminal': publisher.rel(prefix / 'terminal.json', cases_path), 'request_image_bindings': records})
            case['samples'][arm_id] = samples
        cases.append(case)
    publisher.emit(cases_path, {'planned_n': len(cases), 'cases': cases})
    public_manifest = {k: v for k, v in manifest.items() if k not in ('arms', 'public_image_map')}
    public_manifest['arms'] = [{**{k: v for k, v in arm.items() if k != 'run'}, 'run': 'arms/' + arm['id']} for arm in manifest['arms']]
    publisher.emit(out / 'phase_manifest.json', public_manifest)
    publisher.emit(out / 'cost_summary.json', {'arms': cost, 'new_export_inference': 0,
                   'notes': 'Saved per-request settlements and guard run increments are distinct, unchanged accounting sources; neither is a provider invoice.'})
    asset_path = out / 'assets.json'
    publisher.emit(asset_path, {'assets': [{**{k: v for k, v in item.items() if k != 'target'},
                               'path': publisher.rel(item['target'], asset_path)} for item in publisher.assets.values()]})
    readme = out / 'README.md'
    readme.write_text('# Complete phase evidence\n\n'
        f'This archive contains {len(cases)} questions across {len(runs)} completed arms. '
        'The original question text, complete options and native image bytes are retained.\n\n'
        '- [Cases, options, native images and per-sample links](cases.json)\n'
        '- [Public phase configuration](phase_manifest.json)\n'
        '- [Image provenance and exact-byte deduplication](assets.json)\n'
        '- [Request costs and recovery-accounting differences](cost_summary.json)\n'
        '- [Explicit publication file list](publication_manifest.json)\n\n'
        'Each request image URL is replaced by a path relative to that request file. '
        'The adjacent image metadata, figure label, source filename and request order remain bound to the saved pixels. '
        'Request parameters, response content, reasoning content and observable stream chunks are retained; private credentials, account balances and local absolute paths are removed. '
        'This exporter does not load reference labels or account ledgers and does not generate predictions.\n', encoding='utf-8')
    publisher.files.add(readme)
    # Check only links actually emitted in this publication, no repository scans.
    for document, relative, target in publisher.references:
        if (document.parent / relative).resolve() != target.resolve() or not target.is_file():
            raise ValueError('outgoing_asset_or_evidence_link_is_missing_or_mismatched')
    publication_path = out / 'publication_manifest.json'
    publisher.emit(publication_path, {'status': 'exported', 'planned_n': len(cases), 'arms': list(runs),
                   'asset_count': len(publisher.assets), 'files': sorted([p.relative_to(out).as_posix() for p in publisher.files] + ['publication_manifest.json']),
                   'redactions': dict(publisher.redactions), 'native_image_bytes_preserved': True,
                   'model_content_and_reasoning_retained_except_private_text': True,
                   'request_image_order_and_source_binding_preserved': True,
                   'private_account_ledgers_read': False, 'reference_labels_read': False, 'new_inference': 0})
    return read(publication_path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--image-root', type=Path, action='append', default=[])
    args = parser.parse_args()
    value = export_phase(args.manifest, args.out, args.image_root)
    print(json.dumps({k: value[k] for k in ('status', 'planned_n', 'asset_count', 'new_inference')}))


if __name__ == '__main__':
    main()
