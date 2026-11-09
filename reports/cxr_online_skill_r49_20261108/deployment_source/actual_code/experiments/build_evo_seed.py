"""Build a frozen train-only multimodal reflection seed for both M1 arms."""
import argparse
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from evo_memory.io import read,write,jsonl,now
from evo_memory.runtime import prepare,budget_preflight,configure,Client,make_messages,RunBlocked
from evo_memory.store import MemoryStore
from evo_memory.retrieve import retrieve
from evo_memory.prompts import REFLECT_SYSTEM,reflection_payload,parse_reflection
from experiments.r1_evidence import explicit_answer
from experiments.v12_evidence import question_parts
from experiments.run_direct_vlm import SYSTEM_PROMPT


def run(args,cfg,rootout):
    selected,evaluation,case_map=prepare(cfg,rootout);budget_preflight(cfg,rootout,selected,evaluation)
    seed=args.out;seed.mkdir(parents=True,exist_ok=True)
    done={p.parent.name:read(p) for p in (seed/'checkpoints').glob('*/done.json')}
    def status(**extra):
        value={'status':'running','stage':'seed','updated_utc':now(),'seed_planned_n':len(selected),'seed_completed_n':len(done),
               'eval_planned_n':60,'predictions_committed':{'E':0,'ES':0},'medical_tool_calls':0}
        value.update(extra);write(rootout/'status.json',value)
    if args.prepare_only:status(status='prepared');print('M1_prepared_no_model_calls');return 0
    if len(done)==len(selected) and (seed/'seed_E.jsonl').exists():return 0
    key=sys.stdin.readline().strip() if args.api_key_stdin else ''
    if not key:raise ValueError('missing_API_key')
    store=MemoryStore(seed/'build_state.json',enable_rules=True,capacity=cfg['rule_capacity'])
    client=Client(cfg,rootout,key,status);del key
    try:
        for number,item in enumerate(selected,1):
            row=item['row'];qid=row['question_id'];case=item['case_id'];folder=seed/'checkpoints'/qid
            if qid in done:continue
            prediction_path=folder/'historical_prediction.json'
            if prediction_path.exists():saved=read(prediction_path)
            elif item['historical_prediction'] is not None:
                saved=dict(item['historical_prediction']);write(prediction_path,saved)
            else:
                text=client.invoke('seed:'+qid,'seed_predict',make_messages(SYSTEM_PROMPT,row['question'],row,cfg),folder/'predict')
                answer=explicit_answer(text,question_parts(row['question'])[1])
                saved={'answer':answer,'raw_response':text,'raw_response_available':text is not None,
                       'source':'new_single_D0_style_historical_prediction','source_model':cfg['model'],
                       'prediction_status':'completed' if answer else 'invalid_answer' if text is not None else 'request_failed'}
                write(prediction_path,saved)
            candidates_path=folder/'reflection_candidates.json'
            if candidates_path.exists():candidates=read(candidates_path)
            else:
                allowed_cases={x['case_id'] for x in selected[:number-1]}
                log,_,candidates,_=retrieve(store,row,step=1,current_case=case,seed_cases=allowed_cases,past_cases=set(),top_k_e=0,top_k_s=2,limit=cfg['context_token_limit'])
                write(folder/'reflection_candidate_retrieval.json',log);write(candidates_path,candidates)
            options=question_parts(row['question'])[1];choice=options.get(saved.get('answer'),'No legal historical answer was available.')
            payload=reflection_payload(row,dict(saved,previous_choice_text=choice),item['reference'],candidates)
            text=client.invoke('seed:'+qid,'seed_reflect',make_messages(REFLECT_SYSTEM,payload,row,cfg),folder/'reflect')
            event='seed:'+qid;result={'question_id':qid,'case_id':case,'reflection_status':'memory_update_failed','utc':now()}
            try:
                reflection=parse_reflection(text)
                if not saved.get('raw_response_available'):
                    reflection['episode']['limitations']='Original historical reasoning was not retained; only the saved choice is known. '+str(reflection['episode'].get('limitations',''))
                store.apply(event,reflection,case_id=case,qid=qid,phase='seed_train',step=0,
                    previous_choice_text=choice,correct_choice_text=item['reference']['correct_choice_text'],allowed_rule_ids=[r['id'] for r in candidates])
                result.update(reflection_status='stored',memory_version=store.state['version'],event_id=event)
            except (ValueError,TypeError,KeyError) as exc:result.update(error_type=type(exc).__name__,error=str(exc))
            write(folder/'done.json',result);done[qid]=result
            if number%10==0 or number==2:print(__import__('json').dumps({'event':'seed_progress','completed':number,'planned':len(selected),'requests_used':client.used,'utc':now()}),flush=True)
            status(requests_used=client.used,extra_requests_used=client.extra)
        episodes=store.state['episodes']
        if not any(e['actionable'] for e in episodes):raise RunBlocked('no_actionable_seed_episodes; refusing_unannounced_cold_start')
        jsonl(seed/'seed_E.jsonl',episodes);write(seed/'seed_S.json',store.state['rules'])
        write(seed/'summary.json',{'status':'seed_complete','case_n':len(selected),'reflections_stored':len(episodes),
                                 'actionable_E_n':sum(e['actionable'] for e in episodes),'S_n':len(store.state['rules']),
                                 'requests_used_after_seed':client.used,'utc':now()})
        status(status='seed_complete',requests_used=client.used,extra_requests_used=client.extra)
        return 0
    finally:client.close()


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--config',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--resume',action='store_true');p.add_argument('--api-key-stdin',action='store_true');p.add_argument('--prepare-only',action='store_true')
    args=p.parse_args(argv);rootout=args.out.resolve().parent;rootout.mkdir(parents=True,exist_ok=True)
    import fcntl
    with (rootout/'.generation.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        try:return run(args,read(args.config),rootout)
        except Exception as exc:
            write(rootout/'fatal_error.json',{'phase':'seed','type':type(exc).__name__,'message':str(exc)[:1800],'utc':now()})
            old=read(rootout/'status.json') if (rootout/'status.json').exists() else {}
            write(rootout/'status.json',dict(old,status='stopped',error_type=type(exc).__name__,updated_utc=now()))
            print(__import__('json').dumps({'status':'stopped','phase':'seed','error_type':type(exc).__name__}),flush=True);return 2


if __name__=='__main__':raise SystemExit(main())
