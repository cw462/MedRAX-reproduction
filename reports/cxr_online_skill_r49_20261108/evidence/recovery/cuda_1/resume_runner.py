RUN='[REDACTED]'
ROOT='[REDACTED]'
CODE='[REDACTED]'
PYTHON='[REDACTED]'
RECOVERY='cuda_1'
QID='chexbench_rad_restruct_0163'
ARM='M43-IM-GT-S49'
EXPECTED_PROMPT='Are there any signs of pleural effusion, pneumothorax, or pleural thickening in the image?'
DATA={'chexbench': '[REDACTED]', 'slake': '[REDACTED]', 'vqarad': '[REDACTED]'}
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
        if json.loads(path.read_text())!=value:raise ValueError('immutable_recovery_record_changed:'+path.name)
        return
    temporary=path.with_name('.'+path.name+'.'+uuid.uuid4().hex+'.tmp')
    try:
        with temporary.open('x') as handle:json.dump(value,handle,ensure_ascii=False,indent=2);handle.write('\n');handle.flush();os.fsync(handle.fileno())
        os.link(temporary,path)
    finally:temporary.unlink(missing_ok=True)

def validate_scope(scope,review):
    expected={'recovery_id':RECOVERY,'uses_existing_r49_authorization':True,'new_user_approval_claimed':False,
      'production_tool_retry_limit':1,'new_diagnostic_invocations':0,'new_control_arms':0,
      'retry_current_question_main_plan':False,'technical_null_fill':False,'modify_completed_predictions':False,
      'diagnostic_result_reused':False,'resume_original_stream':True,'registered_identity_cache_overlay':True,
      'historical_attempt_accounting':True}
    if any(scope.get(key)!=value for key,value in expected.items()) or not scope.get('authorization_basis'):
        raise ValueError('explicit_one_case_operational_scope_required')
    if review.get('recovery_id')!=RECOVERY or review.get('verdict')!='ready' or review.get('scope_complete') is not True or not review.get('trace'):
        raise ValueError('actual_operational_review_required')

def commit_healthy_retry(services,recovery,original,result,diagnostic):
    """Only a closed healthy production attempt may replace the active selection."""
    import copy,os,shutil,uuid
    from datetime import datetime,timezone
    from cxr_image_memory_r44 import tool_failure_reason
    services,recovery=Path(services),Path(recovery)
    if tool_failure_reason(result) or result.get('diagnostic_only'):
        raise RuntimeError('production_retry_unhealthy_stop')
    oldkey=original['cache_key'];newkey=oldkey+'_cuda_1'
    if result.get('identity')!=original.get('identity') or result.get('original_image')!=original.get('original_image'):
        raise ValueError('production_retry_identity_changed')
    cache=services/'tool_cache'/newkey
    if not (cache/'started.json').is_file() or json.loads((cache/'result.json').read_text())!=result:
        raise ValueError('production_retry_not_closed')
    selected=services/'tool_selections/R49-AGENT'/QID/'1.json'
    if json.loads(selected.read_text())!=original:raise ValueError('original_active_selection_changed')
    if not tool_failure_reason(original):raise ValueError('original_must_be_actual_failure')
    oldcache=services/'tool_cache'/oldkey
    if not (oldcache/'started.json').is_file() or not (oldcache/'result.json').is_file():raise ValueError('original_failure_not_closed')
    if any(original.get(key)!=value for key,value in json.loads((oldcache/'result.json').read_text()).items()):
        raise ValueError('original_selection_cache_mismatch')
    provenance={'recovery_id':'cuda_1','original_cache_key':oldkey,'retry_cache_key':newkey,
                'original_failure_preserved':True,'production_retry':True}
    healthy={**copy.deepcopy(result),'tool':'chest_xray_expert','cache_hit':False,'cache_key':newkey,'cuda_recovery':provenance}
    if 'image_index' in original:healthy['image_index']=original['image_index']
    recovery.mkdir(parents=True,exist_ok=True)
    archive=recovery/'original_selection.json'
    with selected.open('rb') as source,archive.open('xb') as target:shutil.copyfileobj(source,target)
    failure_events=services.parent/'failure_events';failure_events.mkdir(exist_ok=True)
    archive_relative='failure_events/cuda_1_original_selection.json'
    with selected.open('rb') as source,(services.parent/archive_relative).open('xb') as target:shutil.copyfileobj(source,target)
    registration={'schema':'r49_registered_cuda_retry_v1','recovery_id':'cuda_1','dataset':'chexbench','arm':ARM,
      'question_id':QID,'logical_ordinal':1,'tool':'chest_xray_expert','backend':original['backend'],
      'revision':original['identity']['revision'],'original_image':original['original_image'],
      'args':copy.deepcopy(original['identity']['args']),'identity':copy.deepcopy(original['identity']),
      'original_cache_key':oldkey,'retry_cache_key':newkey,'original_selection':copy.deepcopy(original),
      'retry_selection':healthy,'original_selection_archive':str(archive),
      'original_selection_archive_relative':archive_relative,'status':'healthy_production_retry_registered',
      'production_debug_flags':{'CUDA_LAUNCH_BLOCKING':None,'TORCH_SHOW_CPP_STACKTRACES':None},
      'new_tool_attempts':1,'main_api_calls':0,'diagnostic_result_reused':False,'automatic_retry':False,
      'diagnostic':copy.deepcopy(diagnostic),'utc':datetime.now(timezone.utc).isoformat()}
    write_once(failure_events/'cuda_1_registration.json',registration)
    write_once(recovery/'registration.json',registration)
    temporary=selected.with_name('.1.cuda_1.'+uuid.uuid4().hex+'.tmp')
    try:
        with temporary.open('x') as handle:json.dump(healthy,handle,ensure_ascii=False,indent=2);handle.write('\n');handle.flush();os.fsync(handle.fileno())
        os.replace(temporary,selected)
    finally:temporary.unlink(missing_ok=True)
    return registration

