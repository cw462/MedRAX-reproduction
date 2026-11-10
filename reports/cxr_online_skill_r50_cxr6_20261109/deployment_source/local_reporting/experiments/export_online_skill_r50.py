"""Offline full R50 evidence export after native completion and once-scoring.

Reuses the unchanged image-storage/sanitizer. No inference, Git, private R49
rescoring or added byte/hash validation. Historical raw answer projections are
accompanied by links to already-published complete R49 archives.
"""
import argparse
import json
import os
from pathlib import Path

from export_cxr_vqa_extension import RequestEvidencePublisher,restore_images
from export_cxr_image_memory_gt_r47 import child,derived_assets,emit_text
from export_online_skill_r49 import baseline_sources as old_baselines,copy_records
from online_memory_r50 import read
from run_online_skill_r50 import ARM
from score_online_skill_r50 import EXPECTED,completed_gate,rows
from r50_recovery_evidence import job_completion,generation_completion


def comparison_sources(dataset,inputs,names,r49_run,r49_public_evidence,*,r47_frozen=None,r47_run=None):
    from run_online_skill_r49 import ARM as OLD_ARM
    from score_online_skill_r49 import response_text
    r49_run=Path(r49_run);public=Path(r49_public_evidence)
    if (r49_run/'generation.exitcode').read_text().strip()!='0' or read(r49_run/'manifest.json').get('inputs')!=inputs:
        raise ValueError('saved_R49_complete_original_cohort_required')
    result=old_baselines(dataset,inputs,set(names)-{'R49_online_GT_Skill'},r47_frozen,r47_run)
    result['R49_online_GT_Skill']={}
    for row in inputs:
        q=row['question_id'];prediction=read(r49_run/'predictions'/OLD_ARM/(q+'.json'))
        if prediction.get('arm')!=OLD_ARM or prediction.get('question_id')!=q:raise ValueError('saved_R49_prediction_identity')
        call=r49_run/'services/calls/R49-AGENT'/q/str(prediction['main_calls'])
        raw=response_text(call)
        result['R49_online_GT_Skill'][q]={'prediction':prediction,'source':{'raw':raw,'call_path':str(call),
          'ordinal':call.name,'reuse_chain':[],'technical_stop':False,
          'evidence_status':'received_terminal_text' if raw else 'nonfinal_or_unavailable'}}
        if not (public/'predictions'/OLD_ARM/(q+'.json')).is_file():raise ValueError('already_public_R49_case_missing')
    # adapt() reads only answer/status plus these actual terminal fields. Keep
    # correctness labels entirely outside the reference-free public bundle.
    fields=('raw','call_path','ordinal','reuse_chain','evidence_status','technical_stop')
    for name,values in result.items():
        for q,value in values.items():
            value['prediction']={k:value['prediction'].get(k) for k in ('answer','status')}
            value['source']={k:value['source'][k] for k in fields}
    if set(result)!=set(names):raise ValueError('fixed_R50_historical_comparators')
    return result


def register_tools(publisher,run,inputs):
    by_id={r['question_id']:r for r in inputs}
    for path in sorted((run/'services/tool_selections/R50-AGENT').glob('*/*.json')):
        value=read(path);row=by_id.get(path.parent.name);index=value.get('image_index',1)
        if row is None or type(index) is not int or not 1<=index<=len(row['images']):raise ValueError('tool_original_binding')
        publisher.alias(value.get('original_image'),publisher.sources[row['images'][index-1]])
        derived_assets(publisher,run/'services',value)


def finish_images(publisher,out):
    publisher.emit(out/'image_assets.json',[{k:v for k,v in a.items() if k!='target'}|
      {'path':publisher.rel(a['target'],out/'image_assets.json')} for a in publisher.assets.values()])
    for document,relative,target in publisher.references:
        if (document.parent/relative).resolve()!=target.resolve() or not target.is_file():raise ValueError('outgoing_image_reference_missing')


