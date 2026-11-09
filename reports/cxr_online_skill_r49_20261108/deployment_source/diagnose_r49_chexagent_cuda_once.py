"""Prepare one reviewed isolated CUDA diagnostic within existing R49 technical scope."""
import argparse
import json
from pathlib import Path

from deploy_cxr_online_skill_r49 import CODE, ROOT, RUN, connect, remote_python

DIAGNOSTIC_ID='r49_chexagent_cuda_once_20261108'
ATTEMPT=ROOT+'/runs/online_skill_r49_cuda_diagnostic_20261108/attempt_1'
QID='chexbench_rad_restruct_0163'
MODEL_REVISION='8f19b53a2eceda4c33b0acec6c81fbc293ad80d0'
VISION_REVISION='f0edbf5d90dba44edb7f4f96d8663537cb0749bf'
EXPECTED_PROMPT='Are there any signs of pleural effusion, pneumothorax, or pleural thickening in the image?'
LOCAL=Path(__file__).resolve().parents[1]
SCOPE=LOCAL/'local_assets/r49_cuda_failure_20261108/DIAGNOSTIC_EXECUTION_SCOPE.json'
REVIEW=LOCAL/'local_assets/r49_cuda_failure_20261108/DIAGNOSTIC_REVIEW_READY.json'


def validate_scope_and_review(scope,review):
    if (scope.get('diagnostic_id')!=DIAGNOSTIC_ID or scope.get('attempt')!=1
            or scope.get('uses_existing_r49_authorization') is not True
            or scope.get('new_user_approval_claimed') is not False
            or not isinstance(scope.get('authorization_basis'),str) or not scope['authorization_basis'].strip()
            or scope.get('one_isolated_tool_invocation') is not True
            or any(scope.get(key)!=0 for key in ('main_api_calls','meta_api_calls','embedding_api_calls'))
            or scope.get('automatic_r49_resume') is not False or scope.get('modify_original_run') is not False):
        raise ValueError('existing_R49_diagnostic_scope_record_required')
    if (review.get('diagnostic_id')!=DIAGNOSTIC_ID or review.get('verdict')!='ready'
            or review.get('scope_complete') is not True
            or not isinstance(review.get('trace'),str) or not review['trace'].strip()):
        raise ValueError('actual_diagnostic_review_ready_required')
    return scope,review


def definitions():
    return '\n'.join(key+'='+repr(value) for key,value in dict(
        RUN=RUN,CODE=CODE,ATTEMPT=ATTEMPT,QID=QID,DIAGNOSTIC_ID=DIAGNOSTIC_ID,
        MODEL_REVISION=MODEL_REVISION,VISION_REVISION=VISION_REVISION,
        EXPECTED_PROMPT=EXPECTED_PROMPT).items())+'\n'


