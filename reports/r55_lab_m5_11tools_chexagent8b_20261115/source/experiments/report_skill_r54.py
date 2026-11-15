"""Post-completion scoring and lifecycle funnel. Uses immutable R54 predictions, no API calls."""
import argparse,json,random
from pathlib import Path
from collections import Counter,defaultdict
from run_online_skill_r54 import ARM,released_reward
from online_memory_r49 import read,save_once
from cxr_author_alignment import extract,m4cxr_recall
from r54_author_metrics import adapt,outcomes
from r54_reporting_io import closed_calls,response_text,receipt_resources

def adapt_run(run):
    """Extract every received raw terminal before any feedback/GT is opened."""
    run=Path(run);manifest=read(run/'manifest.json');arm=manifest['arm'];values={}
    for row in manifest['inputs']:
        q=row['question_id'];p=read(run/'predictions'/arm/(q+'.json'))
        event=read(run/'prediction_events'/(q+'.json'))
        if event.get('saved_prediction')!=p or p.get('arm')!=arm or p.get('question_id')!=q:raise ValueError('raw_prediction_binding')
        calls=closed_calls(run/'services/calls/R49-AGENT'/q)
        if not calls or len(calls)!=p['main_calls']:raise ValueError('raw_main_call_membership')
        raw=response_text(calls[-1][0])
        if raw!=p.get('terminal_raw'):raise ValueError('received_terminal_differs_from_saved')
        values[q]=adapt(row,p,{'raw':raw,'call_path':str(calls[-1][0]),'ordinal':calls[-1][0].name,
            'reuse_chain':[],'technical_stop':False,'evidence_status':'received_terminal_text' if raw else 'nonfinal_or_unavailable'})
    return values

def resources(run):
    run=Path(run);groups={}
    slots=['R49-AGENT','R49-META']
    slots.extend(slot for slot in ('R55-TOOL','R55-VERIFY')
                 if (run/'services/calls'/slot).is_dir())
    for slot in slots:
        receipts=[value for folder in (run/'services/calls'/slot).glob('*') if folder.is_dir() for value in closed_calls(folder)]
        groups[slot]=receipt_resources(receipts)
    embeds=[read(p) for p in (run/'services/embeddings').glob('*/result.json')]
    groups['embedding']={'requests':len(embeds),'usage_tokens_known':sum((v.get('usage') or {}).get('total_tokens',0) or 0 for v in embeds),
        'usage_unknown_count':sum(v.get('usage') is None for v in embeds),'invoice_cost':None}
    tools=[]
    for path in (run/'services/tool_cache').glob('*/result.json'):
        value=read(path);events=path.parent/'artifacts/backend_events.json'
        tools.append({'cache_key':path.parent.name,'backend':value.get('backend'),'status':value.get('status'),
            'elapsed_s':value.get('elapsed_s'),'actual_model_events':read(events) if events.is_file() else value.get('actual_model_events',[]),
            'gpu_peak_bytes':value.get('cuda_peak_allocated_bytes_by_visible_device')})
    groups['tool_attempts']=tools
    groups['timing_note']='Request/backend elapsed sums can overlap; not billed wall time. GPU rental/energy, authoritative Credits and invoices unknown.'
    groups['GPU_cost']=None
    return groups

def report(run,historical=None,*,adapted=None):
    global ARM
    run=Path(run);done=read(run/'complete.json');manifest=read(run/'manifest.json')
    ARM=manifest['arm']
    if done['status']!='generation_complete' or done['arm']!=ARM:raise ValueError('not_complete_R54')
    inputs=manifest['inputs'];ids={r['question_id'] for r in inputs}
    if {p.stem for p in (run/'predictions'/ARM).glob('*.json')}!=ids:raise ValueError('not_full_denominator')
    if len(ids)!=done['questions']:raise ValueError('size_mismatch')
    adapted=adapt_run(run) if adapted is None else adapted
    if set(adapted)!=ids:raise ValueError('reference_free_adaptation_membership')
    details=[];sub=defaultdict(list);rng=random.Random(0)
    for row in inputs:
        q=row['question_id'];p=read(run/'predictions'/ARM/(q+'.json'));f=read(run/'feedback'/(q+'.json'))
        if p!=f['saved_prediction']:raise ValueError('feedback_prediction_changed')
        c=read(run/'contexts'/(q+'.json'));answer=adapted[q]['explicit_answer']
        outcome=outcomes(row,adapted[q],f['reference_annotation']['answer'],rng)
        value={'question_id':q,'correct':outcome['aligned_correct'],'adapted':adapted[q],
               'explicit_answer':answer,'candidate_hit':bool(c['selected_skills']),
               'activated':bool(p.get('activated_skill_ids')),'same_image_hit':bool(p['same_image_ids']),
               'main_calls':p.get('main_calls',0),'tool_calls':p.get('tool_calls',0),
               'word_recall':outcome['word_recall']}
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
        'macro_accuracy_pct':sum(100*sum(x['correct'] for x in v)/len(v) for v in sub.values())/len(sub),
        'missing_answers':sum(x['explicit_answer'] is None for x in details),
        'word_recall_pct':(100*sum(x['word_recall'] for x in details)/len(details)) if all(x['word_recall'] is not None for x in details) else None,
        'candidate_hit_questions':sum(x['candidate_hit'] for x in details),
        'activated_questions':sum(x['activated'] for x in details),'same_image_hit_questions':sum(x['same_image_hit'] for x in details),
        'subsets':{k:{'n':len(v),'correct':sum(x['correct'] for x in v),'accuracy_pct':100*sum(x['correct'] for x in v)/len(v)} for k,v in sub.items()},
        'pipeline':dict(pipeline),'eligibility_reasons':dict(reasons),'historical_comparisons':comparison,
        'agent_calls':sum(x['main_calls'] for x in details),'tool_calls':sum(x['tool_calls'] for x in details),
        'meta_calls':len(list((run/'services/calls/R49-META').glob('*/1/result.json'))),
        'resources':resources(run),
        'limitations':'Online post-prediction feedback; paired arm comparison is in pair_summary.json. Candidate/activation/adoption are distinct; adopted credit is not causal gain.'}
    return summary,details
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run',type=Path,required=True);p.add_argument('--historical',type=Path);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    summary,details=report(a.run,a.historical);save_once(a.out/'summary.json',summary);save_once(a.out/'per_question.json',details)
    print(json.dumps(summary,ensure_ascii=False,indent=2))
