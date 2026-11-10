"""Private single-use R50 preparation/deployment/health/serial launch transport.

No old predictions or private metrics are rerun. Keys enter only via stdin.
"""
import argparse
import copy
from datetime import datetime,timezone
import json
from pathlib import Path
import shlex
import time

from deploy_cxr_action_r41 import connect,remote_python,ROOT,PYTHON,TRANSPORT_HOME
from deploy_cxr_online_skill_r49 import DATA,REFS,DATASETS,COUNTS,EMBED_BASE,EMBED_MODEL

LOCAL=Path(__file__).resolve().parents[1]
PREP=LOCAL/'local_assets/r50_cxr6_preparation'
SAVED49=Path('D:/MedRAX_Experiment_Artifacts/online_skill_r49_20261108')
OLD_CODE=ROOT+'/code_cxr_online_skill_r49_20261108'
RUN=ROOT+'/runs/online_skill_r50_cxr6_20261109'
CODE=ROOT+'/code_cxr_online_skill_r50_cxr6_20261109'
ARM='M43-IM-GT-S50-CXR6'
TOOLS=('medgemma','llava_rad','chest_xray_expert','llava_med_qa','xray_phrase_grounding','medvlm_r1')
NEW=('medgemma','llava_rad','medvlm_r1')
DONOR=ROOT+'/runs/cxr_vqa_toolsets_20261105/vqarad/runtime_c_ready.json'
HEALTH_IMAGE=ROOT+'/runs/cxr_vqa_backend_readiness/training_xmlab120.jpg'
PATHS=('medgemma_model','medvlm_model','llavarad_source','llavarad_model','vicuna_model','biomedbert_config')


def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))


def write_new(p,value):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x',encoding='utf-8') as f:json.dump(value,f,ensure_ascii=False,indent=2);f.write('\n')


def stamp():return datetime.now(timezone.utc).isoformat()


def require_review():
    v=read(PREP/'EXECUTION_REVIEW_READY.json')
    assert v['scope_complete'] is True and v['verdict']=='ready' and v['arm']==ARM
    assert v.get('session_id') and v.get('modelUsage') and v.get('code_review_completed') is True
    return v


def program(ds):
    command=[PYTHON,'-u',CODE+'/experiments/run_online_skill_r50.py',
      '--config',RUN+'/configs/'+ds+'.json','--data',DATA[ds],
      '--reference-dir',REFS[ds],'--out',RUN+'/generation/'+ds,
      '--dataset',ds,'--expect-questions',str(COUNTS[ds]),
      '--embedding-model',EMBED_MODEL,'--embedding-base-url',EMBED_BASE]
    if ds=='chexbench':command+=['--order-manifest',RUN+'/configs/chexbench_order.json']
    return command


