"""Lossless saved-archive E evidence export, with explicit per-request image map."""
import argparse,base64,hashlib,json,os,shutil
from pathlib import Path
from cxr_episodic_feedback_r46 import read,rows,ARMS


def export(source,data,scores,out):
    assert not out.exists(),'new_evidence_directory_required'
    complete=read(source/'source.complete.json')
    effective=source/('source.effective.exitcode' if complete.get('completion_mode')=='known_progress_metadata_failure_recovery' else 'source.exitcode')
    assert effective.read_text().strip()=='0' and (source/'development.exitcode').read_text().strip()=='0'
    if effective.name=='source.effective.exitcode':assert (source.parent/'jobs/source_recovery_2.exitcode').read_text().strip()=='0'
    assert read(source/'source.complete.json')['main_calls']==24 and read(source/'development.complete.json')['main_calls']==54
    registry={x['question_id']:x for name in ['source_inputs.jsonl','inputs.jsonl'] for x in rows(data/name)}
    image_map={};count=0;bad=[]
    out.mkdir(parents=True)
    for request in sorted((source/'calls').glob('*/*/1/request.json')):
        q=request.parent.parent.name;row=registry[q];value=read(request)
        ref=value['messages'][1]['content'][1]['image_url']['url'];digest=ref['cxr_request_image_base64_sha256']
        encoded=(source/'request_image_base64'/digest).read_text(encoding='ascii');blob=base64.b64decode(encoded,validate=True)
        expected=(data/row['images'][0]).read_bytes();match=blob==expected
        if match:
            target=(data/row['images'][0]).resolve();path=os.path.relpath(target,out).replace('\\','/')
        else:
            target=out/'invalid_request_image_bytes'/(hashlib.sha256(blob).hexdigest()+'.bin');target.parent.mkdir(exist_ok=True);target.write_bytes(blob)
            path=target.relative_to(out).as_posix();bad.append({'request':request.relative_to(source).as_posix(),'question_id':q,'expected_image_match':False})
        item={'path':path,'media_type':ref['media_type'],'matches_expected_original':match,
              'bytes_sha256':hashlib.sha256(blob).hexdigest(),'reconstruction':'base64-encode exact linked bytes; do not repair'}
        if digest in image_map:assert image_map[digest]==item
        image_map[digest]=item;count+=1
    assert count==78
    for path in source.rglob('*'):
        if not path.is_file() or any(part.startswith('.') for part in path.relative_to(source).parts):continue
        if 'request_image_base64' in path.relative_to(source).parts:continue
        target=out/path.relative_to(source);target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(path,target)
    for path in (source.parent/'jobs').iterdir():
        if path.is_file() and path.suffix in ['.json','.log','.exitcode']:
            target=out/'job_records'/path.name;target.parent.mkdir(exist_ok=True);shutil.copyfile(path,target)
    for name in ['summary.json','per_question.jsonl']:
        target=out/'scores'/name;target.parent.mkdir(exist_ok=True);shutil.copyfile(scores/name,target)
    (out/'IMAGE_MAP.json').write_text(json.dumps(image_map,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (out/'IMAGE_ASSESSMENT.json').write_text(json.dumps({'actual_requests':78,'known_image_mismatches':bad,
        'provider_image_decoding_not_attested':True,'image_bytes_not_reencoded':True},indent=2)+'\n',encoding='utf-8')
    (out/'README.md').write_text('''# Saved R46 source-feedback E evidence

All78 main request/started/response/result records are saved, with source predictions, per-case label-reveal events, raw episodes, original frozen E, approved E and readiness record, all development predictions and retrieved contexts. The20 original JPEG files are published in the linked data directory. No medical tools were used: tau is an empty actual tool trajectory, not fabricated evidence.

IMAGE_MAP.json losslessly maps the archived image-base64 references to exact file bytes. IMAGE_ASSESSMENT records any mismatch separately, without fixing a sent request. This verifies saved bytes, not supplier-side decoding. Raw request parameters contain no credentials; config/key are excluded. Source labels are legal training feedback; development labels are read only by the completed offline scorer and are not memory updates.

Costs are per-request usage proxies. Constructing E and using E have separate arm accounting; review CLI estimates are separate from inference billing. This exposed development pilot is not official SOTA or patient-independent testing.
''',encoding='utf-8')
    return {'actual_requests':count,'image_assets':len(image_map),'known_image_mismatches':len(bad),'new_model_calls':0}


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for key in ['source','data','scores','out']:p.add_argument('--'+key,type=Path,required=True)
    a=p.parse_args();print(json.dumps(export(a.source,a.data,a.scores,a.out)))
