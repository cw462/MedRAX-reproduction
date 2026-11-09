"""Bounded second schema repair and explicit ordinary MUTATE field contract."""
import argparse
import inspect
import json
from pathlib import Path

from deploy_cxr_online_skill_r49 import CODE, COUNTS, DATASETS, PREP, PYTHON, RUN, TRANSPORT_HOME, connect, program, remote_python

RECOVERY='mutation_fields_2'
ARM='M43-IM-GT-S49'
SOURCE_QID='chexbench_slake_0013'
SOURCE_EVENT='mutation_'+SOURCE_QID
REPAIR_EVENT=SOURCE_EVENT+'_schema_2'
ALLOWED_SECTIONS=('name','description','applicable_conditions','required_tools','risk_level','core_action')
SCOPE=PREP/'MUTATION_FIELDS_RECOVERY_SCOPE.json'
REVIEW=PREP/'MUTATION_FIELDS_RECOVERY_REVIEW_READY.json'
REPAIR_INSTRUCTION='''

ONE-CASE SCHEMA CLARIFICATION; no new source evidence is supplied.
The preceding mutation used patch_section="content", which names the whole content container and is not a permitted single-field patch.
For PATCH, retain exactly this patch_target_id: {target_json}.
patch_section must be exactly one of: name, description, applicable_conditions, required_tools, risk_level, core_action.
Return the original PATCH schema for one such field; do not replace the whole content container or change branch, task_category or tool_name.
Use only the same original source payload. Do not add clinical facts or consult another case or future feedback.
If the source does not support a valid single-field patch, explicitly return {{"operation":"NONE"}}.
Return one JSON object with operation PATCH or NONE; do not produce CREATE, another target, or a patch to a different scope.
'''
FIELDS_CLARIFICATION='''

EXPLICIT MUTATION FIELD CONTRACT; no new clinical information or source evidence.
For operation PATCH, patch_section must be exactly one of: name, description, applicable_conditions, required_tools, risk_level, core_action.
The names "c" and "content" denote the whole content container and are not permitted patch_section values.
A PATCH changes one such field of an eligible target already present in the supplied window snapshot. Do not change branch, task_category or tool_name.
Keep the original CREATE, PATCH and NONE meanings and the original source-evidence requirements. This clarification introduces no new clinical rule or permission to infer facts.
'''


def write_once(path,value):
    import os,uuid
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists():
        if json.loads(path.read_text())!=value:raise ValueError('immutable_meta_recovery_record_changed')
        return
    temporary=path.with_name('.'+path.name+'.'+uuid.uuid4().hex+'.tmp')
    try:
        with temporary.open('x') as handle:json.dump(value,handle,ensure_ascii=False,indent=2);handle.write('\n');handle.flush();os.fsync(handle.fileno())
        os.link(temporary,path)
    finally:temporary.unlink(missing_ok=True)


def validate_scope(scope,review):
    expected={'recovery_id':RECOVERY,'uses_existing_r49_authorization':True,'new_user_approval_claimed':False,
      'fresh_meta_repair_limit':1,'extra_agent_calls':0,'extra_embedding_calls':0,'extra_tool_retries':0,
      'new_diagnostic_invocations':0,'modify_completed_records':False,'allowed_sections_unchanged':True,
      'ordinary_field_clarification_all_datasets':True,'extra_meta_calls_per_ordinary_event':0,'automatic_future_repair':False,
      'target_unchanged':True,'automatic_invalid_to_none':False,'keep_cuda_cache_overlay':True,'keep_meta_schema_1_overlay':True}
    if any(scope.get(key)!=value for key,value in expected.items()) or not scope.get('authorization_basis'):
        raise ValueError('exact_meta_schema_operational_scope_required')
    if review.get('recovery_id')!=RECOVERY or review.get('verdict')!='ready' or review.get('scope_complete') is not True or not review.get('trace'):
        raise ValueError('actual_meta_schema_review_required')