def prepare(client):
    assert not (PREP/'configs').exists(),'configs_already_prepared_inspect_not_repeat'
    # Actual completed R49 config copies already transferred once; no duplicate pull.
    cfg49={d:read(SAVED49/'configs'/(d+'.json')) for d in DATASETS}
    runtime=read(SAVED49/'configs/runtime.json');protocol=read(SAVED49/'configs/protocol.json')
    with client.open_sftp() as s:
        with s.open(DONOR) as f:donor=json.loads(f.read())
    write_new(PREP/'donor_runtime.original.json',donor)
    for name in NEW:
        assert donor['tools'][name]['backend']==name
        runtime['tools'][name]=copy.deepcopy(donor['tools'][name])
    runtime['tools']={k:runtime['tools'][k] for k in TOOLS}
    for name,spec in runtime['tools'].items():
        spec['gpu']='1'
        spec['deployment_status']='new3_health_pending' if name in NEW else 'historical_warm_environment_reused_no_new_probe'
        spec.pop('worker_script',None)
        spec.setdefault('worker_env',{}).update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')
        for envname in ('CUDA_LAUNCH_BLOCKING','TORCH_SHOW_CPP_STACKTRACES','CUDA_VISIBLE_DEVICES'):
            spec['worker_env'].pop(envname,None)
    runtime['tools']['xray_phrase_grounding']['worker_script']=CODE+'/experiments/maira_guard_worker_r50.py'
    for key in PATHS:runtime['backend_config'][key]=donor['backend_config'][key]
    arm={'ready':False,'tools':list(TOOLS),'label':ARM}
    runtime['arms']={k:copy.deepcopy(arm) for k in ('M','R50-AGENT')}
    protocol.update(experiment_id='online_skill_r50_cxr6_20261109',request_archive='inline_original_images_semantic_restart_r50')
    assert {k:protocol[k] for k in ('model','temperature','top_p','max_output_tokens','enable_thinking')}==dict(model='qwen3.7-plus',temperature=.2,top_p=.95,max_output_tokens=2048,enable_thinking=False)
    configdir=PREP/'configs';configdir.mkdir()
    write_new(configdir/'runtime.json',runtime);write_new(configdir/'protocol.json',protocol)
    for ds,cfg in cfg49.items():
        assert cfg['model']=='qwen3.7-plus' and cfg['temperature']==.2 and cfg['top_p']==.95 and cfg['max_output_tokens']==2048 and cfg['extra_body']=={'enable_thinking':False}
        cfg.update(experiment_id='online_skill_r50_cxr6_'+ds+'_20261109',protocol=RUN+'/configs/protocol.json',runtime=RUN+'/configs/runtime.json')
        write_new(configdir/(ds+'.json'),cfg)
    write_new(configdir/'chexbench_order.json',read(SAVED49/'configs/chexbench_order.json'))
    source=read(PREP/'SOURCE_PREPARATION.json')
    write_new(PREP/'CONFIG_PREPARATION.json',{'utc':stamp(),'arm':ARM,'new_tools':list(NEW),'menu':list(TOOLS),
      'all_gpu':'1','config_source':'saved actual completed R49 configs reused; donor historical C runtime read once',
      'new_inference_calls':0,'R49_source_or_output_mutation':False,'runtime_sources':source['runtime_sources']})
    print(json.dumps({'status':'prepared_not_deployed','arm':ARM,'menu':list(TOOLS),'main_model':'qwen3.7-plus','new_inference_calls':0}))


