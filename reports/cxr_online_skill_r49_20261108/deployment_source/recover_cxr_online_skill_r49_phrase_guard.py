"""Declared MAIRA EOS-policy amendment; one known-failure retry, no automatic retries."""
import argparse
import inspect
import json
from pathlib import Path

import diagnose_r49_phrase_grounding_once as observation
from deploy_cxr_online_skill_r49 import CODE, COUNTS, DATASETS, PREP, PYTHON, ROOT, RUN, TRANSPORT_HOME, connect, remote_python

RECOVERY='phrase_guard_1'
POLICY_ID='maira_unclosed_tag_eos_guard_v1'
ARM='M43-IM-GT-S49'
TOOL='xray_phrase_grounding'
QID='chexbench_slake_0053'
OLD_KEY='b615fd34f038d096aaa2681413f80d45cd25acf9de235ec65ff029dbec90be56'
SUFFIX='_phrase_guard_1'
DIAGNOSTIC=observation.ATTEMPT
SCOPE=PREP/'PHRASE_GUARD_RECOVERY_SCOPE.json'
REVIEW=PREP/'PHRASE_GUARD_RECOVERY_REVIEW_READY.json'
POLICY_SOURCE=Path(__file__).with_name('r49_phrase_grounding_eos_guard_candidate.py')


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


GUARD=r'''
r=Path(RUN);j=r/'jobs';g=r/'generation/chexbench';s=g/'services';a=r/'recovery'/RECOVERY
for name in ('controller','chexbench'):
 pid=(j/(name+'.pid')).read_text().strip();assert not Path('/proc',pid).exists(), 'R49_process_active'
 assert (j/(name+'.exitcode')).read_text().strip()=='1'
assert (g/'generation.exitcode').read_text().strip()=='1'
assert (j/'chexbench.embedding_arrearage_1.log').read_text(errors='replace').rstrip().splitlines()[-1]=='RuntimeError: tool_failure_stop_no_automatic_retry:nested_backend_error'
ids=[row['question_id'] for row in read(g/'manifest.json')['inputs']];assert len(ids)==618 and ids[168]==QID
for name in ('predictions/M43-IM-GT-S49','prediction_events','feedback','steps'):
 assert {p.stem for p in (g/name).glob('*.json')}==set(ids[:168])
assert {p.stem for p in (g/'contexts').glob('*.json')}==set(ids[:169])
assert {p.parent.name for p in (g/'windows').glob('*/repo.json')}=={'0000','0001','0002','0003','0004'}
for arm,count in [('R49-AGENT',412),('R49-META',148)]:
 starts=list((s/'calls'/arm).glob('*/*/started.json'));assert len(starts)==count
 for start in starts:
  assert (start.parent/'response.json').is_file() and read(start.parent/'result.json').get('response_received') is True
assert len(list((s/'embeddings').glob('*/started.json')))==78 and len(list((s/'embeddings').glob('*/response.json')))==77
assert read(g/'failure_events/embedding_arrearage_1_registration.json')['status']=='healthy_embedding_retry_registered'
assert len(list((s/'tool_selections/R49-AGENT').glob('*/*.json')))==232
selection=s/'tool_selections/R49-AGENT'/QID/'1.json';failed=read(selection)
assert failed['tool']==TOOL and failed['backend']==TOOL and failed['cache_key']==OLD_KEY
assert failed['status']=='completed' and failed['observation'][0]['error']=='' and failed['observation'][1]['analysis_status']=='failed'
assert not (s/'tool_cache'/(OLD_KEY+SUFFIX)).exists()
assert not (g/'failure_events/phrase_guard_1_registration.json').exists()
assert (r/'recovery/embedding_arrearage_1/resume_runner.py').is_file()
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
state({'state':'all_three_datasets_exited_zero_after_phrase_guard_recovery','datasets':list(DATASETS)})
'''


RESUME_RUNNER=r'''
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
'''


