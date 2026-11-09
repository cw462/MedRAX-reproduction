"""Public export of completed Plus experiment, never copies account ledgers."""
import argparse
from pathlib import Path
from export_vote_phase import Publisher,question_parts
from score_votes import read
from history_skills import ID


def export(root,destination):
    root=Path(root);out=Path(destination);run=root/'runs'/ID
    if read(run/'pipeline_status.json')['status']!='completed':raise ValueError('completed_pipeline_required')
    if out.exists() and any(out.iterdir()):raise ValueError('refuse_existing_export')
    cfg=read(run/'arms/H1/protocol.json')
    publisher=Publisher(out,run/'pipeline_status.json',image_roots=[root/cfg['image_root']])
    cases=[]
    rows=read(run/'arms/H1/selection.json')['rows'];rowmap={r['question_id']:r for r in rows}
    for r in rows:
        stem,options=question_parts(r['question']);item=dict(r,stem=stem,options=options)
        item['native_images']=[{'source_filename':s,'image':publisher.rel(publisher.source_image(s),out/'cases.json')} for s in r['images']]
        cases.append(item)
    publisher.emit(out/'cases.json',{'rows':cases,'planned_n':402})
    for arm in ('H1','Reflection','S1','HS'):
        folder=run/'arms'/arm
        for request in folder.glob('checkpoints/*/sample_1/request.json'):
            q=request.parent.parent.name;publisher.bind_request(read(request),rowmap[q])
        for source in folder.rglob('*'):
            if source.is_file() and source.suffix in ('.json','.jsonl') and source.name not in ('ledger_start.json',):
                publisher.copy_json(source,out/source.relative_to(run))
    for dirname in ('inputs','training','skills'):
        for source in (run/dirname).rglob('*.json*'):
            if source.is_file():publisher.copy_json(source,out/source.relative_to(run))
    for source in (root/'reports'/ID/'analysis').glob('*'):
        if source.is_file():
            if source.suffix in ('.json','.jsonl'):publisher.copy_json(source,out/'analysis'/source.name)
            elif source.name=='README.md':
                (out/'analysis').mkdir(parents=True,exist_ok=True);(out/'analysis/README.md').write_text(source.read_text(),encoding='utf-8');publisher.files.add(out/'analysis/README.md')
    for name in ('input_freeze.json','pipeline_status.json','user_execution_approval.json'):
        publisher.copy_json(run/name,out/name)
    publisher.emit(out/'assets.json',{'assets':[{k:v for k,v in a.items() if k!='target'}|{'path':publisher.rel(a['target'],out/'assets.json')} for a in publisher.assets.values()]})
    for document,relative,target in publisher.references:
        if not target.is_file() or (document.parent/relative).resolve()!=target.resolve():raise ValueError('missing_publication_link')
    publisher.emit(out/'publication_manifest.json',{'experiment_id':ID,'new_inference':0,'files':sorted(p.relative_to(out).as_posix() for p in publisher.files)})
    print({'exported_files':len(publisher.files),'account_ledgers_copied':False})


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();export(a.root,a.out)
