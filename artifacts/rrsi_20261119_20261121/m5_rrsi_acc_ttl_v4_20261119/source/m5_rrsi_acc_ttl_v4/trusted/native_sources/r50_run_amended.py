"""Single-arm online R47 same-image feedback + SkeMex-inspired window skill evolution.
No target label reaches inference before that question's immutable prediction.
"""
import argparse,copy,json,math,sys
from pathlib import Path
from cxr_online_primitives_r50 import read,rows,schedule,assert_closed_sends,tool_failure_reason
from online_memory_r50 import save_once,now,safe_qid,ReferenceVault,memory_entry,context
from skill_lifecycle_r50 import DEFAULTS,initial,retrieve,category
from skill_prompts_r50 import PRESCREEN
from r50_services_amended import Services,conditioning
from r50_failure_observation import amendment,validate_prediction_failures,validate_selection_failures,POLICY_ID
from skill_evolve_r50 import evolve
ARM='M43-IM-GT-S50-CXR6'

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

def run_stream(inputs,order,data,out,service,vault,tools,config=None,*,evolver=evolve,reward_fn=released_reward):
    """Replay saved commits on restart; only unfinished work invokes cached API services."""
    out=Path(out);cfg=copy.deepcopy(config or DEFAULTS);ids=[r['question_id'] for r in inputs]
    if not inputs or len(set(ids))!=len(ids):raise ValueError('empty_or_duplicate_stream')
    if [x['question_id'] for x in order]!=ids:raise ValueError('order_mismatch')
    validate_prefix(out,ids);assert_closed_sends(out);repo=initial();memory={};history=[]
    for wi,start in enumerate(range(0,len(inputs),cfg['window'])):
        window=out/'windows'/f'{wi:04d}';snapshot=copy.deepcopy(repo);batch=[]
        save_once(window/'read_snapshot.json',snapshot)
        for index in range(start,min(start+cfg['window'],len(inputs))):
            row=inputs[index];item=order[index];q=safe_qid(row['question_id']);ordinal=index+1
            predpath=out/'predictions'/ARM/(q+'.json');ctxpath=out/'contexts'/(q+'.json')
            prior=memory.setdefault(item['image_key'],[])
            same_text,same_ids=context(prior,item,ordinal)
            if ctxpath.exists():
                ctx=read(ctxpath)
                if ctx['skill_snapshot']!=snapshot or ctx['same_image_ids']!=same_ids or ctx['same_image_context']!=same_text:raise ValueError('resume_context_changed')
                selected=ctx['selected_skills']
                for selected_item in selected:
                    source=snapshot['skills'].get(selected_item['id'])
                    if not source or selected_item['c']!=source['c'] or source['status'] not in ('active','mature'):
                        raise ValueError('selected_skill_not_in_window_snapshot')
            else:
                selected=[]
                if any(s['status'] in ('active','mature') for s in snapshot['skills'].values()):
                    vec=service.embed(row['question']+' '+json.dumps(row.get('options',{})))
                    def screen(pool):
                        chosen=service.meta('screen_'+q,PRESCREEN,{'question':row['question'],'options':row.get('options',{}),'candidates':pool})['ids']
                        save_once(out/'prescreen_events'/(q+'.json'),{'question_id':q,'window':wi,
                            'input_pool_ids':[x['id'] for x in pool],'input_pool_count':len(pool),
                            'returned_ids':copy.deepcopy(chosen),'returned_count':len(chosen),
                            'all_rejected':not bool(chosen),'scope':'actual prescreen input after unchanged per-branch top5; no current label'})
                        return chosen
                    selected=retrieve(snapshot,vec,category(row['question']),tools,cfg,screen)
                ctx={'question_id':q,'ordinal':ordinal,'window':wi,'skill_snapshot':copy.deepcopy(snapshot),
                     'selected_skills':selected,'same_image_ids':same_ids,'same_image_context':same_text}
                save_once(ctxpath,ctx)
            if predpath.exists():result=read(predpath)
            else:
                sections=[s for s in (conditioning(selected),same_text) if s]
                result,calls=service.execute(row,'r50_unbounded',data,'\n\n'.join(sections) or None)
                # Persist steps first; no feedback reader has been called for q yet.
                save_once(out/'steps'/(q+'.json'),calls)
                result.update(question_id=q,arm=ARM,ordinal=ordinal,prediction_saved_at=now(),
                              selected_skill_ids=[s['id'] for s in selected],same_image_ids=same_ids)
                save_once(predpath,result)
            if (result.get('question_id')!=q or result.get('arm')!=ARM or result.get('ordinal')!=ordinal
                    or result.get('selected_skill_ids')!=[s['id'] for s in selected] or result.get('same_image_ids')!=same_ids):
                raise ValueError('saved_prediction_context_identity_changed')
            failed_tools=validate_prediction_failures(out,q,result)
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
                   'steps':read(out/'steps'/(q+'.json')),'injected':[s['id'] for s in selected],
                   'injected_content':selected,'same_image_context':same_text,'feedback_ordinal':ordinal,
                   'technical_failure':bool(failed_tools),'max_step_failure':False,
                   'failed_tool_observations':failed_tools,'execution_protocol_amendment':POLICY_ID,
                   'repeated_no_progress':result.get('status','').startswith('repeated_')}
            if ordinal<=amendment(out)['saved_prefix']:
                trace.pop('failed_tool_observations');trace.pop('execution_protocol_amendment')
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
    failed_selection_count=validate_selection_failures(out)
    save_once(out/'final_repo.json',repo)
    save_once(out/'complete.json',{'status':'generation_complete','arm':ARM,'questions':len(inputs),'windows':history,'mode':'online_post_prediction_feedback',
              'fixed_main_call_limit':None,'fixed_tool_call_limit':None,'final_repo':copy.deepcopy(repo),
              'execution_protocol_amendment':POLICY_ID,'failed_tool_selections_delivered':failed_selection_count})
    return history

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('config','data','reference-dir','out'):p.add_argument('--'+k,type=Path,required=True)
    p.add_argument('--embedding-model',required=True)
    p.add_argument('--embedding-base-url',required=True)
    p.add_argument('--order-manifest',type=Path)
    p.add_argument('--dataset',choices=('chexbench','slake','vqarad'),default='chexbench')
    p.add_argument('--expect-questions',type=int,default=618)
    p.add_argument('--execute',action='store_true');p.add_argument('--api-key-stdin',action='store_true');a=p.parse_args()
    inputs=rows(a.data/'inputs.jsonl');ids=[safe_qid(x['question_id']) for x in inputs]
    if len(inputs)!=a.expect_questions or len(set(ids))!=len(ids):raise ValueError('cohort_size_or_ids')
    allowed={'question_id','question','images','image_id','source','options'}
    if any(set(x)-allowed for x in inputs):raise ValueError('inference_fields_include_labels')
    order=schedule(inputs,a.data,read(a.order_manifest) if a.order_manifest else None);cfg=read(a.config);protocol=read(cfg['protocol']);runtime=read(cfg['runtime'])
    from cxr_image_memory_gt_r47 import validate_protocol
    validate_protocol(protocol)
    if a.dataset=='chexbench' and a.expect_questions==618 and (len({x['image_key'] for x in order})!=488 or sum(bool(x['previous_ids']) for x in order)!=130):raise ValueError('original_CheXbench_group_partition_required')
    tools=runtime['arms']['M']['tools'];runtime['arms']={x:copy.deepcopy(runtime['arms']['M']) for x in ('M','R50-AGENT')}
    for row in inputs:
        for name in row['images']:
            image=(a.data/name).resolve()
            if not image.is_relative_to(a.data.resolve()) or not image.is_file():raise ValueError('missing_or_outside_original_image')
    refs={q:{'file':q+'.json'} for q in ids}
    # Existence checks do not open any current/future annotation during inference setup.
    if any(not (a.reference_dir/(q+'.json')).is_file() for q in ids):raise ValueError('missing_reference_file')
    manifest={'schema':'r50_online_semantic_v1','arm':ARM,'dataset':a.dataset,'inputs':copy.deepcopy(inputs),'order':order,
              'reference_files':refs,'config':cfg,'protocol':protocol,'runtime':runtime,'defaults':DEFAULTS,
              'embedding_model':a.embedding_model,'embedding_base_url':a.embedding_base_url,'policy':'unbounded_adapted_M43_components',
              'r50_method_changes':['six_model_tool_menu','prescreen_for_any_nonempty_candidate_pool'],
              'r50_baseline_controls':{'MAIRA_EOS_guard':'uniform_from_start','MUTATE_fields_clarification':True,'ANALYZE_unique_adoption_clarification':True,'old_failure_registrations_imported':False},
              'initial_repo':'empty','same_image_entries':8,'same_image_chars':12000,
              'grouping':'declared_historical_metadata' if a.order_manifest else 'canonical_image_id_or_relative_paths',
              'implementation_files':sorted(f.name for f in Path(__file__).parent.glob('*r50.py'))}
    if not a.execute:
        print(json.dumps({'questions':len(inputs),'groups':len({x['image_key'] for x in order}),
          'same_image_followups':sum(bool(x['previous_ids']) for x in order),'windows':math.ceil(len(inputs)/30),
          'arms':[ARM],'paid_calls':0,'needs_separate_source_pool':False},ensure_ascii=False));return
    if not a.api_key_stdin:raise ValueError('stdin_key_required')
    key=sys.stdin.readline().strip()
    if not key:raise ValueError('missing_key')
    import run_cxr_vqa_toolsets as base
    a.out.mkdir(parents=True,exist_ok=True)
    with base.exclusive_lock(a.out/'.online.lock'):
        amendment(a.out)
        save_once(a.out/'manifest.json',manifest)
        vault=ReferenceVault(a.reference_dir,refs)
        from r50_baseline_controls import validate_runtime
        validate_runtime(runtime)
        service=Services(cfg,protocol,runtime,a.out/'services',key,a.embedding_model,a.embedding_base_url)
        history=run_stream(inputs,order,a.data,a.out,service,vault,tools)
        print({'completed':len(inputs),'arm':ARM,'windows':len(history)})
if __name__=='__main__':main()
