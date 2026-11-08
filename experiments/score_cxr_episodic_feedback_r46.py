"""Once-only completed E pilot score; adapt all replies before reading dev labels."""
import argparse
from collections import Counter
from decimal import Decimal
import json
from pathlib import Path
import numpy as np
from cxr_author_alignment import m4cxr_normalize,m4cxr_recall
from cxr_episodic_feedback_r46 import read,rows,make_protocol,sha,terminal,ARMS
from score_cxr_skill_probe_r44 import adapted as answer_diagnostics


def resources(source,arm):
    receipts=[read(p) for p in (source/'calls'/arm).glob('*/1/result.json')]
    amounts=[Decimal(r['settlement']['charged_cny']) for r in receipts if r.get('settlement',{}).get('charged_cny') is not None]
    unknown=len(receipts)-len(amounts)
    return {'new_main_sends':len(receipts),'responses':sum(r.get('response_received') is True for r in receipts),'tools':0,
      'prompt_tokens':sum((r.get('usage') or {}).get('prompt_tokens',0) for r in receipts),
      'completion_tokens':sum((r.get('usage') or {}).get('completion_tokens',0) for r in receipts),
      'proxy_cny_known_subtotal':str(sum(amounts)),'proxy_cny_total':str(sum(amounts)) if not unknown else None,
      'unknown_usage_count':unknown,'known_request_elapsed_s':sum(r['elapsed_s'] for r in receipts if r.get('elapsed_s') is not None),
      'unknown_elapsed_count':sum(r.get('elapsed_s') is None for r in receipts),'provider_invoice':False}