def export(data,run,scores,references,reference_dir,out,dataset,*,r49_run,r49_public_evidence,r47_frozen=None,r47_run=None,jobs):
    data,run,scores,out,jobs=map(Path,(data,run,scores,out,jobs))
    if out.exists() or out.resolve().is_relative_to(run.resolve()) or run.resolve().is_relative_to(out.resolve()):
        raise ValueError('new_separate_public_R50_evidence_directory_required')
    controller_native=job_completion(jobs);dataset_native=job_completion(jobs,dataset)
    generation_native=generation_completion(run)
    n,baseline,expected=EXPECTED[dataset];inputs,manifest,_=completed_gate(data,run,n)
    summary,details=read(scores/'summary.json'),read(scores/'per_question.json')
    expected_names={baseline,'R49_online_GT_Skill'}|({'R47_online_GT'} if dataset=='chexbench' else set())
    if (manifest.get('arm')!=ARM or manifest.get('dataset')!=dataset or summary.get('arm')!=ARM
        or summary.get('dataset')!=dataset or summary.get('questions')!=n
        or summary.get('references_read_after_all_arms_adapted') is not True
        or summary['arms'][baseline]['correct']!=expected or set(summary['comparisons'])!=expected_names
        or len(details)!=n or [r['question_id'] for r in details]!=[r['question_id'] for r in inputs]):
        raise ValueError('full_fixed_R50_score_files_required')
    comparisons=comparison_sources(dataset,inputs,expected_names,r49_run,r49_public_evidence,r47_frozen=r47_frozen,r47_run=r47_run)
    out.mkdir(parents=True,exist_ok=False)
    publisher=RequestEvidencePublisher(out,data/'manifest.json',image_roots=(data,))
    for row in inputs:
        for name in row['images']:
            publisher.source_image(name);key=publisher.sources[name];publisher.alias(name,key)
            for root in (str(data),str(data.resolve())):publisher.alias(root.rstrip('/\\')+'/'+name,key)
    register_tools(publisher,run,inputs)
    for path in (run/'services/calls').glob('*/*/*/request.json'):
        request=restore_images(read(path),run/'services')
        for message in request.get('messages',[]):
            if not isinstance(message.get('content'),list):continue
            for block in message['content']:
                text=block.get('text','') if isinstance(block,dict) else ''
                if text.startswith('BOUND CURRENT IMAGE: '):
                    value=json.loads(text[len('BOUND CURRENT IMAGE: '):]);name=value.get('source_filename')
                    if name in publisher.sources:publisher.alias(value.get('path'),publisher.sources[name])
    # These links point to already-published complete archives; no old transfer
    # or private R49 scoring is invoked or disguised as a new experiment.
    old_public=Path(r49_public_evidence).resolve()
    for name,values in comparisons.items():
        for q,value in values.items():
            target=old_public/'predictions/M43-IM-GT-S49'/(q+'.json') if name=='R49_online_GT_Skill' else old_public/'comparison_sources.json'
            if not target.is_file():raise ValueError('existing_public_comparison_archive_missing')
            value['full_existing_public_archive']=os.path.relpath(target,out).replace('\\','/')
    publisher.emit(out/'inputs.jsonl',inputs,jsonl=True);publisher.emit(out/'manifest.json',manifest)
    publisher.emit(out/'comparison_sources.json',comparisons)
    for name in ('summary.json','per_question.json'):publisher.copy_json(scores/name,out/'scores'/name)
    publisher.emit(out/'fee_time.json',summary['resources'])
    source_manifest=next((data/n for n in ('data_manifest.json','manifest.json') if (data/n).is_file()),None)
    if source_manifest:publisher.copy_json(source_manifest,out/'data_manifest.json')
    refs=rows(references);refmap={r['question_id']:r for r in refs};ids=[r['question_id'] for r in inputs]
    if len(refs)!=len(refmap) or set(refmap)!=set(ids):raise ValueError('public_reference_cohort')
    publisher.emit(out/'references.jsonl',[refmap[q] for q in ids],jsonl=True)
    for q in ids:
        value=read(child(Path(reference_dir),q+'.json'));feedback=read(run/'feedback'/(q+'.json'))
        if value.get('question_id')!=q or value.get('answer')!=refmap[q]['answer'] or {k:value[k] for k in ('answer','answer_text') if k in value}!=feedback['reference_annotation']:
            raise ValueError('reused_vault_current_feedback_binding')
        publisher.emit(out/'reference_vault'/(q+'.json'),value)
    for name in ('complete.json','final_repo.json','progress.json','failure.json','failures.json','generation_failure.json','generation_failure_history.json'):
        if (run/name).is_file():publisher.copy_json(run/name,out/name)
    if (run/'generation.exitcode').is_file():emit_text(publisher,out/'generation.exitcode',(run/'generation.exitcode').read_text())
    if generation_native.get('protocol_amendment_used'):
        emit_text(publisher,out/'generation.amendment003.exitcode',(run/'generation.amendment003.exitcode').read_text())
        publisher.copy_json(run/'protocol_amendment.json',out/'protocol_amendment.json')
    if generation_native['technical_continuation_used']:
        for name in ('generation.recovery001.exitcode','generation.recovery002.exitcode'):
            if (run/name).is_file():emit_text(publisher,out/name,(run/name).read_text())
        for name in ('technical_recovery.json','technical_recovery002.json'):
            if (run/name).is_file():publisher.copy_json(run/name,out/name)
        for folder in ('technical_failures','technical_recovery'):
            for path in sorted((run/folder).rglob('*')):
                if path.is_file() and path.suffix in ('.json','.jsonl','.txt','.log','.py','.pid','.exitcode'):
                    copy_records(publisher,path,out/path.relative_to(run))
    for folder in ('predictions','contexts','steps','prediction_events','feedback','windows','prescreen_events','failure_events','failure_observations'):
        for path in sorted((run/folder).rglob('*.json')):publisher.copy_json(path,out/path.relative_to(run))
    for folder in ('calls','embeddings','tool_selections','tool_cache'):
        source=run/'services'/folder
        for path in sorted(source.rglob('*')):
            if not path.is_file() or any(v in ('__pycache__','hf_modules') for v in path.relative_to(source).parts):continue
            if path.suffix not in ('.json','.jsonl','.txt','.log'):continue
            target=out/'services'/folder/path.relative_to(source)
            if folder=='calls' and path.name=='request.json':publisher.emit(target,restore_images(read(path),run/'services'))
            else:copy_records(publisher,path,target)
    for path in sorted(jobs.iterdir()):
        if path.is_file() and path.suffix in ('.json','.log','.exitcode','.pid'):copy_records(publisher,path,out/'job_records'/path.name)
    publisher.emit(out/'source_attribution.json',{'dataset':dataset,'cohort_sources':'inputs.jsonl source and optional data_manifest.json retained',
      'historical_raw_answer_projections':'answer/status and actual raw terminal only, never old correctness labels',
      'complete_historical_archives':'explicit per-question full_existing_public_archive links into previously published R49 evidence',
      'reference_vault_source':'reused previously saved dataset vault, exact answer/answer_text checked against current released feedback',
      'model_interfaces':'Six model identities; MAIRA phrase grounding, not a full CXRAgent architecture reproduction',
      'terms':'Original source attribution and applicable dataset/model terms continue to apply.'})
    finish_images(publisher,out)
    publisher.emit(out/'publication_manifest.json',{'schema':'r50_semantic_public_evidence_v1','scope':'complete_scored_online_stream',
      'dataset':dataset,'arm':ARM,'questions':n,'comparisons':sorted(expected_names),
      'raw_generation_exit':generation_native['original_exit'],'final_generation_exit':generation_native['final_exit'],
      'native_controller_completion':controller_native,'native_dataset_completion':dataset_native,
      'native_generation_completion':generation_native,'initial_nonzero_attempts_retained':controller_native['technical_continuation_used'],
      'saved_predictions':n,'released_feedback':n,'all_question_predictions_are_fresh':True,
      'method_changes':manifest.get('r50_method_changes'),'uniform_inherited_controls':manifest.get('r50_baseline_controls'),
      'old_R49_failed_case_registrations_imported':False,'cross_dataset_feedback_shared':False,
      'public_score_verifier':'experiments/verify_public_online_skill_r50.py','new_inference_calls':0,
      'old_R49_private_score_invoked':False,'no_extra_file_or_image_digest_validation':True,
      'image_digest_use':'unchanged publisher asset naming only, not an inference/clinical integrity gate',
      'clinical_Skill_causality_or_official_SOTA_claim':False,
      'files':sorted({p.relative_to(out).as_posix() for p in publisher.files}|{'publication_manifest.json'}),
      'redactions':dict(publisher.redactions)})
    return {'dataset':dataset,'files':len(publisher.files),'images':len(publisher.assets),'new_inference_calls':0}


