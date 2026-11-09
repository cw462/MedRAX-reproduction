"""One isolated MAIRA invocation with record-only generation/decode/exception capture."""
import argparse
import inspect
import json
from pathlib import Path

from deploy_cxr_online_skill_r49 import CODE, ROOT, RUN, connect, remote_python

DIAGNOSTIC_ID='r49_phrase_grounding_diagnostic_20261109'
ATTEMPT=ROOT+'/runs/online_skill_r49_phrase_grounding_diagnostic_20261109/attempt_1'
QID='chexbench_slake_0053'
TOOL='xray_phrase_grounding'
OLD_KEY='b615fd34f038d096aaa2681413f80d45cd25acf9de235ec65ff029dbec90be56'
MODEL_REVISION='795a2b1cd4a310624b4e3d14b5a23e41fd273deb'
LOCAL=Path(__file__).resolve().parents[1]
FAILURE=LOCAL/'local_assets/r49_phrase_grounding_failure_20261109'
SCOPE=FAILURE/'DIAGNOSTIC_EXECUTION_SCOPE.json'
REVIEW=FAILURE/'DIAGNOSTIC_REVIEW_READY.json'
DEST=LOCAL/'local_assets/r49_phrase_grounding_diagnostic_20261109/attempt_1'


def validate_scope(scope,review):
    required={'diagnostic_id':DIAGNOSTIC_ID,'attempt':1,'uses_existing_r49_authorization':True,'new_user_approval_claimed':False,
      'one_isolated_tool_invocation':True,'main_api_calls':0,'meta_api_calls':0,'embedding_api_calls':0,
      'same_original_input_and_settings':True,'modify_original_run':False,'automatic_r49_resume':False,'result_reused_in_R49':False}
    if any(scope.get(key)!=value for key,value in required.items()) or not scope.get('authorization_basis'):
        raise ValueError('exact_phrase_grounding_diagnostic_scope_required')
    if review.get('diagnostic_id')!=DIAGNOSTIC_ID or review.get('verdict')!='ready' or review.get('scope_complete') is not True or not review.get('trace'):
        raise ValueError('actual_new_phrase_grounding_diagnostic_review_required')


def write_once(path,value):
    import os
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x',encoding='utf-8') as handle:
        json.dump(value,handle,ensure_ascii=False,indent=2);handle.write('\n');handle.flush();os.fsync(handle.fileno())


def token_values(value):
    """Copy token IDs only; do not inspect image tensors or model parameters."""
    value=getattr(value,'sequences',value)
    if hasattr(value,'detach'):value=value.detach()
    if hasattr(value,'cpu'):value=value.cpu()
    if hasattr(value,'tolist'):value=value.tolist()
    if isinstance(value,(list,tuple)):return [token_values(item) for item in value]
    if type(value) is int:return value
    raise TypeError('unexpected_token_ids_type')


def capture_tool(tool,captures):
    """Context manager: original results/kwargs survive; swallowed exceptions are visible."""
    import contextlib,sys,traceback
    from unittest.mock import patch
    @contextlib.contextmanager
    def active():
        processor=tool.processor;generate=tool.model.generate
        target=getattr(tool._run,'__func__',tool._run).__code__
        previous=sys.gettrace()
        if previous is not None:raise RuntimeError('unexpected_existing_python_trace')
        def note_error(stage):
            captures['observability_errors'].append({'stage':stage,'traceback':traceback.format_exc()})
        class ProcessorProxy:
            def __getattr__(self,name):return getattr(processor,name)
            def decode(self,*args,**kwargs):
                value=processor.decode(*args,**kwargs)
                try:
                    captures['decodes'].append({'input_token_ids':token_values(args[0]),'kwargs':kwargs,'decoded_text':value})
                except Exception:note_error('decode_record_only')
                return value
            def convert_output_to_plaintext_or_grounded_sequence(self,*args,**kwargs):
                try:captures['conversion_inputs'].append({'text':args[0],'kwargs':kwargs})
                except Exception:note_error('conversion_input_record_only')
                return processor.convert_output_to_plaintext_or_grounded_sequence(*args,**kwargs)
        def observed_generate(*args,**kwargs):
            value=generate(*args,**kwargs)
            try:
                ids=token_values(value);input_ids=kwargs.get('input_ids')
                length=int(input_ids.shape[-1]) if hasattr(input_ids,'shape') else None
                captures['generations'].append({'output_token_ids':ids,'prompt_length':length,
                  'generated_token_ids':[row[length:] for row in ids] if length is not None else None,
                  'max_new_tokens':kwargs.get('max_new_tokens'),'use_cache':kwargs.get('use_cache'),
                  'model_class':type(tool.model).__name__,'model_device':str(getattr(tool.model,'device',None)),
                  'model_dtype':str(getattr(tool.model,'dtype',None))})
            except Exception:note_error('generation_record_only')
            return value
        def local_trace(frame,event,arg):
            if event=='exception':
                try:
                    kind,error,tb=arg
                    captures['swallowed_exceptions'].append({'exception_type':kind.__name__,'exception_module':kind.__module__,
                      'exception_repr':repr(error),'exception_message':str(error),'filename':frame.f_code.co_filename,
                      'line':frame.f_lineno,'traceback':''.join(traceback.format_exception(kind,error,tb))})
                except Exception:note_error('exception_record_only')
            return local_trace
        def trace(frame,event,arg):return local_trace if frame.f_code is target else None
        try:
            tool.processor=ProcessorProxy()
            with patch.object(tool.model,'generate',observed_generate):
                sys.settrace(trace)
                yield
        finally:
            sys.settrace(previous);tool.processor=processor
    return active()


