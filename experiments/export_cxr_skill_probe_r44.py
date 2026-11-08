"""Streamed private export -> public saved evidence; never calls a model."""
import argparse
import base64
import json
import os
from pathlib import Path
import shutil

from cxr_skill_probe_r44 import ARMS, rows


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def export(source, data, out):
    assert not out.exists(), 'new_public_evidence_directory_required'
    assert (source/'pilot.exitcode').read_text().strip() == '0'
    assert read(source/'complete.json')['new_main_sends'] == 54
    inputs=rows(data/'inputs.jsonl');image_map={}
    for row in inputs:
        for arm in ARMS:
            folder=source/'calls'/arm/row['question_id']/'1'
            request=read(folder/'request.json')
            image_ref=request['messages'][1]['content'][1]['image_url']['url']
            digest=image_ref['cxr_request_image_base64_sha256']
            encoded=(source/'request_image_base64'/digest).read_text(encoding='ascii')
            original=(data/row['images'][0]).resolve()
            assert encoded == base64.b64encode(original.read_bytes()).decode('ascii')
            path=os.path.relpath(original,out).replace('\\','/')
            item={'path':path,'media_type':image_ref['media_type'],
                  'reconstruction':'data:<media_type>;base64,<base64 of exact original file bytes>'}
            if digest in image_map:assert image_map[digest] == item
            image_map[digest]=item
    out.mkdir(parents=True)
    for row in inputs:
        for arm in ARMS:
            relative=Path('calls')/arm/row['question_id']/'1'
            target=out/relative;target.mkdir(parents=True)
            for name in ['request.json','response.json','started.json','result.json']:
                shutil.copyfile(source/relative/name,target/name)
            prediction=out/'predictions'/arm/(row['question_id']+'.json')
            prediction.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(source/'predictions'/arm/prediction.name,prediction)
    for name in ['protocol.json','inputs.json','complete_P0.json','complete_P1.json','complete.json',
                 'pilot.exitcode','pilot.log']:
        shutil.copyfile(source/name,out/name)
    (out/'IMAGE_MAP.json').write_text(json.dumps(image_map,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (out/'README.md').write_text('''# Saved R44 evidence

54 actual requests, responses, send intents and per-request usage/cost records are preserved as saved files. No tools or derived images were used. The config/key are not exported.

`request.json` is the unmodified saved parameter archive from the existing R4.1 transport. Its image content reference is lossless: IMAGE_MAP.json maps each reference to the exact original JPEG. Base64-encode those bytes and restore the recorded media type to reconstruct the image data URI. No answer/reference or source example was sent. All source/development originals are published in the linked data directory.

`result.json` cost is a usage-based local CNY proxy, not a provider invoice. Missing/invalid replies would remain recorded and counted. The pilot is a source/development component comparison, not a rerun of old target benchmarks.
''',encoding='utf-8')
    return {'request_response_pairs':54,'original_development_images':len(image_map),'tools':0}


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    for name in ['source','data','out']:
        parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args()
    print(json.dumps(export(args.source,args.data,args.out)))
