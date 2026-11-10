RUN='/home/imss/cw/MedRAX_reproduction_20261027/runs/online_skill_r50_cxr6_20261109'
CODE='/home/imss/cw/MedRAX_reproduction_20261027/code_cxr_online_skill_r50_cxr6_20261109'
NEW=('medgemma', 'llava_rad', 'medvlm_r1')
HEALTH_IMAGE='/home/imss/cw/MedRAX_reproduction_20261027/runs/cxr_vqa_backend_readiness/training_xmlab120.jpg'

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
