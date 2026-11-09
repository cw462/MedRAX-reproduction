"""One reviewed embedding continuation after explicit DashScope funding confirmation."""
import argparse
import inspect
import json
from pathlib import Path

from deploy_cxr_online_skill_r49 import CODE, COUNTS, DATASETS, EMBED_BASE, EMBED_MODEL, PREP, PYTHON, ROOT, RUN, TRANSPORT_HOME, connect, remote_python

RECOVERY='embedding_arrearage_1'
ARM='M43-IM-GT-S49'
ORIGINAL_ID='000063'
RETRY_ID='000063_arrearage_1'
DIAGNOSTIC=ROOT+'/runs/online_skill_r49_embedding_diagnostic_20261109/attempt_1'
SCOPE=PREP/'EMBEDDING_ARREARAGE_RECOVERY_SCOPE.json'
REVIEW=PREP/'EMBEDDING_ARREARAGE_RECOVERY_REVIEW_READY.json'
FUNDING=PREP/'EMBEDDING_FUNDING_CONFIRMED.json'


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


GUARD=r'''
r=Path(RUN);j=r/'jobs';g=r/'generation/chexbench';s=g/'services';a=r/'recovery'/RECOVERY
for name in ('controller','chexbench'):
 pid=(j/(name+'.pid')).read_text().strip();assert not Path('/proc',pid).exists(), 'R49_process_active'
 assert (j/(name+'.exitcode')).read_text().strip()=='1'
assert (g/'generation.exitcode').read_text().strip()=='1'
tail=(j/'chexbench.mutation_fields_2.log').read_text(errors='replace').rstrip().splitlines()
assert tail[-1]=='RuntimeError: embedding_api_failure_no_automatic_retry:BadRequestError', 'different_latest_failure'
ids=[row['question_id'] for row in read(g/'manifest.json')['inputs']];assert len(ids)==618
for name in ('predictions/M43-IM-GT-S49','contexts','prediction_events','feedback','steps'):
 assert {p.stem for p in (g/name).glob('*.json')}==set(ids[:150]), '150_prefix_boundary_changed:'+name
assert {p.parent.name for p in (g/'windows').glob('*/repo.json')}=={'0000','0001','0002','0003'}
assert not (g/'windows/0004/events.json').exists() and not (g/'windows/0004/repo.json').exists()
for arm,count in [('R49-AGENT',372),('R49-META',137)]:
 starts=list((s/'calls'/arm).glob('*/*/started.json'));assert len(starts)==count
 for start in starts:
  assert (start.parent/'response.json').is_file() and (start.parent/'result.json').is_file()
  receipt=read(start.parent/'result.json');assert receipt.get('response_received') is True and not receipt.get('error')
starts=list((s/'embeddings').glob('*/started.json'));assert len(starts)==63
assert len(list((s/'embeddings').glob('*/response.json')))==62
for start in starts:
 if start.parent.name==ORIGINAL_ID:continue
 assert (start.parent/'response.json').is_file() and read(start.parent/'result.json').get('response_received') is True
 assert not read(start.parent/'result.json').get('error')
bundle=original_failure(s/'embeddings'/ORIGINAL_ID)
assert not (s/'embeddings'/RETRY_ID).exists() and not (g/'failure_events/embedding_arrearage_1_registration.json').exists()
assert len(list((s/'tool_selections/R49-AGENT').glob('*/*.json')))==212
assert (r/'recovery/mutation_fields_2/resume_runner.py').is_file()
assert read(g/'failure_events/meta_schema_2_registration.json')['status']=='valid_meta_schema_repair_registered'
for ds in ('slake','vqarad'):
 assert not (j/(ds+'.pid')).exists()
 out=r/'generation'/ds;assert not out.exists() or not any(out.rglob('*.json'))
'''


CONTROLLER=r'''
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
'''


RESUME_RUNNER=r'''
import argparse,runpy,sys
parser=argparse.ArgumentParser();parser.add_argument('--dataset',choices=DATASETS,required=True);args=parser.parse_args()
sys.path.insert(0,str(Path(CODE)/'experiments'))
from skill_services_r49 import Services
import cxr_online_primitives_r49 as primitives
a=Path(RUN)/'recovery'/RECOVERY
validate_scope(read(a/'SCOPE.json'),read(a/'REVIEW_READY.json'),read(a/'FUNDING_CONFIRMED.json'))
plan=read(a/'plan.json');services_root=Path(RUN)/'generation/chexbench/services'
primitives.assert_closed_sends=closure_overlay(primitives.assert_closed_sends,services_root,a,plan)
Services.embed=embedding_overlay(Services.embed,services_root,a,plan)
# Preserve every prior META/field/CUDA wrapper. Do not rerun their controllers.
sys.argv=[str(Path(RUN)/'recovery/mutation_fields_2/resume_runner.py'),'--dataset',args.dataset]
runpy.run_path(sys.argv[0],run_name='__main__')
'''


