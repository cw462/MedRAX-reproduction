"""Export only completed A1 public evidence; no credential/ledger copying."""
import argparse
from pathlib import Path
from export_vote_phase import Publisher
from score_votes import read
ID='skemex_a1_20261103'


def export(root,out):
    root=Path(root);out=Path(out);run=root/'runs'/ID
    if read(run/'pipeline_status.json')['status']!='completed':raise ValueError('complete_A1_pipeline_required')
    if out.exists() and any(out.iterdir()):raise ValueError('refuse_existing_public_export')
    cfg=read(run/'config.json');publisher=Publisher(out,run/'pipeline_status.json',image_roots=[root/cfg['image_root']])
    rows=read(run/'inputs/rows.json');mapping={r['question_id']:r for r in rows};cases=[];index={q:[] for q in mapping}
    for row in rows:
        cases.append(dict(row,native_images=[{'source_filename':s,'image':publisher.rel(publisher.source_image(s),out/'cases.json')} for s in row['images']]))
    publisher.emit(out/'cases.json',{'rows':cases,'n':402})
    for job in (run/'calls').iterdir():
        for req in job.glob('checkpoints/*/sample_1/request.json'):
            q=req.parent.parent.name;request=read(req)
            has_image=any(isinstance(m.get('content'),list) and any(b.get('type')=='image_url' for b in m['content']) for m in request['messages'])
            if has_image:publisher.bind_request(request,mapping[q])
            index[q].append(publisher.rel(out/req.relative_to(run),out/'query_to_calls.json'))
        for source in job.rglob('*'):
            if source.is_file() and source.suffix in ('.json','.jsonl') and not source.name.startswith('ledger_'):
                publisher.copy_json(source,out/source.relative_to(run))
    for dirname in ('inputs','training','cached_D','predictions','source_predictions','feedback_releases','window_records','evolution'):
        for source in (run/dirname).rglob('*'):
            if not source.is_file() or source.suffix not in ('.json','.jsonl','.md'):continue
            target=out/source.relative_to(run)
            if source.suffix in ('.json','.jsonl'):publisher.copy_json(source,target)
            else:
                target.parent.mkdir(parents=True,exist_ok=True)
                target.write_text(publisher.clean(source.read_text(encoding='utf-8'),target),encoding='utf-8');publisher.files.add(target)
    for name in ('config.json','embedding_version.json','pipeline_status.json','user_execution_approval.json','transport_state.json'):
        if (run/name).exists():publisher.copy_json(run/name,out/name)
    for source in (root/'reports'/ID/'analysis').glob('*'):
        if source.suffix=='.json':publisher.copy_json(source,out/'analysis'/source.name)
        elif source.name=='README.md':
            target=out/'analysis/README.md';target.parent.mkdir(parents=True,exist_ok=True);target.write_text(source.read_text(encoding='utf-8'),encoding='utf-8');publisher.files.add(target)
    publisher.emit(out/'query_to_calls.json',index)
    publisher.emit(out/'assets.json',{'assets':[{k:v for k,v in a.items() if k!='target'}|{'path':publisher.rel(a['target'],out/'assets.json')} for a in publisher.assets.values()]})
    publisher.emit(out/'publication_manifest.json',{'experiment_id':ID,'files':sorted(p.relative_to(out).as_posix() for p in publisher.files),'new_inference':0,'ledgers_copied':False})
    print({'public_files':len(publisher.files)})


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();export(a.root,a.out)