WORKER=r'''
import contextlib,os,socket,sys,time,traceback
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).parent));sys.path.insert(0,str(Path(CODE)/'experiments'))
from eos_guard_policy import install_eos_guard
request=json.load(sys.stdin);folder=Path(request['artifact_dir']);folder.mkdir(parents=True,exist_ok=True)
assert request['tool']==TOOL and request['backend']==TOOL and os.environ.get('CUDA_VISIBLE_DEVICES')=='1'
assert read(Path(CODE)/'configs/cxr_vqa_tool_worker_gpu.json')['cuda_visible_devices']=='1'
validate_scope(read(Path(__file__).parent/'SCOPE.json'),read(Path(__file__).parent/'REVIEW_READY.json'))
captures={'generations':[],'decodes':[],'conversion_inputs':[],'swallowed_exceptions':[],'observability_errors':[]};policy={};factory=[];events=[];began=time.monotonic()
def deny_network(*args,**kwargs):raise RuntimeError('guarded_local_tool_network_forbidden')
with contextlib.ExitStack() as stack:
 stack.enter_context(patch.object(socket.socket,'connect',deny_network));stack.enter_context(patch.object(socket.socket,'connect_ex',deny_network))
 stack.enter_context(patch.object(socket,'create_connection',deny_network))
 import requests
 stack.enter_context(patch.object(requests.sessions.Session,'request',deny_network))
 import cxr_vqa_tool_worker as worker
 import maira_smoke as smoke
 from cxr_image_memory_r44 import tool_failure_reason
 original_factory=smoke.create_maira_tool
 def create(*args,**kwargs):
  if factory:raise RuntimeError('second_guarded_tool_factory_forbidden')
  tool,provenance=original_factory(*args,**kwargs)
  factory.append({'model_revision':provenance['assets'][0]['revision'],'source_commit':provenance['source']['commit'],
    'cuda_visible_devices':os.environ['CUDA_VISIBLE_DEVICES'],'model_device':str(tool.model.device),'model_dtype':str(tool.model.dtype),
    'is_loaded_in_8bit':bool(getattr(tool.model,'is_loaded_in_8bit',False))})
  assert factory[-1]['model_revision']=='795a2b1cd4a310624b4e3d14b5a23e41fd273deb'
  stack.enter_context(capture_tool(tool,captures));stack.enter_context(install_eos_guard(tool,policy))
  return tool,provenance
 stack.enter_context(patch.object(smoke,'create_maira_tool',create))
 with contextlib.redirect_stdout(sys.stderr):
  try:
   with worker.inference_events(request,events):result=worker.execute(request)
  except Exception as error:
   traceback.print_exc(file=sys.stderr)
   write_once(folder/'outer_exception.json',{'type':type(error).__name__,'repr':repr(error),'traceback':traceback.format_exc()})
   result={'status':'failed','observation':None,'error_type':type(error).__name__,'error':str(error)}
 result.update(actual_model_events=events,cuda_visible_devices='1',adapter_revision='cxr-vqa-existing-snapshot-binding-3')
 failure=tool_failure_reason(result)
 write_once(folder/'original_worker_result.json',result)
for name,value in [('generation_tokens.json',captures['generations']),('decode.json',captures['decodes']),('conversion_inputs.json',captures['conversion_inputs']),
                   ('swallowed_exceptions.json',captures['swallowed_exceptions']),('observability_errors.json',captures['observability_errors']),('factory.json',factory),('eos_guard.json',policy)]:
 write_once(folder/name,value)
capture=capture_state(captures,factory,failure)
final_ids=[x['generated_token_ids'][0][-1] if x.get('generated_token_ids') and x['generated_token_ids'][0] else None for x in captures['generations']]
eos_terminated=final_ids==[2]
policy_healthy=not failure and capture['capture_complete'] and eos_terminated and len(policy.get('calls',[]))==1
evidence={**policy,**capture,'generation_policy_changed':True,'same_generation_settings':False,'factory':factory,'cuda_visible_devices':'1',
 'final_generated_token_ids':final_ids,'eos_terminated':eos_terminated,'policy_healthy':policy_healthy,
 'status':'completed_healthy' if policy_healthy else 'failed',
 'elapsed_s':time.monotonic()-began,'clinical_prompt_changed':False,'parser_changed':False,'diagnostic_result_reused':False}
result['generation_policy_evidence']=evidence
if not policy_healthy and result['status']=='completed':
 result['status']='failed';result['error']='guard_policy_incomplete_or_non_eos_termination';result['observation']=None
write_once(folder/'policy_status.json',{'policy_id':POLICY_ID,**capture,'status':'completed_healthy' if policy_healthy else 'failed',
 'health_failure_reason':failure,'eos_terminated':eos_terminated,'policy_healthy':policy_healthy,
 'generation_policy_changed':True,'same_generation_settings':False})
print('CXR_VQA_RESULT='+json.dumps(result,ensure_ascii=False))
'''


def definitions():
    values=dict(RUN=RUN,CODE=CODE,PYTHON=PYTHON,RECOVERY=RECOVERY,POLICY_ID=POLICY_ID,ARM=ARM,TOOL=TOOL,QID=QID,
      OLD_KEY=OLD_KEY,SUFFIX=SUFFIX,DIAGNOSTIC=DIAGNOSTIC,DATASETS=DATASETS,COUNTS=COUNTS)
    return '\n'.join(key+'='+repr(value) for key,value in values.items())+'\n'


def shared_source():
    return 'import json\nfrom pathlib import Path\n'+'\n'.join(inspect.getsource(fn) for fn in
      (read,write_once,validate_scope,ensure_amendment,policy_observe,commit_known_retry,guarded_tools_call))+'\n'