def export_health(health,image,out):
    health,image,out=map(Path,(health,image,out));complete=read(health/'complete.json')
    names={'medgemma','llava_rad','medvlm_r1'}
    if out.exists() or complete.get('status')!='three_new_tools_healthy' or set(complete.get('records',{}))!=names:
        raise ValueError('new_output_and_actual_new3_health_required')
    publisher=RequestEvidencePublisher(out,image.parent/'manifest.json',image_roots=(image.parent,))
    publisher.source_image(image.name);key=publisher.sources[image.name]
    for name,value in complete['records'].items():
        result=value['result'];events=result.get('actual_model_events',[])
        if value['native_exit_code']!=0 or value['status']!='completed_healthy' or result.get('cuda_visible_devices')!='1' or len(events)!=1 or events[0].get('status')!='completed':
            raise ValueError('actual_current_healthy_witness_required:'+name)
        publisher.alias(value['input_image'],key)
    for path in sorted(health.rglob('*')):
        if path.is_file() and (path.suffix in ('.json','.jsonl','.log','.txt') or path.name=='exitcode'):
            copy_records(publisher,path,out/path.relative_to(health))
    publisher.emit(out/'scope.json',{'scope':'one actual local health invocation each for three added tools, separate from production',
      'tools':sorted(names),'old_three_tools_reprobed':False,'main_META_embedding_calls':0,
      'health_outputs_reused_in_production_caches_Skill_or_scores':False,'hardware_cost_unknown':True,
      'model_identity':'pinned donor paths and caller/backend revision records; not independently weight-attested',
      'input_image':'existing training_xmlab120 readiness sample; provenance in actual saved requests',
      'new_inference_from_export':0,'extra_hash_validation':False})
    finish_images(publisher,out)
    publisher.emit(out/'publication_manifest.json',{'scope':'current_new3_health_evidence_only','files':sorted(p.relative_to(out).as_posix() for p in publisher.files),
      'new_inference_calls':0,'images':len(publisher.assets),'redactions':dict(publisher.redactions)})
    return {'scope':'health','files':len(publisher.files),'images':len(publisher.assets),'new_inference_calls':0}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='mode',required=True)
    ds=sub.add_parser('dataset')
    for name in ('data','run','scores','references','reference-dir','out','r49-run','r49-public-evidence','jobs'):ds.add_argument('--'+name,type=Path,required=True)
    for name in ('r47-frozen','r47-run'):ds.add_argument('--'+name,type=Path)
    ds.add_argument('--dataset',choices=EXPECTED,required=True)
    hp=sub.add_parser('health')
    for name in ('health','image','out'):hp.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args()
    if a.mode=='health':value=export_health(a.health,a.image,a.out)
    else:value=export(a.data,a.run,a.scores,a.references,a.reference_dir,a.out,a.dataset,
      r49_run=a.r49_run,r49_public_evidence=a.r49_public_evidence,r47_frozen=a.r47_frozen,r47_run=a.r47_run,jobs=a.jobs)
    print(json.dumps(value,ensure_ascii=False))
