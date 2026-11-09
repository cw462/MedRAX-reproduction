"""Explicit one-case production retry/cache amendment; never a general retry loop."""
import argparse
import inspect
import json
from pathlib import Path

from deploy_cxr_online_skill_r49 import CODE, COUNTS, DATA, DATASETS, PREP, PYTHON, ROOT, RUN, TRANSPORT_HOME, connect, program, remote_python

RECOVERY='cuda_1'
QID='chexbench_rad_restruct_0163'
ARM='M43-IM-GT-S49'
EXPECTED_PROMPT='Are there any signs of pleural effusion, pneumothorax, or pleural thickening in the image?'
SCOPE=PREP/'CUDA_PRODUCTION_RECOVERY_SCOPE.json'
REVIEW=PREP/'CUDA_PRODUCTION_RECOVERY_REVIEW_READY.json'


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


GUARD=r'''
from pathlib import Path
import json
r=Path(RUN);j=r/'jobs';g=r/'generation/chexbench';a=r/'recovery'/RECOVERY
def read(path):return json.loads(path.read_text())
for name in ('controller','chexbench'):
 pid=(j/(name+'.pid')).read_text().strip();assert not Path('/proc',pid).exists(), 'R49_process_active'
 assert (j/(name+'.exitcode')).read_text().strip()=='1'
assert (g/'generation.exitcode').read_text().strip()=='1'
manifest=read(g/'manifest.json');ids=[row['question_id'] for row in manifest['inputs']]
assert ids[40]==QID and len(ids)==618
for folder in ('predictions/M43-IM-GT-S49','prediction_events','feedback','steps'):
 assert {p.stem for p in (g/folder).glob('*.json')}==set(ids[:40]), 'committed_prefix_changed:'+folder
assert {p.stem for p in (g/'contexts').glob('*.json')}==set(ids[:41])
assert len(list((g/'windows').glob('*/repo.json')))==1
s=g/'services';requests=list((s/'calls/R49-AGENT').glob('*/*/started.json'))
assert len(requests)==94 and len(list((s/'calls/R49-META').glob('*/*/started.json')))==13
assert len(list((s/'embeddings').glob('*/started.json')))==2
for start in list((s/'calls').glob('*/*/*/started.json'))+list((s/'embeddings').glob('*/started.json')):
 assert (start.parent/'response.json').is_file() and (start.parent/'result.json').is_file()
 receipt=read(start.parent/'result.json');assert receipt.get('response_received') is True and not receipt.get('error')
assert [p.parent.name for p in (s/'calls/R49-AGENT'/QID).glob('*/started.json')]==['1']
old=read(s/'tool_selections/R49-AGENT'/QID/'1.json')
assert old['tool']=='chest_xray_expert' and old['backend']=='chest_xray_expert'
assert old['identity']['args']=={'question':EXPECTED_PROMPT}
assert any(event.get('status')=='failed' for event in old['actual_model_events'])
assert 'CUDA error: device kernel image is invalid' in json.dumps(old['observation'])
key=old['cache_key'];assert Path(key).name==key and '..' not in key
assert not (s/'tool_cache'/(key+'_cuda_1')).exists(), 'production_retry_already_attempted'
assert (s/'tool_cache'/key/'started.json').is_file() and (s/'tool_cache'/key/'result.json').is_file()
assert not (g/'failure_events/cuda_1_registration.json').exists()
runtime=read(r/'configs/runtime.json')
assert runtime['tools']==manifest['runtime']['tools'] and runtime['backend_config']==manifest['runtime']['backend_config']
expert=runtime['tools']['chest_xray_expert']
assert expert['backend']==old['backend'] and expert['revision']==old['identity']['revision'] and expert['gpu']=='1'
assert Path(runtime['backend_config']['chexagent_snapshot']).name=='8f19b53a2eceda4c33b0acec6c81fbc293ad80d0'
assert Path(runtime['backend_config']['vision_snapshot']).name=='f0edbf5d90dba44edb7f4f96d8663537cb0749bf'
for ds in ('slake','vqarad'):
 assert not (j/(ds+'.pid')).exists()
 out=r/'generation'/ds;assert not out.exists() or not any(out.rglob('*.json'))
'''