HEALTH=r'''
from pathlib import Path
import fcntl,json,os,subprocess,sys,time,shutil
sys.path.insert(0,CODE+'/experiments')
from cxr_image_memory_r44 import tool_failure_reason
root=Path(RUN)/'health';root.mkdir(exist_ok=True)
lock=(root/'.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
runtime=json.loads((Path(RUN)/'configs/runtime.json').read_text())
ready=json.loads((Path(RUN)/'EXECUTION_REVIEW_READY.json').read_text())
assert ready['scope_complete'] is True and ready['verdict']=='ready'
assert json.loads((Path(CODE)/'configs/cxr_vqa_tool_worker_gpu.json').read_text())=={'cuda_visible_devices':'1'}
assert Path(HEALTH_IMAGE).is_file()
def put(p,v):
 with p.open('x') as f:json.dump(v,f,ensure_ascii=False,indent=2);f.write('\n')
records={}
for name in NEW:
 folder=root/name;folder.mkdir()
 mem=int(subprocess.check_output(['nvidia-smi','--id=1','--query-gpu=memory.used','--format=csv,noheader,nounits'],text=True).strip())
 assert mem<500,'GPU1_busy_do_not_probe_or_touch_other_jobs'
 assert shutil.disk_usage(root).free>3*1024**3,'insufficient_free_disk'
 spec=runtime['tools'][name];assert spec['gpu']=='1'
 req={'tool':name,'backend':spec['backend'],'args':{'question':'Describe the visible findings.'},
  'image':HEALTH_IMAGE,'artifact_dir':str(folder/'artifacts'),'runtime':runtime['backend_config']}
 put(folder/'request.json',req)
 put(folder/'started.json',{'utc':time.time(),'tool':name,'gpu':'1','revision':spec.get('revision'),
  'image':HEALTH_IMAGE,'health_only':True,'main_META_embedding_calls':0,'enter_skill_memory_or_scores':False})
 env=dict(os.environ,CUDA_VISIBLE_DEVICES='1',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',MPLBACKEND='Agg',TOKENIZERS_PARALLELISM='false')
 env.update(spec.get('worker_env',{}));env['CUDA_VISIBLE_DEVICES']='1'
 for flag in ('CUDA_LAUNCH_BLOCKING','TORCH_SHOW_CPP_STACKTRACES'):env.pop(flag,None)
 tick=time.monotonic();rc=None;failure=None;result=None
 command=[spec['python'],CODE+'/experiments/cxr_vqa_tool_worker.py']
 if spec.get('cpu_affinity') is not None:command=['taskset','-c',str(spec['cpu_affinity']),*command]
 try:
  with (folder/'stdout.log').open('xb') as out,(folder/'stderr.log').open('xb') as err:
   p=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=out,stderr=err,env=env)
   put(folder/'process.json',{'pid':p.pid,'command':command,'gpu':'1'})
   try:p.communicate(json.dumps(req).encode(),timeout=spec.get('timeout',900))
   except subprocess.TimeoutExpired:
    p.kill();p.communicate();raise RuntimeError('health_tool_timeout')
   rc=p.returncode
  (folder/'exitcode').write_text(str(rc)+'\n')
  if rc:raise RuntimeError('health_worker_exit_'+str(rc))
  result=json.loads((folder/'stdout.log').read_text().split('CXR_VQA_RESULT=')[-1])
  failure=tool_failure_reason(result)
  events=result.get('actual_model_events',[])
  if not failure and (result.get('cuda_visible_devices')!='1' or len(events)!=1 or events[0].get('status')!='completed'):
   failure='actual_gpu_or_model_event_missing'
  obs=result.get('observation') or {}
  if not failure and (not isinstance(obs,dict) or not str(obs.get('answer','')).strip()):failure='empty_health_answer'
 except Exception as error:failure=repr(error)
 record={'status':'failed' if failure else 'completed_healthy','tool':name,'failure':failure,
  'native_exit_code':rc,'elapsed_s':time.monotonic()-tick,'result':result,'revision':spec.get('revision'),
  'input_image':HEALTH_IMAGE,'health_only':True,'main_META_embedding_calls':0,'production_cache_or_skill_reuse':False}
 put(folder/'completed.json',record);records[name]=record
 if failure:
  put(root/'failure.json',{'tool':name,'records':records,'production_started':False});raise SystemExit(1)
put(root/'complete.json',{'status':'three_new_tools_healthy','tools':list(NEW),'records':records,
 'old_three_tools_reprobed':False,'main_META_embedding_calls':0,'hash_validation':False})
print(json.dumps({'health':'three_new_tools_healthy','tools':list(NEW),'production_started':False}))
'''


CONTROLLER=r'''
from pathlib import Path
import fcntl,json,os,subprocess,sys,time,shutil
r=Path(RUN);jobs=r/'jobs'
lock=(jobs/'.controller.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
ready=json.loads((r/'EXECUTION_REVIEW_READY.json').read_text())
assert ready['verdict']=='ready' and ready['scope_complete'] is True
health=json.loads((r/'health/complete.json').read_text());assert health['status']=='three_new_tools_healthy'
assert not any((jobs/(ds+'.pid')).exists() for ds in DATASETS)
main_key=sys.stdin.buffer.readline();embedding_key=sys.stdin.buffer.readline().strip().decode()
assert main_key.strip() and embedding_key
def state(v):
 p=jobs/'queue_status.json';t=p.with_suffix('.tmp');t.write_text(json.dumps(v,indent=2)+'\n');t.replace(p)
for ds in DATASETS:
 while True:
  mem=int(subprocess.check_output(['nvidia-smi','--id=1','--query-gpu=memory.used','--format=csv,noheader,nounits'],text=True).strip())
  state({'state':'waiting_gpu1' if mem>=500 else 'starting_dataset','dataset':ds,'gpu1_used_mib':mem,'other_jobs_modified':False})
  if mem<500:break
  time.sleep(60)
 assert shutil.disk_usage(r).free>3*1024**3,'insufficient_free_disk'
 env=dict(os.environ,R50_EMBEDDING_API_KEY=embedding_key,LANGCHAIN_TRACING_V2='false',LANGSMITH_TRACING='false')
 for flag in ('CUDA_LAUNCH_BLOCKING','TORCH_SHOW_CPP_STACKTRACES'):env.pop(flag,None)
 with (jobs/(ds+'.log')).open('xb',buffering=0) as log:
  p=subprocess.Popen(PROGRAMS[ds]+['--execute','--api-key-stdin'],stdin=subprocess.PIPE,stdout=log,stderr=subprocess.STDOUT,env=env)
  (jobs/(ds+'.pid')).write_text(str(p.pid));state({'state':'running_dataset','dataset':ds,'pid':p.pid})
  p.communicate(main_key)
 rc=p.returncode;(jobs/(ds+'.exitcode')).write_text(str(rc)+'\n')
 out=r/'generation'/ds
 if out.is_dir():(out/'generation.exitcode').write_text(str(rc)+'\n')
 if rc:
  state({'state':'dataset_failed_stop_queue','dataset':ds,'exit_code':rc,'pid':p.pid});raise SystemExit(rc)
 complete=json.loads((out/'complete.json').read_text())
 assert complete['status']=='generation_complete' and complete['questions']==COUNTS[ds] and complete['arm']==ARM
state({'state':'all_three_datasets_exited_zero','datasets':DATASETS,'arm':ARM})
'''