DIAGNOSTIC_RUNNER=r'''
import argparse,contextlib,importlib.metadata,json,os,socket,sys,time,traceback
from pathlib import Path
from unittest.mock import patch

def write_once(path,value):
 with path.open('x',encoding='utf-8') as handle:
  json.dump(value,handle,ensure_ascii=False,indent=2);handle.write('\n');handle.flush();os.fsync(handle.fileno())

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--request',required=True,type=Path);args=parser.parse_args()
 request=json.loads(args.request.read_text());out=args.request.parent
 assert out==Path(ATTEMPT) and request['backend']=='chest_xray_expert'
 assert request['args']=={'question':EXPECTED_PROMPT}
 assert Path(request['artifact_dir'])==out/'artifacts'
 assert os.environ.get('CUDA_VISIBLE_DEVICES')=='1' and os.environ.get('CUDA_LAUNCH_BLOCKING')=='1'
 config=json.loads((Path(CODE)/'configs/cxr_vqa_tool_worker_gpu.json').read_text())
 assert config['cuda_visible_devices']=='1', 'existing_worker_gpu_binding_changed'
 write_once(out/'worker_started.json',{'pid':os.getpid(),'diagnostic_id':DIAGNOSTIC_ID,'tool_invocations':1,
  'main_api_calls':0,'meta_api_calls':0,'embedding_api_calls':0,'automatic_r49_resume':False})
 events=[];began=time.monotonic();error=None
 def deny_network(*args,**kwargs):raise RuntimeError('isolated_diagnostic_network_forbidden')
 sys.path.insert(0,str(Path(CODE)/'experiments'))
 with contextlib.ExitStack() as stack:
  stack.enter_context(patch.object(socket.socket,'connect',deny_network))
  stack.enter_context(patch.object(socket.socket,'connect_ex',deny_network))
  stack.enter_context(patch.object(socket,'create_connection',deny_network))
  import requests
  stack.enter_context(patch.object(requests.sessions.Session,'request',deny_network))
  import cxr_vqa_tool_worker as worker
  from cxr_image_memory_r44 import tool_failure_reason
  with contextlib.redirect_stdout(sys.stderr):
   try:
    with worker.inference_events(request,events):
     from transformers.generation.utils import GenerationMixin
     tracked_generate=GenerationMixin.generate
     def traced_generate(model,*args,**kwargs):
      try:return tracked_generate(model,*args,**kwargs)
      except BaseException:
       path=out/'generate_exception.txt'
       if not path.exists():
        with path.open('x',encoding='utf-8') as handle:traceback.print_exc(file=handle)
       traceback.print_exc(file=sys.stderr)
       raise
     with patch.object(GenerationMixin,'generate',traced_generate):
      result=worker.execute(request)
   except Exception as exc:
    traceback.print_exc(file=sys.stderr)
    result={'status':'failed','observation':None,'error_type':type(exc).__name__,'error':str(exc)}
    error=type(exc).__name__
  result.update(actual_model_events=events,cuda_visible_devices='1',
    adapter_revision='cxr-vqa-existing-snapshot-binding-3',diagnostic_only=True)
  write_once(out/'result.json',result)
  failure=tool_failure_reason(result)
  versions={}
  for name in ('torch','torchvision','transformers','triton','accelerate','safetensors'):
   try:versions[name]=importlib.metadata.version(name)
   except importlib.metadata.PackageNotFoundError:versions[name]=None
  status={'diagnostic_id':DIAGNOSTIC_ID,'status':'failed' if failure else 'completed_healthy',
    'health_failure_reason':failure,'exception_type':error,'elapsed_s':time.monotonic()-began,
    'tool_invocations':1,'main_api_calls':0,'meta_api_calls':0,'embedding_api_calls':0,
    'automatic_r49_resume':False,'result_may_replace_original_failure':False,
    'environment_changes':'subprocess_debug_flags_only_no_library_or_model_changes','packages':versions}
  write_once(out/'status.json',status)
  print(json.dumps(status))
  return 1 if failure else 0

if __name__=='__main__':raise SystemExit(main())
'''