def definitions():
    values=dict(RUN=RUN,CODE=CODE,PYTHON=PYTHON,RECOVERY=RECOVERY,ARM=ARM,ORIGINAL_ID=ORIGINAL_ID,RETRY_ID=RETRY_ID,
      DIAGNOSTIC=DIAGNOSTIC,EMBED_MODEL=EMBED_MODEL,EMBED_BASE=EMBED_BASE,DATASETS=DATASETS,COUNTS=COUNTS)
    return '\n'.join(key+'='+repr(value) for key,value in values.items())+'\n'


def shared_source():
    return 'import json\nfrom pathlib import Path\n'+'\n'.join(inspect.getsource(fn) for fn in
      (read,write_once,validate_scope,sanitize,original_failure,embedding_vector,retry_once,embedding_overlay,closure_overlay))+'\n'


def stage(client):
    scope,review,funding=read(SCOPE),read(REVIEW),read(FUNDING);validate_scope(scope,review,funding)
    remote_python(client,definitions()+shared_source()+GUARD+r'''
import importlib.metadata,shutil
from openai import BadRequestError
assert importlib.metadata.version('openai')=='1.109.1' and BadRequestError.status_code==400
diagnostic=Path(DIAGNOSTIC);status=read(diagnostic/'status.json');error=read(diagnostic/'error.json')
assert (diagnostic/'exitcode').read_text().strip()=='1'
assert status['diagnostic_id']=='r49_embedding_400_once_20261109' and status['embedding_requests']==1 and status['http_status']==400
assert all(status[key]==0 for key in ('agent_calls','meta_calls','cxr_tool_calls','gpu_calls'))
assert error['body']['code']=='Arrearage' and error['http_status']==400
a.mkdir(parents=True,exist_ok=True)
assert not (a/'plan.json').exists() and not (a/'controller.started.json').exists(), 'embedding_recovery_already_staged'
(a/'prior_jobs').mkdir();(a/'original_failure').mkdir();(a/'diagnostic_evidence').mkdir()
for path in j.iterdir():
 if path.is_file() and path.suffix in ('.json','.log','.pid','.exitcode'):shutil.copyfile(path,a/'prior_jobs'/path.name)
shutil.copyfile(g/'generation.exitcode',a/'prior_generation.exitcode')
for name in ('request.json','started.json','result.json'):shutil.copyfile(s/'embeddings'/ORIGINAL_ID/name,a/'original_failure'/name)
for name in ('scope.json','review_ready.json','request.json','started.json','packages.json','wire_request.json','http_response.json','error.json','status.json','exitcode'):
 shutil.copyfile(diagnostic/name,a/'diagnostic_evidence'/name)
write_once(g/'failure_events/embedding_arrearage_1_original_failure.json',bundle)
plan={'recovery_id':RECOVERY,'original_failure_bundle':bundle,'committed_questions_before':150,'committed_windows_before':4,
 'sdk_evidence':{'sdk_version':importlib.metadata.version('openai'),'BadRequestError_status_code':BadRequestError.status_code},
 'diagnostic':{'diagnostic_id':status['diagnostic_id'],'http_status':400,'error_code':'Arrearage','elapsed_s':status['elapsed_s'],
   'embedding_requests':1,'usage':status.get('usage'),'result_reused_in_R49':False,'original_error_body_reconstructed':False},
 'fresh_production_embedding_limit':1,'previous_wrapper':'recovery/mutation_fields_2/resume_runner.py'}
write_once(a/'plan.json',plan)
print(json.dumps({'staged':True,'recovery_id':RECOVERY,'new_api_calls':0,'committed_questions_preserved':150}))
''',timeout=30)
    with client.open_sftp() as sftp:
        for name,value in [('SCOPE.json',scope),('REVIEW_READY.json',review),('FUNDING_CONFIRMED.json',funding)]:
            with sftp.open(RUN+'/recovery/'+RECOVERY+'/'+name,'w') as handle:handle.write(json.dumps(value,indent=2)+'\n')
        for name,source in [('controller.py',CONTROLLER),('resume_runner.py',RESUME_RUNNER)]:
            with sftp.open(RUN+'/recovery/'+RECOVERY+'/'+name,'w') as handle:handle.write(definitions()+shared_source()+source)


