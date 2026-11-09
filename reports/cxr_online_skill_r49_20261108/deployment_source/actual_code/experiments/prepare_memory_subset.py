"""Freeze a reproducible question subset and extract its original images.

Selection is declared before any model call and never uses labels or outcomes:
  * rows are taken in frozen file order within one split;
  * only single-image questions whose audit status is `readable`;
  * cases quarantined by the leakage-exclusion manifest are removed;
  * the first N survivors are kept.

The script verifies every extracted image byte-for-byte against the frozen image
audit and refuses to write the subset if anything differs. Output layout:

  <out>/inputs/<name>.jsonl        exact three-field frozen rows
  <out>/images/figures/...         original image bytes, frozen relative paths
  <out>/selection_manifest.json    rule, counts, hashes, per-question record

Usage:
  python experiments/prepare_memory_subset.py --splits DIR --exclusions FILE \
      --image-audit FILE --archive ZIP --out DIR --train 60 --validation 40
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import zipfile


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def read_jsonl(path):
    return [json.loads(line) for line in Path(path).read_text(encoding='utf-8-sig').splitlines() if line.strip()]


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def select(rows, audit_split, excluded, image_by_name, limit):
    chosen, seen_cases = [], set()
    for row in rows:
        qid = row['question_id']
        case_hash = audit_split[qid]['case_hash']
        if case_hash in excluded or case_hash in seen_cases:
            continue
        if len(row['images']) != 1:
            continue
        fact = image_by_name.get(row['images'][0])
        if fact is None or fact.get('status') != 'readable' or qid not in fact.get('question_ids', []):
            continue
        chosen.append({'question_id': qid, 'case_hash': case_hash, 'question': row['question'],
                       'images': row['images'], 'image_sha256': [fact['sha256']]})
        seen_cases.add(case_hash)
        if len(chosen) >= limit:
            break
    return chosen


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--splits', type=Path, required=True)
    parser.add_argument('--exclusions', type=Path, required=True)
    parser.add_argument('--image-audit', type=Path, required=True)
    parser.add_argument('--archive', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--train', type=int, default=60)
    parser.add_argument('--validation', type=int, default=40)
    args = parser.parse_args(argv)

    audit = {row['question_id']: row for row in read_jsonl(args.splits / 'audit_index.jsonl')}
    excluded_payload = read_json(args.exclusions)
    excluded = {
        'memory_train': set(excluded_payload['excluded_case_hashes_by_split']['memory_train']),
        'validation': set(excluded_payload['excluded_case_hashes_by_split']['validation']),
    }
    image_by_name = {row['dataset_image_path']: row for row in read_jsonl(args.image_audit)}

    selections = {}
    for split, limit in (('memory_train', args.train), ('validation', args.validation)):
        rows = read_jsonl(args.splits / f'{split}.inputs.jsonl')
        chosen = select(rows, audit, excluded[split], image_by_name, limit)
        if len(chosen) < limit:
            raise SystemExit(f'Only {len(chosen)} eligible {split} questions, wanted {limit}')
        qids = {c['question_id'] for c in chosen}
        cases = {c['case_hash'] for c in chosen}
        if len(qids) != len(chosen) or len(cases) != len(chosen):
            raise SystemExit('Selection is not question/case unique')
        selections[split] = chosen

    train_cases = {c['case_hash'] for c in selections['memory_train']}
    validation_cases = {c['case_hash'] for c in selections['validation']}
    if train_cases & validation_cases:
        raise SystemExit('Selected train and validation cases overlap')

    args.out.mkdir(parents=True, exist_ok=False)
    (args.out / 'inputs').mkdir()
    records = {}
    with zipfile.ZipFile(args.archive) as archive:
        names = set(archive.namelist())
        for split, chosen in selections.items():
            lines = []
            for item in chosen:
                member = item['images'][0]
                if member not in names:
                    raise SystemExit(f'Archive member missing: {member}')
                data = archive.read(member)
                if sha256_bytes(data) != item['image_sha256'][0]:
                    raise SystemExit(f'Extracted image differs from the frozen audit: {member}')
                target = args.out / 'images' / member
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
                lines.append(json.dumps({'question_id': item['question_id'],
                                         'question': item['question'],
                                         'images': item['images']}, ensure_ascii=False) + '\n')
                records[item['question_id']] = {
                    'split': split, 'case_hash': item['case_hash'],
                    'image': member, 'image_sha256': item['image_sha256'][0]}
            (args.out / 'inputs' / f'{split}_subset_v1.jsonl').write_text(''.join(lines), encoding='utf-8')

    manifest = {
        'schema_version': 1,
        'rule': 'first N single-image readable non-quarantined rows in frozen file order, case-unique',
        'uses_labels': False, 'uses_outcomes': False, 'uses_model_calls': False,
        'splits_dir': str(args.splits.resolve()),
        'splits_manifest_sha256': sha256_bytes((args.splits / 'manifest.json').read_bytes()),
        'exclusions_sha256': sha256_bytes(args.exclusions.read_bytes()),
        'image_audit_sha256': sha256_bytes(args.image_audit.read_bytes()),
        'archive_sha256': sha256_bytes(args.archive.read_bytes()),
        'counts': {split: len(chosen) for split, chosen in selections.items()},
        'questions': records,
    }
    (args.out / 'selection_manifest.json').write_text(
        json.dumps(manifest, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    print(json.dumps({'counts': manifest['counts'], 'out': str(args.out)}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
