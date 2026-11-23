"""Prepare TTL inputs in place from explicitly bound, existing native datasets."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from m5rrsi.data import prepare


def build(binding, destination):
    out = Path(destination).resolve()
    if out.exists():
        raise ValueError('Use a new preparation directory')
    rows, references, metadata = [], [], {}
    counts = {'slake': 114, 'vqarad': 116, 'chexbench': 618}
    if binding['dataset_order'] != ['slake', 'vqarad', 'chexbench']:
        raise ValueError('Original native dataset order is required')
    for dataset in binding['dataset_order']:
        manifest = json.loads(Path(binding['manifests'][dataset]).read_text())
        data = Path(binding['data'][dataset]).resolve()
        refdir = Path(binding['references'][dataset]).resolve()
        inputs, order = manifest['inputs'], manifest['order']
        if len(inputs) != counts[dataset] or len(order) != len(inputs):
            raise ValueError('Frozen cohort denominator changed')
        views = manifest['runtime']['backend_config']['r54_image_views_by_path']
        for ordinal, (row, item) in enumerate(zip(inputs, order), 1):
            qid = row['question_id']
            if qid != item['question_id']:
                raise ValueError('Original native question order changed')
            images, annotations = [], []
            for name in row['images']:
                path = (data / name).resolve(strict=True)
                if not path.is_relative_to(data):
                    raise ValueError('Original image is outside its declared data root')
                annotation = views.get(str(path)) or views.get(str(data / name))
                if annotation is None:
                    raise ValueError('Rebind the existing input-only view annotations before preparation')
                images.append(str(path))
                annotations.append(annotation)
            rows.append({'id': qid, 'dataset': dataset, 'question': row['question'],
                         'options': [{'label': k, 'text': v} for k, v in row.get('options', {}).items()],
                         'images': images, 'group_keys': [dataset + ':' + item['image_key']]})
            filename = manifest['reference_files'][qid]['file']
            if filename != qid + '.json':
                raise ValueError('Unexpected native reference filename')
            reference = json.loads((refdir / filename).read_text())
            if reference['question_id'] != qid:
                raise ValueError('Reference identity changed')
            references.append({'id': qid, 'reference': reference['answer']})
            metadata[qid] = {'native_row': row,
                             'order_item': {**item, 'image_key': dataset + ':' + item['image_key']},
                             'ordinal': ordinal, 'image_annotations': annotations}
    if len(rows) != len({row['id'] for row in rows}):
        raise ValueError('Duplicate frozen case IDs')
    if len(rows) != 848:
        raise ValueError('Exactly 848 original cases are required')
    out.mkdir(parents=True)
    private = out / 'private'
    trusted = out / 'trusted'
    private.mkdir(mode=0o700)
    trusted.mkdir(mode=0o700)
    for path, records in ((out / 'public_cases.jsonl', rows), (private / 'references.jsonl', references)):
        path.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in records), encoding='utf-8')
        path.chmod(0o600)
    (trusted / 'native_cases.json').write_text(json.dumps(metadata, ensure_ascii=False) + '\n', encoding='utf-8')
    manifest = prepare(out / 'public_cases.jsonl', out / 'stream.json')
    return {'questions': manifest['n'], 'datasets': counts, 'data_copied': False,
            'initial_memory': 'empty', 'new_model_requests': 0}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binding', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(json.loads(args.binding.read_text()), args.out)))
