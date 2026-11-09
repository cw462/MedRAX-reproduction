RUN='[REDACTED]'
CODE='[REDACTED]'
PYTHON='[REDACTED]'
RECOVERY='phrase_guard_1'
POLICY_ID='maira_unclosed_tag_eos_guard_v1'
ARM='M43-IM-GT-S49'
TOOL='xray_phrase_grounding'
QID='chexbench_slake_0053'
OLD_KEY='b615fd34f038d096aaa2681413f80d45cd25acf9de235ec65ff029dbec90be56'
SUFFIX='_phrase_guard_1'
DIAGNOSTIC='[REDACTED]'
DATASETS=('chexbench', 'slake', 'vqarad')
COUNTS={'chexbench': 618, 'slake': 114, 'vqarad': 116}
import json
from pathlib import Path
def read(path):return json.loads(Path(path).read_text())

def write_once(path,value):
    import os,uuid
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    if path.is_file():
        if read(path)!=value:raise ValueError('immutable_phrase_guard_record_changed')
        return
    temporary=path.with_name('.'+path.name+'.'+uuid.uuid4().hex+'.tmp')
    try:
        with temporary.open('x') as handle:json.dump(value,handle,ensure_ascii=False,indent=2);handle.write('\n');handle.flush();os.fsync(handle.fileno())
        os.link(temporary,path)
    finally:temporary.unlink(missing_ok=True)

def validate_scope(scope,review):
    expected={'recovery_id':RECOVERY,'uses_existing_r49_authorization':True,'new_user_approval_claimed':False,
      'activation_boundary_chexbench':168,'known_failed_guarded_retry_limit':1,'all_new_physical_maira_calls':True,
      'generation_policy_changed':True,'same_generation_settings':False,'clinical_prompt_changed':False,'parser_changed':False,
      'max_new_tokens':300,'extra_agent_calls_for_repair':0,'extra_meta_calls_for_repair':0,'extra_embedding_calls_for_repair':0,
      'automatic_tool_retry':False,'modify_completed_records':False,'retain_all_prior_overlays':True,'diagnostic_result_reused':False}
    if any(scope.get(key)!=value for key,value in expected.items()) or not scope.get('authorization_basis'):
        raise ValueError('actual_phrase_guard_scope_required')
    if review.get('recovery_id')!=RECOVERY or review.get('verdict')!='ready' or review.get('scope_complete') is not True or not review.get('trace'):
        raise ValueError('actual_new_phrase_guard_review_required')

def ensure_amendment(stream,recovery_root,dataset):
    from datetime import datetime,timezone
    stream,recovery_root=Path(stream),Path(recovery_root);path=stream/'failure_events/phrase_guard_1_amendment.json'
    fixed={'schema':'r49_phrase_guard_amendment_v1','recovery_id':RECOVERY,'dataset':dataset,'arm':ARM,'policy_id':POLICY_ID,
      'activation_boundary_chexbench':168,'activation_committed_questions':168 if dataset=='chexbench' else 0,
      'scope':'all_new_physical_MAIRA_calls_after_activation','token_ids':{'obj_start':32000,'obj_end':32001,'box_start':32202,'box_end':32203,'eos':2},
      'max_new_tokens':300,'generation_policy_changed':True,'same_generation_settings':False,'legacy_healthy_cache_reuse':True,
      'automatic_retry':False,'clinical_prompt_changed':False,'parser_changed':False,'diagnostic_result_reused':False,
      'cache_naming':'unchanged_legacy_identity_and_key_plus_explicit_policy_suffix; image_fingerprint_is_existing_naming_not_a_validation_gate'}
    if path.is_file():
        record=read(path)
        if any(record.get(key)!=value for key,value in fixed.items()):raise ValueError('phrase_guard_amendment_changed')
    else:
        record={**fixed,'legacy_cache_keys_at_activation':sorted(p.name for p in (stream/'services/tool_cache').glob('*') if p.is_dir()),
          'protected_existing_selections':sorted(str(p.relative_to(stream)) for p in (stream/'services/tool_selections').glob('*/*/*.json')
            if not (dataset=='chexbench' and p.parent.name==QID and p.name=='1.json')),'utc':datetime.now(timezone.utc).isoformat()}
        write_once(path,record)
    write_once(recovery_root/'amendments'/(dataset+'.json'),record)
    return record

