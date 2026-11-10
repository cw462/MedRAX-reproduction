RUN='/home/imss/cw/MedRAX_reproduction_20261027/runs/online_skill_r50_cxr6_20261109'
CODE='/home/imss/cw/MedRAX_reproduction_20261027/code_cxr_online_skill_r50_cxr6_20261109'
Q='chexbench_slake_0068'
NAME='002_medgemma_tokenizer_load'
TOOL='medgemma'

from pathlib import Path
import json,os,subprocess,time,traceback
r=Path(RUN);folder=r/'technical_recovery'/NAME
def put(name,v):
 with (folder/name).open('x') as f:json.dump(v,f,ensure_ascii=False,indent=2);f.write('\n')
rc=None
try:
 runtime=json.loads((r/'configs/runtime.json').read_text());spec=runtime['tools'][TOOL]
 original=json.loads((folder/'original_request.json').read_text())
 request=dict(original,artifact_dir=str(folder/'artifacts'));put('request.json',request)
 env=dict(os.environ,CUDA_VISIBLE_DEVICES=spec.get('gpu','1'),MPLBACKEND='Agg',TOKENIZERS_PARALLELISM='false')
 env.update(spec.get('worker_env',{}));env.update(CUDA_VISIBLE_DEVICES='1',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')
 env.pop('CUDA_LAUNCH_BLOCKING',None);env.pop('TORCH_SHOW_CPP_STACKTRACES',None)
 assert json.loads((Path(CODE)/'configs/cxr_vqa_tool_worker_gpu.json').read_text())=={'cuda_visible_devices':'1'}
 command=[spec['python'],spec.get('worker_script') or CODE+'/experiments/cxr_vqa_tool_worker.py']
 if spec.get('cpu_affinity') is not None:command=['taskset','-c',str(spec['cpu_affinity']),*command]
 tick=time.monotonic()
 with (folder/'backend.stdout.log').open('xb') as out,(folder/'backend.stderr.log').open('xb') as err:
  p=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=out,stderr=err,env=env)
  put('process.json',{'pid':p.pid,'command':command,'gpu':'1','automatic_retry':False})
  try:p.communicate(json.dumps(request).encode(),timeout=spec.get('timeout',600))
  except subprocess.TimeoutExpired:
   p.kill();p.communicate();raise RuntimeError('explicit_technical_retry_timeout_no_further_retry')
  rc=p.returncode
 (folder/'worker.exitcode').write_text(str(rc)+'\n')
 if rc:raise RuntimeError('worker_exit_'+str(rc))
 result=json.loads((folder/'backend.stdout.log').read_text().split('CXR_VQA_RESULT=')[-1])
 result.update(elapsed_s=time.monotonic()-tick,backend=spec['backend'],
  identity=json.loads((folder/'original_result.json').read_text())['identity'],
  utc=__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat())
 put('result.json',result)
 import sys
 sys.path.insert(0,CODE+'/experiments')
 from cxr_image_memory_r44 import tool_failure_reason
 failure=tool_failure_reason(result);events=result.get('actual_model_events',[])
 if not failure and (len(events)!=1 or events[0].get('kind')!='generate' or events[0].get('status')!='completed'):
  failure='actual_single_generate_event_missing'
 if not failure and not str((result.get('observation') or {}).get('answer','')).strip():failure='empty_tool_answer'
 put('completed.json',{'status':'failed' if failure else 'completed_healthy','failure':failure,
  'native_worker_exit_code':rc,'question_id':Q,'selection_ordinal':1,'tool':TOOL,
  'scope':'one technical retry of confirmed zero-generation tokenizer load failure',
  'original_failed_records_retained':True,'adopted_into_production':False,'automatic_retry':False,
  'new_main_META_embedding_calls':0,'clinical_answer_quality_checked':False})
 if failure:raise SystemExit(1)
except Exception as exc:
 traceback.print_exc()
 if not (folder/'completed.json').exists():put('completed.json',{'status':'failed','exception_type':type(exc).__name__,
  'error':str(exc),'native_worker_exit_code':rc,'automatic_retry':False,'adopted_into_production':False})
 raise