def capture_state(captures,factory_calls,failure):
    tokens=(len(captures['generations'])==1 and captures['generations'][0].get('prompt_length') is not None
      and bool(captures['generations'][0].get('output_token_ids')))
    decoded=(len(captures['decodes'])==1 and isinstance(captures['decodes'][0].get('decoded_text'),str)
      and isinstance(captures['decodes'][0].get('input_token_ids'),list))
    converted=(len(captures['conversion_inputs'])==1 and decoded
      and captures['conversion_inputs'][0]['text']==captures['decodes'][0]['decoded_text'])
    exception=bool(captures['swallowed_exceptions'])
    complete=(len(factory_calls)==1 and tokens and decoded and converted and not captures['observability_errors']
      and (failure not in ('nested_backend_error','analysis_status_not_completed') or exception))
    return {'status':'failed' if failure else ('completed_healthy' if complete else 'observability_failed'),
      'capture_complete':complete,'token_capture_complete':tokens,'decode_capture_complete':decoded,
      'conversion_capture_complete':converted,'exception_recorded':exception}


def definitions():
    values=dict(RUN=RUN,CODE=CODE,ATTEMPT=ATTEMPT,QID=QID,TOOL=TOOL,OLD_KEY=OLD_KEY,MODEL_REVISION=MODEL_REVISION,DIAGNOSTIC_ID=DIAGNOSTIC_ID)
    return '\n'.join(key+'='+repr(value) for key,value in values.items())+'\n'


def shared_source():
    return 'import json\nfrom pathlib import Path\n'+'\n'.join(inspect.getsource(fn) for fn in
      (validate_scope,write_once,token_values,capture_tool,capture_state))+'\n'


