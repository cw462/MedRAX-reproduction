"""Publish one finished E0-E3 milestone without labels, scoring or ledger access."""
import argparse
import json
from pathlib import Path

from export_vote_phase import Publisher, BOUND, SAMPLE_FILES, ATTEMPT_FILES, question_parts
from score_votes import read, resources

STAGES={
 '01_E2':['E2_Batch','E2_Sequential'],
 '02_E1':['E1_DeepSeek','E1_QwenFlash'],
 '03_E3':['E3_Classifier','E3_Report','E3_Evidence'],
 '04_E0':['E0_Heldout'],
}


def export(manifest_path, stage, destination):
    manifest_path=Path(manifest_path).resolve();manifest=read(manifest_path)
    root=Path(manifest['root']);out=Path(destination).resolve()
    if out.exists() and any(out.iterdir()):raise ValueError('milestone_already_exported')
    specs={a['id']:a for a in manifest['arms']}
    selected=STAGES[stage]
    runs={a:root/specs[a]['out'] for a in selected}
    for a,p in runs.items():
        status=read(p/'status.json')['status']
        if status not in ('generation_complete','ineligible_image_input'):
            raise ValueError('milestone_generation_not_finished:'+a)
    cfg=read(next(iter(runs.values()))/'protocol.json')
    publisher=Publisher(out,manifest_path,image_roots=[root/cfg['image_root']])
    rows=read(next(iter(runs.values()))/'question_selection.json')['rows']
    cases_path=out/'cases.json'
    for row in rows:
        for image in row['images']:publisher.source_image(image)
    usage={};arm_summary={}
    for arm,run in runs.items():
        target=out/'arms'/arm
        for filename in ('protocol.json','status.json','question_selection.json','selection.json',
                         'predictions.jsonl','first_image_use_review.json','fatal_error.json'):
            source=run/filename
            if source.exists():publisher.copy_json(source,target/filename)
        records=[]
        for row in read(run/'selection.json')['rows']:
            folder=run/'checkpoints'/row['question_id']/'sample_1'
            if not (folder/'terminal.json').exists():continue
            request=read(folder/'request.json')
            # A sequential request contains the union of previously introduced
            # images in its same-case history; a batch contains the case union.
            sources=[json.loads(b['text'][len(BOUND):])['source_filename']
                for m in request['messages'] if isinstance(m.get('content'),list)
                for b in m['content'] if b.get('type')=='text' and str(b.get('text','')).startswith(BOUND)]
            publisher.bind_request(request,{'images':sources})
            for filename in SAMPLE_FILES:
                if (folder/filename).exists():publisher.copy_json(folder/filename,target/folder.relative_to(run)/filename)
            for n in range(1,3):
                attempt=folder/f'attempt_{n}'
                for filename in ATTEMPT_FILES:
                    if (attempt/filename).exists():publisher.copy_json(attempt/filename,target/attempt.relative_to(run)/filename)
            records.append(read(folder/'terminal.json'))
        for dirname in ('question_view','evidence_projection','case_evidence_used','stop_events','stop_acknowledgements'):
            folder=run/dirname
            if folder.exists():
                for source in folder.rglob('*'):
                    if source.is_file() and source.suffix in ('.json','.jsonl'):
                        publisher.copy_json(source,target/source.relative_to(run))
        usage[arm]=resources(records)
        if (run/'ledger_final_summary.json').exists():
            saved=read(run/'ledger_final_summary.json')
            usage[arm]['run_increment_proxy_cny']=saved['run_increment_cny']
        state=read(run/'status.json')
        arm_summary[arm]={'status':state['status'],'planned_questions':len(rows),'saved_request_terminals':len(records),
                          'requests_used':state.get('requests_used'),'case_count':len({r['case_id'] for r in rows})}
    cases=[]
    for row in rows:
        stem,options=question_parts(row['question'])
        item=dict(row,stem=stem,options=options)
        item['native_images']=[{'source_filename':s,'image':publisher.rel(publisher.source_image(s),cases_path)} for s in row['images']]
        item['arms']={}
        for arm,run in runs.items():
            unit='case_'+row['case_id'] if specs[arm]['mode']=='case_batch' else row['question_id']
            folder=out/'arms'/arm/'checkpoints'/unit/'sample_1'
            item['arms'][arm]=({'request':publisher.rel(folder/'request.json',cases_path),
                               'terminal':publisher.rel(folder/'terminal.json',cases_path)}
                              if (folder/'terminal.json').exists() else {'status':'not_run_image_gate'})
        cases.append(item)
    publisher.emit(cases_path,{'planned_n':len(rows),'cases':cases,'reference_labels_included':False})
    if stage=='03_E3':
        experiment=root/manifest['out']
        publisher.copy_json(experiment/'caption_modalities.v2.json',out/'caption_modalities.json')
        cache=experiment/'case_tool_evidence'
        for dirname in ('cases','invocations','tool_provenance','initialization_errors'):
            for source in (cache/dirname).rglob('*.json'):
                publisher.copy_json(source,out/'tool_cache'/source.relative_to(cache))
        for filename in ('plan.json','index.json'):
            publisher.copy_json(cache/filename,out/'tool_cache'/filename)
        history=experiment/'recovery_history/01_classifier_serialization'
        if history.exists():
            publisher.copy_json(history/'incident.json',out/'recovery_history/01_classifier_serialization/incident.json')
            for source in (history/'case_tool_evidence/invocations').glob('*/*/chest_xray_classifier/*.json'):
                publisher.copy_json(source,out/'recovery_history/01_classifier_serialization'/source.relative_to(history))
    publisher.emit(out/'summary.json',{'stage':stage,'arms':arm_summary,'usage':usage,'scoring_performed':False,
                   'actual_token_plan_credits':None,'previous_predictions_unchanged':True})
    publisher.emit(out/'configuration.json',{k:v for k,v in manifest.items() if k!='arms'} | {'arms':[specs[a] for a in selected]})
    asset_path=out/'assets.json'
    publisher.emit(asset_path,{'assets':[{k:v for k,v in a.items() if k!='target'} | {'path':publisher.rel(a['target'],asset_path)} for a in publisher.assets.values()]})
    text=f'# {stage}: generation milestone\n\nGeneration for this milestone has finished. Accuracy is deliberately deferred until every planned arm finishes.\n\n'
    text+='[Complete questions, options, images and saved requests/responses](cases.json) · [Usage and status](summary.json) · [Configuration](configuration.json) · [Image provenance](assets.json).\n\n'
    text+='|Arm|Planned questions|Saved request terminals|Status|\n|---|---:|---:|---|\n'
    for arm,a in arm_summary.items():text+=f"|{arm}|{a['planned_questions']}|{a['saved_request_terminals']}|{a['status']}|\n"
    text+='\nCNY amounts are inherited bookkeeping proxies, not provider prices or Credits conversion. Actual Credits are unknown. Case-batch requests are counted once; their child answers do not add cost.\n'
    (out/'README.md').write_text(text,encoding='utf-8');publisher.files.add(out/'README.md')
    for document,relative,target in publisher.references:
        if not target.is_file() or (document.parent/relative).resolve()!=target.resolve():raise ValueError('missing_publication_link')
    publisher.emit(out/'publication_manifest.json',{'stage':stage,'new_inference':0,'files':sorted(p.relative_to(out).as_posix() for p in publisher.files)})
    return {'stage':stage,'files':len(publisher.files),'arms':arm_summary}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--manifest',type=Path,required=True)
    p.add_argument('--stage',choices=STAGES,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();print(json.dumps(export(a.manifest,a.stage,a.out)))
