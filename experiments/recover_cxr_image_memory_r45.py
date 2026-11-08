"""Account for one inspected known tool failure without changing frozen inference.

No retries or automatic conversion of later failures. A separate effective
completion is allowed only after the unchanged runner reaches its known final
all-tools-healthy audit and every failed selection has an explicit null terminal.
"""
import argparse
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import subprocess
import sys

from cxr_image_memory_r44 import read,write,tool_failure_reason


def calls_for(run,qid):
    calls=sorted((run/'calls/M43-IM'/qid).glob('*/started.json'),key=lambda p:int(p.parent.name))
    for started in calls:
        folder=started.parent
        if not (folder/'response.json').exists() or not (folder/'result.json').exists():raise ValueError('unknown_sent_no_recovery')
        receipt=read(folder/'result.json')
        if receipt.get('error') or receipt.get('response_received') is not True:raise ValueError('unhealthy_main_receipt_no_recovery')
    return calls


def selections_for(run,qid):
    return [(p,read(p)) for p in sorted((run/'tool_selections/M43-IM'/qid).glob('*.json'),key=lambda p:int(p.stem))]


def record_known_stop(root,frozen,qid):
    run=root/'generation';progress=read(run/'progress.json')
    if progress.get('status')!='stopped' or progress.get('question_id')!=qid or 'tool_unhealthy_stop:' not in progress.get('error',''):
        raise ValueError('not_current_inspected_tool_stop')
    if (run/'predictions/M43-IM'/(qid+'.json')).exists():raise ValueError('prediction_already_saved')
    calls=calls_for(run,qid);selections=selections_for(run,qid)
    bad=[(p,x) for p,x in selections if tool_failure_reason(x)]
    if not calls or not bad:raise ValueError('no_definite_tool_failure')
    # Unknown/ongoing tool work cannot be converted into a known failure.
    for path,obs in bad:
        if obs.get('status') not in ('failed','completed'):raise ValueError('unresolved_tool_status')
        if any(e.get('status') not in ('failed','completed') for e in (obs.get('actual_model_events') or [])):
            raise ValueError('unresolved_backend_event')
        if not (run/'tool_cache'/obs['cache_key']/'result.json').is_file():raise ValueError('tool_result_not_final')
    policy=frozen['policy'][qid];main_cap,tool_cap=(6,4) if policy=='C41' else (4,2)
    if len(calls)>main_cap or len(selections)>tool_cap:raise ValueError('policy_budget_exceeded')
    note={'question_id':qid,'diagnosis':'Inspected known tool failure; root cause may remain unknown. No request/tool retry.',
          'main_calls':len(calls),'tool_calls':len(selections),
          'failed_cache_keys':[x['cache_key'] for _,x in bad],
          'failed_tools':[x['tool'] for _,x in bad],
          'failed_selection_ordinals':[p.stem for p,_ in bad],
          'original_progress':progress,'reference_read':False,'operator_known_failure_accounting':True}
    write(root/'recovery/known_tool_stops'/(qid+'.json'),note)
    result={'question_id':qid,'arm':'M43-IM','answer':None,'reason':None,'status':'missing_tool_unhealthy_stop',
        'technical_failure':True,'main_calls':len(calls),'tool_calls':len(selections),
        'new_main_calls':len(calls),'new_tool_calls':len(selections),'reused_M43':False,'terminal_raw':None,
        'observations':[x for _,x in selections if tool_failure_reason(x) is None],
        'elapsed_s':None,'elapsed_status':'interrupted_episode_not_measured',
        'technical_stop_receipt':'recovery/known_tool_stops/'+qid+'.json'}
    write(run/'predictions/M43-IM'/(qid+'.json'),result)
    return note