def ensure_amendment(stream,recovery_root,dataset,original_system):
    """Freeze the old ordinary-event boundary once; do not reclassify on replay."""
    from datetime import datetime,timezone
    stream,recovery_root=Path(stream),Path(recovery_root)
    path=stream/'failure_events/mutation_fields_2_amendment.json'
    fixed={'schema':'r49_mutation_fields_amendment_v1','recovery_id':RECOVERY,'dataset':dataset,'arm':ARM,
      'original_system':original_system,'clarification':FIELDS_CLARIFICATION,'allowed_sections':list(ALLOWED_SECTIONS),
      'ordinary_event_rule':"system == original MUTATE and event == 'mutation_' + payload['trajectory']['id']",
      'extra_ordinary_meta_calls':0,'new_clinical_information':False,'same_original_payload':True,
      'cached_original_or_clarified_replay':True,'automatic_future_repair':False,'status':'active'}
    if path.is_file():
        record=json.loads(path.read_text())
        if any(record.get(key)!=value for key,value in fixed.items()):raise ValueError('mutation_field_amendment_changed')
        protected=record['protected_original_events']
        if not isinstance(protected,list) or protected!=sorted(set(protected)):raise ValueError('invalid_protected_event_boundary')
    else:
        protected=[]
        for request_path in (stream/'services/calls/R49-META').glob('*/1/request.json'):
            request=json.loads(request_path.read_text());messages=request['messages']
            if messages[0]['content']!=original_system:continue
            payload=json.loads(messages[1]['content'][0]['text']);event=request_path.parent.parent.name
            trajectory_id=payload.get('trajectory',{}).get('id')
            if not isinstance(trajectory_id,str) or event!='mutation_'+trajectory_id:continue
            for name in ('started.json','response.json','result.json'):
                if not (request_path.parent/name).is_file():raise RuntimeError('unclosed_original_mutation_boundary')
            protected.append(event)
        record={**fixed,'protected_original_events':sorted(protected),
          'committed_questions_at_activation':len(list((stream/'predictions'/ARM).glob('*.json'))),
          'utc':datetime.now(timezone.utc).isoformat()}
        write_once(path,record)
    write_once(recovery_root/'amendments'/(dataset+'.json'),record)
    return record


