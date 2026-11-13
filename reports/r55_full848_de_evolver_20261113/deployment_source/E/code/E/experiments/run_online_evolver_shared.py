"""R55 11-tool online D/E runner with post-prediction EvolveR distillation.
No target label reaches inference before that question's immutable prediction.
"""
import argparse,copy,hashlib,json,os,sys
from pathlib import Path
from cxr_online_primitives_r49 import read,rows,schedule,assert_closed_sends
from online_memory_r49 import save_once,now,safe_qid,ReferenceVault,memory_entry,context
from skill_lifecycle_r49 import initial,category
from skill_policy_r54 import DEFAULTS,windows
from skill_services_evolver_shared import Services, validate_writer
from failure_observation_r54 import validate_prediction_failures,validate_selection_failures
from experience_feedback_r54 import released_feedback
ARM='R55-D'
DATASET_COUNTS = {'chexbench':618, 'slake':114, 'vqarad':116}

def released_reward(row,result,reference):
    from cxr_author_alignment import extract,choice,m4cxr_normalize
    answer=extract(result.get('terminal_raw'),row['question_id'],row.get('options')).answer
    y=reference['answer']
    if answer is None:return 0
    return int(choice(answer,row['options'])==y if row.get('options') else m4cxr_normalize(answer)==m4cxr_normalize(y))

def validate_prefix(out,ids):
    predictions={p.stem for p in (out/'predictions'/ARM).glob('*.json')}
    feedback={p.stem for p in (out/'feedback').glob('*.json')}
    n=len(predictions)
    if predictions!=set(ids[:n]):raise ValueError('predictions_not_sequential_prefix')
    if feedback not in (set(ids[:n]),set(ids[:max(0,n-1)])):raise ValueError('feedback_not_saved_prediction_prefix')
    for name in ('contexts','steps'):
        members={p.stem for p in (out/name).glob('*.json')}
        if members not in (set(ids[:n]),set(ids[:min(len(ids),n+1)])):raise ValueError(name+'_not_sequential_prefix')
    events={p.stem for p in (out/'prediction_events').glob('*.json')}
    if events not in (set(ids[:n]),set(ids[:max(0,n-1)])):raise ValueError('prediction_events_not_saved_prefix')

