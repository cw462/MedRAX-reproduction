"""Budgeted saved calls; no memory, retrieval, labels or online feedback."""
import json,os,re,time
from datetime import datetime,timezone
from decimal import Decimal
from pathlib import Path

def now():return datetime.now(timezone.utc).isoformat()
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def write(p,v):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);t=p.with_suffix(p.suffix+'.tmp')
 with t.open('w',encoding='utf-8') as f:json.dump(v,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())
 t.replace(p)
def lines(p):return [json.loads(s) for s in Path(p).read_text(encoding='utf-8-sig').splitlines() if s.strip()]
def answer(text,legal):
 if not isinstance(text,str):return None
 s=text.replace('**','').replace('`','').strip();values=[]
 for ln in s.splitlines():
  m=re.match(r'^\s*Answer\s*:\s*\(?([A-Z])\)?(?:\s*[).:]\s*.*|\s*)$',ln,re.I)
  if m:values.append(m[1].upper())
 if values:return values[0] if len(set(values))==1 and values[0] in legal else None
 return s.upper() if len(s)==1 and s.upper() in legal else None
class StopRun(RuntimeError):pass
class CaseBudget(RuntimeError):pass

class Client:
 def __init__(self,cfg,out,key,status):
  from langchain_openai import ChatOpenAI
  from experiments.provider_profile import get_profile
  from experiments.v12_ledger import V12ProviderLedger
  self.cfg,self.out,self.status=cfg,Path(out),status;self.profile=get_profile(cfg['model'])
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
  from langchain_core.utils.function_calling import convert_to_openai_tool
  from experiments.run_direct_vlm import retryable
  folder=Path(folder);request=folder/'request.json';wire=convert_to_openai_messages(messages)
  schema=[convert_to_openai_tool(t) for t in tools] if tools else []
  body=dict(model=self.cfg['model'],temperature=self.cfg['temperature'],top_p=self.cfg['top_p'],max_tokens=self.cfg['max_tokens'],messages=wire,tools=schema,tool_choice='none' if force_final else 'auto')
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
    request_id='official:'+str(folder.relative_to(self.out)).replace('/' ,':')+':'+str(ordinal)
    try:r=self.ledger.reserve(request_id=request_id,estimated_input_tokens=min(estimated,self.profile.max_input_tokens),max_output_tokens=self.cfg['max_tokens'],model=self.cfg['model'],metadata={'arm':folder.parts[-3][:30],'phase':folder.name[:60],'model_call':ordinal})
    except Exception as exc:raise StopRun(type(exc).__name__+':'+str(exc)) from exc
    self.used+=1;self.extra+=int(ordinal==2);result=dict(ordinal=ordinal,started_utc=now(),response_received=False,retryable=False)
    write(d/'started.json',result);write(self.out/'request_budget.json',{'used':self.used,'extra':self.extra});self.status(active_call=str(folder.relative_to(self.out)),requests_used=self.used,extra_requests_used=self.extra)
    response=None;usage=None;error=None;stop=None;began=time.monotonic()
    try:
     bound=self.model.bind_tools(tools,tool_choice='none' if force_final else 'auto') if tools else self.model
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
 """Only invocation caps/persistence; official Agent's ReAct nodes stay unchanged."""
 def __init__(self,client,folder,status):self.client,self.folder,self.status=client,Path(folder),status;self.n=0;self.tools=[]
 def bind_tools(self,tools):self.tools=tools;return self
 def invoke(self,messages):
  if self.n>=4:raise CaseBudget('official_four_central_calls_exhausted')
  self.n+=1
  # Last turn disables further tool requests to honor the unified central cap.
  value=self.client.invoke(self.folder/('model_'+str(self.n)),messages,self.tools,force_final=self.n==4)
  if value is None:raise CaseBudget('technical_model_failure')
  return value
