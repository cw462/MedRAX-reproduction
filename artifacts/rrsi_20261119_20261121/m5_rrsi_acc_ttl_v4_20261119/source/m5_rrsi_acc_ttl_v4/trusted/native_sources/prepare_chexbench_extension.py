"""Freeze the author-defined CheXbench Axis 2 subset from the gated release."""

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import tempfile

from PIL import Image, ImageOps

from score_cxr_vqa_toolsets import normalize


REPO = 'StanfordAIMI/chexbench'
REVISION = '97fc510924d1d268665e271d30fa1465afa5ca36'
SELECTION = (
    ('Visual Question Answering', 'Rad-Restruct', 115),
    ('Visual Question Answering', 'SLAKE', 123),
    ('Fine-Grained Reasoning', 'OpenI', 380),
)


def download_release():
    from huggingface_hub import get_token, hf_hub_download
    if not get_token():
        raise SystemExit('Hugging Face login is unavailable in the server credential slot.')
    try:
        return Path(hf_hub_download(REPO, 'data.json', repo_type='dataset', revision=REVISION, token=True))
    except Exception as exc:
        # Error bodies and request headers may contain authentication material.
        status = getattr(getattr(exc, 'response', None), 'status_code', None)
        raise SystemExit(f'Official CheXbench download failed ({type(exc).__name__}, HTTP {status}).') from None


def selected_rows(bench):
    ids = set()
    for task, subset, count in SELECTION:
        selected = [(i, row) for i, row in enumerate(bench[task]) if row['data_source'] == subset]
        if len(selected) != count:
            raise ValueError(f'Author task/source selector yielded {len(selected)}, expected {count}: {task}/{subset}')
        for index, row in selected:
            options = {chr(65+i): row[f'option_{i}'] for i in range(4) if isinstance(row.get(f'option_{i}'), str)}
            gold = row['answer']
            if set(options) != {'A', 'B'} or type(gold) is not int or gold not in (0, 1):
                raise ValueError(f'Unexpected option/answer schema in {task}/{subset}/{index}')
            # The official evaluator indexes the original task list. Preserve
            # that index even when a release also includes its own unique ID.
            source_id = row.get('unique_id')
            qid = f'chexbench_{subset.lower().replace("-", "_")}_{index:04d}'
            if qid in ids or not isinstance(row['question'], str) or not row['question'].strip():
                raise ValueError(f'Invalid source question at {task}/{index}')
            ids.add(qid)
            yield qid, task, subset, index, source_id, row, options, chr(65+gold)


def image_fingerprints(path):
    """Use identical file bytes and identical decoded RGB pixels as two checks."""
    with Image.open(path) as im:
        im = ImageOps.exif_transpose(im).convert('RGB')
        pixels = hashlib.sha256(str(im.size).encode() + im.tobytes()).hexdigest()
    return hashlib.sha256(path.read_bytes()).hexdigest(), pixels


def image_relative(value):
    path = PurePosixPath(value)
    if path.is_absolute() or '..' in path.parts or '\\' in value or ':' in value:
        raise ValueError('Official image path requires an explicit local path mapping')
    if path.parts[:1] == ('data',):
        path = PurePosixPath(*path.parts[1:])
    return path


def jsonl(path, rows):
    path.write_text(''.join(json.dumps(row, ensure_ascii=False)+'\n' for row in rows), encoding='utf-8')


def prepare(release, source_root, independent_slake, out):
    if out.exists():
        raise FileExistsError(out)
    source_bytes = release.read_bytes()
    bench = json.loads(source_bytes)
    inputs, references, overlap = [], [], []
    fingerprints = {}
    independent = defaultdict(list)
    independent_paths = defaultdict(list)
    for line in (independent_slake/'inputs.jsonl').read_text(encoding='utf-8').splitlines():
        row = json.loads(line)
        for img in row['images']:
            if img not in fingerprints:
                fingerprints[img] = image_fingerprints(independent_slake/img)
            independent[fingerprints[img][1]].append(row)
        original = row.get('source', {}).get('original_image')
        if original:
            independent_paths[PurePosixPath(original).parts[-2:]].append(row)
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=out.parent) as tmp:
        stage = Path(tmp)/'frozen'
        stage.mkdir()
        digests = {}
        for qid, task, subset, index, source_id, row, options, gold in selected_rows(bench):
            official = row['image_path']
            paths = [official] if isinstance(official, str) else official
            if not isinstance(paths, list) or not paths:
                raise ValueError(f'No official image for {qid}')
            bound, pixel_keys = [], []
            for value in paths:
                rel = image_relative(value)
                if rel not in digests:
                    src = source_root / rel
                    if not src.is_file():
                        raise FileNotFoundError(f'Missing original image named by author release: {rel}')
                    digests[rel] = image_fingerprints(src)
                    target = stage / 'images' / rel
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(src, target)
                bound.append((PurePosixPath('images') / rel).as_posix())
                pixel_keys.append(digests[rel][1])
            image_id = 'pixels_' + hashlib.sha256('\n'.join(sorted(pixel_keys)).encode()).hexdigest()
            source = dict(dataset=REPO, subset=subset, task=task, task_index=index, official_id=source_id,
                          official_image_paths=paths, image_pixel_ids=pixel_keys,
                          official_study_id=row.get('study_id'), official_patient_id=row.get('patient_id'))
            inputs.append(dict(question_id=qid, question=row['question'], options=options, images=bound,
                               image_id=image_id, source=source))
            references.append(dict(question_id=qid, answer=gold, answer_text=options[gold]))
            if subset == 'SLAKE':
                same_image = {r['question_id']: r for key in pixel_keys for r in independent[key]}
                same_path = {r['question_id']: r for name in paths for r in independent_paths[PurePosixPath(name).parts[-2:]]}
                pixel_matches = sorted(same_image)
                same_image.update(same_path)
                same_question = sorted(k for k,r in same_image.items() if normalize(r['question']) == normalize(row['question']))
                if same_image:
                    overlap.append(dict(question_id=qid, image_id=image_id, same_image=sorted(same_image),
                                        same_question=same_question, same_pixels=pixel_matches, same_official_path=sorted(same_path)))

        jsonl(stage/'inputs.jsonl', inputs)
        jsonl(stage/'references.jsonl', references)
        jsonl(stage/'slake_overlap.jsonl', overlap)
        manifest = dict(repo=REPO, revision=REVISION, source_sha256=hashlib.sha256(source_bytes).hexdigest(),
                        selection=[dict(task=t, subset=s, n=n) for t,s,n in SELECTION],
                        questions=len(inputs), question_ids=[r['question_id'] for r in inputs],
                        unique_images=len({pixel for _,pixel in digests.values()}),
                        image_sha256={str(p): b for p,(b,_) in digests.items()},
                        slake_overlap=dict(chexbench_questions_on_shared_images=len(overlap),
                                           shared_image_groups=len({r['image_id'] for r in overlap}),
                                           chexbench_shared_questions=sum(bool(r['same_question']) for r in overlap),
                                           independent_shared_questions=len({q for r in overlap for q in r['same_question']})),
                        fields_for_history='No clinical history projected from reference text or report.')
        (stage/'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
        stage.rename(out)
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--official-json', type=Path, help='Pinned official download staged separately')
    parser.add_argument('--source-images', type=Path, required=True)
    parser.add_argument('--independent-slake', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    manifest = prepare(args.official_json or download_release(), args.source_images, args.independent_slake, args.out)
    print(json.dumps({k: manifest[k] for k in ('revision', 'questions', 'unique_images', 'slake_overlap')}))