CONTROLLER=r'''
import fcntl,os,subprocess,sys,time,shutil
r=Path(RUN);j=r/'jobs';a=r/'recovery'/RECOVERY;g=r/'generation/chexbench';s=g/'services'
lock=(j/'.controller.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
scope=read(a/'SCOPE.json');review=read(a/'REVIEW_READY.json');validate_scope(scope,review)
main_key=sys.stdin.buffer.readline();embedding_key=sys.stdin.buffer.readline().strip().decode();assert main_key.strip() and embedding_key
def state(value):
 value.update(recovery=RECOVERY,prior_production_attempts_include_exit1=True)
 path=j/'queue_status.json';tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(value,indent=2)+'\n');tmp.replace(path)
def wait_gpu1(dataset):
 while True:
  memory=int(subprocess.check_output(['nvidia-smi','--id=1','--query-gpu=memory.used','--format=csv,noheader,nounits'],text=True).strip())
  state({'state':'waiting_gpu1' if memory>=500 else 'ready_gpu1','dataset':dataset,'gpu1_used_mib':memory})
  if memory<500:break
  time.sleep(60)
 assert shutil.disk_usage(r).free>3*1024**3
assert os.environ.get('CUDA_LAUNCH_BLOCKING') is None and os.environ.get('TORCH_SHOW_CPP_STACKTRACES') is None
wait_gpu1('chexbench_production_retry')
sys.path.insert(0,str(Path(CODE)/'experiments'))
import run_cxr_vqa_toolsets as base
from cxr_image_memory_r44 import tool_failure_reason
plan=read(a/'plan.json');original=read(s/'tool_selections/R49-AGENT'/QID/'1.json')
runtime=read(r/'configs/runtime.json');spec=runtime['tools']['chest_xray_expert']
assert all(name not in spec.get('worker_env',{}) for name in ('CUDA_LAUNCH_BLOCKING','TORCH_SHOW_CPP_STACKTRACES'))
write_once(a/'production_retry_started.json',{'recovery_id':RECOVERY,'question_id':QID,'main_api_calls':0,'tool_attempts':1,'automatic_retry':False})
folder=s/'tool_cache'/(original['cache_key']+'_cuda_1');assert not folder.exists()
state({'state':'production_tool_retry_running','dataset':'chexbench','question_id':QID})
tool=base.Tools(runtime,Path(DATA['chexbench']),s)
result,cache_hit=tool.observe('chest_xray_expert',spec,original['identity']['args'],Path(original['original_image']),original['identity'],folder,folder/'result.json')
assert cache_hit is False
failure=tool_failure_reason(result)
if failure:
 write_once(a/'production_retry_failed.json',{'status':'stopped','failure_reason':failure,'main_api_calls':0,'automatic_retry':False})
 state({'state':'production_tool_retry_failed_stop_queue','dataset':'chexbench','failure_reason':failure})
 raise RuntimeError('cuda_1_production_retry_failed:'+failure)
registration=commit_healthy_retry(s,a,original,result,plan['diagnostic'])
state({'state':'healthy_production_retry_registered','dataset':'chexbench','question_id':QID})
for ds in DATASETS:
 wait_gpu1(ds)
 command=[PYTHON,'-u',str(a/'resume_runner.py')] if ds=='chexbench' else PROGRAMS[ds]+['--execute','--api-key-stdin']
 logfile=j/(ds+'.'+RECOVERY+'.log')
 with logfile.open('xb',buffering=0) as log:
  process=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=log,stderr=subprocess.STDOUT,
   env=dict(os.environ,R49_EMBEDDING_API_KEY=embedding_key,LANGCHAIN_TRACING_V2='false',LANGSMITH_TRACING='false'))
  (a/(ds+'.pid')).write_text(str(process.pid));(j/(ds+'.pid')).write_text(str(process.pid))
  state({'state':'running_dataset','dataset':ds,'pid':process.pid,'log':str(logfile),'current_attempt_exit':None})
  process.communicate(main_key)
 rc=process.returncode;(a/(ds+'.exitcode')).write_text(str(rc)+'\n');(j/(ds+'.exitcode')).write_text(str(rc)+'\n')
 out=r/'generation'/ds
 if out.is_dir():(out/'generation.exitcode').write_text(str(rc)+'\n')
 if rc:
  state({'state':'dataset_failed_stop_queue','dataset':ds,'pid':process.pid,'exit_code':rc,'log':str(logfile)})
  raise SystemExit(rc)
 complete=read(out/'complete.json');assert complete['status']=='generation_complete' and complete['questions']==COUNTS[ds]
state({'state':'all_three_datasets_exited_zero_after_registered_cuda_retry','datasets':list(DATASETS)})
'''


RESUME_RUNNER=r'''
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
'''