def run_stream(inputs,order,data,out,service,vault,tools,config=None,*,evolver,route,reward_fn=released_reward):
    """Replay saved commits on restart; only unfinished work invokes cached API services."""
    out=Path(out);cfg=copy.deepcopy(config or DEFAULTS);ids=[r['question_id'] for r in inputs]
    if not inputs or len(set(ids))!=len(ids):raise ValueError('empty_or_duplicate_stream')
    if [x['question_id'] for x in order]!=ids:raise ValueError('order_mismatch')
    validate_prefix(out,ids);assert_closed_sends(out);repo=initial();memory={};history=[]
    for wi,(start,end) in enumerate(windows(len(inputs))):
        window=out/'windows'/f'{wi:04d}';snapshot=copy.deepcopy(repo);batch=[]
        save_once(window/'read_snapshot.json',snapshot)
        for index in range(start,end):
            row=inputs[index];item=order[index];q=safe_qid(row['question_id']);ordinal=index+1
            predpath=out/'predictions'/ARM/(q+'.json');ctxpath=out/'contexts'/(q+'.json')
            prior=memory.setdefault(item['image_key'],[])
            same_text,same_ids=context(prior,item,ordinal)
            if ctxpath.exists():
                ctx=read(ctxpath)
                if ctx['skill_snapshot']!=snapshot or ctx['same_image_ids']!=same_ids or ctx['same_image_context']!=same_text:raise ValueError('resume_context_changed')
                if ctx['selected_skills']:
                    raise ValueError('unexpected_legacy_skill_selection')
            else:
                ctx={'question_id':q,'ordinal':ordinal,'window':wi,'skill_snapshot':copy.deepcopy(snapshot),
                     'selected_skills':[],'same_image_ids':same_ids,'same_image_context':same_text}
                save_once(ctxpath,ctx)
            if predpath.exists():result=read(predpath)
            else:
                service.experience_snapshot=snapshot if route=='experience' else None
                sections=[s for s in (same_text,) if s]
                result,calls=service.execute(row,'r49_unbounded',data,'\n\n'.join(sections) or None)
                # Persist steps first; no feedback reader has been called for q yet.
                save_once(out/'steps'/(q+'.json'),calls)
                result.update(question_id=q,arm=ARM,ordinal=ordinal,prediction_saved_at=now(),
                              selected_skill_ids=[],same_image_ids=same_ids)
                save_once(predpath,result)
            if (result.get('question_id')!=q or result.get('arm')!=ARM or result.get('ordinal')!=ordinal
                    or result.get('selected_skill_ids')!=[] or result.get('same_image_ids')!=same_ids):
                raise ValueError('saved_prediction_context_identity_changed')
            failure_count=validate_prediction_failures(out,q,result)
            prediction_event={'question_id':q,'arm':ARM,'ordinal':ordinal,'image_key':item['image_key'],'saved_prediction':copy.deepcopy(result)}
            save_once(out/'prediction_events'/(q+'.json'),prediction_event)
            eventpath=out/'feedback'/(q+'.json')
            if eventpath.exists():
                event=read(eventpath)
                if event['saved_prediction']!=result or event['ordinal']!=ordinal or event['question_id']!=q or event['image_key']!=item['image_key']:raise ValueError('feedback_binding_changed')
            else:
                reference=vault.after_prediction(q,predpath)
                event={'question_id':q,'ordinal':ordinal,'image_key':item['image_key'],'saved_prediction':copy.deepcopy(result),
                       'reference_annotation':{k:reference[k] for k in ('answer','answer_text') if k in reference},
                       'released_at':now(),'timing':'after_immutable_prediction','provenance':'dataset_annotation_feedback_not_patient_history'}
                save_once(eventpath,event)
            # Only released feedback is now eligible for same-image memory and Skill learning.
            prior.append(memory_entry(row,result,event))
            trace={'id':q,'row':row,'category':category(row['question']),
                   'reward':reward_fn(row,result,event['reference_annotation']),
                   'source_label':event['reference_annotation']['answer'],'prediction':result,
                   'steps':read(out/'steps'/(q+'.json')),'injected':result.get('activated_skill_ids',[]),
                   'activated_skill_ids':result.get('activated_skill_ids',[]),
                   'candidate_skill_ids':[],
                   'injected_content':[],'same_image_context':same_text,'feedback_ordinal':ordinal,
                   'technical_failure':bool(failure_count) or result.get('status') == 'main_response_unavailable_after_retry','max_step_failure':False,
                   'repeated_no_progress':result.get('status','').startswith('repeated_')}
            if route == 'experience':
                trace['distillation_feedback'] = released_feedback(event)
            save_once(window/'trajectories'/(q+'.json'),trace);batch.append(trace)
        finish=window/'repo.json'
        if finish.exists():repo=read(finish)
        else:
            repo=evolver(service,snapshot,batch,wi,window,data,tools,cfg)
            save_once(finish,repo)
        history.append({'window':wi,'episodes':len(batch),'correct':sum(t['reward'] for t in batch),
                        'active_skills':sum(s['status'] in ('active','mature') for s in repo['skills'].values()),
                        'skill_hit_questions':sum(bool(t['injected']) for t in batch)})
    assert_closed_sends(out,require_receipts=True)
    expected=set(ids)
    for folder in (out/'predictions'/ARM,out/'contexts',out/'steps',out/'prediction_events',out/'feedback'):
        if {p.stem for p in folder.glob('*.json')}!=expected:raise ValueError('incomplete_artifact_membership:'+folder.name)
    validate_selection_failures(out)
    save_once(out/'final_repo.json',repo)
    save_once(out/'complete.json',{'status':'generation_complete','arm':ARM,'questions':len(inputs),'windows':history,'mode':'online_post_prediction_feedback',
              'candidate_hit_questions':sum(bool(read(out/'contexts'/(q+'.json'))['selected_skills']) for q in ids),
              'fixed_main_call_limit':None,'fixed_tool_call_limit':None,'final_repo':copy.deepcopy(repo)})
    return history

