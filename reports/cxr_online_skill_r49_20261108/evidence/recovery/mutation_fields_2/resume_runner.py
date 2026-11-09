RUN='[REDACTED]'
CODE='[REDACTED]'
PYTHON='[REDACTED]'
RECOVERY='mutation_fields_2'
ARM='M43-IM-GT-S49'
SOURCE_QID='chexbench_slake_0013'
SOURCE_EVENT='mutation_chexbench_slake_0013'
REPAIR_EVENT='mutation_chexbench_slake_0013_schema_2'
ALLOWED_SECTIONS=('name', 'description', 'applicable_conditions', 'required_tools', 'risk_level', 'core_action')
REPAIR_INSTRUCTION='\n\nONE-CASE SCHEMA CLARIFICATION; no new source evidence is supplied.\nThe preceding mutation used patch_section="content", which names the whole content container and is not a permitted single-field patch.\nFor PATCH, retain exactly this patch_target_id: {target_json}.\npatch_section must be exactly one of: name, description, applicable_conditions, required_tools, risk_level, core_action.\nReturn the original PATCH schema for one such field; do not replace the whole content container or change branch, task_category or tool_name.\nUse only the same original source payload. Do not add clinical facts or consult another case or future feedback.\nIf the source does not support a valid single-field patch, explicitly return {{"operation":"NONE"}}.\nReturn one JSON object with operation PATCH or NONE; do not produce CREATE, another target, or a patch to a different scope.\n'
FIELDS_CLARIFICATION='\n\nEXPLICIT MUTATION FIELD CONTRACT; no new clinical information or source evidence.\nFor operation PATCH, patch_section must be exactly one of: name, description, applicable_conditions, required_tools, risk_level, core_action.\nThe names "c" and "content" denote the whole content container and are not permitted patch_section values.\nA PATCH changes one such field of an eligible target already present in the supplied window snapshot. Do not change branch, task_category or tool_name.\nKeep the original CREATE, PATCH and NONE meanings and the original source-evidence requirements. This clarification introduces no new clinical rule or permission to infer facts.\n'
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