def script(text,**values):return '\n'.join(k+'='+repr(v) for k,v in values.items())+'\n'+text


def stage(client):
    require_review();assert not (PREP/'stage.started.json').exists(),'stage_already_invoked_inspect'
    write_new(PREP/'stage.started.json',{'utc':stamp(),'code':CODE,'run':RUN})
    remote_python(client,script(r'''
from pathlib import Path
import json,shutil
r=Path(RUN);c=Path(CODE)
assert not r.exists() and not c.exists(),'R50_namespace_already_exists'
assert shutil.disk_usage(r.parent).free>3*1024**3
(r/'configs').mkdir(parents=True);(r/'jobs').mkdir();(c/'experiments').mkdir(parents=True);(c/'configs').mkdir()
for p in (Path(OLD_CODE)/'experiments').glob('*.py'):shutil.copyfile(p,c/'experiments'/p.name)
(c/'configs/cxr_vqa_tool_worker_gpu.json').write_text(json.dumps({'cuda_visible_devices':'1'})+'\n')
print(json.dumps({'independent_R50_code_created':True,'GPU':'1','models_or_env_rebuilt':False}))
''',RUN=RUN,CODE=CODE,OLD_CODE=OLD_CODE),timeout=30)
    files=read(PREP/'SOURCE_PREPARATION.json')['runtime_sources']
    with client.open_sftp() as s:
        for relative in files:s.put(str(LOCAL/relative),CODE+'/'+relative)
        s.put(str(PREP/'support/run_cxr_vqa_toolsets.py'),CODE+'/experiments/run_cxr_vqa_toolsets.py')
        for p in (PREP/'configs').glob('*.json'):s.put(str(p),RUN+'/configs/'+p.name)
        for name in ('EXECUTION_REVIEW_READY.json','EVALUATION_PROTOCOL.json'):s.put(str(PREP/name),RUN+'/'+name)
        with s.open(RUN+'/queue_controller.py','w') as f:
            f.write(script(CONTROLLER,RUN=RUN,ARM=ARM,DATASETS=DATASETS,COUNTS=COUNTS,PROGRAMS={d:program(d) for d in DATASETS}))
        with s.open(RUN+'/health_controller.py','w') as f:f.write(script(HEALTH,RUN=RUN,CODE=CODE,NEW=NEW,HEALTH_IMAGE=HEALTH_IMAGE))
    # No API, tools or annotation file opens in these cohort/config dry-runs.
    remote_python(client,script(r'''
import pathlib,subprocess,json
for ds,command in PROGRAMS.items():
 wrapper="import pathlib,runpy,sys,socket\nreference=pathlib.Path(sys.argv[1]).resolve()\nold=pathlib.Path.open\ndef guarded(self,*a,**kw):\n if self.resolve().is_relative_to(reference):raise RuntimeError('dryrun_reference_open_forbidden')\n return old(self,*a,**kw)\npathlib.Path.open=guarded\ndef deny(*a,**kw):raise RuntimeError('dryrun_network_forbidden')\nsocket.socket.connect=deny\nsys.argv=sys.argv[2:]\nsys.path.insert(0,str(pathlib.Path(sys.argv[0]).parent))\nfrom r50_baseline_controls import validate_runtime\nvalidate_runtime(__import__('json').loads(pathlib.Path(RUNTIME).read_text()))\nrunpy.run_path(sys.argv[0],run_name='__main__')\n".replace('RUNTIME',repr(RUN+'/configs/runtime.json'))
 subprocess.run(command[:1]+['-c',wrapper,REFS[ds]]+command[2:],check=True)
print(json.dumps({'three_dryruns':'passed','new_inference':0,'reference_file_opens':0,'new_tool_probes':0}))
''',PROGRAMS={d:program(d) for d in DATASETS},REFS=REFS,RUN=RUN),timeout=60)
    write_new(PREP/'stage.completed.json',{'utc':stamp(),'status':'staged_three_dryruns_passed','new_inference_calls':0})


