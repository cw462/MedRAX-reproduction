RUN='[REDACTED]'
CODE='[REDACTED]'
PYTHON='[REDACTED]'
RECOVERY='embedding_arrearage_1'
ARM='M43-IM-GT-S49'
ORIGINAL_ID='000063'
RETRY_ID='000063_arrearage_1'
DIAGNOSTIC='[REDACTED]'
EMBED_MODEL='text-embedding-v4'
EMBED_BASE='https://dashscope.aliyuncs.com/compatible-mode/v1'
DATASETS=('chexbench', 'slake', 'vqarad')
COUNTS={'chexbench': 618, 'slake': 114, 'vqarad': 116}
import json
from pathlib import Path
def read(path):
    return json.loads(Path(path).read_text())

def write_once(path,value):
    import os,uuid
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists():
        if read(path)!=value:raise ValueError('immutable_embedding_recovery_record_changed')
        return
    temporary=path.with_name('.'+path.name+'.'+uuid.uuid4().hex+'.tmp')
    try:
        with temporary.open('x') as handle:json.dump(value,handle,ensure_ascii=False,indent=2);handle.write('\n');handle.flush();os.fsync(handle.fileno())
        os.link(temporary,path)
    finally:temporary.unlink(missing_ok=True)

def validate_scope(scope,review,funding):
    expected={'recovery_id':RECOVERY,'uses_existing_r49_authorization':True,'new_user_approval_claimed':False,
      'fresh_production_embedding_limit':1,'same_original_embedding_input':True,'sdk_defaults_unchanged':True,
      'extra_agent_calls_for_repair':0,'extra_meta_calls_for_repair':0,'extra_tool_retries':0,
      'modify_completed_records':False,'automatic_future_embedding_retry':False,'retain_all_prior_overlays':True}
    if any(scope.get(key)!=value for key,value in expected.items()) or not scope.get('authorization_basis'):
        raise ValueError('exact_embedding_recovery_scope_required')
    if review.get('recovery_id')!=RECOVERY or review.get('verdict')!='ready' or review.get('scope_complete') is not True or not review.get('trace'):
        raise ValueError('actual_new_embedding_recovery_review_required')
    if (funding.get('recovery_id')!=RECOVERY or funding.get('provider')!='aliyun_dashscope' or
        funding.get('funding_confirmed') is not True or funding.get('confirmation_source')!='explicit_user_reply' or
        not funding.get('confirmation_reply') or not funding.get('confirmed_at')):
        raise ValueError('explicit_actual_funding_confirmation_required')

def sanitize(value,key):
    if isinstance(value,dict):return {name:sanitize(item,key) for name,item in value.items()}
    if isinstance(value,list):return [sanitize(item,key) for item in value]
    return value.replace(key,'[REDACTED]') if isinstance(value,str) and key else value

def original_failure(folder):
    folder=Path(folder)
    if not all((folder/name).is_file() for name in ('request.json','started.json','result.json')) or (folder/'response.json').exists():
        raise RuntimeError('original_embedding_failure_boundary_changed')
    bundle={name:read(folder/(name+'.json')) for name in ('request','started','result')}
    request=bundle['request'];receipt=bundle['result']
    if (set(request)!={'model','input'} or request['model']!=EMBED_MODEL or not isinstance(request['input'],str) or
        receipt.get('error_type')!='BadRequestError' or receipt.get('response_received') is not False):
        raise RuntimeError('not_the_confirmed_embedding_http_failure')
    return bundle

def embedding_vector(response):
    import math
    data=response.get('data')
    vector=data[0].get('embedding') if isinstance(data,list) and len(data)==1 else None
    if (response.get('model')!=EMBED_MODEL or not isinstance(vector,list) or len(vector)!=1024 or
        any(type(item) not in (int,float) or not math.isfinite(item) for item in vector) or not any(vector)):
        raise ValueError('invalid_retry_embedding_model_or_1024_vector')
    return vector

