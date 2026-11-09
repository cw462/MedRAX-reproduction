RUN='[REDACTED]'
CODE='[REDACTED]'
PYTHON='[REDACTED]'
RECOVERY='adoption_1'
ARM='M43-IM-GT-S49'
SOURCE_IDS=('chexbench_slake_0081', 'chexbench_slake_0082')
DUPLICATE_SKILL='s_e1a0642fabefb0c7'
ANALYSIS_CLARIFICATION="\n\nEXPLICIT ATTRIBUTION UNIQUENESS CONTRACT; no new clinical information or source evidence.\nReport each injected skill_id at most once in skill_adoption. A single entry must represent that skill's adoption in this trajectory using the one best supported actual zero-based step_index and its concise evidence; do not create separate entries for multiple steps.\nKeep the original ADOPTED_POSITIVE, ADOPTED_NEGATIVE and IGNORED meanings, original source-evidence requirements and all other output fields unchanged. Never invent an injected ID, step, tool execution or patient fact. This is a uniqueness/schema clarification, not a new clinical guideline.\n"
SELECTION_INSTRUCTION='\nBOUNDED ATTRIBUTION REPRESENTATIVE SELECTION ONLY; no new source information.\nThe original response repeated one injected skill_id with two different step/evidence entries. Both original entries have the same ADOPTED_POSITIVE status.\nUse only the original completed trajectory, released feedback, original image and the two original entries supplied below. Select the original entry best supported by its actual recorded step as the representative; this does not add a second credit.\nReturn exactly one JSON object {"selected_duplicate_index":0} or {"selected_duplicate_index":1}. The index refers to the two-entry duplicate_entries array, not the trajectory step number.\nDo not rewrite, add or infer any status, step, evidence, clinical content or other analysis field. Do not return a new adoption list. The selected original entry and all other unique entries will be copied verbatim by the caller.\n'
DATASETS=('chexbench', 'slake', 'vqarad')
COUNTS={'chexbench': 618, 'slake': 114, 'vqarad': 116}
import json
from pathlib import Path
def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))

def write_once(path,value):
    import os,uuid
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    if path.is_file():
        if read(path)!=value:raise ValueError('immutable_adoption_recovery_record_changed')
        return
    temporary=path.with_name('.'+path.name+'.'+uuid.uuid4().hex+'.tmp')
    try:
        with temporary.open('x',encoding='utf-8') as handle:json.dump(value,handle,ensure_ascii=False,indent=2);handle.write('\n');handle.flush();os.fsync(handle.fileno())
        os.link(temporary,path)
    finally:temporary.unlink(missing_ok=True)

def validate_authorization(scope,authorization):
    expected={'recovery_id':RECOVERY,'uses_existing_r49_authorization':True,'new_user_approval_claimed':False,
      'fresh_meta_repair_limit':2,'assess_only':True,'write_phase_analysis_unchanged':True,'representative_index_only':True,
      'extra_agent_calls_for_repair':0,'extra_embedding_calls_for_repair':0,'extra_tool_retries':0,
      'analysis_clarification_all_datasets':True,'extra_meta_calls_per_ordinary_analysis':0,'automatic_future_repair':False,
      'modify_completed_records':False,'retain_all_prior_overlays':True}
    if any(scope.get(key)!=value for key,value in expected.items()) or not scope.get('authorization_basis'):
        raise ValueError('exact_adoption_repair_scope_required')
    expected_auth={'recovery_id':RECOVERY,'verdict':'audit_deferred_until_full_generation','review_completed':False,'scope_complete':False,
      'exact_user_reply':'这个可以跑完再审计？','confirmation_source':'explicit_user_reply','audit_before_publication':True,'implementation_checks_passed':True}
    if any(authorization.get(key)!=value for key,value in expected_auth.items()):
        raise ValueError('truthful_user_directed_postrun_audit_authorization_required')

def duplicate_entries(adoption):
    from collections import Counter
    if not isinstance(adoption,list) or len(adoption)!=3:raise ValueError('known_adoption_shape_changed')
    counts=Counter(item['skill_id'] for item in adoption)
    if {sid for sid,count in counts.items() if count>1}!={DUPLICATE_SKILL} or counts[DUPLICATE_SKILL]!=2:
        raise ValueError('known_duplicate_skill_changed')
    entries=[item for item in adoption if item['skill_id']==DUPLICATE_SKILL]
    if any(item.get('status')!='ADOPTED_POSITIVE' for item in entries) or {item.get('step_index') for item in entries}!={0,1} or entries[0]==entries[1]:
        raise ValueError('known_conflicting_representatives_changed')
    return entries

