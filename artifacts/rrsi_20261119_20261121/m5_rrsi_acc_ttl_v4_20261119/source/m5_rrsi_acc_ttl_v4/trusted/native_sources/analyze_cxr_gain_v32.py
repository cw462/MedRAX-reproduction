"""Completed-pair analysis; historical sensitivity removes one whole JSON fence only."""
import argparse
from collections import Counter
from copy import deepcopy
from datetime import datetime
import json
from pathlib import Path

import numpy as np

from cxr_evidence_v32 import strip_json_fence
from run_cxr_vqa_toolsets import parse_final
from score_cxr_vqa_extension import bootstrap, cluster_keys, grade, rows


def historical_fence(prediction, calls):
    if prediction['status']=='completed':return prediction,False
    replies=[c for c in calls if c.get('response')]
    if not replies:return prediction,False
    message=max(replies,key=lambda c:int(c['ordinal']))['response']['choices'][0]['message']
    raw=message.get('content')
    if message.get('tool_calls') or not isinstance(raw,str):return prediction,False
    stripped=strip_json_fence(raw)
    if stripped==raw:return prediction,False
    parsed=parse_final(stripped)
    return ({**prediction,**parsed},True) if parsed['status']=='completed' else (prediction,False)


def analyze(data,run,historical,dest):
    for arm in ['M-AS','M-A']:
        if not (run/f'complete_{arm}.json').exists():raise ValueError('Both new arms must be complete')
    inputs=rows(data/'inputs.jsonl');ids={r['question_id'] for r in inputs}
    original=rows(historical/'predictions_M.jsonl')
    if {p['question_id'] for p in original}!=ids:raise ValueError('Historical cohort mismatch')
    # Extraction has no reference argument; all recovered outputs retain the original answer strings.
    repaired={};recovery=[]
    for p in original:
        qid=p['question_id'];callfile=historical/'calls/M'/(qid+'.json')
        values=json.loads(callfile.read_text()) if p['status']!='completed' and callfile.exists() else []
        value,changed=historical_fence(p,values);repaired[qid]=value
        recovery.append({'question_id':qid,'changed':changed,'original_answer':p.get('answer'),'answer':value.get('answer')})
    refs={r['question_id']:r['answer'] for r in rows(data/'references.jsonl')}
    if set(refs)!=ids:raise ValueError('Reference cohort mismatch')
    strict=json.loads((run/'offline_score/summary.json').read_text())
    predictions={'M':repaired}
    for arm in ['M-AS','M-A']:
        predictions[arm]={qid:json.loads((run/'predictions'/arm/(qid+'.json')).read_text()) for qid in ids}
    summary=deepcopy(strict);summary['rule']='New arms use their unchanged predictions (generation removes one enclosing JSON fence). Historical M secondary sensitivity strips one complete JSON fence then runs original answer/reason parser. No prose extraction, new aliases, reason inference or semantic interpretation. Original strict score retained separately.'
    summary['historical_M_fence_recovered']=sum(v['changed'] for v in recovery)
    subsets=np.array([r.get('source',{}).get('subset','all') for r in inputs]);clusters=cluster_keys(inputs);scored={};details=[]
    for arm,values in predictions.items():
        evaluated=[grade(row,values[row['question_id']],refs[row['question_id']]) for row in inputs]
        correct=np.array([v[0] for v in evaluated],dtype=int);scored[arm]=correct
        groups={}
        for s in sorted(set(subsets)):
            mask=subsets==s
            groups[str(s)]={'n':int(mask.sum()),'correct':int(correct[mask].sum()),'accuracy_pct':float(correct[mask].mean()*100),'missing':int(sum(v[1] for v,m in zip(evaluated,mask) if m))}
        summary['arms'][arm].update(correct=int(correct.sum()),missing=sum(v[1] for v in evaluated),micro_pct=float(correct.mean()*100),macro_pct=float(np.mean([g['accuracy_pct'] for g in groups.values()])),subsets=groups)
        for row,(good,missing) in zip(inputs,evaluated):details.append({'arm':arm,'question_id':row['question_id'],'answer':values[row['question_id']].get('answer'),'reference':refs[row['question_id']],'correct':bool(good),'missing':bool(missing)})
    for arm in ['M-AS','M-A']:
        delta=scored[arm]-scored['M']
        summary['comparisons'][arm+' vs M']={'corrections':int(sum(delta>0)),'harms':int(sum(delta<0)),'net':int(delta.sum()),'micro_delta_pp':float(delta.mean()*100),'macro_delta_pp':float(np.mean([delta[subsets==s].mean() for s in set(subsets)])*100),'confidence':bootstrap(delta,clusters,subsets),'changes':[{'question_id':r['question_id'],'delta':int(v)} for r,v in zip(inputs,delta) if v]}
    metrics={}
    for arm in ['M-AS','M-A']:
        values=list(predictions[arm].values());starts=[];unknown=[];usages=[]
        for p in (run/'calls'/arm).glob('*/*/started.json'):
            started=json.loads(p.read_text());starts.append(started['utc'])
            if not (p.parent/'response.json').exists():unknown.append(started['request_id'])
            result=p.parent/'result.json'
            if result.exists():
                usage=json.loads(result.read_text()).get('usage')
                if usage:usages.append(usage)
        complete=json.loads((run/f'complete_{arm}.json').read_text())['utc']
        retrieval=[json.loads(p.read_text()) for p in (run/'retrieval'/arm).glob('*.json')]
        metrics[arm]={'questions':len(values),'status_counts':dict(Counter(v['status'] for v in values)),
            'questions_with_tools':sum(v.get('tool_calls',0)>0 for v in values),'main_limit_hits':sum(v.get('main_calls')==6 for v in values),'tool_limit_hits':sum(v.get('tool_calls')==4 for v in values),'format_repair_questions':sum(bool(v.get('format_errors')) for v in values),'format_error_events':sum(len(v.get('format_errors',[])) for v in values),'revised_answers':sum(bool(v.get('revised')) for v in values),'injected_questions':sum(bool(v.get('selected_ids')) for v in retrieval),'retrieval_record_count':len(retrieval),'selected_skill_frequency':dict(Counter(cid for v in retrieval for cid in v.get('selected_ids',[]))),
            'first_send_utc':min(starts),'complete_utc':complete,'wall_seconds':(datetime.fromisoformat(complete)-datetime.fromisoformat(min(starts))).total_seconds(),'unknown_sent_request_ids':unknown,'usage_records':len(usages),'known_input_tokens':sum(v.get('prompt_tokens',0) or 0 for v in usages),'known_output_tokens':sum(v.get('completion_tokens',0) or 0 for v in usages)}
    dest.mkdir(parents=True,exist_ok=False)
    for name,obj in [('mechanical_sensitivity_summary.json',summary),('historical_M_fence_recovery.json',recovery),('behavior_resources.json',metrics)]:
        (dest/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (dest/'mechanical_sensitivity_per_question.jsonl').write_text(''.join(json.dumps(v,ensure_ascii=False)+'\n' for v in details),encoding='utf-8')
    return summary,metrics


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for name in ['data','run','historical','dest']:p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();s,m=analyze(a.data,a.run,a.historical,a.dest)
    print(json.dumps({'historical_M_recovered':s['historical_M_fence_recovered'],'behavior':m}))