def launch(client,name):
    require_review();assert (PREP/'stage.completed.json').is_file()
    receipt=PREP/(name+'.launch.started.json');assert not receipt.exists(),'launch_already_invoked_inspect_not_repeat'
    write_new(receipt,{'utc':stamp(),'run':RUN,'name':name})
    source=script(r'''
from pathlib import Path
import fcntl,json,os,shlex,subprocess
r=Path(RUN);j=r/'jobs';lock=(j/('.'+NAME+'.launch.lock')).open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
assert not (j/(NAME+'.started.json')).exists() and not (j/(NAME+'.pid')).exists(),'duplicate_launch_forbidden'
if NAME=='controller':
 assert json.loads((r/'health/complete.json').read_text())['status']=='three_new_tools_healthy'
 key=__import__('sys').stdin.buffer.readline()+__import__('sys').stdin.buffer.readline();assert len(key.splitlines())==2
 rd,wr=os.pipe();os.write(wr,key);os.close(wr)
else:rd=os.open(os.devnull,os.O_RDONLY)
wrapper=shlex.join([PYTHON,'-u',str(r/SCRIPT)])+'; rc=$?; printf "%s\n" "$rc" > '+shlex.quote(str(j/(NAME+'.exitcode')))+'; exit "$rc"'
try:
 with (j/(NAME+'.log')).open('xb',buffering=0) as log:p=subprocess.Popen(['bash','-c',wrapper],stdin=rd,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
 (j/(NAME+'.pid')).write_text(str(p.pid));(j/(NAME+'.started.json')).write_text(json.dumps({'pid':p.pid,'arm':ARM,'gpu':'1','utc':__import__('time').time()}))
 print(json.dumps({'launched':NAME,'pid':p.pid,'arm':ARM,'gpu':'1'}))
finally:os.close(rd)
''',RUN=RUN,NAME=name,PYTHON=PYTHON,ARM=ARM,SCRIPT='queue_controller.py' if name=='controller' else 'health_controller.py')
    keys=None
    if name=='controller':keys=(TRANSPORT_HOME/'.secrets/token_plan_api.key').read_bytes().strip()+b'\n'+(TRANSPORT_HOME/'.secrets/qwen_api.key').read_bytes().strip()+b'\n'
    remote_python(client,source,timeout=30,input_bytes=keys)
    write_new(PREP/(name+'.launch.completed.json'),{'utc':stamp(),'name':name,'launch_command_returned_zero':True})


def health(client):
    launch(client,'health')
    # Only the fresh doc-following validator owns this waiting invocation.
    with client.open_sftp() as s:
        while True:
            try:
                with s.open(RUN+'/jobs/health.exitcode') as f:rc=f.read().decode().strip()
                break
            except FileNotFoundError:time.sleep(10)
        # The health artifacts are small and newly created, not old R49 pulls.
        import stat
        def pull(remote,local):
            local.mkdir(parents=True,exist_ok=True)
            for e in s.listdir_attr(remote):
                if e.filename.startswith('.'):continue
                p=local/e.filename;r=remote+'/'+e.filename
                if stat.S_ISDIR(e.st_mode):pull(r,p)
                elif stat.S_ISREG(e.st_mode):
                    assert not p.exists(),'health_result_already_pulled_inspect'
                    s.get(r,str(p),prefetch=False)
        pull(RUN+'/health',PREP/'health')
    write_new(PREP/'HEALTH_RECEIPT.json',{'utc':stamp(),'native_exit_code':int(rc),'health_tools':list(NEW),'old_three_reprobed':False,'production_inference':False})
    if rc!='0':raise RuntimeError('health_failed_preserved_no_automatic_retry')
    print(json.dumps({'health':'three_new_tools_healthy','gpu':'1','production_started':False}))