def launch(client):
    remote_python(client,definitions()+shared_source()+GUARD+r'''
import fcntl,os,shlex,subprocess,sys
lock=(j/'.queue_launch.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
assert not (a/'controller.started.json').exists(), 'embedding_recovery_launch_already_claimed'
validate_scope(read(a/'SCOPE.json'),read(a/'REVIEW_READY.json'),read(a/'FUNDING_CONFIRMED.json'))
keys=sys.stdin.buffer.readline()+sys.stdin.buffer.readline();assert len(keys.splitlines())==2
rd,wr=os.pipe();os.write(wr,keys);os.close(wr)
write_once(a/'controller.started.json',{'recovery_id':RECOVERY,'status':'launch_intent','fresh_production_embedding_limit':1,'automatic_retry':False})
command=shlex.join([PYTHON,'-u',str(a/'controller.py')])+'; rc=$?; printf "%s\n" "$rc" > '+str(a/'controller.exitcode')+'; printf "%s\n" "$rc" > '+str(j/'controller.exitcode')+'; exit "$rc"'
try:
 with (a/'controller.log').open('xb',buffering=0) as log:
  process=subprocess.Popen(['bash','-c',command],stdin=rd,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
 record={'recovery_id':RECOVERY,'pid':process.pid,'prior_attempts_include_exit1':True,'frozen_runtime_files_edited':False,'embedding_alias_overlay_declared':True}
 write_once(a/'controller.launched.json',record);(a/'controller.pid').write_text(str(process.pid));(j/'controller.pid').write_text(str(process.pid))
 print(json.dumps(record))
finally:os.close(rd)
''',timeout=30,input_bytes=(TRANSPORT_HOME/'.secrets/token_plan_api.key').read_bytes().strip()+b'\n'+(TRANSPORT_HOME/'.secrets/qwen_api.key').read_bytes().strip()+b'\n')


def status(client):
    remote_python(client,definitions()+r'''
from pathlib import Path
import json,shutil
r=Path(RUN);j=r/'jobs';a=r/'recovery'/RECOVERY
def text(path):return path.read_text().strip() if path.is_file() else None
def phase(name):
 pid=text(a/(name+'.pid'));return {'pid':pid,'alive':bool(pid and Path('/proc',pid).exists()),'exit':text(a/(name+'.exitcode'))}
value={'recovery':RECOVERY,'controller':phase('controller'),'prior_production_attempts_include_exit1':True,
 'queue':json.loads((j/'queue_status.json').read_text()) if (j/'queue_status.json').is_file() else None,
 'registered':(r/'generation/chexbench/failure_events/embedding_arrearage_1_registration.json').is_file(),'datasets':{},'free_bytes':shutil.disk_usage(r).free}
for ds in DATASETS:
 g=r/'generation'/ds;s=g/'services';item=dict(phase(ds),saved=len(list((g/'predictions/M43-IM-GT-S49').glob('*.json'))),
 contexts=len(list((g/'contexts').glob('*.json'))),prediction_events=len(list((g/'prediction_events').glob('*.json'))),feedback=len(list((g/'feedback').glob('*.json'))),
 main_sends=len(list((s/'calls/R49-AGENT').glob('*/*/started.json'))),main_responses=len(list((s/'calls/R49-AGENT').glob('*/*/response.json'))),
 meta_sends=len(list((s/'calls/R49-META').glob('*/*/started.json'))),meta_responses=len(list((s/'calls/R49-META').glob('*/*/response.json'))),
 embeddings_sent=len(list((s/'embeddings').glob('*/started.json'))),embeddings_received=len(list((s/'embeddings').glob('*/response.json'))),
 tools=len(list((s/'tool_selections/R49-AGENT').glob('*/*.json'))),windows=len(list((g/'windows').glob('*/repo.json'))),complete=(g/'complete.json').exists())
 log=j/(ds+'.'+RECOVERY+'.log')
 if item['exit'] not in (None,'0') and log.is_file():item['failure_tail']=log.read_text(errors='replace').splitlines()[-16:]
 value['datasets'][ds]=item
print(json.dumps(value))
''',timeout=30)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('mode',choices=('stage','launch','status'))
    args=parser.parse_args()
    with connect() as client:globals()[args.mode](client)
