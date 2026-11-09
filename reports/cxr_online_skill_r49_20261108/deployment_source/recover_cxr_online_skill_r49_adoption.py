"""Two bounded representative choices at assess only; full audit follows generation."""
import argparse
import inspect
import json
from pathlib import Path

from deploy_cxr_online_skill_r49 import CODE, COUNTS, DATASETS, PREP, PYTHON, RUN, TRANSPORT_HOME, connect, remote_python
from recover_cxr_online_skill_r49_phrase_guard import CONTROLLER as PREVIOUS_CONTROLLER

RECOVERY='adoption_1'
ARM='M43-IM-GT-S49'
SOURCE_IDS=('chexbench_slake_0081','chexbench_slake_0082')
DUPLICATE_SKILL='s_e1a0642fabefb0c7'
SCOPE=PREP/'ADOPTION_RECOVERY_SCOPE.json'
AUTHORIZATION=PREP/'ADOPTION_EXECUTION_AUTHORIZATION.json'
ANALYSIS_CLARIFICATION='''

EXPLICIT ATTRIBUTION UNIQUENESS CONTRACT; no new clinical information or source evidence.
Report each injected skill_id at most once in skill_adoption. A single entry must represent that skill's adoption in this trajectory using the one best supported actual zero-based step_index and its concise evidence; do not create separate entries for multiple steps.
Keep the original ADOPTED_POSITIVE, ADOPTED_NEGATIVE and IGNORED meanings, original source-evidence requirements and all other output fields unchanged. Never invent an injected ID, step, tool execution or patient fact. This is a uniqueness/schema clarification, not a new clinical guideline.
'''
SELECTION_INSTRUCTION='''
BOUNDED ATTRIBUTION REPRESENTATIVE SELECTION ONLY; no new source information.
The original response repeated one injected skill_id with two different step/evidence entries. Both original entries have the same ADOPTED_POSITIVE status.
Use only the original completed trajectory, released feedback, original image and the two original entries supplied below. Select the original entry best supported by its actual recorded step as the representative; this does not add a second credit.
Return exactly one JSON object {"selected_duplicate_index":0} or {"selected_duplicate_index":1}. The index refers to the two-entry duplicate_entries array, not the trajectory step number.
Do not rewrite, add or infer any status, step, evidence, clinical content or other analysis field. Do not return a new adoption list. The selected original entry and all other unique entries will be copied verbatim by the caller.
'''


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


GUARD=r'''
r=Path(RUN);j=r/'jobs';g=r/'generation/chexbench';s=g/'services';a=r/'recovery'/RECOVERY
for name in ('controller','chexbench'):
 pid=(j/(name+'.pid')).read_text().strip();assert not Path('/proc',pid).exists(), 'R49_process_active'
 assert (j/(name+'.exitcode')).read_text().strip()=='1'
assert (g/'generation.exitcode').read_text().strip()=='1'
assert (j/'chexbench.phrase_guard_1.log').read_text(errors='replace').rstrip().splitlines()[-1]=='ValueError: duplicate_skill_adoption'
ids=[row['question_id'] for row in read(g/'manifest.json')['inputs']];assert len(ids)==618
for name in ('predictions/M43-IM-GT-S49','contexts','prediction_events','feedback','steps'):
 assert {p.stem for p in (g/name).glob('*.json')}==set(ids[:210])
assert {p.parent.name for p in (g/'windows').glob('*/repo.json')}=={f'{wi:04d}' for wi in range(6)}
assert not (g/'windows/0006/repo.json').exists() and not (g/'windows/0006/events.json').exists()
assert {p.stem for p in (g/'windows/0006/trajectories').glob('*.json')}==set(ids[180:210])
for arm,count in [('R49-AGENT',490),('R49-META',223)]:
 starts=list((s/'calls'/arm).glob('*/*/started.json'));assert len(starts)==count
 for start in starts:
  assert (start.parent/'response.json').is_file() and read(start.parent/'result.json').get('response_received') is True
assert len(list((s/'embeddings').glob('*/started.json')))==110 and len(list((s/'embeddings').glob('*/response.json')))==109
assert read(g/'failure_events/embedding_arrearage_1_registration.json')['status']=='healthy_embedding_retry_registered'
assert read(g/'failure_events/phrase_guard_1_registration.json')['status']=='healthy_guarded_production_retry_registered'
assert len(list((s/'tool_selections/R49-AGENT').glob('*/*.json')))==265
for qid in SOURCE_IDS:
 assert qid in ids[180:210]
 assert not (s/'calls/R49-META'/('analysis_'+qid+'_adoption_1')).exists()
assert not (g/'failure_events/adoption_1_registration.json').exists()
assert (r/'recovery/phrase_guard_1/resume_runner.py').is_file()
for ds in ('slake','vqarad'):
 assert not (j/(ds+'.pid')).exists()
 out=r/'generation'/ds;assert not out.exists() or not any(out.rglob('*.json'))
'''

