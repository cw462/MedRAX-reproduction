"""Extract only author-referenced originals from the official image archives."""

import argparse
from collections import defaultdict
import json
from pathlib import Path, PurePosixPath
import shutil
import tarfile
import zipfile

from prepare_chexbench_extension import image_relative, selected_rows


def stage(release, openi, slake, dest):
    nlm_paths = defaultdict(set)
    slake_paths = defaultdict(set)
    for _, _, subset, _, _, row, _, _ in selected_rows(json.loads(release.read_bytes())):
        values = row['image_path']
        for name in ([values] if isinstance(values, str) else values):
            path = image_relative(name)
            if subset == 'SLAKE':
                slake_paths[path.parts[-2:]].add(path)
            else:
                nlm_paths[path.name].add(path)

    def write(handle, paths):
        paths = sorted(paths)
        target = dest/paths[0]
        target.parent.mkdir(parents=True, exist_ok=True)
        temp = target.with_name('.'+target.name+'.part')
        with temp.open('wb') as output:
            shutil.copyfileobj(handle, output)
        temp.replace(target)
        for path in paths[1:]:
            alias = dest/path
            alias.parent.mkdir(parents=True, exist_ok=True)
            if alias.is_file():
                if alias.read_bytes()!=target.read_bytes():
                    raise ValueError(f'Existing image binding differs: {path}')
            else:
                alias.hardlink_to(target)

    seen = set()
    with tarfile.open(openi, 'r|gz') as archive:
        for member in archive:
            key = PurePosixPath(member.name).name
            if member.isfile() and key in nlm_paths:
                if key in seen:
                    raise ValueError(f'Duplicate NLM image name: {key}')
                seen.add(key)
                with archive.extractfile(member) as handle:
                    write(handle, nlm_paths[key])
    if missing := nlm_paths.keys()-seen:
        raise ValueError(f'{len(missing)} NLM image names absent from official archive')

    seen = set()
    with zipfile.ZipFile(slake) as archive:
        for member in archive.infolist():
            key = PurePosixPath(member.filename).parts[-2:]
            if not member.is_dir() and key in slake_paths:
                if key in seen:
                    raise ValueError(f'Duplicate SLAKE image path: {key}')
                seen.add(key)
                with archive.open(member) as handle:
                    write(handle, slake_paths[key])
    if missing := slake_paths.keys()-seen:
        raise ValueError(f'{len(missing)} SLAKE image paths absent from official archive')
    return {'openi_unique_images':len(nlm_paths), 'slake_unique_images':len(slake_paths)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    for arg in ('release','openi','slake','dest'):
        parser.add_argument('--'+arg,type=Path,required=True)
    args = parser.parse_args()
    print(json.dumps(stage(args.release,args.openi,args.slake,args.dest)))
