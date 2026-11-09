RUN='[REDACTED]'
CODE='[REDACTED]'
ATTEMPT='[REDACTED]'
QID='chexbench_slake_0053'
TOOL='xray_phrase_grounding'
OLD_KEY='b615fd34f038d096aaa2681413f80d45cd25acf9de235ec65ff029dbec90be56'
MODEL_REVISION='795a2b1cd4a310624b4e3d14b5a23e41fd273deb'
DIAGNOSTIC_ID='r49_phrase_grounding_diagnostic_20261109'
import json
from pathlib import Path
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
