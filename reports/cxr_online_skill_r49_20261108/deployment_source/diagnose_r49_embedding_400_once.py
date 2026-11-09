"""One neutral embedding diagnostic; no clinical input or production recovery."""
import argparse
import inspect
import json
from pathlib import Path

from deploy_cxr_online_skill_r49 import EMBED_BASE, EMBED_MODEL, PREP, PYTHON, ROOT, TRANSPORT_HOME, connect, remote_python

DIAGNOSTIC_ID='r49_embedding_400_once_20261109'
OUT=ROOT+'/runs/online_skill_r49_embedding_diagnostic_20261109/attempt_1'
NEUTRAL_TEXT='This is a neutral diagnostic sentence.'
SCOPE=PREP/'EMBEDDING_DIAGNOSTIC_SCOPE.json'
REVIEW=PREP/'EMBEDDING_DIAGNOSTIC_REVIEW_READY.json'
LOCAL=Path(__file__).resolve().parents[1]/'local_assets/r49_embedding_diagnostic_20261109'


def validate_scope(scope,review):
    expected={'diagnostic_id':DIAGNOSTIC_ID,'uses_existing_r49_authorization':True,'new_user_approval_claimed':False,
      'neutral_embedding_calls':1,'agent_calls':0,'meta_calls':0,'cxr_tool_calls':0,'gpu_calls':0,
      'send_failed_skill_input':False,'modify_original_run':False,'automatic_r49_resume':False,
      'production_embedding_retry':False,'change_encoding_format':False}
    if any(scope.get(key)!=value for key,value in expected.items()) or not scope.get('authorization_basis'):
        raise ValueError('one_neutral_embedding_diagnostic_scope_required')
    if review.get('diagnostic_id')!=DIAGNOSTIC_ID or review.get('verdict')!='ready' or review.get('scope_complete') is not True or not review.get('trace'):
        raise ValueError('actual_embedding_diagnostic_review_required')


def sanitize(value,key):
    if isinstance(value,dict):return {name:sanitize(item,key) for name,item in value.items()}
    if isinstance(value,list):return [sanitize(item,key) for item in value]
    return value.replace(key,'[REDACTED]') if isinstance(value,str) and key else value


def record(path,value,key):
    with Path(path).open('x',encoding='utf-8') as handle:
        json.dump(sanitize(value,key),handle,ensure_ascii=False,indent=2);handle.write('\n')


def wire_hooks(out,key):
    state={'requests':0}
    def request_hook(request):
        state['requests']+=1
        if state['requests']!=1:raise RuntimeError('second_diagnostic_request_forbidden')
        body=json.loads(request.read().decode('utf-8'))
        if request.method!='POST' or str(request.url).rstrip('/')!=EMBED_BASE.rstrip('/')+'/embeddings' or body.get('model')!=EMBED_MODEL or body.get('input')!=NEUTRAL_TEXT:
            raise RuntimeError('nonneutral_or_wrong_endpoint_request_forbidden')
        # JSON body only: never copy Authorization or other request headers.
        record(out/'wire_request.json',body,key)
    def response_hook(response):
        response.read()
        try:body=response.json()
        except ValueError:body={'non_json_body':response.text}
        record(out/'http_response.json',{'http_status':response.status_code,
          'request_id':response.headers.get('x-request-id'),'body':body},key)
    return {'request':[request_hook],'response':[response_hook]},state


def diagnostic_call(client,out,key,state):
    import math,time
    from openai import APIStatusError,APIConnectionError,APITimeoutError
    began=time.monotonic();code=3
    result={'diagnostic_id':DIAGNOSTIC_ID,'agent_calls':0,'meta_calls':0,'cxr_tool_calls':0,'gpu_calls':0,
      'production_input_reused':False,'production_embedding_retry':False,'automatic_r49_resume':False,
      'requested_model':EMBED_MODEL,'encoding_format_argument':'omitted_preserve_installed_SDK_default',
      'provider_invoice':False}
    try:
        # Deliberately identical SDK argument shape; no encoding/dimension override.
        response=client.embeddings.create(model=EMBED_MODEL,input=NEUTRAL_TEXT).model_dump()
        record(out/'response.json',response,key)
        data=response.get('data');vector=data[0].get('embedding') if isinstance(data,list) and len(data)==1 else None
        valid=isinstance(vector,list) and bool(vector) and all(type(v) in (int,float) and math.isfinite(v) for v in vector)
        valid=valid and response.get('model')==EMBED_MODEL
        result.update(status='completed_healthy' if valid else 'unexpected_response',response_received=True,
          returned_model=response.get('model'),dimensions=len(vector) if isinstance(vector,list) else None,
          usage=response.get('usage'),usable_diagnostic_vector=bool(valid))
        code=0 if valid else 1
    except APIStatusError as exc:
        record(out/'error.json',{'error_type':type(exc).__name__,'http_status':exc.status_code,
          'request_id':getattr(exc,'request_id',None),'body':exc.body},key)
        result.update(status='known_http_error',response_received=True,http_status=exc.status_code,
          error_type=type(exc).__name__,request_id=getattr(exc,'request_id',None),usage=None,usable_diagnostic_vector=False)
        code=1
    except (APIConnectionError,APITimeoutError) as exc:
        record(out/'error.json',{'error_type':type(exc).__name__,'classification':'transport_or_timeout_unknown_no_retry'},key)
        result.update(status='transport_unknown_stop',response_received=False,error_type=type(exc).__name__,usage=None,usable_diagnostic_vector=False)
        code=2
    except Exception as exc:
        record(out/'error.json',{'error_type':type(exc).__name__,'classification':'unexpected_stop_no_retry'},key)
        result.update(status='unexpected_stop',error_type=type(exc).__name__,usage=None,usable_diagnostic_vector=False)
    result.update(embedding_requests=state['requests'],elapsed_s=time.monotonic()-began)
    record(out/'status.json',result,key);(out/'exitcode').write_text(str(code)+'\n')
    return code,result


