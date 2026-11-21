"""Re-run failed original ROI requests against the repaired CPU worker."""
import argparse
from collections import Counter
import json
import os
from pathlib import Path
import subprocess
import sys


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def prepare_requests(work):
    for arm in ('B0', 'L1'):
        services = work / arm / 'services'
        for path in sorted((services / 'tool_selections/R49-AGENT').glob('*/*.json')):
            receipt = read(path)
            if receipt['tool'] != 'roi_crop' or receipt['status'] != 'failed':
                continue
            source = services / 'tool_cache' / receipt['cache_key']
            yield arm, path.parent.name, int(path.stem), source, read(source / 'request.json')


def replay_worker(request, output, worker, interpreter):
    request = dict(request, artifact_dir=str(output / 'artifacts'))
    output.mkdir(parents=True)
    (output / 'request.json').write_text(json.dumps(request, ensure_ascii=False) + '\n', encoding='utf-8')
    result = subprocess.run([str(interpreter), '-B', str(worker)], input=json.dumps(request),
                            capture_output=True, text=True, timeout=90,
                            env={**os.environ, 'CUDA_VISIBLE_DEVICES': '', 'PYTHONDONTWRITEBYTECODE': '1'})
    (output / 'backend.stdout.log').write_text(result.stdout, encoding='utf-8')
    (output / 'backend.stderr.log').write_text(result.stderr, encoding='utf-8')
    if result.returncode:
        return {'status': 'failed', 'returncode': result.returncode}
    final = next(line for line in reversed(result.stdout.splitlines()) if line.startswith('CXR_VQA_RESULT='))
    envelope = json.loads(final.split('=', 1)[1])
    if envelope['status'] == 'completed':
        if envelope['original_image'] != request['image'] or not envelope['derived_images']:
            raise ValueError('Original image binding or crop artifacts differ')
    (output / 'result.json').write_text(json.dumps(envelope, ensure_ascii=False) + '\n', encoding='utf-8')
    return envelope


def replay(work, native, out):
    worker = native / 'code/M5/experiments/tool_worker_r54.py'
    helper = native / 'jobs/lab-resident-tools/r55_lab_resident_tools.py'
    if not helper.is_file():
        raise FileNotFoundError(helper)
    interpreter = read(work / 'B0/manifest.json')['runtime']['tools']['roi_crop']['python']
    out.mkdir(parents=True)
    counts = {arm: Counter() for arm in ('B0', 'L1')}
    records = []
    for arm, qid, ordinal, source, request in prepare_requests(work):
        previous = (source / 'backend.stderr.log').read_text(encoding='utf-8')
        missing_helper = "No module named 'r55_lab_resident_tools'" in previous
        counts[arm]['old_missing_resident_helper'] += int(missing_helper)
        target = out / arm / qid / str(ordinal)
        envelope = replay_worker(request, target, worker, interpreter)
        counts[arm][envelope['status']] += 1
        records.append({'arm': arm, 'question_id': qid, 'tool_ordinal': ordinal,
                        'old_cache_path': str(source.relative_to(work)), 'old_missing_resident_helper': missing_helper,
                        'new_result_path': (target / 'result.json').relative_to(out).as_posix(),
                        'status': envelope['status'], 'original_image': request['image'], 'args': request['args']})
    summary = {'work': str(work), 'worker': str(worker), 'arms': {k: dict(v) for k, v in counts.items()},
               'requests': len(records), 'results': records, 'paid_model_requests': 0, 'official_scores_recomputed': False}
    (out / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: v for k, v in summary.items() if k != 'results'}, ensure_ascii=False), flush=True)
    return int(not records or any(r['status'] != 'completed' for r in records))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('work', 'native', 'out'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    sys.exit(replay(args.work, args.native, args.out))