def queue(client):launch(client,'controller')


def status(client):
    remote_python(client,script(r'''
from pathlib import Path
import json,shutil
r=Path(RUN);j=r/'jobs'
def text(p):return p.read_text().strip() if p.exists() else None
def phase(n):
 pid=text(j/(n+'.pid'));return {'pid':pid,'alive':bool(pid and Path('/proc',pid).exists()),'exit':text(j/(n+'.exitcode'))}
amended=(j/'protocol_amendment003.json').exists()
mapfile=j/('protocol_amendment003.json' if amended else ('technical_continuation002.json' if (j/'technical_continuation002.json').exists() else 'technical_continuation001.json'))
continuation=json.loads(mapfile.read_text()) if mapfile.exists() else None
if amended:
 number='amendment003'
 assert continuation['schema']=='r50_explicit_protocol_amendment_v1' and continuation['arm']==ARM
 assert continuation['active_controller']=='controller_amendment003' and continuation['dataset_jobs']=={ds:ds+'_amendment003' for ds in DATASETS}
elif continuation:
 number='002' if mapfile.name=='technical_continuation002.json' else '001'
 assert continuation['schema']==('r50_explicit_technical_continuation_v2' if number=='002' else 'r50_explicit_technical_continuation_v1') and continuation['arm']==ARM
 assert continuation['active_controller']=='controller_recovery'+number and continuation['dataset_jobs']=={'chexbench':'chexbench_recovery'+number,'slake':'slake','vqarad':'vqarad'}
controller=continuation['active_controller'] if continuation else 'controller'
queuefile=j/(continuation['active_queue_status'] if continuation else 'queue_status.json')
v={'arm':ARM,'controller':phase(controller),'health':phase('health'),'queue':json.loads(queuefile.read_text()) if queuefile.exists() else None,'datasets':{},'free_bytes':shutil.disk_usage(r).free}
if amended:v.update(protocol_amendment=continuation,original_controller=phase('controller'),prior_controllers={name:phase(name) for name in ('controller_recovery001','controller_recovery002')})
elif continuation:v.update(technical_continuation=continuation,original_controller=phase('controller'))
if continuation and number=='002':v['prior_continuation_controller']=phase('controller_recovery001')
for ds in DATASETS:
 g=r/'generation'/ds;s=g/'services'
 job=continuation['dataset_jobs'][ds] if continuation else ds
 d=dict(phase(job),saved=len(list((g/'predictions'/ARM).glob('*.json'))),contexts=len(list((g/'contexts').glob('*.json'))),feedback=len(list((g/'feedback').glob('*.json'))),main_sends=len(list((s/'calls/R50-AGENT').glob('*/*/started.json'))),main_responses=len(list((s/'calls/R50-AGENT').glob('*/*/response.json'))),meta_sends=len(list((s/'calls/R50-META').glob('*/*/started.json'))),windows=len(list((g/'windows').glob('*/repo.json'))),complete=(g/'complete.json').exists())
 if job!=ds:d['original_attempt']=phase(ds)
 if amended and ds=='chexbench':d['prior_attempts']={name:phase(name) for name in ('chexbench_recovery001','chexbench_recovery002')}
 if job=='chexbench_recovery002':d['prior_continuation_attempt']=phase('chexbench_recovery001')
 if d['exit'] not in (None,'0') and (j/(job+'.log')).exists():d['failure_tail']=(j/(job+'.log')).read_text(errors='replace').splitlines()[-18:]
 v['datasets'][ds]=d
print(json.dumps(v))
''',RUN=RUN,ARM=ARM,DATASETS=DATASETS),timeout=30)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['prepare','stage','health','queue','status']);a=p.parse_args()
    with connect() as client:globals()[a.mode](client)