def mutation_fields_overlay(original_meta,services_root,recovery_root,target,amendment):
    """One confirmed repair plus zero-extra-call clarification, never a repair loop."""
    import copy
    from datetime import datetime,timezone
    services_root,recovery_root=Path(services_root).resolve(),Path(recovery_root)
    def meta(self,event,system,payload,image_row=None,data=None):
        if self.out.resolve()!=services_root:
            return original_meta(self,event,system,payload,image_row,data)
        current_repair=amendment['dataset']=='chexbench' and event==SOURCE_EVENT
        trajectory_id=payload.get('trajectory',{}).get('id')
        ordinary=system==amendment['original_system'] and isinstance(trajectory_id,str) and event=='mutation_'+trajectory_id
        if not current_repair:
            if not ordinary:return original_meta(self,event,system,payload,image_row,data)
            if image_row is not None:raise ValueError('ordinary_mutation_extra_image_forbidden')
            request_path=self.out/'calls/R49-META'/event/'1/request.json'
            protected=event in amendment['protected_original_events']
            if request_path.is_file():
                saved_system=json.loads(request_path.read_text())['messages'][0]['content']
                if saved_system==system and protected:chosen=system
                elif saved_system==system+FIELDS_CLARIFICATION and not protected:chosen=system+FIELDS_CLARIFICATION
                else:raise ValueError('unrecognized_cached_mutation_prompt_stop')
            else:
                if protected:raise RuntimeError('protected_mutation_request_missing_stop')
                chosen=system+FIELDS_CLARIFICATION
            return original_meta(self,event,chosen,payload,image_row,data)
        if image_row is not None:raise ValueError('schema_repair_extra_image_forbidden')
        if event not in amendment['protected_original_events'] or trajectory_id!=SOURCE_QID:
            raise ValueError('confirmed_repair_not_in_protected_boundary')
        old_folder=self.out/'calls/R49-META'/SOURCE_EVENT/'1'
        if any(not (old_folder/name).is_file() for name in ('request.json','started.json','response.json','result.json')):
            raise RuntimeError('original_meta_not_closed_no_reissue')
        # Calling the original method retains its cached-request semantic check.
        invalid=original_meta(self,event,system,payload,image_row,data)
        if (system!=amendment['original_system'] or invalid.get('operation')!='PATCH' or invalid.get('patch_section')!='content'
                or invalid.get('patch_target_id')!=target or target not in payload['snapshot']):
            raise ValueError('different_meta_failure_requires_diagnosis')
        instruction=REPAIR_INSTRUCTION.format(target_json=json.dumps(target,ensure_ascii=False))
        repaired=original_meta(self,REPAIR_EVENT,system+instruction,copy.deepcopy(payload),None,data)
        operation=repaired.get('operation')
        if operation not in ('PATCH','NONE'):raise ValueError('meta_schema_repair_invalid_operation_stop')
        if operation=='PATCH' and (repaired.get('patch_target_id')!=target or repaired.get('patch_section') not in ALLOWED_SECTIONS):
            raise ValueError('meta_schema_repair_invalid_patch_stop')
        new_folder=self.out/'calls/R49-META'/REPAIR_EVENT/'1'
        for folder in (old_folder,new_folder):
            if any(not (folder/name).is_file() for name in ('request.json','started.json','response.json','result.json')):
                raise RuntimeError('unclosed_meta_repair_stop')
            receipt=json.loads((folder/'result.json').read_text())
            if receipt.get('response_received') is not True or receipt.get('error'):
                raise RuntimeError('unhealthy_meta_repair_receipt_stop')
        old_control={key:invalid.get(key) for key in ('operation','patch_section','patch_target_id')}
        new_control={key:repaired.get(key) for key in ('operation','patch_section','patch_target_id')}
        registration_path=self.out.parent/'failure_events/meta_schema_2_registration.json'
        registered=json.loads(registration_path.read_text()) if registration_path.is_file() else None
        recorded_at=registered['utc'] if registered else datetime.now(timezone.utc).isoformat()
        record={'schema':'r49_registered_meta_schema_repair_v2','recovery_id':RECOVERY,'dataset':'chexbench','arm':ARM,
          'source_question_id':SOURCE_QID,'source_event':SOURCE_EVENT,'repair_event':REPAIR_EVENT,'window_index':4,
          'target_skill_id':target,'original_call_relative':'services/calls/R49-META/'+SOURCE_EVENT+'/1',
          'repair_call_relative':'services/calls/R49-META/'+REPAIR_EVENT+'/1',
          'original_control':old_control,'repair_control':new_control,'repair_instruction':instruction,
          'same_original_payload':True,'new_meta_calls':1,'extra_agent_calls':0,'extra_embedding_calls':0,'extra_tool_calls':0,
          'automatic_invalid_to_none':False,'new_clinical_information':False,'status':'valid_meta_schema_repair_registered',
          'utc':recorded_at}
        write_once(registration_path,record)
        write_once(recovery_root/'registration.json',record)
        return repaired
    return meta


