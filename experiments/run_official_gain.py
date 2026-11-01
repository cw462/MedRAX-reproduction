"""D/M/P generator: official ReAct vs option-guided visual evidence, no labels."""
import argparse,fcntl,importlib.util,json,os,subprocess,sys,uuid
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]));sys.path.insert(0,str(Path(__file__).resolve().parent))
from official_gain.runtime import read,write,lines,now,answer,Client,OfficialModelProxy,CaseBudget,StopRun

def load_official(repo):
 spec=importlib.util.spec_from_file_location('_gain_official_agent',repo/'medrax/agent/agent.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m.Agent

def prepare(cfg,out):
 from run_direct_vlm import request_for,SYSTEM_PROMPT
 from v12_evidence import question_parts,build_images
 from provider_profile import get_profile
 root=Path(cfg['root']);rows=lines(root/cfg['input']);repo=root/cfg['repo']
 if len(rows)!=60 or len({x['question_id'] for x in rows})!=60 or any(set(x)!={'question_id','question','images'} for x in rows):raise ValueError('fixed_sixty_whitelisted_inputs_required')
 if (out/'protocol.json').exists():
  protocol=read(out/'protocol.json')
  if any(protocol.get(k)!=v for k,v in cfg.items()) or read(out/'selection.json')['rows']!=rows:raise ValueError('frozen_protocol_or_input_conflict')
  return rows,protocol
 commit=subprocess.check_output(['git','-C',str(repo),'rev-parse','HEAD'],text=True).strip()
 if commit!=cfg['official_commit']:raise ValueError('official_snapshot_mismatch')
 cached=root/cfg['direct_cache'];cache_cfg=read(cached/'protocol.json');cache_ok=cache_cfg['system_prompt']==SYSTEM_PROMPT and all(cache_cfg[k]==cfg[k] for k in ('model','temperature','top_p')) and cache_cfg['max_output_tokens']==cfg['max_tokens']
 cache_ok=cache_ok and read(cached/'selection.json')['rows']==rows
 # One compatibility comparison, including exact actual image bytes for all rows.
 for row in rows:
  question_parts(row['question']);build_images(row,root/cfg['image_root'])
  q=cached/'checkpoints'/row['question_id']
  if cache_ok:
   saved=read(q/'request.json')
   cache_ok=saved.get('messages')==request_for(row,root/cfg['image_root']) and saved.get('model')==cfg['model'] and saved.get('temperature')==cfg['temperature'] and saved.get('top_p')==cfg['top_p'] and saved.get('max_tokens')==cfg['max_tokens']
 protocol=dict(cfg,implementation_commit=os.environ.get('MEDRAX_CODE_COMMIT','unrecorded'),direct_cache_reused=cache_ok,initial_system=SYSTEM_PROMPT,reference_labels_read_by_generator=False,normal_request_upper_bound=420 if cache_ok else 480)
 for name,value in [('protocol.json',protocol),('selection.json',{'rows':rows,'planned_n':60})]:
  p=out/name
  if p.exists() and read(p)!=value:raise ValueError('frozen_protocol_or_input_conflict')
  if not p.exists():write(p,value)
 if not (out/'budget_preflight.json').exists():
  profile=get_profile(cfg['model']);state=read(root/cfg['ledger']);maximum=profile.input_cny_per_million*profile.max_input_tokens+profile.output_cny_per_million*cfg['max_tokens'];estimate=maximum*protocol['normal_request_upper_bound']/Decimal(1000000)
  available=Decimal(state['policy']['cap_cny'])-Decimal(state['committed_cny'])
  write(out/'budget_preflight.json',{'normal_request_upper_bound':protocol['normal_request_upper_bound'],'estimated_normal_upper_cny':str(estimate),'remaining_sufficient':available>=estimate,'existing_cap_preserved':True,'not_provider_invoice':True})
  if state.get('blocked') or available<estimate:raise StopRun('existing_budget_cannot_cover_frozen_normal_upper_bound')
 return rows,protocol

def run(cfg,out,prepare_only=False):
 # Must precede any transformers/HF import, including nested vision encoders.
 os.environ.update(HF_HOME=str(Path(cfg['root'])/'models/hf_full'),HF_HUB_CACHE=str(Path(cfg['root'])/'models/hf_full/hub'),TRANSFORMERS_CACHE=str(Path(cfg['root'])/'models/hf_full/hub'),HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',TOKENIZERS_PARALLELISM='false',MPLBACKEND='Agg')
 from run_direct_vlm import request_for
 from v12_evidence import question_parts,build_images,multimodal_content
 from official_gain.evidence_agent import run_p,ToolSession
 rows,protocol=prepare(cfg,out);root=Path(cfg['root']);counts={a:sum((out/'predictions'/r['question_id']/a/'terminal.json').exists() for r in rows) for a in ('D','M','P')}
 def status(state='running',**extra):write(out/'status.json',dict(status=state,updated_utc=now(),completed=counts,planned_n=60,**extra))
 if prepare_only:status('prepared');print(json.dumps({'prepared':True,'cache_D':protocol['direct_cache_reused'],'normal_upper_calls':protocol['normal_request_upper_bound']}));return
 key=sys.stdin.readline().strip()
 if not key:raise ValueError('missing_api_key_on_stdin')
 client=Client(cfg,out,key,status);del key
 try:
  status(stage='D')
  for row in rows:
   q=row['question_id'];folder=out/'predictions'/q/'D';p=folder/'terminal.json'
   if p.exists():continue
   if protocol['direct_cache_reused']:
    original=root/cfg['direct_cache']/'checkpoints'/q
    terminal=read(original/'terminal.json');attempts=sorted(original.glob('attempt_*/response.json'))
    if not attempts:raise StopRun('direct_saved_response_missing')
    raw=read(attempts[-1])['content'];write(folder/'source.json',{'cache':str(original),'request':str(original/'request.json'),'terminal':terminal})
   else:
    response=client.invoke(folder/'calls/direct',request_for(row,root/cfg['image_root']));raw=response.content if response else ''
   write(p,dict(question_id=q,arm='D',answer=answer(raw,question_parts(row['question'])[1]),raw_response=raw,cache_reused=protocol['direct_cache_reused'],committed_utc=now()));counts['D']+=1;status(stage='D')
  status(stage='initializing_six_medical_tools')
  import tool_registry_ext
  runtime_artifacts=out/'artifacts'/('runtime_'+uuid.uuid4().hex);runtime_artifacts.mkdir(parents=True)
  tools,provenance=tool_registry_ext.build_tools(root/cfg['repo'],cache_dir=root/'models/hf_full',classifier_checkpoint=root/'models/home/.torchxrayvision/models_data/nih-pc-chex-mimic_ch-google-openi-kaggle-densenet121-d121-tw-lr001-rot45-tr15-sc15-seed0-best.pt',report_cache=root/'models/hf_report',segmentation_checkpoint=root/'models/home/.torchxrayvision/models_data/pspnet_chestxray_best_model_4.pth',temp_dir=runtime_artifacts,tools=cfg['tools'])
  write(out/'runtime_tools.json',provenance)
  OfficialAgent=load_official(root/cfg['repo'])
  system=(root/cfg['repo']/'medrax/docs/system_prompts.txt').read_text().split('[MEDICAL_ASSISTANT]',1)[1].split('[GENERAL_ASSISTANT]',1)[0].strip()
  write(out/'official_prompt.json',{'system':system,'user_prefix':'Solve using your own vision and reasoning and use tools to complement your reasoning. Trust your own judgement over any tools.','format_adaptation':'Return Answer: <letter> and a short reason; tool budgets are experimental, not upstream policy.'})
  from langchain_core.messages import HumanMessage
  for arm in ('M','P'):
   for i,row in enumerate(rows,1):
    q=row['question_id'];folder=out/'predictions'/q/arm;p=folder/'terminal.json'
    if p.exists():continue
    status(stage=arm,active_question=q,position=i);images=build_images(row,root/cfg['image_root']);direct=read(out/'predictions'/q/'D'/'terminal.json')
    if arm=='P':record=run_p(row,images,direct,client,tools,out,folder)
    else:
     session=ToolSession(tools,images,out,folder,arm);proxy=OfficialModelProxy(client,folder/'calls',status)
     agent=OfficialAgent(proxy,tools=session.proxies(),system_prompt=system,log_tools=False)
     prompt='Solve using your own vision and reasoning and use tools to complement your reasoning. Trust your own judgement over any tools.\n'+row['question']+'\nReturn Answer: <one legal letter> followed by a short reason. The experiment permits at most four medical tool calls and four model calls.'
     raw='';error=None
     try:
      for event in agent.workflow.stream({'messages':[HumanMessage(content=multimodal_content(prompt,images))]},{'recursion_limit':16}):
       if 'process' in event:raw=event['process']['messages'][-1].content
     except StopRun:raise
     except CaseBudget as exc:error={'type':type(exc).__name__,'message':str(exc)[:1600]}
     except Exception as exc:raise StopRun('official_controller_exception:'+type(exc).__name__+':'+str(exc)) from exc
     record=dict(question_id=q,arm=arm,answer=answer(raw,question_parts(row['question'])[1]),raw_response=raw,model_calls=proxy.n,tool_requested=session.requested,tool_actual=session.actual,tool_cache_hits=session.cache_hits,unresolved_prior_tool_results=session.unresolved_prior,new_visual_inputs=0,error=error,committed_utc=now())
     write(folder/'observations.json',session.observations)
    write(p,record);counts[arm]+=1;status(stage=arm,position=i)
  all_predictions=[read(out/'predictions'/r['question_id']/a/'terminal.json') for a in ('D','M','P') for r in rows]
  (out/'predictions.jsonl').write_text(''.join(json.dumps(v,ensure_ascii=False)+'\n' for v in all_predictions),encoding='utf-8');status('generation_complete',requests_used=client.used,extra_requests_used=client.extra)
 except Exception as exc:
  write(out/'fatal_error.json',{'type':type(exc).__name__,'message':str(exc)[:2000],'utc':now()});status('stopped',error_type=type(exc).__name__);raise
 finally:client.close()

def main():
 p=argparse.ArgumentParser();p.add_argument('--config',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--prepare-only',action='store_true');p.add_argument('--resume',action='store_true');p.add_argument('--api-key-stdin',action='store_true');a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
 with (a.out/'.generation.lock').open('a') as lock:
  fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB);run(read(a.config),a.out,a.prepare_only)
if __name__=='__main__':main()