def score(source,data,out,source_completion_exit=None,source_recovery_jobs=None):
    assert not out.exists(),'new_output_required'
    assert (source_completion_exit or source/'source.exitcode').read_text().strip()=='0'
    assert (source/'development.exitcode').read_text().strip()=='0'
    src=rows(data/'source_inputs.jsonl');inputs=rows(data/'inputs.jsonl');spec=make_protocol(src,inputs,data)
    assert read(source/'protocol.json')==spec
    scomplete=read(source/'source.complete.json');complete=read(source/'development.complete.json')
    if scomplete.get('completion_mode')=='known_progress_metadata_failure_recovery':
        assert (source/'source.exitcode').read_text().strip()=='1' and scomplete['original_source_exit']==1
        assert ((source_recovery_jobs or source.parent/'jobs')/'source_recovery_2.exitcode').read_text().strip()=='0'
        assert scomplete['closed_prefix_cases_reused_without_api']==2 and scomplete['prefix_main_requests_not_retried']==4
    assert scomplete['source_cases']==12 and scomplete['main_calls']==24 and complete['pairs']==27 and complete['main_calls']==54
    ready=read(source/'MEMORY_REVIEW_READY.json');library=source/'approved_E.json'
    assert ready['approved_library_sha256']==complete['approved_E_sha256']==sha(library)
    original_E=read(source/'frozen_E.json');approved_E=read(library)
    assert sha(source/'frozen_E.json')==scomplete['frozen_E_sha256']==approved_E['source_frozen_E_sha256']
    original_by_id={e['question_id']:e for e in original_E['episodes']}
    assert all(original_by_id[e['question_id']]==e for e in approved_E['episodes'])
    source_ids=set(spec['source_question_ids']);ids={x['question_id'] for x in inputs}
    adapted={};accounting={};memory_counts=Counter();memory_nonempty=0
    for arm,expected in [('SOURCE',source_ids),('SOURCE_REFLECT',source_ids),('P0',ids),('P1',ids)]:
        for name in ['started.json','request.json','response.json','result.json']:
            assert {p.parent.parent.name for p in (source/'calls'/arm).glob('*/1/'+name)}==expected,(arm,name)
        for q in expected:
            receipt=read(source/'calls'/arm/q/'1/result.json');assert receipt.get('response_received') is True and not receipt.get('error')
        accounting[arm]=resources(source,arm)
    for arm in ARMS:
        assert {p.stem for p in (source/'predictions'/arm).glob('*.json')}==ids
        for row in inputs:
            q=row['question_id'];pred=read(source/'predictions'/arm/(q+'.json'));ctx=read(source/'contexts'/arm/(q+'.json'))
            assert set(ctx['included_ids'])<=source_ids and (arm=='P1' or not ctx['included_ids'])
            call=read(source/'calls'/arm/q/'1/response.json');value=terminal(call,q);diagnostic=answer_diagnostics(call,q)
            assert pred['answer']==value['answer']==diagnostic['answer'];adapted[q,arm]=diagnostic
            if arm=='P1':
                memory_counts.update(ctx['included_ids']);memory_nonempty+=bool(ctx['included_ids'])
    # Label access boundary: all complete receipts and both reference-free
    # terminal adaptations above precede opening development references.
    references=rows(data/'references.jsonl');assert len(references)==27 and {x['question_id'] for x in references}==ids
    refs={r['question_id']:r for r in references};details=[]
    for row in inputs:
        q=row['question_id'];ref=refs[q];d={'question_id':q,'question':row['question'],'image_id':row['image_id'],
           'reference':ref['answer'],'content_type':ref['content_type']}
        for arm in ARMS:
            val=dict(adapted[q,arm]);ans=val['answer'];val.update(correct=bool(ans is not None and m4cxr_normalize(ans)==m4cxr_normalize(ref['answer'])),
               word_recall=m4cxr_recall(ans,ref['answer']) if ans is not None else 0.0);d[arm]=val
        d['change']='correction' if d['P1']['correct'] and not d['P0']['correct'] else 'harm' if d['P0']['correct'] and not d['P1']['correct'] else 'unchanged'
        details.append(d)
    groups=sorted({r['image_id'] for r in details});n=np.array([sum(r['image_id']==g for r in details) for g in groups])
    diff=np.array([sum(int(r['P1']['correct'])-int(r['P0']['correct']) for r in details if r['image_id']==g) for g in groups])
    draws=np.random.default_rng(20261108).integers(0,len(groups),size=(10000,len(groups)))
    interval=list(np.percentile(100*diff[draws].sum(1)/n[draws].sum(1),[2.5,97.5]))
    changes=Counter(r['change'] for r in details);net=changes['correction']-changes['harm']
    summary={'n':27,'images':8,'arms':{arm:{'correct':sum(r[arm]['correct'] for r in details),
       'missing':sum(r[arm]['answer'] is None for r in details),'accuracy_pct':100*sum(r[arm]['correct'] for r in details)/27,
       'word_recall_mean':sum(r[arm]['word_recall'] for r in details)/27,
       'whole_json_valid':sum(r[arm]['raw_whole_json_valid'] for r in details),
       'original_M_contract_diagnostic':sum(r[arm]['original_M_contract_compliant'] for r in details),
       'by_content_type':{category:{'n':sum(r['content_type']==category for r in details),
           'correct':sum(r['content_type']==category and r[arm]['correct'] for r in details)} for category in sorted({r['content_type'] for r in details})}} for arm in ARMS},
       'corrections':changes['correction'],'harms':changes['harm'],'net':net,'paired_image_interval_pp':interval,
       'resources':accounting,'source_cost_not_recounted_as_development':True,
       'source_completion':{'raw_exit':(source/'source.exitcode').read_text().strip(),
           'effective_exit':(source_completion_exit or source/'source.exitcode').read_text().strip(),
           'mode':scomplete.get('completion_mode','normal'),'source_wall_including_interruptions':scomplete.get('wall_seconds_including_interruption',scomplete.get('elapsed_s'))},
       'development_elapsed_seconds':complete['elapsed_s'],
       'memory':{'approved_source_episodes':len(approved_E['episodes']),'queries':27,'nonempty_queries':memory_nonempty,
           'total_selected':sum(memory_counts.values()),'counts_by_source_id':dict(memory_counts),
           'source_annotation_counts':dict(Counter(e['y'] for e in original_E['episodes'])),
           'gamma_limitation':'source feedback comparison rules, not actionable unlabeled-case diagnostic rules'},
       'source_feedback':'current source annotation after source answer, reflection, memory append; no dev feedback',
       'primary_metric':'common explicit answer + M4CXR EM; JSON diagnostic not an extra primary gate',
       'priority_signal':net>=2 and changes['harm']<=1,'not_unseen_test':True,'overall_best_target_goal_achieved':False}
    out.mkdir(parents=True);(out/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (out/'per_question.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in details),encoding='utf-8')
    return summary


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for key in ['source','data','out']:p.add_argument('--'+key,type=Path,required=True)
    p.add_argument('--source-completion-exit',type=Path)
    p.add_argument('--source-recovery-jobs',type=Path)
    a=p.parse_args();print(json.dumps(score(a.source,a.data,a.out,a.source_completion_exit,a.source_recovery_jobs)))