CONTROLLER=PREVIOUS_CONTROLLER.replace("read(a/'REVIEW_READY.json')","read(a/'EXECUTION_AUTHORIZATION.json')").replace('validate_scope(','validate_authorization(').replace(
    'all_three_datasets_exited_zero_after_phrase_guard_recovery','all_three_datasets_exited_zero_after_adoption_recovery')

RESUME_RUNNER=r'''
import argparse,runpy,sys
parser=argparse.ArgumentParser();parser.add_argument('--dataset',choices=DATASETS,required=True);args=parser.parse_args()
sys.path.insert(0,str(Path(CODE)/'experiments'))
from skill_services_r49 import Services
from skill_prompts_r49 import ANALYZE
import skill_evolve_r49 as evolving
a=Path(RUN)/'recovery'/RECOVERY
validate_authorization(read(a/'SCOPE.json'),read(a/'EXECUTION_AUTHORIZATION.json'))
stream=Path(RUN)/'generation'/args.dataset;amendment=ensure_amendment(stream,a,args.dataset,ANALYZE)
Services.meta=analysis_meta_overlay(Services.meta,stream/'services',amendment)
evolving.evolve=assessment_evolve_overlay(evolving.evolve,evolving,a,args.dataset,read(a/'plan.json'))
sys.argv=[str(Path(RUN)/'recovery/phrase_guard_1/resume_runner.py'),'--dataset',args.dataset]
runpy.run_path(sys.argv[0],run_name='__main__')
'''


def definitions():
    values=dict(RUN=RUN,CODE=CODE,PYTHON=PYTHON,RECOVERY=RECOVERY,ARM=ARM,SOURCE_IDS=SOURCE_IDS,DUPLICATE_SKILL=DUPLICATE_SKILL,
      ANALYSIS_CLARIFICATION=ANALYSIS_CLARIFICATION,SELECTION_INSTRUCTION=SELECTION_INSTRUCTION,DATASETS=DATASETS,COUNTS=COUNTS)
    return '\n'.join(key+'='+repr(value) for key,value in values.items())+'\n'


def shared_source():
    return 'import json\nfrom pathlib import Path\n'+'\n'.join(inspect.getsource(fn) for fn in
      (read,write_once,validate_authorization,duplicate_entries,effective_adoption,ensure_amendment,analysis_meta_overlay,representative_choice,assessment_evolve_overlay))+'\n'


def stage_payload():
    return definitions()+shared_source()+GUARD+r'''
import shutil
sys_path=str(Path(CODE)/'experiments')
import sys
sys.path.insert(0,sys_path)
from run_cxr_action_r41 import parse
for qid in SOURCE_IDS:
 duplicate_entries(parse(read(s/'calls/R49-META'/('analysis_'+qid)/'1/response.json')['choices'][0]['message']['content'])['skill_adoption'])
assert shutil.disk_usage(r).free>3*1024**3
assert not a.exists(), 'adoption_recovery_already_staged'
a.mkdir(parents=True);(a/'prior_jobs').mkdir()
for path in j.iterdir():
 if path.is_file() and path.suffix in ('.json','.log','.pid','.exitcode'):shutil.copyfile(path,a/'prior_jobs'/path.name)
shutil.copyfile(g/'generation.exitcode',a/'prior_generation.exitcode')
plan={'recovery_id':RECOVERY,'window_index':6,'window_question_ids':ids[180:210],'activation_committed_questions':210,'committed_windows_before':6,
 'source_ids':list(SOURCE_IDS),'duplicate_skill_id':DUPLICATE_SKILL,'new_meta_request_limit':2,'representative_index_only':True,
 'previous_wrapper':'recovery/phrase_guard_1/resume_runner.py','audit_timing':'after_full_generation_before_publication'}
write_once(a/'plan.json',plan)
print(json.dumps({'staged':True,'recovery_id':RECOVERY,'api_calls':0,'tool_calls':0,'committed_questions_preserved':210}))
'''