def stage(client):
    remote_python(client,definitions()+r'''
from pathlib import Path
import json
r=Path(RUN);out=Path(ATTEMPT)
assert not out.exists(), 'diagnostic_attempt_already_prepared_check_state'
j=r/'jobs'
for name in ('controller','chexbench'):
 pid=(j/(name+'.pid')).read_text().strip()
 assert not Path('/proc',pid).exists(), 'R49_process_still_active'
 assert (j/(name+'.exitcode')).read_text().strip()=='1'
selection=r/'generation/chexbench/services/tool_selections/R49-AGENT'/QID/'1.json'
failed=json.loads(selection.read_text())
assert failed['tool']=='chest_xray_expert' and failed['backend']=='chest_xray_expert'
assert any(event.get('status')=='failed' for event in failed['actual_model_events'])
assert failed['identity']['args']=={'question':EXPECTED_PROMPT}
runtime=json.loads((r/'configs/runtime.json').read_text())
spec=runtime['tools']['chest_xray_expert'];backend=runtime['backend_config']
assert spec['gpu']=='1' and spec['backend']=='chest_xray_expert'
assert Path(spec['python']).name=='python' and '.venv-chexagent' in str(Path(spec['python']).parent)
assert Path(backend['chexagent_snapshot']).name==MODEL_REVISION
assert Path(backend['vision_snapshot']).name==VISION_REVISION
assert Path(failed['original_image']).name=='CXR729_IM-2288-1001.png'
config=json.loads((Path(CODE)/'configs/cxr_vqa_tool_worker_gpu.json').read_text())
assert config['cuda_visible_devices']=='1'
out.mkdir(parents=True)
request={'tool':'chest_xray_expert','backend':'chest_xray_expert','args':dict(failed['identity']['args']),
 'image':failed['original_image'],'artifact_dir':str(out/'artifacts'),'runtime':backend}
plan={'diagnostic_id':DIAGNOSTIC_ID,'question_id':QID,'attempt':1,'main_api_calls':0,'meta_api_calls':0,
 'embedding_api_calls':0,'tool_invocations':1,'max_new_tokens':512,'dtype':'bfloat16',
 'physical_gpu':'1','model_revision':MODEL_REVISION,'vision_revision':VISION_REVISION,
 'python':spec['python'],'cpu_affinity':spec.get('cpu_affinity'),'timeout_seconds':spec.get('timeout',600),'worker_code_root':CODE,
 'worker_env':spec.get('worker_env',{}),'original_selection_file':str(selection),
 'automatic_retry':False,'automatic_r49_resume':False,'byte_or_pixel_checks':False,
 'diagnostic_flags':{'CUDA_LAUNCH_BLOCKING':'1','TORCH_SHOW_CPP_STACKTRACES':'1'}}
for name,value in [('request.json',request),('plan.json',plan)]:
 with (out/name).open('x') as handle:json.dump(value,handle,indent=2);handle.write('\n')
print(json.dumps({'prepared':True,'path':str(out),'inference_calls':0,'actual_review_and_scope_records_required':True}))
''',timeout=30)
    with client.open_sftp() as sftp:
        with sftp.open(ATTEMPT+'/diagnostic_runner.py','w') as handle:
            handle.write(definitions()+DIAGNOSTIC_RUNNER)


