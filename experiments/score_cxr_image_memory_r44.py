"""Completed sequential-memory comparison using the existing answer metric."""
import argparse
from collections import Counter
from decimal import Decimal
from datetime import datetime
from pathlib import Path
import random
import numpy as np
from cxr_image_memory_r44 import read,rows,write,tool_failure_reason
from score_cxr_author_alignment import adapt,outcomes
from analyze_cxr_author_alignment import terminal,registry
from score_cxr_vqa_extension import cluster_keys,bootstrap


def new_terminal(run,qid,prediction):
    folder=run/'calls/M43-IM'/qid
    actual=sorted(folder.glob('*/started.json'),key=lambda p:int(p.parent.name))
    if not actual:raise ValueError('new_prediction_without_actual_request:'+qid)
    for started in actual:
        base=started.parent
        if not (base/'response.json').exists() or not (base/'result.json').exists():raise ValueError('unknown_sent_request:'+qid)
        result=read(base/'result.json')
        if result.get('error') or result.get('response_received') is not True:raise ValueError('unhealthy_request_receipt:'+qid)
    last=actual[-1].parent
    if int(last.name)!=prediction['main_calls']:raise ValueError('actual_call_count_mismatch:'+qid)
    raw=read(last/'response.json');message=raw['choices'][0]['message'];content=message.get('content')
    if isinstance(content,list):content='\n'.join(x.get('text','') for x in content if isinstance(x,dict) and x.get('type')=='text')
    technical=bool(prediction.get('technical_failure')) or any(x in prediction['status'] for x in ['tool_unhealthy','transport_unknown'])
    unavailable=not isinstance(content,str) or not content.strip()
    nonfinal=bool(message.get('tool_calls')) or bool(message.get('function_call'))
    return {'raw':None if technical or nonfinal or unavailable else content,'call_path':str(last),'ordinal':last.name,'reuse_chain':[],
        'evidence_status':'technical_stop' if technical else 'nonfinal_or_unavailable' if nonfinal or unavailable else 'received_terminal_text',
        'technical_stop':technical}


def resource_report(run,predictions):
    receipts=[read(p) for p in (run/'calls/M43-IM').glob('*/*/result.json')]
    selections=[read(p) for p in (run/'tool_selections/M43-IM').glob('*/*.json')]
    known=[Decimal(x['settlement']['charged_cny']) for x in receipts if x.get('settlement',{}).get('charged_cny') is not None]
    unknown=len(receipts)-len(known)
    return {'new_main_sends':len(list((run/'calls/M43-IM').glob('*/*/started.json'))),
        'new_main_responses':len(list((run/'calls/M43-IM').glob('*/*/response.json'))),
        'logical_tool_selections':len(selections),'cache_hits':sum(bool(x.get('cache_hit')) for x in selections),
        'fresh_tool_attempts':sum(not x.get('cache_hit') for x in selections),
        'completed_backend_model_events':sum(e.get('status')=='completed' for x in selections if not x.get('cache_hit') for e in x.get('actual_model_events',[])),
        'tool_elapsed_seconds':sum(x.get('elapsed_s',0) for x in selections if not x.get('cache_hit')),
        'model_request_elapsed_seconds_known':sum(x['elapsed_s'] for x in receipts if x.get('elapsed_s') is not None),
        'unknown_request_elapsed_count':sum(x.get('elapsed_s') is None for x in receipts),
        'new_episode_elapsed_seconds_known':sum(x['elapsed_s'] for x in predictions if not x.get('reused_M43') and x.get('elapsed_s') is not None),
        'unknown_episode_elapsed_count':sum(not x.get('reused_M43') and x.get('elapsed_s') is None for x in predictions),
        'input_tokens_known':sum((x.get('usage') or {}).get('prompt_tokens',0) for x in receipts),
        'output_tokens_known':sum((x.get('usage') or {}).get('completion_tokens',0) for x in receipts),
        'proxy_cny_known_subtotal':str(sum(known)),'proxy_cny_total':str(sum(known)) if unknown==0 else None,
        'unknown_usage_count':unknown,'provider_invoice':False,'historical_calls_recounted_as_new':False,
        'model_ids':sorted({x.get('model_returned') for x in receipts if x.get('model_returned')})}


