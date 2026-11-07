"""Publish completed extension arms with sanitized request and tool evidence."""

import argparse
import base64
import hashlib
import json
from pathlib import Path

from export_cxr_vqa_toolsets import CALL_FILES, rows
from export_vote_phase import Publisher, read


class RequestEvidencePublisher(Publisher):
    """Retain malformed archived request bytes without treating them as valid images."""

    def from_uri(self, uri, source=None):
        try:
            return super().from_uri(uri, source)
        except (SyntaxError, OSError) as exc:
            if source is not None:
                raise
            data = base64.b64decode(uri.split(',', 1)[1], validate=True)
            if len(data) > 100 * 1024 * 1024:
                raise ValueError('image_above_export_size_limit') from exc
            digest = hashlib.sha256(data).hexdigest()
            target = self.out / 'invalid_request_image_bytes' / (digest + '.bin')
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists() and target.read_bytes() != data:
                raise ValueError('existing_export_asset_conflict') from exc
            if not target.exists():
                target.write_bytes(data)
            self.files.add(target)
            self.assets[digest] = dict(target=target, bytes=len(data), size=None,
                sha256=digest, byte_preserving=True, reused_existing_public_image=False,
                integrity='invalid_archived_request_image', validation_error=str(exc))
            self.uri_cache[hashlib.sha256(uri.encode('ascii')).hexdigest()] = digest
            return digest


def emit_tool_results(publisher, out, values):
    """Keep complete tool evidence in files small enough for repository hosting."""
    batches, current, size = [], [], 0
    for value in values:
        row_size = len(json.dumps(value, ensure_ascii=False).encode('utf-8')) + 1
        if current and size + row_size > 40_000_000:
            batches.append(current)
            current, size = [], 0
        current.append(value)
        size += row_size
    if current or not batches:
        batches.append(current)
    if len(batches) == 1:
        publisher.emit(out / 'raw_tool_results.jsonl', batches[0], jsonl=True)
        return
    parts = []
    for index, batch in enumerate(batches, 1):
        name = f'raw_tool_results/part_{index:03d}.jsonl'
        publisher.emit(out / name, batch, jsonl=True)
        if (out / name).stat().st_size >= 100_000_000:
            raise ValueError('One tool evidence partition exceeds the hosting file limit')
        parts.append({'path': name, 'records': len(batch)})
    publisher.emit(out / 'raw_tool_results_index.json', {'parts': parts})


def restore_images(value, run):
    if isinstance(value, dict):
        digest = value.get('cxr_request_image_base64_sha256')
        if digest is not None:
            if len(digest) != 64 or any(c not in '0123456789abcdef' for c in digest):
                raise ValueError('Invalid archived image identifier')
            encoded = (run / 'request_image_base64' / digest).read_text(encoding='ascii')
            return 'data:' + value['media_type'] + ';base64,' + encoded
        return {key: restore_images(item, run) for key, item in value.items()}
    if isinstance(value, list):
        return [restore_images(item, run) for item in value]
    return value


def export(data, run, score_dir, out, arms, reuse_url):
    if out.exists():
        raise FileExistsError(out)
    summary = read(score_dir / 'summary.json')
    inputs = rows(data / 'inputs.jsonl')
    for arm in arms:
        if not (run / f'complete_{arm}.json').is_file() or arm not in summary['arms']:
            raise ValueError('Arm must have completed generation and isolated scoring: ' + arm)
        if sum(1 for _ in (run / 'predictions' / arm).glob('*.json')) != len(inputs):
            raise ValueError('Prediction count differs from the scored cohort')
    publisher = RequestEvidencePublisher(out, data / 'manifest.json', image_roots=(data,))
    for row in inputs:
        for name in row['images']:
            digest = publisher.sources.get(name)
            if digest is None:
                publisher.source_image(name)
                digest = publisher.sources[name]
            publisher.alias(str(data / name), digest)
            publisher.alias(str((data / name).resolve()), digest)

    selections, tool_results = {}, {}
    cache = (run / 'tool_cache').resolve()
    for arm in arms:
        selections[arm] = []
        for path in sorted((run / 'tool_selections' / arm).glob('*/*.json')):
            observed = read(path)
            selections[arm].append(dict(question_id=path.parent.name, ordinal=path.stem, **observed))
            key = observed['cache_key']
            if key in tool_results:
                continue
            folder = (cache / key).resolve()
            if not folder.is_relative_to(cache):
                raise ValueError('Tool evidence outside the run cache')
            for name in observed.get('derived_images', []):
                image = Path(name).resolve()
                if not image.is_relative_to(cache):
                    raise ValueError('Derived image outside the run cache')
                publisher.alias(name, publisher.put_image(publisher.read_image(image)))
            raw = folder / 'artifacts/raw.json'
            stderr = folder / 'backend.stderr.log'
            tool_results[key] = dict(cache_key=key, backend=observed.get('backend'),
                                    status=observed.get('status'),
                                    raw_result=read(raw) if raw.is_file() else None,
                                    backend_stderr=stderr.read_text(errors='replace') if stderr.is_file() else None)

    for name in ('inputs.jsonl', 'references.jsonl'):
        values = rows(data / name)
        for row in values:
            if 'images' in row:
                row['images'] = [publisher.rel(publisher.source_image(image), out / name) for image in row['images']]
        publisher.emit(out / name, values, jsonl=True)
    publisher.copy_json(data / 'manifest.json', out / 'data_manifest.json')
    for name in ('summary.json', 'per_question.jsonl'):
        publisher.copy_json(score_dir / name, out / name)
    publisher.copy_json(run / 'protocol.json', out / 'protocol.json')
    for arm in arms:
        for name in (f'complete_{arm}.json', f'runtime_full_{arm}.json'):
            publisher.copy_json(run / name, out / name)
        publisher.emit(out / f'predictions_{arm}.jsonl',
                       [read(run / 'predictions' / arm / (row['question_id'] + '.json')) for row in inputs], jsonl=True)
        publisher.emit(out / f'tool_selections_{arm}.jsonl', selections[arm], jsonl=True)
        for row in inputs:
            qid = row['question_id']
            calls = []
            for request in sorted((run / 'calls' / arm / qid).glob('*/request.json')):
                entry = {'ordinal': request.parent.name}
                for name in CALL_FILES:
                    path = request.parent / name
                    if path.is_file():
                        entry[path.stem] = restore_images(read(path), run)
                entry.get('started', {}).pop('reserved', None)
                entry.get('result', {}).pop('ledger_remaining_proxy_cny', None)
                calls.append(entry)
            publisher.emit(out / 'calls' / arm / (qid + '.json'), calls)
    emit_tool_results(publisher, out, tool_results.values())
    publisher.emit(out / 'reuse.json', {'D_M_C_X_evidence': reuse_url})
    publisher.emit(out / 'image_assets.json', [
        {key: value for key, value in item.items() if key != 'target'} |
        {'path': publisher.rel(item['target'], out / 'image_assets.json')}
        for item in publisher.assets.values()])
    publisher.emit(out / 'publication_manifest.json', {
        'files': sorted(path.relative_to(out).as_posix() for path in publisher.files),
        'redactions': dict(publisher.redactions)})


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    for name in ('data', 'run', 'score-dir', 'out'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--arms', nargs='+', default=['O', 'M-R'])
    parser.add_argument('--reuse-url', required=True)
    args = parser.parse_args()
    export(args.data.resolve(), args.run.resolve(), args.score_dir.resolve(), args.out.resolve(), args.arms, args.reuse_url)