RUNNER=r'''
import argparse,contextlib,importlib.metadata,os,socket,sys,time,traceback
from unittest.mock import patch

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--request',required=True,type=Path);args=parser.parse_args()
 out=args.request.parent;request=json.loads(args.request.read_text());plan=json.loads((out/'plan.json').read_text())
 assert out==Path(ATTEMPT) and request['backend']==TOOL and request['tool']==TOOL
 validate_scope(json.loads((out/'EXECUTION_SCOPE.json').read_text()),json.loads((out/'REVIEW_READY.json').read_text()))
 assert request['args']==plan['original_args'] and Path(request['artifact_dir'])==out/'artifacts'
 assert os.environ.get('CUDA_VISIBLE_DEVICES')=='1'
 worker_gpu=json.loads((Path(CODE)/'configs/cxr_vqa_tool_worker_gpu.json').read_text())
 assert worker_gpu['cuda_visible_devices']=='1'
 write_once(out/'worker_started.json',{'diagnostic_id':DIAGNOSTIC_ID,'pid':os.getpid(),'tool_invocations':1,
  'main_api_calls':0,'meta_api_calls':0,'embedding_api_calls':0,'automatic_r49_resume':False})
 captures={'generations':[],'decodes':[],'conversion_inputs':[],'swallowed_exceptions':[],'observability_errors':[]};events=[];began=time.monotonic()
 sys.path.insert(0,str(Path(CODE)/'experiments'))
 def deny_network(*args,**kwargs):raise RuntimeError('phrase_grounding_diagnostic_network_forbidden')
 with contextlib.ExitStack() as stack:
  stack.enter_context(patch.object(socket.socket,'connect',deny_network))
  stack.enter_context(patch.object(socket.socket,'connect_ex',deny_network))
  stack.enter_context(patch.object(socket,'create_connection',deny_network))
  import requests
  stack.enter_context(patch.object(requests.sessions.Session,'request',deny_network))
  import cxr_vqa_tool_worker as worker
  import maira_smoke as smoke
  from cxr_image_memory_r44 import tool_failure_reason
  original_factory=smoke.create_maira_tool;factory_calls=[]
  def factory(*args,**kwargs):
   if factory_calls:raise RuntimeError('second_diagnostic_factory_forbidden')
   tool,provenance=original_factory(*args,**kwargs)
   factory_calls.append({'device':kwargs.get('device'),'tool_name':tool.name,
     'is_loaded_in_8bit':bool(getattr(tool.model,'is_loaded_in_8bit',False)),
     'is_loaded_in_4bit':bool(getattr(tool.model,'is_loaded_in_4bit',False)),
     'model_device':str(tool.model.device),'model_dtype':str(tool.model.dtype),
     'model_revision':provenance['assets'][0]['revision'],'source_commit':provenance['source']['commit']})
   assert factory_calls[-1]['model_revision']==MODEL_REVISION
   stack.enter_context(capture_tool(tool,captures))
   return tool,provenance
  stack.enter_context(patch.object(smoke,'create_maira_tool',factory))
  with contextlib.redirect_stdout(sys.stderr):
   try:
    with worker.inference_events(request,events):result=worker.execute(request)
   except Exception as exc:
    traceback.print_exc(file=sys.stderr)
    write_once(out/'outer_exception.json',{'exception_type':type(exc).__name__,'exception_repr':repr(exc),'traceback':traceback.format_exc()})
    result={'status':'failed','observation':None,'error_type':type(exc).__name__,'error':str(exc)}
  result.update(actual_model_events=events,cuda_visible_devices='1',diagnostic_only=True,
    adapter_revision='cxr-vqa-existing-snapshot-binding-3')
  write_once(out/'result.json',result)
  failure=tool_failure_reason(result)
 for name,value in [('generation_tokens.json',captures['generations']),('decode.json',captures['decodes']),('conversion_inputs.json',captures['conversion_inputs']),
                    ('swallowed_exceptions.json',captures['swallowed_exceptions']),('observability_errors.json',captures['observability_errors']),('factory.json',factory_calls)]:
  write_once(out/name,value)
 versions={}
 for name in ('torch','transformers','bitsandbytes','accelerate'):
  try:versions[name]=importlib.metadata.version(name)
  except importlib.metadata.PackageNotFoundError:versions[name]=None
 capture=capture_state(captures,factory_calls,failure)
 status={'diagnostic_id':DIAGNOSTIC_ID,**capture,'health_failure_reason':failure,
  'elapsed_s':time.monotonic()-began,'tool_invocations':1,'main_api_calls':0,'meta_api_calls':0,'embedding_api_calls':0,
  'automatic_retry':False,'automatic_r49_resume':False,'result_reused_in_R49':False,'original_run_modified':False,
  'generation_records':len(captures['generations']),'decode_records':len(captures['decodes']),'conversion_records':len(captures['conversion_inputs']),
  'swallowed_exception_types':[x['exception_type'] for x in captures['swallowed_exceptions']],
  'observability_error_count':len(captures['observability_errors']),'cuda_visible_devices':os.environ.get('CUDA_VISIBLE_DEVICES'),
  'factory_calls':len(factory_calls),'packages':versions,'generation_arguments_changed':False,'parse_fallback':False}
 write_once(out/'status.json',status);print(json.dumps(status))
 return 1 if failure or not capture['capture_complete'] else 0

if __name__=='__main__':raise SystemExit(main())
'''


