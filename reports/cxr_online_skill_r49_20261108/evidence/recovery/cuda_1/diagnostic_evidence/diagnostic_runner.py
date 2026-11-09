RUN='[REDACTED]'
CODE='[REDACTED]'
ATTEMPT='[REDACTED]'
QID='chexbench_rad_restruct_0163'
DIAGNOSTIC_ID='r49_chexagent_cuda_once_20261108'
MODEL_REVISION='8f19b53a2eceda4c33b0acec6c81fbc293ad80d0'
VISION_REVISION='f0edbf5d90dba44edb7f4f96d8663537cb0749bf'
EXPECTED_PROMPT='Are there any signs of pleural effusion, pneumothorax, or pleural thickening in the image?'

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