GUARD=r'''
from pathlib import Path
import json,sys
r=Path(RUN);j=r/'jobs';g=r/'generation/chexbench';s=g/'services';a=r/'recovery'/RECOVERY
def read(path):return json.loads(path.read_text())
for name in ('controller','chexbench'):
 pid=(j/(name+'.pid')).read_text().strip();assert not Path('/proc',pid).exists(), 'R49_process_active'
 assert (j/(name+'.exitcode')).read_text().strip()=='1'
assert (g/'generation.exitcode').read_text().strip()=='1'
tail=(j/'chexbench.meta_schema_1.log').read_text(errors='replace').rstrip().splitlines()
assert tail[-1]=='ValueError: invalid_patch_section', 'different_latest_failure'
ids=[row['question_id'] for row in read(g/'manifest.json')['inputs']]
assert len(ids)==618
for name in ('predictions/M43-IM-GT-S49','contexts','prediction_events','feedback','steps'):
 assert {p.stem for p in (g/name).glob('*.json')}==set(ids[:150]), '150_prefix_boundary_changed:'+name
assert {p.parent.name for p in (g/'windows').glob('*/repo.json')}=={'0000','0001','0002','0003'}
assert not (g/'windows/0004/events.json').exists() and not (g/'windows/0004/repo.json').exists()
for number in range(5):
 window=g/'windows'/f'{number:04d}'
 assert (window/'read_snapshot.json').is_file()
 assert {p.stem for p in (window/'trajectories').glob('*.json')}==set(ids[number*30:(number+1)*30])
assert (g/'windows/0004/buffer.json').is_file()
for arm,count in [('R49-AGENT',372),('R49-META',136)]:
 assert len(list((s/'calls'/arm).glob('*/*/started.json')))==count
assert len(list((s/'embeddings').glob('*/started.json')))==62
for start in list((s/'calls').glob('*/*/*/started.json'))+list((s/'embeddings').glob('*/started.json')):
 assert (start.parent/'response.json').is_file() and (start.parent/'result.json').is_file()
 receipt=read(start.parent/'result.json');assert receipt.get('response_received') is True and not receipt.get('error')
assert not (s/'calls/R49-META'/REPAIR_EVENT).exists(), 'fresh_repair_event_already_claimed'
assert not (g/'failure_events/meta_schema_2_registration.json').exists()
sys.path.insert(0,str(Path(CODE)/'experiments'))
from run_cxr_action_r41 import parse
source=s/'calls/R49-META'/SOURCE_EVENT/'1'
draft=parse(read(source/'response.json')['choices'][0]['message']['content'])
request=read(source/'request.json');source_payload=json.loads(request['messages'][1]['content'][0]['text'])
assert draft['operation']=='PATCH' and draft['patch_section']=='content' and draft['patch_target_id'] in source_payload['snapshot']
assert len(request['messages'][1]['content'])==1, 'unexpected_mutation_image_payload'
assert (r/'recovery/cuda_1/resume_runner.py').is_file()
assert (r/'recovery/meta_schema_1/resume_runner.py').is_file()
assert read(g/'failure_events/cuda_1_registration.json')['status']=='healthy_production_retry_registered'
assert read(g/'failure_events/meta_schema_1_registration.json')['status']=='valid_meta_schema_repair_registered'
for ds in ('slake','vqarad'):
 assert not (j/(ds+'.pid')).exists()
 out=r/'generation'/ds;assert not out.exists() or not any(out.rglob('*.json'))
'''


CONTROLLER=r'''
import fcntl,os,subprocess,sys,time,shutil
r=Path(RUN);j=r/'jobs';a=r/'recovery'/RECOVERY
lock=(j/'.controller.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
validate_scope(read(a/'SCOPE.json'),read(a/'REVIEW_READY.json'))
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
 command=[PYTHON,'-u',str(a/'resume_runner.py'),'--dataset',ds]
 logfile=j/(ds+'.'+RECOVERY+'.log')
 with logfile.open('xb',buffering=0) as log:
  process=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=log,stderr=subprocess.STDOUT,
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
state({'state':'all_three_datasets_exited_zero_after_mutation_fields_amendment','datasets':list(DATASETS)})
'''


RESUME_RUNNER=r'''
import argparse,runpy,sys
parser=argparse.ArgumentParser();parser.add_argument('--dataset',choices=DATASETS,required=True);args=parser.parse_args()
sys.path.insert(0,str(Path(CODE)/'experiments'))
from skill_services_r49 import Services
from skill_prompts_r49 import MUTATE
a=Path(RUN)/'recovery'/RECOVERY;plan=read(a/'plan.json')
stream=Path(RUN)/'generation'/args.dataset
amendment=ensure_amendment(stream,a,args.dataset,MUTATE)
Services.meta=mutation_fields_overlay(Services.meta,stream/'services',a,plan['target_skill_id'],amendment)
if args.dataset=='chexbench':
 # Replay only the earlier wrappers, not either consumed recovery controller.
 runpy.run_path(str(Path(RUN)/'recovery/meta_schema_1/resume_runner.py'),run_name='__main__')
else:
 sys.argv=PROGRAMS[args.dataset][2:]+['--execute','--api-key-stdin']
 runpy.run_path(sys.argv[0],run_name='__main__')
'''


