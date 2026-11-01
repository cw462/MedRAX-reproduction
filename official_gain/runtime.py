"""Budgeted saved calls; no memory, retrieval, labels or online feedback."""
import json,os,re,time
from datetime import datetime,timezone
from decimal import Decimal
from pathlib import Path

def now():return datetime.now(timezone.utc).isoformat()
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def write(p,v):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);t=p.with_suffix(p.suffix+'.tmp')
 def scalar(x):
  if type(x).__module__.startswith('numpy'):
   return x.tolist() if hasattr(x,'tolist') else x.item()
  raise TypeError('unsupported_record_type:'+type(x).__name__)
 with t.open('w',encoding='utf-8') as f:json.dump(v,f,ensure_ascii=False,indent=2,allow_nan=False,default=scalar);f.write('\n');f.flush();os.fsync(f.fileno())
 t.replace(p)
def lines(p):return [json.loads(s) for s in Path(p).read_text(encoding='utf-8-sig').splitlines() if s.strip()]
def answer(text,legal):
 # Same label-free rule already disclosed for scoring the previous run.
 # Reading old terminals never invokes this function or changes their fields.
 from experiments.official_gain_answer_scoring import explicit_answer
 return explicit_answer(text,legal)[0]
class StopRun(RuntimeError):pass
class CaseBudget(RuntimeError):pass

FINAL_CALL_INSTRUCTION = ('This is the final permitted model call for this question. '
 'The remaining tool-call budget is 0 and no further model call is available. '
 'Use the original images, the full question and ALL options, and any existing '
 'tool observations already in this conversation to choose the single best legal '
 'option even when an attribute remains uncertain. Do not request or propose '
 'another tool call. Submit Answer: <one legal option letter> followed by a short '
 'evidence reason. Unknown observations remain unknown; do not invent facts.')

def request_tool_parameters(tools,force_final=False):
 """Parameters shared verbatim by the request record and the actual SDK call."""
 if force_final or not tools:return {}
 from langchain_core.utils.function_calling import convert_to_openai_tool
 return {'tools':[convert_to_openai_tool(t) for t in tools],'tool_choice':'auto'}

def request_identifier(cfg,out,folder,ordinal):
 """Stable within a run/resume, distinct across runs sharing the same ledger."""
 namespace=cfg.get('run_id')
 if cfg.get('repaired_execution') and not namespace:
  raise StopRun('repaired_run_requires_explicit_run_id')
 if namespace is not None and (not isinstance(namespace,str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,63}',namespace)):
  raise StopRun('invalid_nonsecret_run_id')
 prefix='official:'+namespace if namespace else 'official'
 value=prefix+':'+Path(folder).relative_to(Path(out)).as_posix().replace('/',':')+':'+str(ordinal)
 if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,179}',value):
  raise StopRun('invalid_stable_request_identifier')
 return value

def encode_tool(value):
 from experiments.worker_bridge import encode_value
 def prepare(v):
  if type(v).__module__.startswith('numpy'):
   return {'__official_numpy__':str(v.dtype),'is_array':getattr(v,'ndim',0)>0,'value':v.tolist()}
  if isinstance(v,tuple):return tuple(prepare(x) for x in v)
  if isinstance(v,list):return [prepare(x) for x in v]
  if isinstance(v,dict):return {k:prepare(x) for k,x in v.items()}
  return v
 return encode_value(prepare(value))

def decode_tool(value):
 from experiments.worker_bridge import decode_value
 def restore(v):
  if isinstance(v,dict) and set(v)=={'__official_numpy__','is_array','value'}:
   import numpy as np
   a=np.asarray(v['value'],dtype=v['__official_numpy__']);return a if v['is_array'] else a[()]
  if isinstance(v,tuple):return tuple(restore(x) for x in v)
  if isinstance(v,list):return [restore(x) for x in v]
  if isinstance(v,dict):return {k:restore(x) for k,x in v.items()}
  return v
 return restore(decode_value(value))

