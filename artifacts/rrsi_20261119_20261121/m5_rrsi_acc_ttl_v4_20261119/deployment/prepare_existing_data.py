"""Prepare the original 848-case stream and a separate native integration pair."""
import argparse
import copy
import json
from pathlib import Path
import sys


COUNTS = {'slake': 114, 'vqarad': 116, 'chexbench': 618}
NATIVE_FIELDS = ('question_id', 'question', 'options', 'images', 'image_id', 'source')


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def labels(path):
    rows = read(path)
    result = {row['question_id']: {key: row[key] for key in ('answer', 'answer_text') if key in row}
              for row in rows}
    if len(result) != len(rows):
        raise ValueError('Duplicate private reference IDs')
    return result


def write_records(path, rows):
    path.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
    path.chmod(0o600)


def image_paths(assets, row):
    return [str((assets / name).resolve(strict=True)) for name in row['images']]


def original_digests(row):
    records = row['image_hashes']
    if len(records) != len(row['images']):
        raise ValueError('Original image digest binding has changed')
    return [record['file_sha256'] for record in records]


def views_for(native, row, dataset, base):
    declared = native['runtime']['backend_config']['r54_image_views_by_path']
    digests = original_digests(row)
    source_row = next(value for value in native['inputs'] if value['question_id'] == row['question_id'])
    result = []
    for name, digest in zip(source_row['images'], digests):
        original = base / 'data' / dataset / name
        value = declared.get(str(original)) or declared.get(str(original.resolve()))
        if value is None:
            matches = [item for item in declared.values() if item.get('recorded_asset_id') == digest]
            if not matches or any(item != matches[0] for item in matches[1:]):
                raise ValueError('Original input-only image annotation is missing or ambiguous')
            value = matches[0]
        result.append(copy.deepcopy(value))
    return result


def materialize(out, public, references, metadata, expected_digests, prepare):
    if out.exists():
        raise ValueError('Preparation destination already exists: ' + str(out))
    out.mkdir(parents=True)
    (out / 'private').mkdir(mode=0o700)
    (out / 'trusted').mkdir(mode=0o700)
    write_records(out / 'public_cases.jsonl', public)
    write_records(out / 'private/references.jsonl', references)
    path = out / 'trusted/native_cases.json'
    path.write_text(json.dumps(metadata, ensure_ascii=False) + '\n', encoding='utf-8')
    path.chmod(0o600)
    manifest = prepare(out / 'public_cases.jsonl', out / 'stream.json')
    unique_images = {}
    for row in manifest['cases']:
        actual = [image['sha256'] for image in row['images']]
        if actual != expected_digests[row['id']]:
            raise ValueError('Original image bytes differ from the existing source record: ' + row['id'])
        for image in row['images']:
            unique_images[image['path']] = Path(image['path']).stat().st_size
    return {'questions': manifest['n'], 'unique_images': len(unique_images),
            'original_image_bytes': sum(unique_images.values()),
            'original_image_digest_bindings_matched': True,
            'public_cases': str(out / 'public_cases.jsonl'), 'stream': str(out / 'stream.json'),
            'references': str(out / 'private/references.jsonl'),
            'native_metadata': str(out / 'trusted/native_cases.json')}