GUARD=r'''
r=Path(RUN);out=Path(ATTEMPT);j=r/'jobs'
for name in ('controller','chexbench'):
 pid=(j/(name+'.pid')).read_text().strip();assert not Path('/proc',pid).exists(), 'R49_process_still_active'
 assert (j/(name+'.exitcode')).read_text().strip()=='1'
selection=r/'generation/chexbench/services/tool_selections/R49-AGENT'/QID/'1.json'
failed=json.loads(selection.read_text())
assert failed['tool']==TOOL and failed['backend']==TOOL and failed['cache_key']==OLD_KEY
assert failed['status']=='completed' and failed['observation'][0]['error']==''
assert failed['observation'][1]['analysis_status']=='failed'
assert all(event['status']=='completed' for event in failed.get('actual_model_events',[]))
assert not (r/'generation/chexbench/predictions/M43-IM-GT-S49'/(QID+'.json')).exists()
runtime=json.loads((r/'configs/runtime.json').read_text());spec=runtime['tools'][TOOL]
assert spec['gpu']=='1' and spec['backend']==TOOL and spec['revision']=='MedRAX-dae30e2f136ef0b2a40885a4c335386e9ffad052'
assert '.venv-maira' in str(Path(spec['python']).parent)
assert json.loads((Path(CODE)/'configs/cxr_vqa_tool_worker_gpu.json').read_text())['cuda_visible_devices']=='1'
'''