class Client:
 def __init__(self,cfg,out,key,status):
  from langchain_openai import ChatOpenAI
  from experiments.provider_profile import get_profile
  from experiments.v12_ledger import V12ProviderLedger
  self.cfg,self.out,self.status=cfg,Path(out),status;self.profile=get_profile(cfg['model'])
  # Reject an unnamespaced repaired run before opening the shared ledger.
  request_identifier(cfg,self.out,self.out/'predictions'/'probe'/'M'/'calls'/'model_1',1)
  state=read(Path(cfg['root'])/cfg['ledger']);self.cap=state['policy']['cap_cny']
  self.ledger=V12ProviderLedger(Path(cfg['root'])/cfg['ledger'],self.profile,cap_cny=self.cap,inherit_ledger_path=Path(cfg['root'])/cfg['inherit_ledger'])
  self.model=ChatOpenAI(model=cfg['model'],base_url=self.profile.base_url,api_key=key,temperature=cfg['temperature'],top_p=cfg['top_p'],max_tokens=cfg['max_tokens'],timeout=cfg['timeout_seconds'],max_retries=0)
  b=read(self.out/'request_budget.json') if (self.out/'request_budget.json').exists() else {};self.used=b.get('used',0);self.extra=b.get('extra',0)
  if not (self.out/'ledger_start.json').exists():write(self.out/'ledger_start.json',{'committed_cny':str(Decimal(self.cap)-self.ledger.remaining),'utc':now()})
 def close(self):
  try:write(self.out/'ledger_final_summary.json',{'run_increment_cny':str(Decimal(self.cap)-self.ledger.remaining-Decimal(read(self.out/'ledger_start.json')['committed_cny'])),'price_basis':self.profile.price_basis,'provider_invoice':False,'utc':now()})
  finally:self.ledger.close()
 def invoke(self,folder,messages,tools=None,force_final=False):
  from langchain_core.messages import AIMessage
  from langchain_core.messages.utils import convert_to_openai_messages
  from experiments.run_direct_vlm import retryable
  folder=Path(folder);request=folder/'request.json';wire=convert_to_openai_messages(messages)
  tool_parameters=request_tool_parameters(tools,force_final)
  body=dict(model=self.cfg['model'],temperature=self.cfg['temperature'],top_p=self.cfg['top_p'],max_tokens=self.cfg['max_tokens'],messages=wire,**tool_parameters)
  if request.exists():
   saved=read(request)
   if saved!=body:raise StopRun('resume_request_conflict')
  else:write(request,body)
  for ordinal in (1,2):
   d=folder/('attempt_'+str(ordinal));result_path=d/'result.json'
   if result_path.exists():result=read(result_path)
   elif (d/'started.json').exists():
    if not (d/'response.json').exists():raise StopRun('interrupted_unknown_request_not_reissued')
    result=dict(read(d/'started.json'),response_received=True,recovered_saved_response=True)
    write(result_path,result) # original response reused; conservative ledger recovery remains untouched.
   else:
    if self.used>=self.cfg['max_requests'] or ordinal==2 and self.extra>=self.cfg['max_extra_requests']:raise StopRun('persistent_request_budget')
    estimated=sum(len(str(m)) for m in wire)//2+2600
    request_id=request_identifier(self.cfg,self.out,folder,ordinal)
    try:r=self.ledger.reserve(request_id=request_id,estimated_input_tokens=min(estimated,self.profile.max_input_tokens),max_output_tokens=self.cfg['max_tokens'],model=self.cfg['model'],metadata={'arm':folder.parts[-3][:30],'phase':folder.name[:60],'model_call':ordinal})
    except Exception as exc:raise StopRun(type(exc).__name__+':'+str(exc)) from exc
    self.used+=1;self.extra+=int(ordinal==2);result=dict(ordinal=ordinal,started_utc=now(),response_received=False,retryable=False)
    write(d/'started.json',result);write(self.out/'request_budget.json',{'used':self.used,'extra':self.extra});self.status(active_call=str(folder.relative_to(self.out)),requests_used=self.used,extra_requests_used=self.extra)
    response=None;usage=None;error=None;stop=None;began=time.monotonic()
    try:
     # The fourth M call has NO tools schema or tool_choice field. Merely
     # binding the schema with tool_choice=none did not work in the prior run.
     bound=self.model.bind(**tool_parameters) if tool_parameters else self.model
     response=bound.invoke(wire);write(d/'response.json',response.model_dump(mode='json'));usage=response.usage_metadata
     result.update(response_received=True,usage=usage)
     if not self.profile.identity_ok(response.response_metadata.get('model_name')):stop='returned_model_mismatch';error=RuntimeError(stop)
    except Exception as exc:
     error=exc;result.update(error_type=type(exc).__name__,error_message=str(exc)[:1400],retryable=retryable(exc))
     if not result['retryable']:stop=type(exc).__name__
    finally:
     result.update(ended_utc=now(),elapsed_s=round(time.monotonic()-began,3))
     billed={'prompt_tokens':usage['input_tokens'],'completion_tokens':usage['output_tokens']} if usage and 'input_tokens' in usage and 'output_tokens' in usage and error is None else None
     try:result['settlement']=self.ledger.settle(r,usage=billed,response_received=response is not None,error_type=type(error).__name__ if error else None)
     except Exception as exc:stop=type(exc).__name__+':'+str(exc);result['settlement_error']=stop
     if stop:result['stop_reason']=stop
     write(result_path,result)
   if result.get('stop_reason'):raise StopRun(result['stop_reason'])
   if result.get('response_received'):return AIMessage(**read(d/'response.json'))
   if not result.get('retryable') or ordinal==2:return None
   time.sleep(2)

class OfficialModelProxy:
 """Invocation caps, persistence and final-call closure; upstream nodes unchanged."""
 def __init__(self,client,folder,status):self.client,self.folder,self.status=client,Path(folder),status;self.n=0;self.tools=[]
 def bind_tools(self,tools):self.tools=tools;return self
 def invoke(self,messages):
  if self.n>=4:raise CaseBudget('official_four_central_calls_exhausted')
  self.n+=1
  final=self.n==4
  if final:
   from langchain_core.messages import HumanMessage
   messages=list(messages)+[HumanMessage(content=FINAL_CALL_INSTRUCTION)]
  value=self.client.invoke(self.folder/('model_'+str(self.n)),messages,self.tools,force_final=final)
  if value is None:raise CaseBudget('technical_model_failure')
  return value
