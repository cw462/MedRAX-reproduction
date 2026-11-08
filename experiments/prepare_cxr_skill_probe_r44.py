"""Select an official SLAKE train/source and validation/development probe.

Selection uses split, task metadata, IDs and image overlap only.  Development
answers are copied mechanically to a separate file and never printed here.
"""
import argparse
from collections import Counter
from io import BytesIO
import hashlib
import json
from pathlib import Path
import re
import zipfile

from PIL import Image, ImageOps

REVISION = 'a9083ce6c34ac3ffb17671a605962924d8a8f9e9'
REPO = Path(__file__).resolve().parents[1]
TARGETS = {
    'chexbench': REPO/'reports/cxr_vqa_extension/results/chexbench',
    'slake': REPO/'reports/cxr_vqa_toolsets/results/slake',
    'vqarad': REPO/'reports/cxr_vqa_toolsets/results/vqarad',
}


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def rows(path):
    return [json.loads(x) for x in path.read_text(encoding='utf-8').splitlines() if x.strip()]


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')


def jsonl(path, values):
    path.write_text(''.join(json.dumps(x, ensure_ascii=False)+'\n' for x in values), encoding='utf-8')


def pixels(blob):
    # Existing project decoded-image deduplication, not patient identification.
    with Image.open(BytesIO(blob)) as image:
        image = ImageOps.exif_transpose(image).convert('RGB')
        return hashlib.sha256(str(image.size).encode()+image.tobytes()).hexdigest()


def eligible(row):
    return all(row[key] == value for key, value in {
        'q_lang':'en', 'modality':'X-Ray', 'answer_type':'CLOSED', 'location':'Lung'
    }.items())


def prepare(cache, out):
    assert not out.exists(), 'new_data_directory_required'
    training = sorted(filter(eligible, read(cache/'train.json')), key=lambda x:x['qid'])
    validation = sorted(filter(eligible, read(cache/'validation.json')), key=lambda x:x['qid'])
    target_pixels, target_xmlab, scanned = set(), set(), set()
    for folder in TARGETS.values():
        for row in rows(folder/'inputs.jsonl'):
            source = row.get('source', {})
            target_xmlab.update(re.findall(r'xmlab\d+', json.dumps(source)))
            known = source.get('image_pixel_ids', [])
            if known:
                target_pixels.update(known)
            else:
                for rel in row['images']:
                    path = (folder/rel).resolve()
                    if path not in scanned:
                        target_pixels.add(pixels(path.read_bytes())); scanned.add(path)
    overlap, image_data, pixel_ids = [], {}, {}
    with zipfile.ZipFile(cache/'imgs.zip') as archive:
        members = archive.namelist()
        for name in sorted({x['img_name'] for x in training+validation}):
            matches = [x for x in members if x == name or x.endswith('/'+name)]
            assert len(matches) == 1, name
            image_data[name] = archive.read(matches[0])
            pixel_ids[name] = pixels(image_data[name])
    def clean(values, split):
        result = []
        for row in values:
            name = row['img_name']
            origin_overlap = name.split('/')[0] in target_xmlab
            pixel_overlap = pixel_ids[name] in target_pixels
            if origin_overlap or pixel_overlap:
                overlap.append({'split':split, 'qid':row['qid'], 'image':name,
                                'target_origin_overlap':origin_overlap,
                                'target_exact_pixel_overlap':pixel_overlap})
            else:
                result.append(row)
        return result
    train_clean = clean(training, 'train')
    dev_clean = clean(validation, 'validation')
    training_pixels = {pixel_ids[x['img_name']] for x in train_clean}
    development = []
    for row in dev_clean:
        if pixel_ids[row['img_name']] in training_pixels:
            overlap.append({'split':'validation', 'qid':row['qid'], 'image':row['img_name'],
                            'eligible_train_exact_pixel_overlap':True})
        else:
            development.append(row)
    # One lowest-qid example per available task category on different images,
    # then lowest qids on new images until twelve. Never consult answer values.
    source, used_pixels = [], set()
    for category in sorted({x['content_type'] for x in train_clean}):
        candidate = next(x for x in train_clean if x['content_type'] == category
                         and pixel_ids[x['img_name']] not in used_pixels)
        source.append(candidate); used_pixels.add(pixel_ids[candidate['img_name']])
    for candidate in train_clean:
        if len(source) == 12: break
        if pixel_ids[candidate['img_name']] not in used_pixels:
            source.append(candidate); used_pixels.add(pixel_ids[candidate['img_name']])
    source.sort(key=lambda x:x['qid'])
    assert len(source) == 12 and development
    assert not used_pixels & {pixel_ids[x['img_name']] for x in development}
    out.mkdir(parents=True)
    selected_images = sorted({x['img_name'] for x in source+development})
    for name in selected_images:
        path = out/'images'/name; path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(image_data[name])
    def input_row(row, split):
        return {'question_id':f"r44_{split}_{row['qid']}", 'question':row['question'],
                'images':['images/'+row['img_name']], 'image_id':pixel_ids[row['img_name']],
                'source':{'dataset':'BoKelvin/SLAKE', 'revision':REVISION, 'split':split,
                          'original_qid':row['qid'], 'original_image':row['img_name']}}
    jsonl(out/'source_examples.jsonl', [dict(input_row(x, 'train'), answer=x['answer'],
          content_type=x['content_type']) for x in source])
    jsonl(out/'inputs.jsonl', [input_row(x, 'validation') for x in development])
    jsonl(out/'references.jsonl', [{'question_id':f"r44_validation_{x['qid']}",
          'answer':x['answer'], 'content_type':x['content_type'],
          'image_id':pixel_ids[x['img_name']]} for x in development])
    manifest = {
        'experiment_id':'skill_probe_r44_20261108', 'source_repo':'https://huggingface.co/datasets/BoKelvin/SLAKE',
        'revision':REVISION, 'license':'CC-BY-4.0',
        'filter':{'q_lang':'en','modality':'X-Ray','answer_type':'CLOSED','location':'Lung'},
        'source_split':'official train.json', 'development_split':'official validation.json',
        'source_questions':len(source), 'source_images':len(used_pixels),
        'development_questions':len(development),
        'development_images':len({x['img_name'] for x in development}),
        'eligible_before_overlap':{'train':len(training),'validation':len(validation)},
        'eligible_after_target_overlap':{'train':len(train_clean),'validation':len(dev_clean)},
        'source_qids':[x['qid'] for x in source],
        'development_qids':[x['qid'] for x in development],
        'source_category_counts':dict(Counter(x['content_type'] for x in source)),
        'development_category_counts':dict(Counter(x['content_type'] for x in development)),
        'source_selection':'lowest qid per sorted content_type on distinct decoded images, then lowest qids on new images to 12',
        'development_selection':'all eligible validation rows, excluding existing targets by origin or exact decoded pixels and eligible training-image duplicates',
        'selection_uses_answers':False, 'development_answers_human_inspected_before_generation':False,
        'target_overlap':overlap,
        'original_images':[{'path':'images/'+name, 'decoded_pixel_id':pixel_ids[name],
                            'bytes':len(image_data[name])} for name in selected_images],
        'patient_independence':'unknown; no patient/exam IDs supplied, exact image and origin exclusions only',
        'not_official_test_benchmark':True,
    }
    write(out/'manifest.json', manifest)
    return {k:manifest[k] for k in ['source_questions','source_images','development_questions',
            'development_images','source_qids','development_qids','source_category_counts',
            'development_category_counts','eligible_after_target_overlap']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--cache', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.cache, args.out), ensure_ascii=False))