def policy_observe(self,spec,args,image,identity,folder,recovery_root):
    """A fresh suffix cache uses exactly one original-settings worker plus the declared EOS guard."""
    import os,subprocess,time,shutil
    from datetime import datetime,timezone
    folder=Path(folder);saved=folder/'result.json'
    if saved.is_file():return read(saved),True
    if (folder/'started.json').is_file():return {'status':'started_unknown','observation':None,'automatic_retry':False},False
    memory=int(subprocess.check_output(['nvidia-smi','--id=1','--query-gpu=memory.used','--format=csv,noheader,nounits'],text=True).strip())
    if memory>=500:raise RuntimeError('GPU1_busy_no_tool_started')
    if shutil.disk_usage(Path(RUN)).free<=3*1024**3:raise RuntimeError('insufficient_free_disk_no_tool_started')
    folder.mkdir(parents=True,exist_ok=True)
    request={'tool':TOOL,'backend':spec['backend'],'args':args,'image':str(image),'artifact_dir':str(folder/'artifacts'),'runtime':self.runtime['backend_config']}
    write_once(folder/'request.json',request)
    write_once(folder/'started.json',{'identity':identity,'policy_id':POLICY_ID,'generation_policy_changed':True,'automatic_retry':False,
      'utc':datetime.now(timezone.utc).isoformat()})
    command=[spec['python'],'-u',str(Path(recovery_root)/'maira_guard_worker.py')]
    if spec.get('cpu_affinity') is not None:command=['taskset','-c',str(spec['cpu_affinity']),*command]
    env=dict(os.environ,CUDA_VISIBLE_DEVICES=spec.get('gpu','1'),MPLBACKEND='Agg',TOKENIZERS_PARALLELISM='false');env.update(spec.get('worker_env',{}))
    for key in list(env):
        if key.endswith(('_API_KEY','_AUTH_TOKEN')) or key in ('ANTHROPIC_AUTH_TOKEN','HF_TOKEN'):env.pop(key)
    env.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1');tick=time.monotonic()
    try:
        completed=subprocess.run(command,input=json.dumps(request),capture_output=True,text=True,env=env,timeout=spec.get('timeout',600))
        (folder/'backend.stderr.log').write_text(completed.stderr);(folder/'backend.stdout.log').write_text(completed.stdout)
        if completed.returncode:raise RuntimeError('policy_worker_exit_'+str(completed.returncode))
        result=json.loads(completed.stdout.split('CXR_VQA_RESULT=')[-1])
    except Exception as error:
        stderr=getattr(error,'stderr',None)
        if stderr is not None and not (folder/'backend.stderr.log').exists():
            (folder/'backend.stderr.log').write_text(stderr.decode(errors='replace') if isinstance(stderr,bytes) else stderr)
        result={'status':'failed','observation':None,'error_type':type(error).__name__,'error':str(error),'automatic_retry':False}
    result.update(elapsed_s=time.monotonic()-tick,backend=spec['backend'],identity=identity,utc=datetime.now(timezone.utc).isoformat())
    write_once(saved,result)
    return result,False

def commit_known_retry(stream,recovery_root,original,active,plan):
    import os,uuid
    from datetime import datetime,timezone
    stream,recovery_root=Path(stream),Path(recovery_root)
    path=stream/'failure_events/phrase_guard_1_registration.json';existing=read(path) if path.is_file() else {}
    archive=stream/'failure_events/phrase_guard_1_original_selection.json'
    if read(archive)!=original or read(recovery_root/'original_selection.json')!=original:
        raise ValueError('original_phrase_failure_archive_changed')
    registration={'schema':'r49_registered_phrase_guard_retry_v1','recovery_id':RECOVERY,'dataset':'chexbench','arm':ARM,
      'question_id':QID,'question_ordinal':169,'logical_tool_ordinal':1,'tool':TOOL,'backend':TOOL,
      'original_cache_key':OLD_KEY,'retry_cache_key':OLD_KEY+SUFFIX,'original_selection_archive_relative':'failure_events/phrase_guard_1_original_selection.json',
      'identity':original['identity'],'canonical_original_image':original['original_image'],'original_selection':original,'active_selection':active,
      'policy_id':POLICY_ID,'generation_policy_changed':True,'same_generation_settings':False,'diagnostic':plan['diagnostic'],
      'guarded_production_retry_limit':1,'automatic_retry':False,'status':'healthy_guarded_production_retry_registered',
      'utc':existing.get('utc') or datetime.now(timezone.utc).isoformat()}
    write_once(path,registration);write_once(recovery_root/'registration.json',registration)
    selection=stream/'services/tool_selections/R49-AGENT'/QID/'1.json'
    if read(selection)==active:return
    if read(selection)!=original:raise ValueError('active_phrase_selection_not_original_failure')
    temporary=selection.with_name('.'+selection.name+'.'+uuid.uuid4().hex+'.tmp')
    try:
        with temporary.open('x') as handle:json.dump(active,handle,ensure_ascii=False,indent=2);handle.write('\n');handle.flush();os.fsync(handle.fileno())
        os.replace(temporary,selection)
    finally:temporary.unlink(missing_ok=True)