def effective_adoption(original,index):
    import copy
    entries=duplicate_entries(original)
    if type(index) is not int or index not in (0,1):raise ValueError('representative_index_must_be_zero_or_one')
    selected_position=[position for position,item in enumerate(original) if item['skill_id']==DUPLICATE_SKILL][index]
    return [copy.deepcopy(item) for position,item in enumerate(original)
      if item['skill_id']!=DUPLICATE_SKILL or position==selected_position]

def ensure_amendment(stream,recovery_root,dataset,original_system):
    from datetime import datetime,timezone
    stream,recovery_root=Path(stream),Path(recovery_root);path=stream/'failure_events/analysis_unique_adoption_amendment.json'
    fixed={'schema':'r49_analysis_unique_adoption_amendment_v1','recovery_id':RECOVERY,'dataset':dataset,'arm':ARM,
      'activation_committed_questions':210 if dataset=='chexbench' else 0,'original_system':original_system,
      'clarification':ANALYSIS_CLARIFICATION,'ordinary_event_rule':"system == original ANALYZE and event == 'analysis_' + payload['trajectory']['id']",
      'extra_ordinary_meta_calls':0,'automatic_future_repair':False,'new_clinical_information':False,'status':'active'}
    if path.is_file():
        record=read(path)
        if any(record.get(key)!=value for key,value in fixed.items()):raise ValueError('analysis_uniqueness_amendment_changed')
    else:
        protected=[]
        for request_path in (stream/'services/calls/R49-META').glob('*/1/request.json'):
            request=read(request_path);messages=request['messages']
            if messages[0]['content']!=original_system:continue
            payload=json.loads(messages[1]['content'][0]['text']);qid=payload.get('trajectory',{}).get('id');event=request_path.parent.parent.name
            if isinstance(qid,str) and event=='analysis_'+qid:
                if any(not (request_path.parent/name).is_file() for name in ('started.json','response.json','result.json')):
                    raise RuntimeError('unclosed_old_analysis_no_retry')
                protected.append(event)
        record={**fixed,'protected_original_events':sorted(protected),'utc':datetime.now(timezone.utc).isoformat()}
        write_once(path,record)
    write_once(recovery_root/'amendments'/(dataset+'.json'),record)
    return record

def analysis_meta_overlay(original_meta,services_root,amendment):
    services_root=Path(services_root).resolve()
    def meta(self,event,system,payload,image_row=None,data=None):
        qid=payload.get('trajectory',{}).get('id')
        if self.out.resolve()!=services_root or system!=amendment['original_system'] or not isinstance(qid,str) or event!='analysis_'+qid:
            return original_meta(self,event,system,payload,image_row,data)
        request=self.out/'calls/R49-META'/event/'1/request.json';protected=event in amendment['protected_original_events']
        if request.is_file():
            saved=read(request)['messages'][0]['content']
            if saved==system and protected:chosen=system
            elif saved==system+ANALYSIS_CLARIFICATION and not protected:chosen=system+ANALYSIS_CLARIFICATION
            else:raise ValueError('unrecognized_analysis_prompt_no_retry')
        else:
            if protected:raise RuntimeError('protected_original_analysis_request_missing')
            chosen=system+ANALYSIS_CLARIFICATION
        return original_meta(self,event,chosen,payload,image_row,data)
    return meta

def representative_choice(service,stream,qid,analysis,trajectory):
    import copy
    from run_cxr_action_r41 import parse
    event='analysis_'+qid;repair_event=event+'_adoption_1';folder=Path(stream)/'services/calls/R49-META'/event/'1'
    if any(not (folder/name).is_file() for name in ('request.json','started.json','response.json','result.json')):
        raise RuntimeError('original_analysis_not_closed_no_reissue')
    request=read(folder/'request.json');raw=read(folder/'response.json')['choices'][0]['message']['content']
    if parse(raw)!=analysis:raise ValueError('old_write_analysis_changed')
    source=json.loads(request['messages'][1]['content'][0]['text'])
    if source['trajectory']!=trajectory or qid!=trajectory['id']:raise ValueError('original_source_trajectory_changed')
    original=analysis['skill_adoption'];entries=duplicate_entries(original)
    if any(item['skill_id'] not in trajectory['injected'] for item in original):raise ValueError('original_adoption_not_injected')
    messages=copy.deepcopy(request['messages'])
    messages.append({'role':'assistant','content':raw})
    instruction=SELECTION_INSTRUCTION+json.dumps({'duplicate_skill_id':DUPLICATE_SKILL,'duplicate_entries':entries},ensure_ascii=False)
    messages.append({'role':'user','content':instruction})
    selected=parse(service.call({'question_id':repair_event},'R49-META',1,messages))
    if set(selected)!={'selected_duplicate_index'}:raise ValueError('choice_only_reply_required')
    index=selected['selected_duplicate_index'];effective=effective_adoption(original,index)
    return effective,{'source_event':event,'repair_event':repair_event,'source_question_id':qid,'duplicate_skill_id':DUPLICATE_SKILL,
      'original_adoption':original,'selected_duplicate_index':index,'effective_adoption':effective,
      'original_call_relative':'services/calls/R49-META/'+event+'/1','repair_call_relative':'services/calls/R49-META/'+repair_event+'/1',
      'selection_instruction':instruction,'source_payload_unchanged':True,'new_clinical_information':False}

