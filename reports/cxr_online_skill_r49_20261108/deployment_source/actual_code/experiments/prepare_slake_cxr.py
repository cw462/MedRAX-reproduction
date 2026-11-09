"""Prepare the official SLAKE test CXR subset; never manufacture a 114-item list."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import zipfile

REVISION = 'a9083ce6c34ac3ffb17671a605962924d8a8f9e9'
SOURCE = 'https://huggingface.co/datasets/BoKelvin/SLAKE'


def write_jsonl(path, rows):
    path.write_text(''.join(json.dumps(x, ensure_ascii=False) + '\n' for x in rows), encoding='utf-8')


def prepare(source, out):
    from PIL import Image
    rows = json.loads((source / 'test.json').read_text(encoding='utf-8'))
    selected = [r for r in rows if r['q_lang'] == 'en' and r['modality'] == 'X-Ray'
                and r['answer_type'] == 'CLOSED' and r['location'] == 'Lung']
    out.mkdir(parents=True, exist_ok=True)
    inputs, refs = [], []
    with zipfile.ZipFile(source / 'imgs.zip') as archive:
        members = archive.namelist()
        for image in sorted({r['img_name'] for r in selected}):
            matches = [p for p in members if p == image or p.endswith('/' + image)]
            if len(matches) != 1:
                raise ValueError('unique_official_original_required:' + image)
            rel = PurePosixPath(image)
            if rel.is_absolute() or '..' in rel.parts:
                raise ValueError('unsafe_image_path')
            target = out / 'images' / image
            target.parent.mkdir(parents=True, exist_ok=True)
            if not target.exists(): target.write_bytes(archive.read(matches[0]))
            with Image.open(target) as im: im.verify()
    for row in selected:
        qid = 'slake_' + str(row['qid'])
        inputs.append({'question_id': qid, 'question': row['question'],
                       'images': ['images/' + row['img_name']], 'image_id': str(row['img_id']),
                       'source': {'dataset': 'SLAKE', 'revision': REVISION, 'split': 'test',
                                  'original_qid': row['qid'], 'original_image': row['img_name']}})
        refs.append({'question_id': qid, 'answer': row['answer'], 'answer_type': 'CLOSED',
                     'image_id': str(row['img_id']), 'content_type': row['content_type']})
    write_jsonl(out / 'inputs.jsonl', inputs)
    write_jsonl(out / 'references.jsonl', refs)
    manifest = {'name': 'SLAKE-English-CXR-Closed', 'source': SOURCE, 'revision': REVISION,
                'license': 'CC-BY-4.0', 'split': 'official test.json', 'questions': len(inputs),
                'images': len({r['image_id'] for r in inputs}),
                'filter': {'q_lang': 'en', 'modality': 'X-Ray', 'answer_type': 'CLOSED', 'location': 'Lung'},
                'paper_114_list_obtained': False, 'strict_paper_subset_reproduction_claim': False,
                'note': '114 matches the reported count by filtering; original independent paper IDs were not located. No sampling or added options.',
                'excluded_inference_fields': ['answer', 'answer_type', 'content_type', 'triple', 'masks', 'knowledge graph'],
                'test_json_sha256': hashlib.sha256((source / 'test.json').read_bytes()).hexdigest(),
                'question_ids': [x['question_id'] for x in inputs],
                'patient_exam_ids': 'not supplied; paired bootstrap clusters use image_id',
                'visual_review': 'pending independent original-image inspection'}
    (out / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return manifest


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--source', type=Path, required=True)
    p.add_argument('--out', type=Path, default=Path('data/slake_cxr'))
    a = p.parse_args(); print(json.dumps(prepare(a.source, a.out), ensure_ascii=False))
