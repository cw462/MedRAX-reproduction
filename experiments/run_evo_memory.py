"""M1 E/ES: immutable predictions, completed-case feedback, independent updates."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from evo_memory.io import read,write,lines,jsonl,now
from evo_memory.runtime import Client,configure,make_messages,RunBlocked
from evo_memory.store import MemoryStore
from evo_memory.retrieve import retrieve
from evo_memory.feedback import PredictionJournal,FeedbackBroker
from evo_memory.prompts import BASE_SYSTEM,REFLECT_SYSTEM,answer_payload,reflection_payload,parse_reflection
from experiments.r1_evidence import explicit_answer
from experiments.v12_evidence import question_parts


def run(args,cfg,rootout):
    configure(cfg);protocol=read(rootout/'protocol.json')
    if any(protocol.get(k)!=v for k,v in cfg.items()):raise ValueError('frozen_config_changed')
    import hashlib
    for key in ('eval_input','case_index'):
        if hashlib.sha256((Path(cfg['root'])/cfg[key]).read_bytes()).hexdigest()!=protocol['source_fingerprints'][key]:raise ValueError('fixed_input_or_case_map_changed_on_resume')
    seed=args.seed.resolve();stream=args.out.resolve()
    if read(seed/'summary.json')['status']!='seed_complete':raise ValueError('seed_not_complete')
    source=read(rootout/'eval_selection.json');rows=source['rows'];case_map=source['case_map'];row_map={r['question_id']:r for r in rows}
    seed_E=lines(seed/'seed_E.jsonl');seed_S=read(seed/'seed_S.json');seed_cases={e['source_case_id'] for e in seed_E}
    stores={arm:MemoryStore(stream/'arms'/arm/'state.json',episodes=seed_E,rules=seed_S if arm=='ES' else [],enable_rules=arm=='ES',capacity=cfg['rule_capacity']) for arm in cfg['arms']}
    journal=PredictionJournal(stream/'predictions')
    broker=FeedbackBroker(Path(cfg['root'])/cfg['eval_labels_broker_source'],rows,case_map,journal,stream/'feedback',arms=tuple(cfg['arms']))
    def all_records():return [journal.get(r['question_id'],a) for r in rows for a in cfg['arms'] if journal.get(r['question_id'],a) is not None]
    def status(**extra):
        committed=all_records()
        value={'status':'running','stage':'stream','updated_utc':now(),'seed_completed_n':protocol['seed_n'],
               'eval_planned_n':60,'predictions_committed':{a:sum(p['arm']==a for p in committed) for a in cfg['arms']},
               'feedback_case_n':len(broker.released_cases()),'memory_version':{a:s.state['version'] for a,s in stores.items()},'medical_tool_calls':0}
        value.update(extra);write(rootout/'status.json',value)
    key=sys.stdin.readline().strip() if args.api_key_stdin else ''
    if not key:raise ValueError('missing_API_key')
    client=Client(cfg,rootout,key,status);del key
    try:
        for step,row in enumerate(rows,1):
            qid=row['question_id'];case=case_map[qid]
            for arm in cfg['arms']:
                if journal.get(qid,arm) is not None:continue
                if case in broker.released_cases():raise RunBlocked('missing_submitted_prediction_after_feedback; no_rescore_allowed')
                folder=journal.path(qid,arm).parent;store=stores[arm]
                if (folder/'retrieval.json').exists():log=read(folder/'retrieval.json')
                else:
                    log,_,_,visible=retrieve(store,row,step=step,current_case=case,seed_cases=seed_cases,past_cases=broker.released_cases(),
                        top_k_e=cfg['top_k_e'],top_k_s=cfg['top_k_s'] if arm=='ES' else 0,limit=cfg['context_token_limit'])
                    write(folder/'memory_before.json',{'step':step,'case_id':case,'memory_version':store.state['version'],**visible})
                    write(folder/'retrieval.json',log)
                messages=make_messages(BASE_SYSTEM,answer_payload(row,log['memory_context']),row,cfg)
                raw=None;blocked=None;started=now()
                try:raw=client.invoke(qid+':'+arm,'answer_'+arm,messages,stream/'calls'/qid/arm/'answer')
                except RunBlocked as exc:blocked=exc
                answer=explicit_answer(raw,question_parts(row['question'])[1])
                # A genuine failed request is a submitted failure, not a fake not_run.
                call_folder=stream/'calls'/qid/arm/'answer'
                attempted=any(call_folder.glob('attempt_*/started.json'))
                if not attempted and blocked is not None:raise blocked
                prediction={'question_id':qid,'case_id':case,'step':step,'arm':arm,'answer':answer,
                    'status':'completed' if answer else 'invalid_answer' if raw is not None else 'request_failed',
                    'raw_response':raw,'selected_E_ids':log['selected_E_ids'],'selected_S_ids':log['selected_S_ids'],
                    'memory_version':log['memory_version'],'reference_available_to_answer_client':False,
                    'started_utc':started,'committed_utc':now(),'medical_tool_calls':0}
                journal.commit(prediction)
                if blocked is not None:raise blocked
            if broker.ready(case):
                feedback=broker.release(case,step)
                if step==len(rows):
                    write(stream/'last_case_no_reflection.json',{'case_id':case,'step':step,'question_ids':[q for _,q in broker.cases[case]],'reason':'No future query can benefit; feedback released but no reflection paid.'})
                else:
                    for _,past_qid in broker.cases[case]:
                        past_row=row_map[past_qid];reference=feedback['references'][past_qid]
                        for arm in cfg['arms']:
                            folder=stream/'updates'/arm/past_qid
                            if (folder/'done.json').exists():continue
                            store=stores[arm];prediction=journal.get(past_qid,arm)
                            store.selected_feedback('stats:'+arm+':'+past_qid,prediction['selected_S_ids'],prediction['answer']==reference['answer'])
                            before=read(journal.path(past_qid,arm).parent/'memory_before.json')
                            candidates=[r for r in before['rules'] if r['id'] in prediction['selected_S_ids']]
                            saved={'raw_response':prediction['raw_response'],'answer':prediction['answer'],
                                   'previous_choice_text':question_parts(past_row['question'])[1].get(prediction['answer'],'No legal answer was submitted.')}
                            messages=make_messages(REFLECT_SYSTEM,reflection_payload(past_row,saved,reference,candidates),past_row,cfg)
                            text=client.invoke(past_qid+':'+arm,'reflect_'+arm,messages,stream/'calls'/past_qid/arm/'reflect')
                            result={'question_id':past_qid,'arm':arm,'case_id':case,'available_after_step':step,'status':'memory_update_failed','utc':now()}
                            try:
                                reflection=parse_reflection(text)
                                event='online:'+arm+':'+past_qid
                                store.apply(event,reflection,case_id=case,qid=past_qid,phase='past_stream',step=step,
                                    previous_choice_text=saved['previous_choice_text'],correct_choice_text=reference['correct_choice_text'],
                                    allowed_rule_ids=[r['id'] for r in candidates])
                                result.update(status='stored',event_id=event,memory_version=store.state['version'])
                            except (ValueError,KeyError,TypeError) as exc:result.update(error_type=type(exc).__name__,error=str(exc))
                            write(folder/'done.json',result)
            if step%10==0 or step==2:print(json.dumps({'event':'stream_progress','step':step,'planned':60,'requests_used':client.used,'utc':now()}),flush=True)
            status(requests_used=client.used,extra_requests_used=client.extra)
        records=all_records()
        if len(records)!=120:raise ValueError('not_all120_predictions_committed')
        jsonl(stream/'predictions.jsonl',records)
        status(status='generation_complete',requests_used=client.used,extra_requests_used=client.extra,completed_n=60)
        write(stream/'summary.json',{'status':'generation_complete','predictions':120,'feedback_cases':len(broker.released_cases()),'utc':now()})
        return 0
    finally:client.close()


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--config',type=Path,required=True);p.add_argument('--seed',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--resume',action='store_true');p.add_argument('--api-key-stdin',action='store_true');args=p.parse_args(argv)
    rootout=args.out.resolve().parent;rootout.mkdir(parents=True,exist_ok=True)
    import fcntl
    with (rootout/'.generation.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        try:return run(args,read(args.config),rootout)
        except Exception as exc:
            write(rootout/'fatal_error.json',{'phase':'stream','type':type(exc).__name__,'message':str(exc)[:1800],'utc':now()})
            old=read(rootout/'status.json') if (rootout/'status.json').exists() else {}
            write(rootout/'status.json',dict(old,status='stopped',error_type=type(exc).__name__,updated_utc=now()))
            print(json.dumps({'status':'stopped','phase':'stream','error_type':type(exc).__name__}),flush=True);return 2


if __name__=='__main__':raise SystemExit(main())