def retry_once(client,folder,request):
    """One namespaced production attempt; an unknown/failed attempt is never retried."""
    import httpx,time
    from datetime import datetime,timezone
    from openai import APIStatusError,APIConnectionError,APITimeoutError
    folder=Path(folder);key=client.api_key
    if not isinstance(key,str) or not key or str(client.base_url).rstrip('/')!=EMBED_BASE.rstrip('/'):
        raise ValueError('original_embedding_client_identity_required')
    if (folder/'response.json').is_file():
        if read(folder/'request.json')!=request or not (folder/'started.json').is_file():raise ValueError('retry_request_changed')
        receipt=read(folder/'result.json')
        if receipt.get('response_received') is not True or receipt.get('error'):raise RuntimeError('retry_not_healthy_no_reissue')
        response=read(folder/'response.json');embedding_vector(response);return response
    if (folder/'started.json').exists():raise RuntimeError('retry_started_no_reissue_even_if_failure_known')
    folder.mkdir(parents=True,exist_ok=True)
    write_once(folder/'request.json',request)
    write_once(folder/'started.json',{'sent_intent':True,'recovery_id':RECOVERY,'automatic_retry':False,'utc':datetime.now(timezone.utc).isoformat()})
    state={'sent':0};tick=time.monotonic();response=None
    def request_hook(wire):
        if state['sent']:raise RuntimeError('second_embedding_recovery_request_forbidden')
        body=json.loads(wire.read().decode())
        if (wire.method!='POST' or str(wire.url).rstrip('/')!=EMBED_BASE.rstrip('/')+'/embeddings' or
            body.get('model')!=request['model'] or body.get('input')!=request['input']):
            raise ValueError('embedding_recovery_wire_identity_changed')
        # Keep actual SDK-added JSON parameters, never request headers.
        write_once(folder/'wire_request.json',sanitize(body,key));state['sent']=1
    def response_hook(wire):
        wire.read()
        try:body=wire.json()
        except ValueError:body={'non_json_body':wire.text}
        write_once(folder/'http_response.json',sanitize({'http_status':wire.status_code,
          'request_id':wire.headers.get('x-request-id'),'body':body},key))
    try:
        with httpx.Client(event_hooks={'request':[request_hook],'response':[response_hook]},follow_redirects=False,timeout=client.timeout) as http_client:
            with client.with_options(http_client=http_client,max_retries=0) as sdk:
                response=sdk.embeddings.create(**request).model_dump()
        write_once(folder/'response.json',sanitize(response,key));embedding_vector(response)
    except APIStatusError as exc:
        write_once(folder/'error.json',sanitize({'error_type':type(exc).__name__,'http_status':exc.status_code,
          'request_id':getattr(exc,'request_id',None),'body':exc.body},key))
        write_once(folder/'result.json',sanitize({'response_received':True,'error':type(exc).__name__,'error_type':type(exc).__name__,
          'http_status':exc.status_code,'request_id':getattr(exc,'request_id',None),'usage':None,'elapsed_s':time.monotonic()-tick,
          'physical_requests':state['sent'],'automatic_retry':False},key))
        raise RuntimeError('known_embedding_retry_http_failure_stop_no_retry') from None
    except (APIConnectionError,APITimeoutError) as exc:
        write_once(folder/'error.json',{'error_type':type(exc).__name__,'classification':'transport_unknown_no_retry'})
        write_once(folder/'result.json',{'response_received':False,'error':type(exc).__name__,'error_type':type(exc).__name__,
          'usage':None,'elapsed_s':time.monotonic()-tick,'physical_requests':state['sent'],'automatic_retry':False})
        raise RuntimeError('unknown_embedding_retry_send_stop_no_retry') from None
    except Exception as exc:
        write_once(folder/'error.json',{'error_type':type(exc).__name__,'classification':'unexpected_stop_no_retry'})
        write_once(folder/'result.json',{'response_received':response is not None,'error':type(exc).__name__,'error_type':type(exc).__name__,
          'usage':response.get('usage') if isinstance(response,dict) else None,'elapsed_s':time.monotonic()-tick,
          'physical_requests':state['sent'],'automatic_retry':False})
        raise RuntimeError('unexpected_embedding_retry_failure_stop_no_retry') from None
    write_once(folder/'result.json',sanitize({'response_received':True,'model_returned':response.get('model'),'usage':response.get('usage'),
      'elapsed_s':time.monotonic()-tick,'error':None,'physical_requests':state['sent'],'automatic_retry':False,
      'accounting':'embedding_provider_usage_record_only_not_invoice','utc':datetime.now(timezone.utc).isoformat()},key))
    return response

