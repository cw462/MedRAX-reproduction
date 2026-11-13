"""R54 event sampling and strict candidate selection. No model/tool changes."""
import copy,json
from collections import Counter
import skill_lifecycle_r49 as old
DEFAULTS=copy.deepcopy(old.DEFAULTS)
DEFAULTS.update(top_k=4,window=30,buffer=20,max_active_per_step=1,max_activated_per_question=2,
                cold_boundaries=[10,20,30],govern_questions=60)

def windows(n):
    start=0
    for end in [10,20,30]+list(range(60,n+30,30)):
        end=min(end,n)
        if end>start:yield start,end
        start=end
        if start==n:return

def image_key(t):
    row=t['row'];return str(row.get('image_id') or tuple(row.get('images',[])))

def eligibility(t):
    if any(t.get(k) for k in ('technical_failure','max_step_failure','repeated_no_progress')):
        return False,'technical_or_no_progress'
    if not t.get('steps'):return False,'no_steps'
    if t['reward']<=0:return True,'incorrect_answer'
    if t.get('prediction',{}).get('observations'):return True,'tool_supported_success'
    if t.get('activated_skill_ids'):return True,'activated_skill'
    return False,'direct_success_without_observed_operation'

def buffer_select(ts,cfg):
    """No length bias. First cover distinct images/events, then fill remaining slots."""
    valid=[t for t in ts if eligibility(t)[0]]
    valid.sort(key=lambda t:(t['reward']>0,t['feedback_ordinal'],t['id']))
    chosen=[];counts=Counter();events=set()
    while valid and len(chosen)<cfg['buffer']:
        idx=min(range(len(valid)),key=lambda i:(counts[image_key(valid[i])],
            (valid[i]['category'],eligibility(valid[i])[1]) in events,i))
        t=valid.pop(idx);chosen.append(t);counts[image_key(t)]+=1
        events.add((t['category'],eligibility(t)[1]))
    return chosen

def retrieve(repo,vector,cat,tools,cfg,prescreen):
    # Use inherited similarity/utility/recency ranking, but screen even one candidate.
    poolcfg=copy.deepcopy(cfg);poolcfg['top_k']=max(1,len(repo['skills']))
    pool=old.retrieve(repo,vector,cat,tools,poolcfg,None)
    pool=pool[:15]
    if not pool:return []
    if prescreen is None:raise ValueError('r54_requires_applicability_screen')
    ids=prescreen(pool)
    if not isinstance(ids,list) or len(ids)!=len(set(ids)) or not set(ids)<={s['id'] for s in pool}:
        raise ValueError('invalid_screen_ids')
    return [s for s in pool if s['id'] in ids][:cfg['top_k']]

EVENTS={'tool_disagreement','scope_gap','output_boundary','targeted_verification',
        'tool_parameter_repair','evidence_sufficient_stop','other','none'}
def check_analysis(a,t):
    if a.get('output_intent') not in ('CREATE','PATCH','NONE'):raise ValueError('analysis_intent')
    if a.get('event_type') not in EVENTS:raise ValueError('event_type')
    if a.get('support_level') not in ('observed','hypothesis','none'):raise ValueError('support_level')
    idx=a.get('evidence_steps')
    if not isinstance(idx,list) or any(type(i)!=int or not 0<=i<len(t['steps']) for i in idx):raise ValueError('evidence_steps')
    if a['output_intent']=='NONE' and not a.get('none_reason'):raise ValueError('none_reason_required')
    if a['output_intent']!='NONE' and (not idx or not a.get('trigger') or not a.get('observed_operation')):
        raise ValueError('unsupported_write_intent')
    if not isinstance(a.get('skill_adoption'),list):raise ValueError('adoption_list')
    allowed=set(t.get('activated_skill_ids',[]));seen=set()
    for x in a['skill_adoption']:
        if x['skill_id'] not in allowed or x['skill_id'] in seen:raise ValueError('credit_not_activated_or_duplicate')
        seen.add(x['skill_id'])
    return a