def stage(client):
    scope,authorization=read(SCOPE),read(AUTHORIZATION);validate_authorization(scope,authorization)
    remote_python(client,stage_payload(),timeout=30)
    with client.open_sftp() as sftp:
        for name,value in [('SCOPE.json',scope),('EXECUTION_AUTHORIZATION.json',authorization)]:
            with sftp.open(RUN+'/recovery/'+RECOVERY+'/'+name,'wx') as handle:handle.write(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
        for name,source in [('controller.py',CONTROLLER),('resume_runner.py',RESUME_RUNNER)]:
            with sftp.open(RUN+'/recovery/'+RECOVERY+'/'+name,'wx') as handle:handle.write(definitions()+shared_source()+source)


def launch(client):
    remote_python(client,definitions()+shared_source()+GUARD+r'''
import fcntl,os,shlex,subprocess,sys
lock=(j/'.queue_launch.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
assert not (a/'controller.started.json').exists(), 'adoption_launch_already_claimed'
validate_authorization(read(a/'SCOPE.json'),read(a/'EXECUTION_AUTHORIZATION.json'))
keys=sys.stdin.buffer.readline()+sys.stdin.buffer.readline();assert len(keys.splitlines())==2
rd,wr=os.pipe();os.write(wr,keys);os.close(wr)
write_once(a/'controller.started.json',{'recovery_id':RECOVERY,'status':'launch_intent','fresh_meta_repair_limit':2,'automatic_retry':False})
command=shlex.join([PYTHON,'-u',str(a/'controller.py')])+'; rc=$?; printf "%s\n" "$rc" > '+str(a/'controller.exitcode')+'; printf "%s\n" "$rc" > '+str(j/'controller.exitcode')+'; exit "$rc"'
try:
 with (a/'controller.log').open('xb',buffering=0) as log:
  process=subprocess.Popen(['bash','-c',command],stdin=rd,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
 record={'recovery_id':RECOVERY,'pid':process.pid,'prior_attempts_include_exit1':True,'frozen_runtime_files_edited':False,'audit_deferred_until_full_generation':True}
 write_once(a/'controller.launched.json',record);(a/'controller.pid').write_text(str(process.pid));(j/'controller.pid').write_text(str(process.pid));print(json.dumps(record))
finally:os.close(rd)
''',timeout=30,input_bytes=(TRANSPORT_HOME/'.secrets/token_plan_api.key').read_bytes().strip()+b'\n'+(TRANSPORT_HOME/'.secrets/qwen_api.key').read_bytes().strip()+b'\n')


def status(client):
    remote_python(client,definitions()+shared_source()+r'''
import shutil
r=Path(RUN);j=r/'jobs';a=r/'recovery'/RECOVERY
def text(path):return path.read_text().strip() if path.is_file() else None
def phase(name):
 pid=text(a/(name+'.pid'));return {'pid':pid,'alive':bool(pid and Path('/proc',pid).exists()),'exit':text(a/(name+'.exitcode'))}
value={'recovery':RECOVERY,'controller':phase('controller'),'audit_deferred_until_full_generation':True,
 'queue':read(j/'queue_status.json') if (j/'queue_status.json').is_file() else None,
 'registered':(r/'generation/chexbench/failure_events/adoption_1_registration.json').is_file(),'datasets':{},'free_bytes':shutil.disk_usage(r).free}
for ds in DATASETS:
 g=r/'generation'/ds;s=g/'services';value['datasets'][ds]=dict(phase(ds),saved=len(list((g/'predictions'/ARM).glob('*.json'))),
 contexts=len(list((g/'contexts').glob('*.json'))),prediction_events=len(list((g/'prediction_events').glob('*.json'))),feedback=len(list((g/'feedback').glob('*.json'))),
 main_sends=len(list((s/'calls/R49-AGENT').glob('*/*/started.json'))),main_responses=len(list((s/'calls/R49-AGENT').glob('*/*/response.json'))),
 meta_sends=len(list((s/'calls/R49-META').glob('*/*/started.json'))),meta_responses=len(list((s/'calls/R49-META').glob('*/*/response.json'))),
 embeddings_sent=len(list((s/'embeddings').glob('*/started.json'))),embeddings_received=len(list((s/'embeddings').glob('*/response.json'))),
 tools=len(list((s/'tool_selections/R49-AGENT').glob('*/*.json'))),windows=len(list((g/'windows').glob('*/repo.json'))),complete=(g/'complete.json').exists())
 log=j/(ds+'.'+RECOVERY+'.log')
 if value['datasets'][ds]['exit'] not in (None,'0') and log.is_file():value['datasets'][ds]['failure_tail']=log.read_text(errors='replace').splitlines()[-16:]
print(json.dumps(value))
''',timeout=30)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('mode',choices=('stage','launch','status'))
    args=parser.parse_args()
    with connect() as client:globals()[args.mode](client)