def embedding_overlay(original_embed,services_root,recovery_root,plan):
    """Alias only this exact closed-failure input to its real healthy retry."""
    from datetime import datetime,timezone
    services_root,recovery_root=Path(services_root).resolve(),Path(recovery_root)
    request=plan['original_failure_bundle']['request']
    def embed(self,text):
        if self.out.resolve()!=services_root or text!=request['input']:return original_embed(self,text)
        if self.embed_model!=request['model']:raise ValueError('registered_embedding_model_changed')
        old=original_failure(services_root/'embeddings'/ORIGINAL_ID)
        if old!=plan['original_failure_bundle']:raise ValueError('original_failed_embedding_records_changed')
        retry_folder=services_root/'embeddings'/RETRY_ID
        response=retry_once(self.embedding_client,retry_folder,request)
        vector=embedding_vector(response);receipt=read(retry_folder/'result.json')
        stream=services_root.parent
        path=stream/'failure_events/embedding_arrearage_1_registration.json'
        existing=read(path) if path.is_file() else {}
        registration={'schema':'r49_registered_embedding_http_failure_v1','recovery_id':RECOVERY,'dataset':'chexbench','arm':ARM,
          'original_embedding_id':ORIGINAL_ID,'retry_embedding_id':RETRY_ID,
          'original_call_relative':'services/embeddings/'+ORIGINAL_ID,'retry_call_relative':'services/embeddings/'+RETRY_ID,
          'original_failure_archive_relative':'failure_events/embedding_arrearage_1_original_failure.json',
          'identity':dict(request,endpoint=EMBED_BASE,encoding_format_argument='omitted_preserve_installed_SDK_default'),
          'original_failure':{'error_type':'BadRequestError','http_status':400,'http_status_evidence':'installed_sdk_BadRequestError_status_code_400',
            'sdk_version':plan['sdk_evidence']['sdk_version'],'http_body_missing':True,'specific_body_unknown':True,'response_archive_absent':True},
          'diagnostic':plan['diagnostic'],'retry':{'response_received':True,'model_returned':response['model'],'dimensions':len(vector),
            'usage':response.get('usage'),'elapsed_s':receipt['elapsed_s']},
          'markers':{'scope':'recovery/'+RECOVERY+'/SCOPE.json','review':'recovery/'+RECOVERY+'/REVIEW_READY.json','funding':'recovery/'+RECOVERY+'/FUNDING_CONFIRMED.json'},
          'same_original_request':True,'new_production_embedding_requests':1,'extra_agent_calls_for_repair':0,'extra_meta_calls_for_repair':0,
          'extra_tool_retries':0,'no_encoding_or_text_change':True,'no_automatic_retry':True,'status':'healthy_embedding_retry_registered',
          'utc':existing.get('utc') or datetime.now(timezone.utc).isoformat()}
        write_once(path,registration);write_once(recovery_root/'registration.json',registration)
        return vector
    return embed