def assessment_evolve_overlay(original_evolve,module,recovery_root,dataset,plan):
    import copy
    from datetime import datetime,timezone
    from unittest.mock import patch
    recovery_root=Path(recovery_root);original_assess=module.assess
    def evolve(service,snapshot,batch,wi,window,data,tools,config):
        if dataset!='chexbench' or wi!=6:return original_evolve(service,snapshot,batch,wi,window,data,tools,config)
        if [item['id'] for item in batch]!=plan['window_question_ids']:raise ValueError('known_assessment_window_changed')
        def assess(repo,trajectories,analyses,cfg):
            amended=copy.deepcopy(analyses);repairs=[];by_id={item['id']:item for item in trajectories}
            for qid in SOURCE_IDS:
                effective,record=representative_choice(service,Path(window).parents[1],qid,analyses[qid],by_id[qid])
                amended[qid]['skill_adoption']=effective;repairs.append(record)
            credits=original_assess(repo,trajectories,amended,cfg)
            stream=Path(window).parents[1];path=stream/'failure_events/adoption_1_registration.json';existing=read(path) if path.is_file() else {}
            registration={'schema':'r49_registered_assessment_adoption_repair_v1','recovery_id':RECOVERY,'dataset':dataset,'arm':ARM,
              'window_index':6,'activation_committed_questions':210,'repairs':repairs,'new_meta_requests':2,
              'assess_only':True,'write_phase_analysis_unchanged':True,'other_analysis_fields_unchanged':True,'automatic_retry':False,
              'status':'two_assess_only_adoption_repairs_registered','utc':existing.get('utc') or datetime.now(timezone.utc).isoformat()}
            write_once(path,registration);write_once(recovery_root/'registration.json',registration)
            return credits
        with patch.object(module,'assess',assess):return original_evolve(service,snapshot,batch,wi,window,data,tools,config)
    return evolve


import fcntl,os,subprocess,sys,time,shutil
r=Path(RUN);j=r/'jobs';a=r/'recovery'/RECOVERY
lock=(j/'.controller.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
validate_authorization(read(a/'SCOPE.json'),read(a/'EXECUTION_AUTHORIZATION.json'))
main_key=sys.stdin.buffer.readline();embedding_key=sys.stdin.buffer.readline().strip().decode();assert main_key.strip() and embedding_key
def state(value):
 value.update(recovery=RECOVERY,prior_production_attempts_include_exit1=True)
 path=j/'queue_status.json';temporary=path.with_suffix('.tmp');temporary.write_text(json.dumps(value,indent=2)+'\n');temporary.replace(path)
for ds in DATASETS:
 while True:
  memory=int(subprocess.check_output(['nvidia-smi','--id=1','--query-gpu=memory.used','--format=csv,noheader,nounits'],text=True).strip())
  state({'state':'waiting_gpu1' if memory>=500 else 'ready_gpu1','dataset':ds,'gpu1_used_mib':memory})
  if memory<500:break
  time.sleep(60)
 assert shutil.disk_usage(r).free>3*1024**3
 logfile=j/(ds+'.'+RECOVERY+'.log')
 with logfile.open('xb',buffering=0) as log:
  process=subprocess.Popen([PYTHON,'-u',str(a/'resume_runner.py'),'--dataset',ds],stdin=subprocess.PIPE,stdout=log,stderr=subprocess.STDOUT,
   env=dict(os.environ,R49_EMBEDDING_API_KEY=embedding_key,LANGCHAIN_TRACING_V2='false',LANGSMITH_TRACING='false'))
  (a/(ds+'.pid')).write_text(str(process.pid));(j/(ds+'.pid')).write_text(str(process.pid))
  state({'state':'running_dataset','dataset':ds,'pid':process.pid,'current_attempt_exit':None,'log':str(logfile)})
  process.communicate(main_key)
 rc=process.returncode;(a/(ds+'.exitcode')).write_text(str(rc)+'\n');(j/(ds+'.exitcode')).write_text(str(rc)+'\n')
 out=r/'generation'/ds
 if out.is_dir():(out/'generation.exitcode').write_text(str(rc)+'\n')
 if rc:
  state({'state':'dataset_failed_stop_queue','dataset':ds,'pid':process.pid,'exit_code':rc,'log':str(logfile)})
  raise SystemExit(rc)
 done=read(out/'complete.json');assert done['status']=='generation_complete' and done['questions']==COUNTS[ds]
state({'state':'all_three_datasets_exited_zero_after_adoption_recovery','datasets':list(DATASETS)})