def launch(client):
    scope,review=validate_scope_and_review(json.loads(SCOPE.read_text(encoding='utf-8')),json.loads(REVIEW.read_text(encoding='utf-8')))
    # Root records the existing R49 authorization basis and the actual completed review.
    with client.open_sftp() as sftp:
        for name,value in (('EXECUTION_SCOPE.json',scope),('REVIEW_READY.json',review)):
            path=ATTEMPT+'/'+name
            try:
                with sftp.open(path,'r') as handle:existing=json.loads(handle.read().decode('utf-8'))
            except FileNotFoundError:
                with sftp.open(path,'wx') as handle:handle.write(json.dumps(value,indent=2)+'\n')
            else:
                if existing!=value:raise ValueError('immutable_diagnostic_record_changed:'+name)
    remote_python(client,definitions()+r'''
from pathlib import Path
import fcntl,json,os,shlex,shutil,subprocess
out=Path(ATTEMPT);r=Path(RUN);j=r/'jobs'
lock=(out/'.launch.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
assert not (out/'started.json').exists(), 'diagnostic_started_no_reissue'
scope=json.loads((out/'EXECUTION_SCOPE.json').read_text());review=json.loads((out/'REVIEW_READY.json').read_text())
assert scope['diagnostic_id']==DIAGNOSTIC_ID and scope['attempt']==1
assert scope['uses_existing_r49_authorization'] is True and scope['new_user_approval_claimed'] is False
assert scope['authorization_basis'] and scope['one_isolated_tool_invocation'] is True
assert all(scope[key]==0 for key in ('main_api_calls','meta_api_calls','embedding_api_calls'))
assert scope['automatic_r49_resume'] is False and scope['modify_original_run'] is False
assert review['diagnostic_id']==DIAGNOSTIC_ID and review['verdict']=='ready' and review['scope_complete'] is True and review['trace']
for name in ('controller','chexbench'):
 pid=(j/(name+'.pid')).read_text().strip();assert not Path('/proc',pid).exists(), 'R49_process_active'
mem=int(subprocess.check_output(['nvidia-smi','--id=1','--query-gpu=memory.used','--format=csv,noheader,nounits'],text=True).strip())
assert mem<500, 'GPU1_busy_diagnostic_not_launched'
assert shutil.disk_usage(out).free>3*1024**3, 'insufficient_free_disk'
plan=json.loads((out/'plan.json').read_text())
env=dict(os.environ);env.update(plan['worker_env'])
for name in list(env):
 if name.endswith(('_API_KEY','_AUTH_TOKEN')) or name in ('ANTHROPIC_AUTH_TOKEN','HF_TOKEN'):env.pop(name)
env.update(CUDA_VISIBLE_DEVICES='1',CUDA_LAUNCH_BLOCKING='1',TORCH_SHOW_CPP_STACKTRACES='1',
 HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',MPLBACKEND='Agg',TOKENIZERS_PARALLELISM='false')
command=[plan['python'],'-u',str(out/'diagnostic_runner.py'),'--request',str(out/'request.json')]
if plan.get('cpu_affinity') is not None:command=['taskset','-c',str(plan['cpu_affinity']),*command]
timeout_executable=shutil.which('timeout');assert timeout_executable, 'timeout_supervisor_unavailable'
assert type(plan['timeout_seconds']) is int and plan['timeout_seconds']>0
command=[timeout_executable,'--signal=TERM','--kill-after=10s',str(plan['timeout_seconds'])+'s',*command]
intent={'diagnostic_id':DIAGNOSTIC_ID,'attempt':1,'status':'launch_intent','main_api_calls':0,
 'meta_api_calls':0,'embedding_api_calls':0,'tool_invocations':1,'automatic_r49_resume':False}
with (out/'started.json').open('x') as handle:json.dump(intent,handle,indent=2);handle.flush();os.fsync(handle.fileno())
wrapper=shlex.join(command)+'; rc=$?; printf "%s\n" "$rc" > '+str(out/'exitcode')+'; exit "$rc"'
with (out/'stdout.log').open('xb',buffering=0) as stdout,(out/'stderr.log').open('xb',buffering=0) as stderr:
 p=subprocess.Popen(['bash','-c',wrapper],stdin=subprocess.DEVNULL,stdout=stdout,stderr=stderr,
                    env=env,start_new_session=True)
record={'diagnostic_id':DIAGNOSTIC_ID,'pid':p.pid,'attempt':1,'automatic_retry':False,'automatic_r49_resume':False}
with (out/'launched.json').open('x') as handle:json.dump(record,handle,indent=2)
(out/'pid').write_text(str(p.pid)+'\n')
print(json.dumps(record))
''',timeout=30)


def status(client):
    remote_python(client,definitions()+r'''
from pathlib import Path
import json
out=Path(ATTEMPT)
def read_optional(name):
 path=out/name;return json.loads(path.read_text()) if path.is_file() else None
pid=(out/'pid').read_text().strip() if (out/'pid').is_file() else None
value={'diagnostic_id':DIAGNOSTIC_ID,'prepared':out.is_dir(),'started':(out/'started.json').is_file(),
 'pid':pid,'alive':bool(pid and Path('/proc',pid).exists()),
 'exit':(out/'exitcode').read_text().strip() if (out/'exitcode').is_file() else None,
 'status':read_optional('status.json'),'automatic_r49_resume':False}
if value['exit'] not in (None,'0') and (out/'stderr.log').is_file():
 value['failure_tail']=(out/'stderr.log').read_text(errors='replace').splitlines()[-20:]
print(json.dumps(value))
''',timeout=30)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('mode',choices=('stage','launch','status'))
    args=parser.parse_args()
    with connect() as client:globals()[args.mode](client)
