"""Export only completed A1 public evidence; no credential/ledger copying."""
import argparse
import hashlib
from io import BytesIO
from pathlib import Path
from export_vote_phase import Publisher
from score_votes import read
from skemex_adapter.transport import ID


class EvidencePublisher(Publisher):
    """Preserve a saved PNG with a bad CRC as evidence, without repairing it."""
    def inspect_image(self,data):
        try:return super().inspect_image(data)
        except SyntaxError as exc:
            if 'bad header checksum' not in str(exc):raise
            from PIL import Image
            with Image.open(BytesIO(data)) as image:
                if image.format!='PNG':raise
                size=list(image.size)
            self.validation_failures.append({'sha256':hashlib.sha256(data).hexdigest(),'error':str(exc),'bytes_unchanged':True,'valid_image_not_claimed':True})
            return '.png',size


def export(root,out):
    root=Path(root);out=Path(out);run=root/'runs'/ID
    state=read(run/'pipeline_status.json')
    source_only=(ID.endswith('_r1') and state.get('status')=='stopped' and state.get('error')=='empty_source_library_no_valid_memory_effect_evaluation'
                 and all((run/'evolution'/f/'complete.json').exists() for f in ('A','B')) and not list((run/'predictions').glob('*.json')))
    if state['status']!='completed' and not source_only:raise ValueError('complete_A1_pipeline_or_terminal_empty_library_required')
    if out.exists() and any(out.iterdir()):raise ValueError('refuse_existing_public_export')
    cfg=read(run/'config.json');publisher=EvidencePublisher(out,run/'pipeline_status.json',image_roots=[root/cfg['image_root']]);publisher.validation_failures=[]
    rows=read(run/'inputs/rows.json');mapping={r['question_id']:r for r in rows};cases=[];index={q:[] for q in mapping}
    for row in rows:
        cases.append(dict(row,native_images=[{'source_filename':s,'image':publisher.rel(publisher.source_image(s),out/'cases.json')} for s in row['images']]))
    publisher.emit(out/'cases.json',{'rows':cases,'n':402})
    native_sources=dict(publisher.sources);variants=[]
    for job in (run/'calls').iterdir():
        # Requests can contain a separately preserved byte variant of a source
        # image. Keep per-request bindings and actual bytes; do not force two
        # different payloads into one source-filename digest or alter originals.
        publisher.sources={};publisher.aliases={}
        for req in job.glob('checkpoints/*/sample_1/request.json'):
            q=req.parent.parent.name;request=read(req)
            has_image=any(isinstance(m.get('content'),list) and any(b.get('type')=='image_url' for b in m['content']) for m in request['messages'])
            if has_image:
                bindings=publisher.bind_request(request,mapping[q])
                for binding in bindings:
                    source=binding['source_filename']
                    if native_sources.get(source)!=binding['sha256']:
                        variants.append({'job':job.name,'question_id':q,'source_filename':source,'native_file_sha256':native_sources.get(source),'actual_request_sha256':binding['sha256'],'mechanism':'unknown; preserve both byte streams without assuming hardware damage'})
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
    reuses=[]
    for reuse in (run/'calls').glob('*/reuse.json'):
        value=read(reuse);q=value['question_id'];job=value['original_job']
        # Public relative reference to the separately preserved original evidence.
        target=out.parent.parent/'skemex_a1_20261103'/'results'/'calls'/job/'checkpoints'/q/'sample_1/request.json'
        reuses.append(dict(value,original_public_request=publisher.rel(target,out/'reused_calls.json')))
    publisher.emit(out/'reused_calls.json',{'records':reuses,'new_paid_calls':0,'original_cost_not_charged_again':True})
    publisher.emit(out/'request_image_variants.json',{'records':variants,'original_requests_and_source_files_unchanged':True})
    publisher.emit(out/'invalid_image_bytes.json',{'records':publisher.validation_failures,'interpretation':'Saved bytes preserved as evidence, not repaired or certified as valid input. Provider decoding and physical cause unknown.'})
    publisher.emit(out/'assets.json',{'assets':[{k:v for k,v in a.items() if k!='target'}|{'path':publisher.rel(a['target'],out/'assets.json')} for a in publisher.assets.values()]})
    publisher.emit(out/'publication_manifest.json',{'experiment_id':ID,'source_only_terminal':source_only,'files':sorted(p.relative_to(out).as_posix() for p in publisher.files),'new_inference':0,'ledgers_copied':False})
    print({'public_files':len(publisher.files)})


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();export(a.root,a.out)