def closure_overlay(original_closed,services_root,recovery_root,plan):
    """Recognize only the attested old HTTP failure, not an unknown embedding send."""
    services_root,recovery_root=Path(services_root).resolve(),Path(recovery_root)
    def closed(root,*,require_receipts=False):
        root=Path(root)
        if (root/'services').resolve()!=services_root:
            return original_closed(root,require_receipts=require_receipts)
        validate_scope(read(recovery_root/'SCOPE.json'),read(recovery_root/'REVIEW_READY.json'),read(recovery_root/'FUNDING_CONFIRMED.json'))
        if plan['sdk_evidence']!={'sdk_version':'1.109.1','BadRequestError_status_code':400}:
            raise ValueError('original_sdk_http400_attestation_required')
        bundle=original_failure(services_root/'embeddings'/ORIGINAL_ID)
        if bundle!=plan['original_failure_bundle'] or read(root/'failure_events/embedding_arrearage_1_original_failure.json')!=bundle:
            raise ValueError('original_closed_http400_failure_changed')
        # These are the frozen primitive's existing main/META closure checks.
        for path in (root/'services/calls').glob('*/*/*/started.json'):
            if not (path.parent/'response.json').is_file():
                raise RuntimeError('unknown_sent_no_reissue:'+str(path.parent.relative_to(root)))
            result=path.parent/'result.json'
            if ((require_receipts and not result.is_file()) or
                (result.is_file() and (read(result).get('error') or read(result).get('response_received') is not True))):
                raise RuntimeError('unclosed_request_receipt:'+str(path.parent.relative_to(root)))
        for path in (root/'services/embeddings').glob('*/started.json'):
            if path.parent.resolve()==(services_root/'embeddings'/ORIGINAL_ID).resolve():continue
            if not (path.parent/'response.json').is_file():raise RuntimeError('unknown_embedding_send_no_retry')
        if require_receipts:
            registration=read(root/'failure_events/embedding_arrearage_1_registration.json')
            if (registration!=read(recovery_root/'registration.json') or registration.get('schema')!='r49_registered_embedding_http_failure_v1' or
                registration.get('recovery_id')!=RECOVERY or registration.get('status')!='healthy_embedding_retry_registered' or
                registration.get('identity')!=dict(bundle['request'],endpoint=EMBED_BASE,encoding_format_argument='omitted_preserve_installed_SDK_default') or
                registration.get('original_embedding_id')!=ORIGINAL_ID or registration.get('retry_embedding_id')!=RETRY_ID):
                raise ValueError('healthy_registered_embedding_finalization_required')
            retry=services_root/'embeddings'/RETRY_ID
            if not (retry/'started.json').is_file() or read(retry/'request.json')!=bundle['request']:
                raise ValueError('healthy_retry_request_proof_required')
            receipt=read(retry/'result.json')
            if receipt.get('response_received') is not True or receipt.get('error'):
                raise RuntimeError('healthy_retry_receipt_required')
            embedding_vector(read(retry/'response.json'))
    return closed


import fcntl,os,subprocess,sys,time,shutil
r=Path(RUN);j=r/'jobs';a=r/'recovery'/RECOVERY
lock=(j/'.controller.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
validate_scope(read(a/'SCOPE.json'),read(a/'REVIEW_READY.json'),read(a/'FUNDING_CONFIRMED.json'))
main_key=sys.stdin.buffer.readline();embedding_key=sys.stdin.buffer.readline().strip().decode();assert main_key.strip() and embedding_key
def state(value):
 value.update(recovery=RECOVERY,prior_production_attempts_include_exit1=True)
 path=j/'queue_status.json';temporary=path.with_suffix('.tmp');temporary.write_text(json.dumps(value,indent=2)+'\n');temporary.replace(path)
for ds in DATASETS:
 while True:
  memory=int(subprocess.check_output(['nvidia-smi','--id=1','--query-gpu=memory.used','--format=csv,noheader,nounits'],text=True).strip())
  state({'state':'waiting_gpu1' if memory>=500 else 'ready_gpu1','dataset':ds,'gpu1_used_mib':memory})
  if memory<500:break
  time.sleep(60)
 assert shutil.disk_usage(r).free>3*1024**3
 logfile=j/(ds+'.'+RECOVERY+'.log')
 with logfile.open('xb',buffering=0) as log:
  process=subprocess.Popen([PYTHON,'-u',str(a/'resume_runner.py'),'--dataset',ds],stdin=subprocess.PIPE,stdout=log,stderr=subprocess.STDOUT,
   env=dict(os.environ,R49_EMBEDDING_API_KEY=embedding_key,LANGCHAIN_TRACING_V2='false',LANGSMITH_TRACING='false'))
  (a/(ds+'.pid')).write_text(str(process.pid));(j/(ds+'.pid')).write_text(str(process.pid))
  state({'state':'running_dataset','dataset':ds,'pid':process.pid,'current_attempt_exit':None,'log':str(logfile)})
  process.communicate(main_key)
 rc=process.returncode;(a/(ds+'.exitcode')).write_text(str(rc)+'\n');(j/(ds+'.exitcode')).write_text(str(rc)+'\n')
 out=r/'generation'/ds
 if out.is_dir():(out/'generation.exitcode').write_text(str(rc)+'\n')
 if rc:
  state({'state':'dataset_failed_stop_queue','dataset':ds,'pid':process.pid,'exit_code':rc,'log':str(logfile)})
  raise SystemExit(rc)
 done=read(out/'complete.json');assert done['status']=='generation_complete' and done['questions']==COUNTS[ds]
state({'state':'all_three_datasets_exited_zero_after_embedding_arrearage_recovery','datasets':list(DATASETS)})