def stage(client):
    scope=json.loads(SCOPE.read_text(encoding='utf-8'));review=json.loads(REVIEW.read_text(encoding='utf-8'));validate_scope(scope,review)
    remote_python(client,definitions()+'import json\nfrom pathlib import Path\n'+GUARD+r'''
import shutil
assert not out.exists(), 'diagnostic_attempt_exists_inspect_no_restage'
assert shutil.disk_usage(r).free>3*1024**3
out.mkdir(parents=True);(out/'original_failure').mkdir()
cache=r/'generation/chexbench/services/tool_cache'/OLD_KEY
shutil.copyfile(selection,out/'original_failure/selection.json')
for name in ('started.json','result.json','backend.stderr.log'):shutil.copyfile(cache/name,out/'original_failure'/name)
request={'tool':TOOL,'backend':TOOL,'args':dict(failed['identity']['args']),'image':failed['original_image'],
 'artifact_dir':str(out/'artifacts'),'runtime':runtime['backend_config']}
plan={'diagnostic_id':DIAGNOSTIC_ID,'question_id':QID,'question_ordinal':169,'logical_tool_ordinal':1,'attempt':1,
 'original_cache_key':OLD_KEY,'original_selection_file':str(selection),'original_args':dict(failed['identity']['args']),
 'model_revision':MODEL_REVISION,'python':spec['python'],'cpu_affinity':spec.get('cpu_affinity'),
 'timeout_seconds':spec.get('timeout',600),'worker_env':spec.get('worker_env',{}),'physical_gpu':'1',
 'main_api_calls':0,'meta_api_calls':0,'embedding_api_calls':0,'tool_invocations':1,
 'automatic_retry':False,'automatic_r49_resume':False,'result_reused_in_R49':False,'generation_arguments_changed':False,
 'observability':'original_bound_generate_and_decode_return_values_plus_exact_original_run_exception_frame'}
for name,value in [('request.json',request),('plan.json',plan)]:
 with (out/name).open('x') as handle:json.dump(value,handle,ensure_ascii=False,indent=2);handle.write('\n')
print(json.dumps({'prepared':True,'diagnostic_id':DIAGNOSTIC_ID,'tool_calls':0,'api_calls':0}))
''',timeout=30)
    with client.open_sftp() as sftp:
        for name,value in [('EXECUTION_SCOPE.json',scope),('REVIEW_READY.json',review)]:
            with sftp.open(ATTEMPT+'/'+name,'wx') as handle:handle.write(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
        with sftp.open(ATTEMPT+'/diagnostic_runner.py','wx') as handle:handle.write(definitions()+shared_source()+RUNNER)


def launch(client):
    validate_scope(json.loads(SCOPE.read_text(encoding='utf-8')),json.loads(REVIEW.read_text(encoding='utf-8')))
    remote_python(client,definitions()+shared_source()+GUARD+r'''
import fcntl,os,shlex,shutil,subprocess
lock=(out/'.launch.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
assert not (out/'started.json').exists(), 'diagnostic_started_unknown_or_done_no_reissue'
validate_scope(json.loads((out/'EXECUTION_SCOPE.json').read_text()),json.loads((out/'REVIEW_READY.json').read_text()))
memory=int(subprocess.check_output(['nvidia-smi','--id=1','--query-gpu=memory.used','--format=csv,noheader,nounits'],text=True).strip())
assert memory<500, 'GPU1_busy_not_launched'
assert shutil.disk_usage(out).free>3*1024**3, 'insufficient_free_disk'
plan=json.loads((out/'plan.json').read_text());request=json.loads((out/'request.json').read_text())
assert request['args']==failed['identity']['args'] and request['image']==failed['original_image'] and request['runtime']==runtime['backend_config']
env=dict(os.environ);env.update(plan['worker_env'])
for name in list(env):
 if name.endswith(('_API_KEY','_AUTH_TOKEN')) or name in ('ANTHROPIC_AUTH_TOKEN','HF_TOKEN'):env.pop(name)
env.update(CUDA_VISIBLE_DEVICES='1',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',MPLBACKEND='Agg',TOKENIZERS_PARALLELISM='false')
command=[plan['python'],'-u',str(out/'diagnostic_runner.py'),'--request',str(out/'request.json')]
if plan.get('cpu_affinity') is not None:command=['taskset','-c',str(plan['cpu_affinity']),*command]
timeout=shutil.which('timeout');assert timeout and type(plan['timeout_seconds']) is int and plan['timeout_seconds']>0
command=[timeout,'--signal=TERM','--kill-after=10s',str(plan['timeout_seconds'])+'s',*command]
write_once(out/'started.json',{'diagnostic_id':DIAGNOSTIC_ID,'attempt':1,'tool_invocations':1,
 'main_api_calls':0,'meta_api_calls':0,'embedding_api_calls':0,'automatic_retry':False,'automatic_r49_resume':False})
wrapper=shlex.join(command)+'; rc=$?; printf "%s\n" "$rc" > '+str(out/'exitcode')+'; exit "$rc"'
with (out/'stdout.log').open('xb',buffering=0) as stdout,(out/'stderr.log').open('xb',buffering=0) as stderr:
 process=subprocess.Popen(['bash','-c',wrapper],stdin=subprocess.DEVNULL,stdout=stdout,stderr=stderr,env=env,start_new_session=True)
record={'diagnostic_id':DIAGNOSTIC_ID,'pid':process.pid,'attempt':1,'automatic_retry':False,'automatic_r49_resume':False}
write_once(out/'launched.json',record);(out/'pid').write_text(str(process.pid)+'\n');print(json.dumps(record))
''',timeout=30)


def status(client):
    remote_python(client,definitions()+r'''
import json
from pathlib import Path
out=Path(ATTEMPT);pid=(out/'pid').read_text().strip() if (out/'pid').is_file() else None
print(json.dumps({'diagnostic_id':DIAGNOSTIC_ID,'prepared':out.is_dir(),'started':(out/'started.json').is_file(),'pid':pid,
 'alive':bool(pid and Path('/proc',pid).exists()),'exit':(out/'exitcode').read_text().strip() if (out/'exitcode').is_file() else None,
 'status':json.loads((out/'status.json').read_text()) if (out/'status.json').is_file() else None,'automatic_r49_resume':False}))
''',timeout=30)


def pull(client):
    import os,stat
    destination=Path('\\\\?\\'+str(DEST.resolve())) if os.name=='nt' else DEST
    with client.open_sftp() as sftp:
        sftp.stat(ATTEMPT+'/exitcode')  # Pull a closed attempt, including a failed/timeout attempt.
        def walk(remote,local):
            local.mkdir(parents=True,exist_ok=True)
            for item in sftp.listdir_attr(remote):
                if item.filename in ('__pycache__',) or item.filename.startswith('.'):continue
                source=remote+'/'+item.filename;target=local/item.filename
                if stat.S_ISDIR(item.st_mode):walk(source,target)
                elif stat.S_ISREG(item.st_mode) and (target.suffix.lower() in ('.json','.log','.txt','.py','.png','.jpg','.jpeg','.npy') or item.filename in ('pid','exitcode')):
                    if not target.exists():
                        part=target.with_name(target.name+'.download_part');sftp.get(source,str(part),prefetch=False);part.replace(target)
        walk(ATTEMPT,destination)
    print(json.dumps({'evidence':str(DEST),'original_run_modified':False,'result_reused_in_R49':False}))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('mode',choices=('stage','launch','status','pull'))
    args=parser.parse_args()
    with connect() as client:globals()[args.mode](client)