def stage_payload():
    return definitions()+shared_source()+GUARD+r'''
import shutil
diagnostic=Path(DIAGNOSTIC);diag=read(diagnostic/'status.json')
assert (diagnostic/'exitcode').read_text().strip()=='1' and diag['capture_complete'] is True
assert diag['tool_invocations']==1 and all(diag[key]==0 for key in ('main_api_calls','meta_api_calls','embedding_api_calls'))
assert shutil.disk_usage(r).free>3*1024**3
assert not a.exists(), 'phrase_guard_already_staged_inspect_state'
a.mkdir(parents=True);(a/'prior_jobs').mkdir()
for path in j.iterdir():
 if path.is_file() and path.suffix in ('.json','.log','.pid','.exitcode'):shutil.copyfile(path,a/'prior_jobs'/path.name)
shutil.copyfile(g/'generation.exitcode',a/'prior_generation.exitcode')
shutil.copyfile(selection,a/'original_selection.json')
archive=g/'failure_events/phrase_guard_1_original_selection.json';assert not archive.exists();shutil.copyfile(selection,archive)
shutil.copytree(diagnostic,a/'diagnostic_evidence',ignore=shutil.ignore_patterns('__pycache__'))
plan={'recovery_id':RECOVERY,'original_selection':failed,'activation_boundary_chexbench':168,'committed_windows_before':5,
 'previous_wrapper':'recovery/embedding_arrearage_1/resume_runner.py','generation_policy_changed':True,'same_generation_settings':False,
 'diagnostic':{'diagnostic_id':diag['diagnostic_id'],'tool_invocations':1,'main_api_calls':0,'meta_api_calls':0,'embedding_api_calls':0,
   'elapsed_s':diag['elapsed_s'],'status':diag['status'],'capture_complete':True,'result_reused_in_R49':False}}
write_once(a/'plan.json',plan)
print(json.dumps({'staged':True,'recovery_id':RECOVERY,'api_calls':0,'tool_calls':0,'committed_questions_preserved':168}))
'''


def stage(client):
    scope,review=read(SCOPE),read(REVIEW);validate_scope(scope,review)
    remote_python(client,stage_payload(),timeout=30)
    worker_source=definitions()+shared_source()+'\n'.join(inspect.getsource(fn) for fn in
      (observation.token_values,observation.capture_tool,observation.capture_state))+'\n'+WORKER
    with client.open_sftp() as sftp:
        for name,value in [('SCOPE.json',scope),('REVIEW_READY.json',review)]:
            with sftp.open(RUN+'/recovery/'+RECOVERY+'/'+name,'wx') as handle:handle.write(json.dumps(value,indent=2)+'\n')
        for name,source in [('controller.py',CONTROLLER),('resume_runner.py',RESUME_RUNNER),('maira_guard_worker.py',None)]:
            with sftp.open(RUN+'/recovery/'+RECOVERY+'/'+name,'wx') as handle:handle.write(worker_source if source is None else definitions()+shared_source()+source)
        sftp.put(str(POLICY_SOURCE),RUN+'/recovery/'+RECOVERY+'/eos_guard_policy.py')


def launch(client):
    remote_python(client,definitions()+shared_source()+GUARD+r'''
import fcntl,os,shlex,subprocess,sys
lock=(j/'.queue_launch.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
assert not (a/'controller.started.json').exists(), 'phrase_guard_launch_already_claimed'
validate_scope(read(a/'SCOPE.json'),read(a/'REVIEW_READY.json'))
keys=sys.stdin.buffer.readline()+sys.stdin.buffer.readline();assert len(keys.splitlines())==2
rd,wr=os.pipe();os.write(wr,keys);os.close(wr)
write_once(a/'controller.started.json',{'recovery_id':RECOVERY,'status':'launch_intent','known_failed_guarded_retry_limit':1,'automatic_retry':False})
command=shlex.join([PYTHON,'-u',str(a/'controller.py')])+'; rc=$?; printf "%s\n" "$rc" > '+str(a/'controller.exitcode')+'; printf "%s\n" "$rc" > '+str(j/'controller.exitcode')+'; exit "$rc"'
try:
 with (a/'controller.log').open('xb',buffering=0) as log:
  process=subprocess.Popen(['bash','-c',command],stdin=rd,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
 record={'recovery_id':RECOVERY,'pid':process.pid,'prior_attempts_include_exit1':True,'frozen_runtime_files_edited':False,'generation_policy_changed':True,'same_generation_settings':False}
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
value={'recovery':RECOVERY,'controller':phase('controller'),'prior_production_attempts_include_exit1':True,'generation_policy_changed':True,
 'same_generation_settings':False,'queue':read(j/'queue_status.json') if (j/'queue_status.json').is_file() else None,
 'registered':(r/'generation/chexbench/failure_events/phrase_guard_1_registration.json').is_file(),'datasets':{},'free_bytes':shutil.disk_usage(r).free}
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
