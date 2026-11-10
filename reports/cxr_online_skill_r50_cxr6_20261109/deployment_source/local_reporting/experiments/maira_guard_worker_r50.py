import json
from pathlib import Path
CODE='/home/imss/cw/MedRAX_reproduction_20261027/code_cxr_online_skill_r50_cxr6_20261109'
RUN='/home/imss/cw/MedRAX_reproduction_20261027/runs/online_skill_r50_cxr6_20261109'
TOOL='xray_phrase_grounding'
POLICY_ID='maira_unclosed_tag_eos_guard_v1'
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


import contextlib,os,socket,sys,time,traceback
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).parent));sys.path.insert(0,str(Path(CODE)/'experiments'))
from maira_eos_guard_r50 import install_eos_guard
request=json.load(sys.stdin);folder=Path(request['artifact_dir']);folder.mkdir(parents=True,exist_ok=True)
assert request['tool']==TOOL and request['backend']==TOOL and os.environ.get('CUDA_VISIBLE_DEVICES')=='1'
assert read(Path(CODE)/'configs/cxr_vqa_tool_worker_gpu.json')['cuda_visible_devices']=='1'
ready=read(Path(RUN)/'EXECUTION_REVIEW_READY.json')
assert ready['scope_complete'] is True and ready['verdict']=='ready'
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