def main():
    p=argparse.ArgumentParser()
    for k in ('frozen','run','references','out'):p.add_argument('--'+k,type=Path,required=True)
    p.add_argument('--completion-exit',type=Path)
    p.add_argument('--recovery-dir',type=Path)
    a=p.parse_args();f=read(a.frozen);inputs=f['inputs'];ids={x['question_id'] for x in inputs}
    if a.out.exists():raise ValueError('new_score_output_directory_required')
    if len(inputs)!=618 or len(ids)!=618:raise ValueError('full618_required')
    if (a.completion_exit or a.run/'generation.exitcode').read_text().strip()!='0':raise ValueError('generation_exit_not_zero')
    complete=read(a.run/'complete_M43-IM.json')
    if complete.get('questions')!=618:raise ValueError('incomplete_generation_receipt')
    known=set(complete.get('known_technical_missing_ids',[]))
    if not known<=ids:raise ValueError('technical_missing_outside_cohort')
    if known and (complete.get('completion_mode')!='independent_known_failure_finalization' or complete.get('original_runner_final_exit')!=1):
        raise ValueError('unsupported_effective_completion_receipt')
    if {p.stem for p in (a.run/'predictions/M43-IM').glob('*.json')}!=ids:raise ValueError('prediction_membership')
    if {p.stem for p in (a.run/'memory_context').glob('*.json')}!=ids:raise ValueError('memory_membership')
    specs=[s for s in registry() if s['dataset']=='chexbench' and s['arm']=='M43']
    if len(specs)!=1:raise ValueError('M43_registry_ambiguous')
    key=specs[0]['key'];adapted=[];predictions=[];order={x['question_id']:x for x in f['order']}
    for row in inputs:
        q=row['question_id'];old=f['baseline'][q];new=read(a.run/'predictions/M43-IM'/(q+'.json'))
        trace=read(a.run/'memory_context'/(q+'.json'));item=order[q]
        actual_calls=list((a.run/'calls/M43-IM'/q).glob('*/started.json'))
        selected_paths=sorted((a.run/'tool_selections/M43-IM'/q).glob('*.json'),key=lambda p:int(p.stem))
        main_cap,tool_cap=(6,4) if f['policy'][q]=='C41' else (4,2)
        if len(actual_calls)>main_cap or len(selected_paths)>tool_cap:raise ValueError('per_question_budget_exceeded')
        if q in known:
            recovery_dir=a.recovery_dir or a.run.parent/'recovery'
            note=read(recovery_dir/'known_tool_stops'/(q+'.json'))
            if new.get('status')!='missing_tool_unhealthy_stop' or new.get('technical_failure') is not True or new.get('answer') is not None or new.get('reason') is not None:
                raise ValueError('invalid_technical_terminal')
            bad_keys=[read(path)['cache_key'] for path in selected_paths if tool_failure_reason(read(path))]
            if len(actual_calls)!=note['main_calls'] or len(selected_paths)!=note['tool_calls'] or bad_keys!=note['failed_cache_keys']:
                raise ValueError('technical_prefix_changed_or_reissued')
        if not set(trace['included_ids'])<=set(item['previous_ids']):raise ValueError('future_or_other_image_memory:'+q)
        if trace['previous_ids']!=item['previous_ids']:raise ValueError('changed_sequential_schedule:'+q)
        original=adapt(row,old,terminal('chexbench',key,q))
        if new.get('reused_M43'):
            if trace['memory'] is not None or any(new.get(k)!=old.get(k) for k in ['answer','reason','status']):raise ValueError('incorrect_baseline_reuse:'+q)
            if list((a.run/'calls/M43-IM'/q).glob('*/started.json')):raise ValueError('reused_row_has_new_call:'+q)
            current=dict(original)
        else:current=adapt(row,new,new_terminal(a.run,q,new))
        predictions.append(new);adapted.append((row,original,current,trace,new))
    resources=resource_report(a.run,predictions)
    if resources['new_main_sends']>f['new_main_ceiling'] or resources['logical_tool_selections']>f['new_tool_ceiling']:raise ValueError('cohort_budget_exceeded')
    if resources['logical_tool_selections']!=complete['new_logical_tool_calls']:raise ValueError('tool_count_receipt_mismatch')
    send_times=[read(p)['utc'] for p in (a.run/'calls/M43-IM').glob('*/*/started.json')]
    completed_at=complete.get('completed_at',complete.get('utc'))
    resources['wall_seconds_including_interruptions']=((datetime.fromisoformat(completed_at)-datetime.fromisoformat(min(send_times))).total_seconds()
        if completed_at and send_times else None)
    if resources['new_main_sends']!=complete['new_main_sends'] or resources['new_main_sends']!=resources['new_main_responses']:raise ValueError('unresolved_send_counts')
    failures=[path for path in (a.run/'tool_selections/M43-IM').glob('*/*.json') if tool_failure_reason(read(path))]
    for path in failures:
        q=path.parent.name;prediction=read(a.run/'predictions/M43-IM'/(q+'.json'))
        if q not in known or prediction.get('technical_failure') is not True or prediction.get('answer') is not None:
            raise ValueError('unaccounted_unhealthy_tool')
    # All actual replies/reuse records are adapted before labels are opened.
    references=rows(a.references);refs={r['question_id']:r['answer'] for r in references}
    if len(references)!=618 or set(refs)!=ids:raise ValueError('reference_ids')
    before=[];after=[];details=[]
    for row,o,n,trace,new in adapted:
        q=row['question_id'];ref=refs[q]
        b=outcomes(row,o,ref,random.Random(0))['aligned_correct'];v=outcomes(row,n,ref,random.Random(0))['aligned_correct']
        before.append(int(b));after.append(int(v));details.append({'question_id':q,'question':row['question'],'options':row.get('options'),
            'image_id':row['image_id'],'reference':ref,'M43':o,'M43_IM':n,'before_correct':b,'after_correct':v,
            'sequence_position':len(order[q]['previous_ids'])+1,'same_image_prior_available':bool(order[q]['previous_ids']),
            'memory_included_ids':trace['included_ids'],'reused_M43':bool(new.get('reused_M43'))})
    before=np.array(before);after=np.array(after);delta=after-before
    if int(before.sum())!=466:raise ValueError('baseline_not_published466_check_archive_or_adapter')
    subsets=np.array([r.get('source',{}).get('subset','all') for r in inputs]);by={}
    def counts(mask):
        d=delta[mask];return {'n':int(mask.sum()),'M43':int(before[mask].sum()),'M43_IM':int(after[mask].sum()),
            'corrections':int((d>0).sum()),'harms':int((d<0).sum()),'net':int(d.sum())}
    for subset in sorted(set(subsets)):by[str(subset)]=counts(subsets==subset)
    positions=np.array([x['sequence_position'] for x in details]);reused=np.array([x['reused_M43'] for x in details])
    report={'n':618,'M43':int(before.sum()),'M43_IM':int(after.sum()),'micro_pct':float(after.mean()*100),
        'macro_pct':float(np.mean([x['M43_IM']/x['n'] for x in by.values()])*100),'corrections':int((delta>0).sum()),
        'harms':int((delta<0).sum()),'net':int(delta.sum()),'subsets':by,'paired_interval':bootstrap(delta,cluster_keys(inputs),subsets),
        'by_position':{str(x):counts(positions==x) for x in sorted(set(positions))},
        'by_regeneration':{'reused':counts(reused),'new_with_memory':counts(~reused)},
        'by_image_occurrence':{'first_or_single':counts(positions==1),'repeated':counts(positions>1)},
        'answer_diagnostics':{'M43':dict(Counter(x[1]['extraction'] for x in adapted)),
                              'M43_IM':dict(Counter(x[2]['extraction'] for x in adapted))},
        'resources':resources,'unseen_test_claim':False,
        'limitations':['Exposed development benchmark; earlier same-image questions and model judgments add context.',
            'Historical reused M43 baseline and single regenerated memory arm retain sampling/runtime confounds.',
            'Same-image groups may cross benchmark subsets; no independent-patient generalization claim.']}
    write(a.out/'summary.json',report);write(a.out/'per_question.json',details);print(report)


if __name__=='__main__':main()