def definitions():
    values=dict(RUN=RUN,CODE=CODE,PYTHON=PYTHON,RECOVERY=RECOVERY,ARM=ARM,SOURCE_QID=SOURCE_QID,
      SOURCE_EVENT=SOURCE_EVENT,REPAIR_EVENT=REPAIR_EVENT,ALLOWED_SECTIONS=ALLOWED_SECTIONS,
      REPAIR_INSTRUCTION=REPAIR_INSTRUCTION,FIELDS_CLARIFICATION=FIELDS_CLARIFICATION,DATASETS=DATASETS,COUNTS=COUNTS,PROGRAMS={ds:program(ds) for ds in DATASETS})
    return '\n'.join(key+'='+repr(value) for key,value in values.items())+'\n'


def shared_source():
    return 'import json\nfrom pathlib import Path\ndef read(path):return json.loads(Path(path).read_text())\n'+\
      '\n'.join(inspect.getsource(fn) for fn in (write_once,validate_scope,ensure_amendment,mutation_fields_overlay))+'\n'


def stage(client):
    scope=json.loads(SCOPE.read_text());review=json.loads(REVIEW.read_text());validate_scope(scope,review)
    remote_python(client,definitions()+GUARD+r'''
import shutil
a.mkdir(parents=True,exist_ok=True)
assert not (a/'plan.json').exists() and not (a/'controller.started.json').exists(), 'meta_schema_recovery_already_staged'
(a/'prior_jobs').mkdir()
for path in j.iterdir():
 if path.is_file() and path.suffix in ('.json','.log','.pid','.exitcode'):shutil.copyfile(path,a/'prior_jobs'/path.name)
shutil.copyfile(g/'generation.exitcode',a/'prior_generation.exitcode')
plan={'recovery_id':RECOVERY,'source_event':SOURCE_EVENT,'repair_event':REPAIR_EVENT,'window_index':4,
 'target_skill_id':draft['patch_target_id'],'original_control':{key:draft.get(key) for key in ('operation','patch_section','patch_target_id')},
 'committed_questions_before':150,'committed_windows_before':4,'fresh_meta_repair_limit':1,
 'extra_agent_calls_for_repair':0,'extra_embedding_calls_for_repair':0,'extra_tool_retries':0,
 'previous_wrapper':'recovery/meta_schema_1/resume_runner.py','ordinary_field_clarification_all_datasets':True,'automatic_invalid_to_none':False}
with (a/'plan.json').open('x') as handle:json.dump(plan,handle,indent=2);handle.write('\n')
print(json.dumps({'staged':True,'recovery_id':RECOVERY,'new_meta_calls':0,'committed_questions_preserved':150}))
''',timeout=30)
    with client.open_sftp() as sftp:
        for name,value in [('SCOPE.json',scope),('REVIEW_READY.json',review)]:
            with sftp.open(RUN+'/recovery/'+RECOVERY+'/'+name,'w') as handle:handle.write(json.dumps(value,indent=2)+'\n')
        for name,source in [('controller.py',CONTROLLER),('resume_runner.py',RESUME_RUNNER)]:
            with sftp.open(RUN+'/recovery/'+RECOVERY+'/'+name,'w') as handle:handle.write(definitions()+shared_source()+source)