def finalize_known_failures(root,frozen,child_exit,log):
    run=root/'generation';records={p.stem:read(p) for p in (root/'recovery/known_tool_stops').glob('*.json')}
    if not records:raise ValueError('no_inspected_known_failures')
    lines=log.read_text(errors='replace').splitlines()
    if child_exit!=1 or not lines or lines[-1].strip()!='ValueError: unhealthy_tool_selection':
        raise ValueError('child_did_not_reach_the_expected_final_tool_audit')
    ids={x['question_id'] for x in frozen['inputs']}
    if len(ids)!=618 or len(frozen['inputs'])!=618:raise ValueError('full618_frozen_required')
    if {p.stem for p in (run/'predictions/M43-IM').glob('*.json')}!=ids:raise ValueError('not_all618_predictions')
    if {p.stem for p in (run/'memory_context').glob('*.json')}!=ids:raise ValueError('not_all618_contexts')
    main_total=0;tools_total=0;bad_seen=set()
    for qid in ids:
        prediction=read(run/'predictions/M43-IM'/(qid+'.json'))
        calls=calls_for(run,qid);selections=selections_for(run,qid)
        main_cap,tool_cap=(6,4) if frozen['policy'][qid]=='C41' else (4,2)
        if len(calls)>main_cap or len(selections)>tool_cap:raise ValueError('policy_budget_exceeded:'+qid)
        main_total+=len(calls);tools_total+=len(selections)
        bad=[(p,x) for p,x in selections if tool_failure_reason(x)]
        if bad:
            if qid not in records:raise ValueError('unregistered_new_tool_failure:'+qid)
            note=records[qid]
            if prediction.get('status')!='missing_tool_unhealthy_stop' or prediction.get('technical_failure') is not True:
                raise ValueError('failed_tool_without_technical_terminal')
            if prediction.get('answer') is not None or prediction.get('reason') is not None:raise ValueError('failure_filled_with_answer')
            if len(calls)!=note['main_calls'] or len(selections)!=note['tool_calls']:raise ValueError('inference_reissued_after_failure')
            if [x['cache_key'] for _,x in bad]!=note['failed_cache_keys']:raise ValueError('changed_failed_tool_records')
            if any(tool_failure_reason(x) for x in prediction.get('observations',[])):raise ValueError('failed_evidence_in_memory')
            bad_seen.add(qid)
        elif qid in records:raise ValueError('registered_failure_evidence_missing')
    if bad_seen!=set(records):raise ValueError('unaccounted_known_failure')
    if main_total>frozen['new_main_ceiling'] or tools_total>frozen['new_tool_ceiling']:raise ValueError('cohort_budget_exceeded')
    receipt={'questions':618,'status':'generation_complete_with_known_technical_missing',
        'completion_mode':'independent_known_failure_finalization','original_runner_final_exit':child_exit,
        'known_technical_missing_ids':sorted(records),'new_main_sends':main_total,'new_logical_tool_calls':tools_total,
        'references_read':False,'failed_tools_not_medical_negative_evidence':True,
        'completed_at':datetime.now(timezone.utc).isoformat()}
    write(run/'complete_M43-IM.json',receipt)
    with (run/'generation.effective.exitcode').open('x') as handle:handle.write('0\n')
    return receipt


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--root',type=Path,required=True);p.add_argument('--frozen',type=Path,required=True)
    p.add_argument('--code',type=Path,required=True);p.add_argument('--mode',choices=['record','resume'],required=True)
    p.add_argument('--qid');p.add_argument('--attempt',type=int);p.add_argument('--api-key-stdin',action='store_true')
    a=p.parse_args();f=read(a.frozen)
    import fcntl
    lock=(a.root/'recovery.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    if a.mode=='record':
        if not a.qid:raise ValueError('explicit_inspected_qid_required')
        print(json.dumps(record_known_stop(a.root,f,a.qid)),flush=True);return
    if not a.api_key_stdin or a.attempt is None:raise ValueError('stdin_key_and_explicit_attempt_required')
    key=sys.stdin.buffer.readline();assert key.strip()
    stem=a.root/'jobs'/('recovery_'+str(a.attempt));started=stem.with_suffix('.started.json');log=stem.with_suffix('.child.log')
    if started.exists() or log.exists():raise ValueError('attempt_already_exists')
    write(started,{'controller_pid':os.getpid(),'known_stop_ids':[p.stem for p in (a.root/'recovery/known_tool_stops').glob('*.json')]})
    command=[sys.executable,'-u',str(a.code/'experiments/run_cxr_image_memory_r44.py'),
             '--frozen',str(a.frozen),'--out',str(a.root/'generation'),'--execute','--api-key-stdin']
    with log.open('xb',buffering=0) as output:
        child=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=output,stderr=subprocess.STDOUT)
        write(stem.with_suffix('.child.json'),{'pid':child.pid,'command':command})
        child.communicate(input=key)
    with stem.with_suffix('.child.exitcode').open('x') as handle:handle.write(str(child.returncode)+'\n')
    try:receipt=finalize_known_failures(a.root,f,child.returncode,log)
    except ValueError as exc:
        write(stem.with_suffix('.incomplete.json'),{'child_exit':child.returncode,'reason':str(exc)})
        raise SystemExit(1)
    write(stem.with_suffix('.complete.json'),receipt)
    print('RECOVERED_COHORT_ALL618_ACCOUNTED',flush=True)


if __name__=='__main__':main()