def shared_source():
    return '\n'.join(inspect.getsource(fn) for fn in (validate_scope,sanitize,record,wire_hooks,diagnostic_call))+'\n'


def definitions(scope=None,review=None):
    return '\n'.join(name+'='+repr(value) for name,value in dict(
      DIAGNOSTIC_ID=DIAGNOSTIC_ID,OUT=OUT,EMBED_MODEL=EMBED_MODEL,EMBED_BASE=EMBED_BASE,NEUTRAL_TEXT=NEUTRAL_TEXT,
      SCOPE_RECORD=scope,REVIEW_RECORD=review).items())+'\n'


def execute(client):
    scope=json.loads(SCOPE.read_text());review=json.loads(REVIEW.read_text());validate_scope(scope,review)
    source=definitions(scope,review)+'import json\nfrom pathlib import Path\n'+shared_source()+r'''
import importlib.metadata,sys
import httpx
from openai import OpenAI
validate_scope(SCOPE_RECORD,REVIEW_RECORD)
out=Path(OUT);assert not out.exists(), 'diagnostic_attempt_exists_no_reissue'
key=sys.stdin.buffer.readline().strip().decode();assert key
out.mkdir(parents=True,exist_ok=False)
record(out/'scope.json',SCOPE_RECORD,key);record(out/'review_ready.json',REVIEW_RECORD,key)
record(out/'request.json',{'model':EMBED_MODEL,'input':NEUTRAL_TEXT},key)
record(out/'started.json',{'diagnostic_id':DIAGNOSTIC_ID,'neutral_embedding_calls':1,'automatic_retry':False},key)
record(out/'packages.json',{name:importlib.metadata.version(name) for name in ('openai','httpx')},key)
hooks,state=wire_hooks(out,key)
with httpx.Client(event_hooks=hooks,follow_redirects=False,timeout=120) as http_client:
 with OpenAI(api_key=key,base_url=EMBED_BASE,max_retries=0,timeout=120,http_client=http_client) as sdk:
  code,result=diagnostic_call(sdk,out,key,state)
print(json.dumps(sanitize(result,key)));raise SystemExit(code)
'''
    remote_python(client,source,timeout=150,input_bytes=(TRANSPORT_HOME/'.secrets/qwen_api.key').read_bytes().strip()+b'\n')


def status(client):
    remote_python(client,definitions()+r'''
from pathlib import Path
import json
out=Path(OUT)
print(json.dumps({'diagnostic_id':DIAGNOSTIC_ID,'started':(out/'started.json').is_file(),
 'status':json.loads((out/'status.json').read_text()) if (out/'status.json').is_file() else None,
 'exit':(out/'exitcode').read_text().strip() if (out/'exitcode').is_file() else None,
 'automatic_r49_resume':False}))
''',timeout=30)


def pull(client):
    LOCAL.mkdir(parents=True,exist_ok=True)
    with client.open_sftp() as sftp:
        for name in ('scope.json','review_ready.json','request.json','started.json','packages.json','wire_request.json',
                     'http_response.json','response.json','error.json','status.json','exitcode'):
            try:sftp.stat(OUT+'/'+name)
            except FileNotFoundError:continue
            target=LOCAL/name
            if not target.exists():sftp.get(OUT+'/'+name,str(target),prefetch=False)
    print(json.dumps({'diagnostic_evidence':str(LOCAL),'production_changed':False}))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('mode',choices=('execute','status','pull'))
    args=parser.parse_args()
    with connect() as client:globals()[args.mode](client)
