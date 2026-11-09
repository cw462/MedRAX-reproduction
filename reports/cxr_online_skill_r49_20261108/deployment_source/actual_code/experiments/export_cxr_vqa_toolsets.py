"""Export a completed CXR comparison without provider credentials or ledgers."""

import argparse
import json
from pathlib import Path

from export_vote_phase import Publisher, read


ARMS = 'DMCX'
CALL_FILES = ('request.json', 'started.json', 'response.json', 'result.json')
RUNTIMES = ('runtime.json', 'runtime_m_repaired.json', 'runtime_c_ready.json', 'runtime_x_ready.json')


def rows(path):
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line]


def export(data, run, out):
    if not all((run / f'complete_{arm}.json').is_file() for arm in ARMS):
        raise ValueError('All four arms must be complete')
    if not (run / 'offline_score/summary.json').is_file():
        raise ValueError('Offline scores are required')
    if out.exists():
        raise FileExistsError(out)

    inputs = rows(data / 'inputs.jsonl')
    originals = {name: str(data / name) for row in inputs for name in row['images']}
    publisher = Publisher(out, data / 'manifest.json', public_map=originals)
    for name, path in originals.items():
        publisher.source_image(name)
        publisher.alias(path, publisher.sources[name])

    selections = {}
    tools = {}
    cache = (run / 'tool_cache').resolve()
    for arm in ARMS:
        selections[arm] = []
        for path in sorted((run / 'tool_selections' / arm).glob('*/*.json')):
            result = read(path)
            key = result['cache_key']
            selections[arm].append(dict(question_id=path.parent.name, ordinal=path.stem, **result))
            if key in tools:
                continue
            for image in result.get('derived_images', []):
                image_path = Path(image).resolve()
                if not image_path.is_relative_to(cache):
                    raise ValueError('Derived image outside tool cache')
                digest = publisher.put_image(publisher.read_image(image_path))
                publisher.alias(image, digest)
            folder = cache / key
            raw = folder / 'artifacts/raw.json'
            stderr = folder / 'backend.stderr.log'
            tools[key] = {'cache_key': key, 'backend': result['backend'], 'status': result['status'],
                          'raw_result': read(raw) if raw.is_file() else None,
                          'backend_stderr': stderr.read_text(errors='replace') if stderr.is_file() else None}

    for filename in ('inputs.jsonl', 'references.jsonl'):
        value = rows(data / filename)
        for row in value:
            if 'images' in row:
                row['images'] = [publisher.rel(publisher.source_image(name), out / filename) for name in row['images']]
        publisher.emit(out / filename, value, jsonl=True)
    publisher.copy_json(data / 'manifest.json', out / 'data_manifest.json')
    for name in ('summary.json', 'changes.jsonl'):
        publisher.copy_json(run / 'offline_score' / name, out / name)
    for name in ('protocol.json', *RUNTIMES, *(f'complete_{a}.json' for a in ARMS)):
        if (run / name).is_file():
            publisher.copy_json(run / name, out / name)

    for arm in ARMS:
        predictions = [read(run / 'predictions' / arm / (r['question_id'] + '.json')) for r in inputs]
        publisher.emit(out / f'predictions_{arm}.jsonl', predictions, jsonl=True)
        publisher.emit(out / f'tool_selections_{arm}.jsonl', selections[arm], jsonl=True)
        for row in inputs:
            qid = row['question_id']
            calls = []
            for request in sorted((run / 'calls' / arm / qid).glob('*/request.json')):
                entry = {'ordinal': int(request.parent.name)}
                for name in CALL_FILES:
                    path = request.parent / name
                    if path.is_file():
                        entry[path.stem] = read(path)
                entry.get('started', {}).pop('reserved', None)
                entry.get('result', {}).pop('ledger_remaining_proxy_cny', None)
                calls.append(entry)
            publisher.emit(out / 'calls' / arm / (qid + '.json'), calls)
    publisher.emit(out / 'raw_tool_results.jsonl', list(tools.values()), jsonl=True)
    publisher.emit(out / 'image_assets.json', [
        {k: v for k, v in item.items() if k != 'target'} |
        {'path': publisher.rel(item['target'], out / 'image_assets.json')}
        for item in publisher.assets.values()
    ])
    publisher.emit(out / 'publication_manifest.json', {
        'files': sorted(p.relative_to(out).as_posix() for p in publisher.files),
        'image_urls': 'Inline request images are relative paths to preserved bytes.',
        'redactions': dict(publisher.redactions),
    })


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    for arg in ('data', 'run', 'out'):
        parser.add_argument(f'--{arg}', type=Path, required=True)
    args = parser.parse_args()
    export(args.data.resolve(), args.run.resolve(), args.out.resolve())