def guarded_tools_call(original_call,services_root,recovery_root,dataset,plan):
    """Preserve old selections/caches, and version only new physical MAIRA generation."""
    import hashlib
    services_root,recovery_root=Path(services_root).resolve(),Path(recovery_root)
    def call(self,row,action,arm,ordinal):
        if self.out.resolve()!=services_root or action['tool']!=TOOL:return original_call(self,row,action,arm,ordinal)
        from cxr_image_memory_r44 import tool_failure_reason
        selection=self.out/'tool_selections'/arm/row['question_id']/(str(ordinal)+'.json')
        known=dataset=='chexbench' and row['question_id']==QID and arm=='R49-AGENT' and ordinal==1
        old=read(selection) if selection.is_file() else None
        if old is not None and (not known or tool_failure_reason(old) is None):return old
        spec=self.runtime['tools'][TOOL];args=action.get('args',{});index=action.get('image_index',1)
        if type(index) is not int or not 1<=index<=len(row['images']):raise ValueError('invalid_bound_image_index')
        image=(self.data_root/row['images'][index-1]).resolve()
        if not image.is_relative_to(self.data_root.resolve()):raise ValueError('invalid_bound_image')
        if spec['gpu']!='1' or spec['backend']!=TOOL:raise ValueError('original_maira_runtime_binding_changed')
        if known:
            if (old!=plan['original_selection'] or old['cache_key']!=OLD_KEY or args!=old['identity']['args'] or
                spec.get('revision')!=old['identity'].get('revision') or str(image)!=old['original_image']):
                raise ValueError('known_phrase_failure_identity_changed')
            identity=old['identity'];key=OLD_KEY
        else:
            # Exact frozen Tools.call cache naming; not an added integrity check.
            identity={'backend':spec['backend'],'revision':spec.get('revision'),'image':hashlib.sha256(image.read_bytes()).hexdigest(),'args':args}
            key=hashlib.sha256(json.dumps(identity,sort_keys=True).encode()).hexdigest()
        legacy=self.out/'tool_cache'/key/'result.json'
        result=None;hit=False;source=None
        if not known and legacy.is_file():
            result=read(legacy);hit=True;source='legacy_healthy_cache'
            if tool_failure_reason(result):
                if key==OLD_KEY and (services_root.parent/'failure_events/phrase_guard_1_registration.json').is_file():result=None
                else:raise RuntimeError('unregistered_legacy_maira_failure_no_retry')
        elif not known and (legacy.parent/'started.json').exists():raise RuntimeError('unknown_legacy_maira_send_no_retry')
        actual_key=key
        if result is None:
            actual_key=key+SUFFIX
            result,hit=policy_observe(self,spec,args,image,identity,self.out/'tool_cache'/actual_key,recovery_root)
            source='guarded_cache' if hit else 'guarded_new'
        active={**result,'tool':TOOL,'cache_key':actual_key,'cache_hit':hit,
          'generation_policy':{'policy_id':POLICY_ID if source!='legacy_healthy_cache' else 'legacy_original_maira',
            'source':source,'generation_policy_changed':source!='legacy_healthy_cache','same_generation_settings':source=='legacy_healthy_cache',
            'applied_actual_invocation':source=='guarded_new' and bool(result.get('generation_policy_evidence')),'bound_original_image':str(image)}}
        if len(row['images'])>1:active['image_index']=index
        if source!='legacy_healthy_cache' and tool_failure_reason(active) is None:
            evidence=result.get('generation_policy_evidence') or {}
            if (evidence.get('policy_id')!=POLICY_ID or evidence.get('capture_complete') is not True or
                evidence.get('eos_terminated') is not True or evidence.get('policy_healthy') is not True or
                evidence.get('final_generated_token_ids')!=[2] or len(evidence.get('calls',[]))!=1):
                raise RuntimeError('guarded_maira_policy_health_proof_missing_stop')
        if known:
            if tool_failure_reason(active):raise RuntimeError('known_guarded_phrase_retry_failed_stop_no_retry')
            policy=result.get('generation_policy_evidence')
            if not policy or policy.get('policy_id')!=POLICY_ID or policy.get('capture_complete') is not True:
                raise RuntimeError('guarded_phrase_retry_missing_actual_policy_evidence')
            commit_known_retry(services_root.parent,recovery_root,old,active,plan)
        else:write_once(selection,active)
        return active
    return call


import argparse,runpy,sys
parser=argparse.ArgumentParser();parser.add_argument('--dataset',choices=DATASETS,required=True);args=parser.parse_args()
sys.path.insert(0,str(Path(CODE)/'experiments'))
import run_cxr_vqa_toolsets as base
a=Path(RUN)/'recovery'/RECOVERY;validate_scope(read(a/'SCOPE.json'),read(a/'REVIEW_READY.json'))
stream=Path(RUN)/'generation'/args.dataset
ensure_amendment(stream,a,args.dataset)
base.Tools.call=guarded_tools_call(base.Tools.call,stream/'services',a,args.dataset,read(a/'plan.json'))
sys.argv=[str(Path(RUN)/'recovery/embedding_arrearage_1/resume_runner.py'),'--dataset',args.dataset]
runpy.run_path(sys.argv[0],run_name='__main__')