def launch(client):
    remote_python(client,definitions()+shared_source()+GUARD+r'''
import fcntl,os,shlex,subprocess,sys
lock=(j/'.queue_launch.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
assert not (a/'controller.started.json').exists(), 'meta_schema_launch_already_claimed'
validate_scope(read(a/'SCOPE.json'),read(a/'REVIEW_READY.json'))
keys=sys.stdin.buffer.readline()+sys.stdin.buffer.readline();assert len(keys.splitlines())==2
rd,wr=os.pipe();os.write(wr,keys);os.close(wr)
write_once(a/'controller.started.json',{'recovery_id':RECOVERY,'status':'launch_intent','fresh_meta_repair_limit':1,'automatic_retry':False})
command=shlex.join([PYTHON,'-u',str(a/'controller.py')])+'; rc=$?; printf "%s\n" "$rc" > '+str(a/'controller.exitcode')+'; printf "%s\n" "$rc" > '+str(j/'controller.exitcode')+'; exit "$rc"'
try:
 with (a/'controller.log').open('xb',buffering=0) as log:
  process=subprocess.Popen(['bash','-c',command],stdin=rd,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
 record={'recovery_id':RECOVERY,'pid':process.pid,'prior_attempts_include_exit1':True,'frozen_runtime_files_edited':False,'meta_schema_overlay_declared':True}
 write_once(a/'controller.launched.json',record);(a/'controller.pid').write_text(str(process.pid));(j/'controller.pid').write_text(str(process.pid))
 print(json.dumps(record))
finally:os.close(rd)
''',timeout=30,input_bytes=(TRANSPORT_HOME/'.secrets/token_plan_api.key').read_bytes().strip()+b'\n'+(TRANSPORT_HOME/'.secrets/qwen_api.key').read_bytes().strip()+b'\n')


def status(client):
    remote_python(client,definitions()+r'''
from pathlib import Path
import json,shutil
r=Path(RUN);j=r/'jobs';a=r/'recovery'/RECOVERY
def text(path):return path.read_text().strip() if path.is_file() else None
def phase(name):
 pid=text(a/(name+'.pid'));return {'pid':pid,'alive':bool(pid and Path('/proc',pid).exists()),'exit':text(a/(name+'.exitcode'))}
value={'recovery':RECOVERY,'controller':phase('controller'),'prior_production_attempts_include_exit1':True,
 'queue':json.loads((j/'queue_status.json').read_text()) if (j/'queue_status.json').is_file() else None,
 'registered':(r/'generation/chexbench/failure_events/meta_schema_2_registration.json').is_file(),
 'datasets':{},'free_bytes':shutil.disk_usage(r).free}
for ds in DATASETS:
 g=r/'generation'/ds;s=g/'services';item=dict(phase(ds),
 saved=len(list((g/'predictions/M43-IM-GT-S49').glob('*.json'))),contexts=len(list((g/'contexts').glob('*.json'))),
 prediction_events=len(list((g/'prediction_events').glob('*.json'))),feedback=len(list((g/'feedback').glob('*.json'))),
 main_sends=len(list((s/'calls/R49-AGENT').glob('*/*/started.json'))),main_responses=len(list((s/'calls/R49-AGENT').glob('*/*/response.json'))),
 meta_sends=len(list((s/'calls/R49-META').glob('*/*/started.json'))),meta_responses=len(list((s/'calls/R49-META').glob('*/*/response.json'))),
 embeddings_sent=len(list((s/'embeddings').glob('*/started.json'))),embeddings_received=len(list((s/'embeddings').glob('*/response.json'))),
 tools=len(list((s/'tool_selections/R49-AGENT').glob('*/*.json'))),windows=len(list((g/'windows').glob('*/repo.json'))),complete=(g/'complete.json').exists())
 log=j/(ds+'.'+RECOVERY+'.log')
 if item['exit'] not in (None,'0') and log.is_file():item['failure_tail']=log.read_text(errors='replace').splitlines()[-16:]
 value['datasets'][ds]=item
if value['controller']['exit'] not in (None,'0') and (a/'controller.log').is_file():
 value['controller_failure_tail']=(a/'controller.log').read_text(errors='replace').splitlines()[-20:]
print(json.dumps(value))
''',timeout=30)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('mode',choices=('stage','launch','status'))
    args=parser.parse_args()
    with connect() as client:globals()[args.mode](client)
