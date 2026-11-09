"""One targeted observation after frozen S1; never route using correctness."""
from __future__ import annotations
import argparse
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import sys
import time
from types import SimpleNamespace
import uuid

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE));sys.path.insert(0,str(HERE.parent))
from run_v9_diagnostic import accounting,append,now,read_jsonl,saved_context,write_json
from run_v11_selection import exception_chain,run_lock
from v11_selection import SELECTOR_PROMPT,parse_choice
from v11_followup import (PLANNER_PROMPT,READER_PROMPT,planner_content,parse_plan,
    apply_plan,reader_content,parse_observation,comparison_with_observation)


def triggered(record):
    selector=record.get('selector') or {}
    return (record.get('route')=='selector' and not record.get('selector_error')
        and selector.get('needs_followup') is True
        and isinstance(selector.get('followup_question'),str)
        and bool(selector['followup_question'].strip()))


def run(a,cfg,out):
    root=Path(cfg['root']);previous=root/cfg['previous_run'];source=root/cfg['source_run']
    if json.loads((previous/'status.json').read_text())['status']!='generation_complete':
        raise ValueError('S1_must_be_complete')
    rows=json.loads((source/'selection.json').read_text(encoding='utf-8'))['rows']
    qids=[r['question_id'] for r in rows]
    s1={r['question_id']:r for r in read_jsonl(previous/'results.jsonl')}
    branches={r['question_id']:r for r in read_jsonl(source/'candidate_results.jsonl') if r['group']==cfg['group']}
    if len(qids)!=60 or len(set(qids))!=60 or set(qids)!=set(s1) or set(qids)!=set(branches):
        raise ValueError('fixed_sixty_required')
    triggers=[q for q in qids if triggered(s1[q])]
    frozen=dict(cfg,question_ids=qids,triggered_question_ids=triggers,labels_loaded=False,
        selector_prompt=SELECTOR_PROMPT,planner_prompt=PLANNER_PROMPT,reader_prompt=READER_PROMPT,
        implementation_sha256={n:hashlib.sha256((HERE/n).read_bytes()).hexdigest()
            for n in ('run_v11_followup.py','v11_followup.py')})
    path=out/'effective_config.json'
    if path.exists() and json.loads(path.read_text(encoding='utf-8'))!=frozen:
        raise ValueError('frozen_followup_configuration_changed')
    if not path.exists():write_json(path,frozen)
    saved=read_jsonl(out/'results.jsonl');done={r['question_id']:r for r in saved}
    if len(saved)!=len(done):raise ValueError('duplicate_terminal_results')
    for q in qids:
        terminal=out/'checkpoints'/q/'terminal.json'
        if q not in done and terminal.exists():
            done[q]=json.loads(terminal.read_text(encoding='utf-8'));append(out/'results.jsonl',done[q])
    def status(state,**extra):
        write_json(out/'status.json',dict(status=state,updated_utc=now(),planned_n=60,completed_n=len(done),
            group=cfg['group'],stage='S2',triggered_n=len(triggers),
            followup_completed=sum(r['route']=='targeted_followup' for r in done.values()),**extra))
    if len(done)==60:status('generation_complete');return 0
    status('prepared')
    print(json.dumps({'event':'prepared','planned_n':60,'triggered_n':len(triggers),'utc':now()}),flush=True)
    if a.prepare_only:return 0
    key=sys.stdin.readline().strip() if a.api_key_stdin else ''
    if not key:raise ValueError('missing_api_key')
    from langchain_openai import ChatOpenAI
    from langchain_core.messages import HumanMessage,SystemMessage,messages_to_dict
    from memory_agent_eval import BudgetedModel
    from run_bc_recovery import new_ctx
    from provider_ledger import ProviderLedger
    from provider_profile import get_profile
    ledger_path=root/cfg['ledger']
    if not ledger_path.is_file():raise ValueError('existing_ledger_required')
    state=json.loads(ledger_path.read_text(encoding='utf-8'))
    if state.get('blocked'):raise ValueError('existing_ledger_blocked')
    profile=get_profile(cfg['model']);cap=state['policy']['cap_cny']
    runtime=SimpleNamespace(tools={'crop_current_image':None},tool_provenance={},model=ChatOpenAI(
        model=profile.model,base_url=profile.base_url,api_key=key,temperature=cfg['temperature'],top_p=cfg['top_p'],
        max_tokens=cfg['max_output_tokens'],max_retries=0,timeout=cfg['request_timeout_seconds']))
    args=SimpleNamespace(max_output_tokens=cfg['max_output_tokens'],max_case_seconds=cfg['max_case_seconds'])
    with ProviderLedger(ledger_path,profile,cap_cny=cap,inherit_ledger_path=root/cfg['inherit_ledger']) as ledger, (out/'execution.trace.jsonl').open('a',encoding='utf-8') as trace:
        if not (out/'ledger_start.json').exists():
            write_json(out/'ledger_start.json',{'committed_cny':state['committed_cny'],'cap_cny':cap,'recorded_utc':now()})
        for row in rows:
            qid=row['question_id']
            if qid in done:continue
            folder=out/'checkpoints'/qid;folder.mkdir(parents=True,exist_ok=True)
            if (folder/'request_started.json').exists():raise RuntimeError('interrupted_request_requires_targeted_recovery:'+qid)
            prior=s1[qid];active=qid in triggers;began,started=time.monotonic(),now()
            result=dict(question_id=qid,group=cfg['group'],stage='S2',initial=prior['initial'],candidate=prior['candidate'],
                final=prior['final'],s1_final=prior['final'],route='targeted_followup' if active else 'inherited_s1',
                selector=prior.get('selector'),selector_error=None if active else prior.get('selector_error'),
                fallback=None if active else prior.get('fallback'),accounting=accounting({}),stop_run=False)
            status('running',active_route=result['route'],active_started_utc=started)
            print(json.dumps({'event':'case_started','index':qids.index(qid)+1,'route':result['route'],'utc':started}),flush=True)
            if active:
                packet=json.loads((previous/'checkpoints'/qid/'comparison.json').read_text(encoding='utf-8'))
                question=prior['selector']['followup_question']
                retrieval_path=Path(branches[qid]['evidence_package']).parent/'retrieval.json'
                retrieval=json.loads(retrieval_path.read_text(encoding='utf-8')) if retrieval_path.exists() else {}
                ctx=new_ctx(qid,str(uuid.uuid4()),[Path(i['path']) for i in packet['images']],runtime,args,trace,1,3)
                ctx['run_id'],ctx['arm']=out.name,'S2_'+cfg['group']
                model=BudgetedModel(runtime.model,ledger,ctx,profile)
                write_json(folder/'request_started.json',{'started_utc':started,'thread_id':ctx['thread_id']})
                def invoke(name,prompt,content):
                    messages=[SystemMessage(content=prompt),HumanMessage(content=content)]
                    response=model.invoke(messages);messages.append(response)
                    write_json(folder/(name+'_messages.json'),messages_to_dict(messages))
                    return response.content
                try:
                    ctx['phase']='action_plan'
                    plan=parse_plan(invoke('plan',PLANNER_PROMPT,planner_content(packet,question,retrieval)),packet)
                    write_json(folder/'action_plan.json',plan)
                    if plan.get('action')=='crop_original':
                        ctx['budget'].reserve('tool','crop_current_image');ctx['actual_tool_attempts']+=1
                    action=apply_plan(packet,plan,folder/'artifacts')
                    write_json(folder/'action.json',action)
                    ctx['phase']='independent_observation'
                    refs=set(packet['refs'])|{i['image_id'] for i in action['images']}
                    observation=parse_observation(invoke('reader',READER_PROMPT,reader_content(packet,question,action)),
                        {i['image_id'] for i in action['images']})
                    write_json(folder/'observation.json',observation)
                    ctx['phase']='symmetric_reselection'
                    choice,payload=parse_choice(invoke('selector',SELECTOR_PROMPT,
                        comparison_with_observation(packet,question,observation,action)),refs|{'followup_observation_1'})
                    result.update(final=packet['private_mapping'][choice],selector=payload,
                        followup_question=question,action=action['action'],new_observation=observation)
                except Exception as exc:
                    result.update(selector_error=type(exc).__name__,fallback='retain_saved_S1')
                    write_json(folder/'error.json',exception_chain(exc))
                result.update(accounting=accounting(ctx),stop_run=ctx.get('stop_run',False),
                    stop_reason=ctx.get('stop_reason') or ctx.get('money_status'))
                write_json(folder/'context.json',saved_context(ctx))
            result['timing']={'started_utc':started,'ended_utc':now(),'elapsed_s':round(time.monotonic()-began,3)}
            write_json(folder/'terminal.json',result);append(out/'results.jsonl',result);done[qid]=result
            print(json.dumps({'event':'case_finished','completed_n':len(done),'route':result['route'],
                'error':result['selector_error'],'elapsed_s':result['timing']['elapsed_s'],'utc':now()}),flush=True)
            if result['stop_run']:status('stopped',reason=result.get('stop_reason'));return 2
        end=json.loads(ledger_path.read_text(encoding='utf-8'));first=json.loads((out/'ledger_start.json').read_text())
        write_json(out/'ledger_final_summary.json',{'start_committed_cny':first['committed_cny'],
            'end_committed_cny':end['committed_cny'],
            'run_increment_cny':str(Decimal(end['committed_cny'])-Decimal(first['committed_cny'])),
            'recorded_utc':now(),'basis':'existing_assumed_rate_ledger_not_invoice'})
    status('generation_complete');return 0


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--prepare-only',action='store_true');p.add_argument('--api-key-stdin',action='store_true')
    a=p.parse_args(argv);cfg=json.loads(a.config.read_text(encoding='utf-8'));out=a.out.resolve();out.mkdir(parents=True,exist_ok=True)
    with run_lock(out):
        try:return run(a,cfg,out)
        except Exception as exc:
            write_json(out/'fatal_error.json',{'utc':now(),'chain':exception_chain(exc)})
            previous=json.loads((out/'status.json').read_text()) if (out/'status.json').exists() else {}
            write_json(out/'status.json',dict(previous,status='stopped',updated_utc=now(),reason=type(exc).__name__))
            raise

if __name__=='__main__':raise SystemExit(main())