def disabled_evolve(service,snapshot,batch,wi,window,data,tools,cfg):
    # No analysis, embedding, retrieval, activation or governance model requests.
    if snapshot['skills']:raise ValueError('no_skill_repo_must_remain_empty')
    save_once(window/'buffer.json',{'retained':[],'eligibility':{}})
    save_once(window/'analyses.json',{})
    save_once(window/'events.json',{'write':[],'credit':[],'govern':[],'disabled':True})
    return snapshot

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('config','data','reference-dir','out'):p.add_argument('--'+k,type=Path,required=True)
    p.add_argument('--skill',choices=('off','evolver'),required=True)
    p.add_argument('--embedding-model',required=True)
    p.add_argument('--embedding-base-url',required=True)
    p.add_argument('--order-manifest',type=Path,required=True)
    p.add_argument('--writer-config',type=Path)
    p.add_argument('--dataset',choices=tuple(DATASET_COUNTS),default='chexbench')
    p.add_argument('--cohort',choices=('full','openi293'),default='full')
    p.add_argument('--medret-provider',choices=('pubmed','medrag_http'),default='pubmed')
    p.add_argument('--medrag-url')
    p.add_argument('--execute',action='store_true');p.add_argument('--api-key-stdin',action='store_true');a=p.parse_args()
    global ARM
    route={'off':'off','evolver':'experience'}[a.skill]
    if route!='experience':
        p.error('this continuation reuses the saved D arm')
    ARM='R55-E-EvolveR'
    if (a.medret_provider=='medrag_http') != bool(a.medrag_url):
        p.error('--medrag-url is required with medrag_http only')
    if a.cohort=='openi293' and a.dataset!='chexbench':
        p.error('openi293 requires --dataset chexbench')
    if (a.skill != 'off') != bool(a.writer_config):
        p.error('--writer-config is required for evolver, and must be omitted for off')
    writer=read(a.writer_config) if a.writer_config else None
    if writer is not None:validate_writer(writer)
    inputs=rows(a.data/'inputs.jsonl');ids=[safe_qid(x['question_id']) for x in inputs]
    if len(inputs)!=DATASET_COUNTS[a.dataset] or len(set(ids))!=len(ids):
        raise ValueError('original_dataset_size_or_question_identity_changed')
    allowed={'question_id','question','images','image_id','source','options'}
    if any(set(x)-allowed for x in inputs):raise ValueError('inference_fields_include_labels')
    order=schedule(inputs,a.data,read(a.order_manifest) if a.order_manifest else None);cfg=read(a.config);protocol=read(cfg['protocol']);runtime=read(cfg['runtime'])
    from cxr_image_memory_gt_r47 import validate_protocol
    validate_protocol(protocol)
    if a.dataset=='chexbench' and (
        len({x['image_key'] for x in order})!=488 or sum(bool(x['previous_ids']) for x in order)!=130
    ):
        raise ValueError('original_CheXbench_group_partition_required')
    if a.cohort=='openi293':
        from compare_r55live import select_laterality
        inputs,order=select_laterality(inputs,order)
        ids=[r['question_id'] for r in inputs]
        if len(ids)!=293:raise ValueError('openi_laterality_cohort_size')
        inputs,order=inputs[:30],order[:30]
        ids=ids[:30]
    if a.cohort!='openi293':
        p.error('required-search pilot requires --cohort openi293')
    from skill_services_evolver_shared import register_r55_tools
    register_r55_tools(runtime)
    tools=runtime['arms']['M']['tools']
    runtime['arms']={x:copy.deepcopy(runtime['arms']['M']) for x in ('M','R49-AGENT')}
    view_counts={}
    for row in inputs:
        for name in row['images']:
            image=(a.data/name).resolve()
            if not image.is_relative_to(a.data.resolve()) or not image.is_file():raise ValueError('missing_or_outside_original_image')
            view=runtime['backend_config'].get('r54_image_views_by_path',{}).get(str(image))
            if view is None:raise ValueError('missing_input_only_view_annotation:'+str(image))
            key_view=view['modality']+'/'+view['view'];view_counts[key_view]=view_counts.get(key_view,0)+1
    refs={q:{'file':q+'.json'} for q in ids}
    # Existence checks do not open any current/future annotation during inference setup.
    if any(not (a.reference_dir/(q+'.json')).is_file() for q in ids):raise ValueError('missing_reference_file')
    manifest={'schema':'r55_11tool_evolver_pair_v1','arm':ARM,'dataset':a.dataset,'inputs':copy.deepcopy(inputs),'order':order,
              'reference_files':refs,'config':cfg,'protocol':protocol,'runtime':runtime,'defaults':DEFAULTS,
              'embedding_model':a.embedding_model,'embedding_base_url':a.embedding_base_url,'policy':'unbounded_adapted_M43_components',
              'skill_enabled':a.skill!='off','skill_route':route,'implementation_revision':'R55-EvolveR-shared-tools.3-required-search-unvalidated','cohort':a.cohort,'writer':writer,'cold_windows':[10,20,30],'govern_every_questions':60,'initial_repo':'empty','same_image_entries':8,'same_image_chars':12000,
              'grouping':'declared_historical_metadata' if a.order_manifest else 'canonical_image_id_or_relative_paths',
              'view_counts_image_occurrences':view_counts,
              'implementation_files':{str(f.relative_to(Path(__file__).parent)):hashlib.sha256(f.read_bytes()).hexdigest()
                                      for f in Path(__file__).parent.rglob('*.py')},
              'source_attestation':'R55 live tool registration and R54 EvolveR post-prediction distillation',
              'deployment_adaptations':['recorded_asset_identity_and_canonical_path_views','appendix_A4_failed_observation_both_arms','complete_backend_IO_archive']}
    from run_online_skill_r55 import manifest_metadata
    manifest['experience_admission']='returned_text_without_validation'
    manifest['new_tool_model_policy']=manifest_metadata()['new_tool_model_policy']
    if not a.execute:
        if (a.out/'manifest.json').is_file() and read(a.out/'manifest.json')!=manifest:
            raise ValueError('existing_output_manifest_mismatch')
        print(json.dumps({'questions':len(inputs),'groups':len({x['image_key'] for x in order}),
          'same_image_followups':sum(bool(x['previous_ids']) for x in order),'windows':len(list(windows(len(inputs)))),
          'view_counts_image_occurrences':view_counts,'arms':[ARM],'tools':tools,'paid_calls':0,'needs_separate_source_pool':False},ensure_ascii=False));return
    if writer is not None and not os.environ.get(writer['api_key_env']):raise ValueError('missing_writer_key_environment')
    if not a.api_key_stdin:raise ValueError('stdin_key_required')
    key=sys.stdin.readline().strip()
    if not key:raise ValueError('missing_key')
    import run_cxr_vqa_toolsets as base
    a.out.mkdir(parents=True,exist_ok=True)
    with base.exclusive_lock(a.out/'.online.lock'):
        save_once(a.out/'manifest.json',manifest)
        vault=ReferenceVault(a.reference_dir,refs)
        service=Services(cfg,protocol,runtime,a.out/'services',key,a.embedding_model,a.embedding_base_url,writer=writer)
        from r55_unvalidated_experience import evolve as evolve_experience
        evolver=disabled_evolve if route=='off' else evolve_experience
        history=run_stream(inputs,order,a.data,a.out,service,vault,tools,evolver=evolver,route=route)
        print({'completed':len(inputs),'arm':ARM,'windows':len(history)})
if __name__=='__main__':main()
