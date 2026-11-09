RUN='[REDACTED]'
CODE='[REDACTED]'
PYTHON='[REDACTED]'
RECOVERY='meta_schema_1'
ARM='M43-IM-GT-S49'
SOURCE_QID='chexbench_slake_0004'
SOURCE_EVENT='mutation_chexbench_slake_0004'
REPAIR_EVENT='mutation_chexbench_slake_0004_schema_1'
ALLOWED_SECTIONS=('name', 'description', 'applicable_conditions', 'required_tools', 'risk_level', 'core_action')
REPAIR_INSTRUCTION='\n\nONE-CASE SCHEMA CLARIFICATION; no new source evidence is supplied.\nThe preceding mutation used patch_section="c", which names the whole content container and is not a permitted single-field patch.\nFor PATCH, retain exactly this patch_target_id: {target_json}.\npatch_section must be exactly one of: name, description, applicable_conditions, required_tools, risk_level, core_action.\nReturn the original PATCH schema for one such field; do not replace the whole content container or change branch, task_category or tool_name.\nUse only the same original source payload. Do not add clinical facts or consult another case or future feedback.\nIf the source does not support a valid single-field patch, explicitly return {{"operation":"NONE"}}.\nReturn one JSON object with operation PATCH or NONE; do not produce CREATE, another target, or a patch to a different scope.\n'
DATASETS=('chexbench', 'slake', 'vqarad')
COUNTS={'chexbench': 618, 'slake': 114, 'vqarad': 116}
PROGRAMS={'chexbench': ['[REDACTED]', '-u', '[REDACTED]', '--config', '[REDACTED]', '--data', '[REDACTED]', '--reference-dir', '[REDACTED]', '--out', '[REDACTED]', '--dataset', 'chexbench', '--expect-questions', '618', '--embedding-model', 'text-embedding-v4', '--embedding-base-url', 'https://dashscope.aliyuncs.com/compatible-mode/v1', '--order-manifest', '[REDACTED]'], 'slake': ['[REDACTED]', '-u', '[REDACTED]', '--config', '[REDACTED]', '--data', '[REDACTED]', '--reference-dir', '[REDACTED]', '--out', '[REDACTED]', '--dataset', 'slake', '--expect-questions', '114', '--embedding-model', 'text-embedding-v4', '--embedding-base-url', 'https://dashscope.aliyuncs.com/compatible-mode/v1'], 'vqarad': ['[REDACTED]', '-u', '[REDACTED]', '--config', '[REDACTED]', '--data', '[REDACTED]', '--reference-dir', '[REDACTED]', '--out', '[REDACTED]', '--dataset', 'vqarad', '--expect-questions', '116', '--embedding-model', 'text-embedding-v4', '--embedding-base-url', 'https://dashscope.aliyuncs.com/compatible-mode/v1']}
import json
from pathlib import Path
def read(path):return json.loads(Path(path).read_text())
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
      'target_unchanged':True,'automatic_invalid_to_none':False,'keep_cuda_cache_overlay':True}
    if any(scope.get(key)!=value for key,value in expected.items()) or not scope.get('authorization_basis'):
        raise ValueError('exact_meta_schema_operational_scope_required')
    if review.get('recovery_id')!=RECOVERY or review.get('verdict')!='ready' or review.get('scope_complete') is not True or not review.get('trace'):
        raise ValueError('actual_meta_schema_review_required')

def exact_meta_overlay(original_meta,services_root,recovery_root,target):
    """The original invalid reply is preserved; only this event gains one new call."""
    import copy
    from datetime import datetime,timezone
    services_root,recovery_root=Path(services_root).resolve(),Path(recovery_root)
    def meta(self,event,system,payload,image_row=None,data=None):
        if event!=SOURCE_EVENT or self.out.resolve()!=services_root:
            return original_meta(self,event,system,payload,image_row,data)
        if image_row is not None:raise ValueError('schema_repair_extra_image_forbidden')
        old_folder=self.out/'calls/R49-META'/SOURCE_EVENT/'1'
        if any(not (old_folder/name).is_file() for name in ('request.json','started.json','response.json','result.json')):
            raise RuntimeError('original_meta_not_closed_no_reissue')
        # Calling the original method retains its cached-request semantic check.
        invalid=original_meta(self,event,system,payload,image_row,data)
        if (invalid.get('operation')!='PATCH' or invalid.get('patch_section')!='c'
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
        registration_path=self.out.parent/'failure_events/meta_schema_1_registration.json'
        registered=json.loads(registration_path.read_text()) if registration_path.is_file() else None
        recorded_at=registered['utc'] if registered else datetime.now(timezone.utc).isoformat()
        record={'schema':'r49_registered_meta_schema_repair_v1','recovery_id':RECOVERY,'dataset':'chexbench','arm':ARM,
          'source_question_id':SOURCE_QID,'source_event':SOURCE_EVENT,'repair_event':REPAIR_EVENT,'window_index':3,
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
 command=[PYTHON,'-u',str(a/'resume_runner.py')] if ds=='chexbench' else PROGRAMS[ds]+['--execute','--api-key-stdin']
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
state({'state':'all_three_datasets_exited_zero_after_registered_meta_schema_repair','datasets':list(DATASETS)})
