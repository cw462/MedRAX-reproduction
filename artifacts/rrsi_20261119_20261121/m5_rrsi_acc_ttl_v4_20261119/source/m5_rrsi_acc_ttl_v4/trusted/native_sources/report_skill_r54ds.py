"""Post-completion scoring and lifecycle funnel. Uses immutable R54 predictions, no API calls."""
import argparse,json
from pathlib import Path
from collections import Counter,defaultdict
from run_online_skill_r54ds import ARM,released_reward
from online_memory_r49 import read,save_once
from cxr_author_alignment import extract,m4cxr_recall

def report(run,historical=None):
    global ARM
    run=Path(run);done=read(run/'complete.json');manifest=read(run/'manifest.json')
    ARM=manifest['arm']
    if done['status']!='generation_complete' or done['arm']!=ARM:raise ValueError('not_complete_R54')
    inputs=manifest['inputs'];ids={r['question_id'] for r in inputs}
    if {p.stem for p in (run/'predictions'/ARM).glob('*.json')}!=ids:raise ValueError('not_full_denominator')
    if len(ids)!=done['questions']:raise ValueError('size_mismatch')
    details=[];sub=defaultdict(list)
    for row in inputs:
        q=row['question_id'];p=read(run/'predictions'/ARM/(q+'.json'));f=read(run/'feedback'/(q+'.json'))
        if p!=f['saved_prediction']:raise ValueError('feedback_prediction_changed')
        c=read(run/'contexts'/(q+'.json'));answer=extract(p.get('terminal_raw'),q,row.get('options')).answer
        value={'question_id':q,'correct':released_reward(row,p,f['reference_annotation']),
               'explicit_answer':answer,'candidate_hit':bool(c['selected_skills']),
               'activated':bool(p.get('activated_skill_ids')),'same_image_hit':bool(p['same_image_ids']),
               'main_calls':p.get('main_calls',0),'tool_calls':p.get('tool_calls',0),
               'word_recall':None if row.get('options') else m4cxr_recall(answer,f['reference_annotation']['answer']) if answer else 0.}
        details.append(value);sub[row.get('source',{}).get('subset','all')].append(value)
    pipeline=Counter();reasons=Counter()
    for window in sorted((run/'windows').iterdir()):
        buf=read(window/'buffer.json');pipeline['retained']+=len(buf['retained'])
        for ok,reason in buf['eligibility'].values():pipeline['eligible']+=int(ok);reasons[reason]+=1
        for a in read(window/'analyses.json').values():pipeline['analysis']+=1;pipeline['analysis_'+a['output_intent']]+=1
        ev=read(window/'events.json')
        for e in ev['write']:
            if 'operation' in e:pipeline['write_'+e['operation']]+=1
            pipeline['initial_rejection']+=int('initial_rejection' in e);pipeline['final_rejection']+=int('rejected' in e)
        for e in ev['credit']:pipeline[e['status']]+=1
        for e in ev['govern']:pipeline['govern_'+e[0]]+=1
    comparison={}
    if historical:
        history=read(historical)
        if {x['question_id'] for x in history}!=ids:raise ValueError('historical_cohort_not_identical')
        by={x['question_id']:x for x in history}
        arms=set.intersection(*(set(x['arms']) for x in history))
        for arm in sorted(arms):
            corrected=sum(x['correct'] and not by[x['question_id']]['arms'][arm]['aligned_correct'] for x in details)
            harmed=sum(not x['correct'] and by[x['question_id']]['arms'][arm]['aligned_correct'] for x in details)
            comparison[arm]={'corrected':corrected,'harmed':harmed,'net':corrected-harmed,
                             'delta_pp':100*(corrected-harmed)/len(details),'causal_skill_effect':False}
    summary={'arm':ARM,'dataset':manifest['dataset'],'questions':len(details),'correct':sum(x['correct'] for x in details),
        'accuracy_pct':100*sum(x['correct'] for x in details)/len(details),
        'missing_answers':sum(x['explicit_answer'] is None for x in details),
        'word_recall_pct':(100*sum(x['word_recall'] for x in details)/len(details)) if all(x['word_recall'] is not None for x in details) else None,
        'candidate_hit_questions':sum(x['candidate_hit'] for x in details),
        'activated_questions':sum(x['activated'] for x in details),'same_image_hit_questions':sum(x['same_image_hit'] for x in details),
        'subsets':{k:{'n':len(v),'correct':sum(x['correct'] for x in v),'accuracy_pct':100*sum(x['correct'] for x in v)/len(v)} for k,v in sub.items()},
        'pipeline':dict(pipeline),'eligibility_reasons':dict(reasons),'historical_comparisons':comparison,
        'agent_calls':sum(x['main_calls'] for x in details),'tool_calls':sum(x['tool_calls'] for x in details),
        'deepseek_writer_received':len(list((run/'services/calls/R54DS-WRITER').glob('*/*/response.json'))),
        'deepseek_writer_validated':sum(read(f)['valid'] for f in (run/'services/calls/R54DS-WRITER').glob('*/*/validation.json')),
        'meta_calls':len(list((run/'services/calls/R49-META').glob('*/1/result.json'))),
        'limitations':'Online post-prediction feedback; paired arm comparison is in pair_summary.json. Candidate/activation/adoption are distinct; adopted credit is not causal gain.'}
    return summary,details
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run',type=Path,required=True);p.add_argument('--historical',type=Path);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    summary,details=report(a.run,a.historical);save_once(a.out/'summary.json',summary);save_once(a.out/'per_question.json',details)
    print(json.dumps(summary,ensure_ascii=False,indent=2))