def registered_call_overlay(base,original_call,registration,services_root):
    """Only this exact registered identity can reuse the new healthy cache."""
    from cxr_image_memory_r44 import tool_failure_reason
    services_root=Path(services_root).resolve()
    def call(self,row,action,arm,ordinal):
        if self.out.resolve()!=services_root or arm!='R49-AGENT' or action.get('tool')!=registration['tool']:
            return original_call(self,row,action,arm,ordinal)
        spec=self.runtime['tools'][action['tool']];index=action.get('image_index',1)
        if type(index) is not int or not 1<=index<=len(row['images']):
            return original_call(self,row,action,arm,ordinal)
        image=(self.data_root/row['images'][index-1]).resolve()
        if (not image.is_relative_to(self.data_root.resolve()) or str(image)!=registration['original_image']
                or spec['backend']!=registration['backend'] or spec.get('revision')!=registration['revision']
                or action.get('args',{})!=registration['args']):
            return original_call(self,row,action,arm,ordinal)
        selected=self.out/'tool_selections'/arm/row['question_id']/(str(ordinal)+'.json')
        if selected.exists():return base.read(selected)
        backend=base.read(self.out/'tool_cache'/registration['retry_cache_key']/'result.json')
        if tool_failure_reason(backend) or backend.get('identity')!=registration['identity']:
            raise RuntimeError('registered_retry_cache_no_longer_healthy')
        value={**backend,'tool':action['tool'],'cache_hit':True,'cache_key':registration['retry_cache_key'],
               'cuda_recovery':registration['retry_selection']['cuda_recovery']}
        if len(row['images'])>1:value['image_index']=index
        base.save(selected,value)
        return value
    return call


import runpy,sys
sys.path.insert(0,str(Path(CODE)/'experiments'))
import run_cxr_vqa_toolsets as base
g=Path(RUN)/'generation/chexbench'
registration=read(g/'failure_events/cuda_1_registration.json')
assert registration['schema']=='r49_registered_cuda_retry_v1' and registration['question_id']==QID
assert registration['status']=='healthy_production_retry_registered'
original_call=base.Tools.call
base.Tools.call=registered_call_overlay(base,original_call,registration,g/'services')
sys.argv=PROGRAMS['chexbench'][2:]+['--execute','--api-key-stdin']
runpy.run_path(sys.argv[0],run_name='__main__')