def definitions():
    return '\n'.join(key+'='+repr(value) for key,value in dict(
      RUN=RUN,ROOT=ROOT,CODE=CODE,PYTHON=PYTHON,RECOVERY=RECOVERY,QID=QID,ARM=ARM,EXPECTED_PROMPT=EXPECTED_PROMPT,
      DATA=DATA,DATASETS=DATASETS,COUNTS=COUNTS,PROGRAMS={ds:program(ds) for ds in DATASETS}).items())+'\n'


def shared_source():
    return 'import json\nfrom pathlib import Path\ndef read(path):return json.loads(Path(path).read_text())\n'+\
      '\n'.join(inspect.getsource(fn) for fn in (write_once,validate_scope,commit_healthy_retry,registered_call_overlay))+'\n'


def stage(client):
    scope=json.loads(SCOPE.read_text(encoding='utf-8'));review=json.loads(REVIEW.read_text(encoding='utf-8'));validate_scope(scope,review)
    remote_python(client,definitions()+GUARD+r'''
import shutil
a.mkdir(parents=True,exist_ok=True)
assert not (a/'plan.json').exists() and not (a/'controller.started.json').exists(), 'recovery_already_staged'
(a/'prior_jobs').mkdir()
for path in j.iterdir():
 if path.is_file() and path.suffix in ('.json','.log','.pid','.exitcode'):shutil.copyfile(path,a/'prior_jobs'/path.name)
shutil.copyfile(g/'generation.exitcode',a/'prior_generation.exitcode')
diagnostic_root=Path(ROOT)/'runs/online_skill_r49_cuda_diagnostic_20261108/attempt_1'
diagnostic=read(diagnostic_root/'status.json')
assert diagnostic['status']=='completed_healthy' and diagnostic['tool_invocations']==1
assert all(diagnostic[field]==0 for field in ('main_api_calls','meta_api_calls','embedding_api_calls'))
assert (diagnostic_root/'exitcode').read_text().strip()=='0'
(a/'diagnostic_evidence').mkdir()
shutil.copyfile(diagnostic_root/'status.json',a/'diagnostic_evidence/status.json')
shutil.copyfile(diagnostic_root/'exitcode',a/'diagnostic_evidence/exitcode')
diag={'tool_invocations':1,'main_api_calls':0,'meta_api_calls':0,'embedding_api_calls':0,
      'elapsed_s':diagnostic['elapsed_s'],'result_reused_in_R49':False}
plan={'recovery_id':RECOVERY,'question_id':QID,'original_cache_key':old['cache_key'],
 'retry_cache_key':old['cache_key']+'_cuda_1','production_tool_retry_limit':1,
 'diagnostic':diag,'main_plan_reissue':False,'technical_null_fill':False,
 'cache_overlay':'exact_registered_backend_revision_original_path_args_only','runtime_source_files_edited':False}
with (a/'plan.json').open('x') as handle:json.dump(plan,handle,indent=2);handle.write('\n')
print(json.dumps({'staged':True,'new_tool_attempts':0,'new_main_calls':0,'recovery_id':RECOVERY}))
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
assert not (a/'controller.started.json').exists(), 'cuda_recovery_launch_already_claimed'
validate_scope(read(a/'SCOPE.json'),read(a/'REVIEW_READY.json'))
keys=sys.stdin.buffer.readline()+sys.stdin.buffer.readline();assert len(keys.splitlines())==2
rd,wr=os.pipe();os.write(wr,keys);os.close(wr)
env=dict(os.environ);env.pop('CUDA_LAUNCH_BLOCKING',None);env.pop('TORCH_SHOW_CPP_STACKTRACES',None)
write_once(a/'controller.started.json',{'recovery_id':RECOVERY,'status':'launch_intent','production_tool_retry_limit':1,'automatic_retry':False})
command=shlex.join([PYTHON,'-u',str(a/'controller.py')])+'; rc=$?; printf "%s\n" "$rc" > '+str(a/'controller.exitcode')+'; printf "%s\n" "$rc" > '+str(j/'controller.exitcode')+'; exit "$rc"'
try:
 with (a/'controller.log').open('xb',buffering=0) as log:
  process=subprocess.Popen(['bash','-c',command],stdin=rd,stdout=log,stderr=subprocess.STDOUT,env=env,start_new_session=True)
 record={'recovery_id':RECOVERY,'pid':process.pid,'prior_attempts_include_exit1':True,'runtime_source_files_edited':False,'cache_resolution_overlay_declared':True}
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
 'production_retry_started':(a/'production_retry_started.json').is_file(),
 'registered':(r/'generation/chexbench/failure_events/cuda_1_registration.json').is_file(),
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
