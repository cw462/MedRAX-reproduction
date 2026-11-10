"""One explicitly attributed retry of a known pre-generation tokenizer failure.

No completed prediction, original failed cache, model/environment or parameter is
changed. This helper does not adopt a result or restart the experiment queue.
"""
import json
from datetime import datetime,timezone
from deploy_cxr6_r50 import connect,remote_python,script,PREP,RUN,CODE,PYTHON,ARM

Q='chexbench_rad_restruct_0227'
KEY='42a5ac09c93a6ac19d79b02eda81d4d4c33048eb56c955ed457f0ce5d6d8c09e'
NAME='001_medvlm_tokenizer_load'
LOCAL=PREP/'failures/001_chex_104'
ATTEMPT=r'''
from pathlib import Path
import json,os,subprocess,time,traceback
r=Path(RUN);folder=r/'technical_recovery'/NAME
def put(name,v):
 with (folder/name).open('x') as f:json.dump(v,f,ensure_ascii=False,indent=2);f.write('\n')
rc=None
try:
 runtime=json.loads((r/'configs/runtime.json').read_text());spec=runtime['tools']['medvlm_r1']
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
  'native_worker_exit_code':rc,'question_id':Q,'selection_ordinal':5,'tool':'medvlm_r1',
  'scope':'one technical retry of confirmed zero-generation tokenizer load failure',
  'original_failed_records_retained':True,'adopted_into_production':False,'automatic_retry':False,
  'new_main_META_embedding_calls':0,'clinical_answer_quality_checked':False})
 if failure:raise SystemExit(1)
except Exception as exc:
 traceback.print_exc()
 if not (folder/'completed.json').exists():put('completed.json',{'status':'failed','exception_type':type(exc).__name__,
  'error':str(exc),'native_worker_exit_code':rc,'automatic_retry':False,'adopted_into_production':False})
 raise
'''

def main():
    marker=LOCAL/'technical_retry.launch.started.json'
    with marker.open('x',encoding='utf-8') as f:json.dump({'utc':datetime.now(timezone.utc).isoformat(),
        'known_failed_tool_no_generate':True,'automatic_retry':False,'actual_adoption_or_queue_restart':False},f)
    source=script(ATTEMPT,RUN=RUN,CODE=CODE,Q=Q,NAME=NAME)
    launch=script(r'''
from pathlib import Path
import json,os,subprocess,shlex,time
r=Path(RUN);g=r/'generation/chexbench';folder=r/'technical_recovery'/NAME
assert not Path('/proc/3167009').exists() and not Path('/proc/3167015').exists(),'original_producer_still_alive'
assert not (g/'predictions'/ARM/(Q+'.json')).exists() and not (g/'feedback'/(Q+'.json')).exists()
cache=g/'services/tool_cache'/KEY
failed=json.loads((cache/'result.json').read_text());selection=json.loads((g/'services/tool_selections/R50-AGENT'/Q/'5.json').read_text())
assert failed['status']=='failed' and failed['error_type']=='ImportError' and failed.get('actual_model_events')==[]
assert selection['cache_key']==KEY and selection['tool']=='medvlm_r1' and selection['status']=='failed'
assert 'Token `ViewChild` out of vocabulary' in (cache/'backend.stderr.log').read_text()
used=int(subprocess.check_output(['nvidia-smi','--id=1','--query-gpu=memory.used','--format=csv,noheader,nounits'],text=True).strip())
assert used<500,'GPU1_busy_no_restart'
folder.mkdir(parents=True,exist_ok=False)
for name,body in [('original_request.json',(cache/'request.json').read_text()),('original_result.json',(cache/'result.json').read_text()),
                  ('original_selection.json',json.dumps(selection))]:
 with (folder/name).open('x') as f:f.write(body)
with (folder/'attempt.py').open('x') as f:f.write(SOURCE)
with (folder/'started.json').open('x') as f:json.dump({'utc':time.time(),'question_id':Q,'selection_ordinal':5,
 'original_cache_key':KEY,'known_pre_generation_failure':True,'max_explicit_attempts':1,'automatic_retry':False,
 'original_model_environment_parameters_unchanged':True,'user_labels_or_completed_predictions_read':False},f,indent=2)
cmd=shlex.join([PYTHON,'-u',str(folder/'attempt.py')])+'; rc=$?; printf "%s\\n" "$rc" > '+shlex.quote(str(folder/'attempt.exitcode'))+'; exit "$rc"'
with (folder/'controller.log').open('xb',buffering=0) as out:
 p=subprocess.Popen(['bash','-c',cmd],stdin=subprocess.DEVNULL,stdout=out,stderr=subprocess.STDOUT,start_new_session=True)
(folder/'attempt.pid').write_text(str(p.pid)+'\n')
print(json.dumps({'explicit_technical_attempt_launched':True,'pid':p.pid,'folder':str(folder),'adopted_or_queue_restarted':False,'gpu':'1'}))
''',RUN=RUN,CODE=CODE,PYTHON=PYTHON,ARM=ARM,Q=Q,KEY=KEY,NAME=NAME,SOURCE=source)
    with connect() as client:remote_python(client,launch,timeout=30)

if __name__=='__main__':main()