def build(root):
    base = Path('/root/autodl-tmp/medrax_r55_top4_full848')
    old = Path('/root/autodl-tmp/medrax_m5_data_rsi_v2_20261117_plus')
    binding = read(old / 'artifacts/native_bindings/plus.json')
    manifests, assets = Path(binding['manifests']), Path(binding['assets'])
    sys.path.insert(0, str(root / 'source/m5_rrsi_acc_ttl_v4'))
    from m5rrsi.data import prepare

    public, references, metadata, expected = [], [], {}, {}
    cohort_sources = {}
    for dataset, count in COUNTS.items():
        source = read(manifests / 'eval_848' / dataset / 'inputs.json')
        private = labels(manifests / 'eval_848' / dataset / 'labels.json')
        native_path = base / 'manifests/M2' / (dataset + '.json')
        native = read(native_path)
        rows, order = source['inputs'], native['order']
        if len(rows) != count or len(native['inputs']) != count or len(order) != count:
            raise ValueError('Original frozen cohort denominator changed')
        ids = [row['question_id'] for row in rows]
        source_ids = [item['question_id'] if isinstance(item, dict) else item for item in source['order']]
        if source_ids != ids:
            raise ValueError('Source input order differs from its declared order')
        if set(private) != set(ids):
            raise ValueError('Private references do not cover the original cohort')
        for ordinal, (row, original, item) in enumerate(zip(rows, native['inputs'], order), 1):
            qid = row['question_id']
            if (qid != original['question_id'] or qid != item['question_id']
                    or row['question'] != original['question']
                    or list(row.get('options', {}).items()) != list(original.get('options', {}).items())):
                raise ValueError('Original question, option, or order binding changed')
            key = dataset + ':' + item['image_key']
            public.append({'id': qid, 'dataset': dataset, 'question': row['question'],
                           'options': [{'label': label, 'text': text} for label, text in row.get('options', {}).items()],
                           'images': image_paths(assets, row), 'group_keys': [key]})
            references.append({'id': qid, 'reference': private[qid]})
            metadata[qid] = {'native_row': copy.deepcopy(original),
                             'order_item': {**copy.deepcopy(item), 'image_key': key},
                             'ordinal': ordinal,
                             'image_annotations': views_for(native, row, dataset, base)}
            expected[qid] = original_digests(row)
        cohort_sources[dataset] = {'questions': count, 'original_manifest': str(native_path),
                                   'source_inputs': str(manifests / 'eval_848' / dataset / 'inputs.json'),
                                   'id_question_option_order_match': True}
    formal_ids = {row['id'] for row in public}
    if len(formal_ids) != len(public) or len(public) != 848:
        raise ValueError('Original primary stream does not contain 848 unique cases')

    train_source = read(manifests / 'train_new/inputs.json')
    train = train_source['inputs']
    train_ids = [row['question_id'] for row in train]
    if set(train_ids) & formal_ids:
        raise ValueError('Integration input source overlaps the formal 848 cases')
    selection = [0, 1]
    selection_rule = 'First two real train_new cases in the existing input order, selected without consulting labels'
    same_image_pair = original_digests(train[selection[0]]) == original_digests(train[selection[1]])
    source_same_image_pair = len({tuple(original_digests(row)) for row in train}) != len(train)
    train_refs = labels(manifests / 'train_new/labels.json')
    probe_public, probe_refs, probe_metadata, probe_digests = [], [], {}, {}
    previous = {}
    for ordinal, index in enumerate(selection, 1):
        row = train[index]
        qid = row['question_id']
        key = 'integration:' + '|'.join(original_digests(row))
        native = {key: copy.deepcopy(row[key]) for key in NATIVE_FIELDS if key in row}
        prior = previous.setdefault(key, [])
        item = {'question_id': qid, 'image_key': key, 'previous_ids': prior.copy()}
        annotation = {key: row[key] for key in ('modality', 'view') if key in row}
        annotation['source'] = 'Existing train_new public image metadata'
        probe_public.append({'id': qid, 'dataset': 'integration_train_new', 'question': row['question'],
                             'options': [{'label': label, 'text': text} for label, text in row.get('options', {}).items()],
                             'images': image_paths(assets, row), 'group_keys': [key]})
        probe_refs.append({'id': qid, 'reference': train_refs[qid]})
        probe_metadata[qid] = {'native_row': native, 'order_item': item, 'ordinal': ordinal,
                                   'image_annotations': [copy.deepcopy(annotation) for _ in row['images']]}
        probe_digests[qid] = original_digests(row)
        prior.append(qid)

    for path in (root / 'prepared', root / 'integration_inputs'):
        if path.exists():
            raise ValueError('Preparation destination already exists: ' + str(path))
    primary = materialize(root / 'prepared', public, references, metadata, expected, prepare)
    probe = materialize(root / 'integration_inputs', probe_public, probe_refs, probe_metadata, probe_digests, prepare)
    report = {'status': 'prepared', 'dataset_order': list(COUNTS), 'cohorts': cohort_sources,
              'primary': primary, 'integration': probe,
              'integration_case_ids': [row['id'] for row in probe_public],
              'integration_source_positions': [index + 1 for index in selection],
              'integration_selection': selection_rule,
              'integration_same_image_pair': same_image_pair,
              'integration_same_image_probe_available': same_image_pair,
              'integration_source_has_same_image_pair': source_same_image_pair,
              'integration_formal_id_overlap': False, 'private_feedback_preserves_answer_text': True,
              'original_files_modified': False, 'data_copied': False, 'new_model_requests': 0,
              'data_transferred_to_client': False}
    (root / 'deployment').mkdir(exist_ok=True)
    (root / 'deployment/data_prepared.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    print(json.dumps(build(parser.parse_args().root.resolve()), ensure_ascii=False, indent=2))
