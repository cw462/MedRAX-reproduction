"""Compare complete paired R55 D/E runs using archived binary rewards."""
import argparse
import json
import re
from collections import Counter
from pathlib import Path


def read(path):
    return json.loads(path.read_text())


def load(path):
    manifest=read(path/'manifest.json')
    complete=read(path/'complete.json')
    ids=[r['question_id'] for r in manifest['inputs']]
    if complete['status']!='generation_complete' or complete['questions']!=len(ids):
        raise ValueError(f'incomplete_run:{path}')
    rows={}
    for filename in (path/'windows').glob('*/trajectories/*.json'):
        t=read(filename)
        if t['id'] in rows or t['reward'] not in (0,1):
            raise ValueError('duplicate_or_invalid_trajectory')
        rows[t['id']]=t
    if set(rows)!=set(ids):
        raise ValueError('missing_trajectory')
    return manifest,rows


def laterality(row):
    options=list((row.get('options') or {}).values())
    if row.get('source',{}).get('subset')!='OpenI' or len(options)!=2:
        return False
    a,b=(re.findall(r'[a-z0-9]+',x.lower()) for x in options)
    sides={'left','right'}
    return {frozenset(set(a)&sides),frozenset(set(b)&sides)}=={
        frozenset({'left'}),frozenset({'right'})
    } and ['side' if x in sides else x for x in a]==['side' if x in sides else x for x in b]


def select_laterality(inputs, order):
    if [row['question_id'] for row in inputs] != [item['question_id'] for item in order]:
        raise ValueError('order_mismatch')
    selected = [row for row in inputs if laterality(row)]
    ids = {row['question_id'] for row in selected}
    filtered = [
        {**item, 'previous_ids': [qid for qid in item['previous_ids'] if qid in ids]}
        for item in order if item['question_id'] in ids
    ]
    return selected, filtered


def step_searches(step):
    for key in ('pre_answer_experience_search', 'experience_search'):
        if key in step:
            yield step[key]


def actions(trace):
    """Only successful tool calls after delivery count as post-search observations."""
    experience_ids = []
    executed = []
    observations = trace['prediction']['observations']
    for step in trace['steps']:
        for search_record in step_searches(step):
            for principle in search_record['results']:
                if principle['id'] not in experience_ids:
                    experience_ids.append(principle['id'])
        for call in step.get('executed_calls', []):
            index = call['observation_index']
            observation = observations[index]
            action = call['action']
            args = action.get('args') or {}
            text = ' '.join(str(args.get(k, '')) for k in ('question','phrase','prompt','query','focus','concern'))
            # Lexical flag for audit; the recorded action and result remain authoritative.
            side_query = bool(re.search(r'\b(left|right|side|laterality|hemithorax)\b',text,re.I))
            executed.append({
                'step_index':step['step_index'], 'experience_ids_before':list(experience_ids),
                'side_query':side_query, **call,
                'returned_observation':observation.get('observation'),
                'raw_result_file':observation.get('raw_result_file'),
                'cache_hit':observation.get('cache_hit'),
                'backend_invoked':observation.get('backend_invoked', True),
            })
    if len(executed) != trace['prediction']['tool_calls']:
        raise ValueError('executed_action_count_mismatch:'+trace['id'])
    return executed


def audit_actions(ids, off, on):
    rows=[]
    after_search_by_tool=Counter()
    per_arm_completed = {'D':Counter(), 'E':Counter()}
    per_arm_requested = {'D':Counter(), 'E':Counter()}
    for qid in ids:
        a,b=off[qid],on[qid]
        checks=[record for step in b['steps'] for record in step_searches(step)]
        searches=[record for record in checks if record.get('status') != 'empty_bank']
        required=next((record for record in checks if record.get('trigger')=='required_pre_answer'), None)
        off_actions,on_actions=actions(a),actions(b)
        for arm, executions in (('D',off_actions), ('E',on_actions)):
            per_arm_requested[arm].update(r['action']['tool'] for r in executions)
            per_arm_completed[arm].update(r['action']['tool'] for r in executions
                                          if r['status']=='completed' and not r['failed'] and r['backend_invoked'])
        completed_after_search=[r for r in on_actions if r['experience_ids_before']
                                and r['status']=='completed' and not r['failed'] and r['backend_invoked']]
        after_search_by_tool.update(r['action'].get('tool', 'unknown') for r in completed_after_search)
        verified=[r for r in completed_after_search if r['side_query']]
        rows.append({'question_id':qid,'question':b['row']['question'],'options':b['row'].get('options',{}),
                     'reference':b['source_label'],'off_correct':bool(a['reward']),'on_correct':bool(b['reward']),
                     'off_answer':a['prediction']['answer'],'on_answer':b['prediction']['answer'],
                     'off_reason':a['prediction'].get('reason'),'on_reason':b['prediction'].get('reason'),
                     'searches':searches,'required_pre_answer_search':required,'off_actions':off_actions,'on_actions':on_actions,
                     'completed_side_queries_after_experience':len(verified)})
    return {
        'tool_calls_by_arm':{arm:dict(per_arm_requested[arm]) for arm in ('D','E')},
        'completed_tool_calls_by_arm':{arm:dict(per_arm_completed[arm]) for arm in ('D','E')},
        'experience_search_questions':sum(bool(r['searches']) for r in rows),
        'experience_delivered_questions':sum(any(s['results'] for s in r['searches']) for r in rows),
        'required_pre_answer_checks':sum(r['required_pre_answer_search'] is not None for r in rows),
        'required_pre_answer_lookups':sum((r['required_pre_answer_search'] or {}).get('status')=='retrieved' for r in rows),
        'required_pre_answer_empty_bank':sum((r['required_pre_answer_search'] or {}).get('status')=='empty_bank' for r in rows),
        'completed_calls_after_experience_by_tool':dict(after_search_by_tool),
        'completed_side_queries_after_experience':sum(r['completed_side_queries_after_experience'] for r in rows),
        'questions_with_completed_side_query_after_experience':sum(bool(r['completed_side_queries_after_experience']) for r in rows),
        'corrected_with_completed_side_query_after_experience':sum(
            not r['off_correct'] and r['on_correct'] and bool(r['completed_side_queries_after_experience']) for r in rows),
        'harmed_with_completed_side_query_after_experience':sum(
            r['off_correct'] and not r['on_correct'] and bool(r['completed_side_queries_after_experience']) for r in rows),
    },rows


def measure(ids, a, b):
    if not ids:
        return None
    corrected=[q for q in ids if not a[q]['reward'] and b[q]['reward']]
    harmed=[q for q in ids if a[q]['reward'] and not b[q]['reward']]
    return {'n':len(ids),'off_correct':sum(a[q]['reward'] for q in ids),
            'on_correct':sum(b[q]['reward'] for q in ids),
            'corrected_ids':corrected,'harmed_ids':harmed,'net':len(corrected)-len(harmed),
            'delta_pp':100*(len(corrected)-len(harmed))/len(ids),
            'tool_calls_off':sum(a[q]['prediction']['tool_calls'] for q in ids),
            'tool_calls_on':sum(b[q]['prediction']['tool_calls'] for q in ids),
            'main_calls_off':sum(a[q]['prediction']['main_calls'] for q in ids),
            'main_calls_on':sum(b[q]['prediction']['main_calls'] for q in ids),
            'memory_exposed_questions':sum(bool(b[q]['injected']) for q in ids)}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--off',type=Path,required=True)
    parser.add_argument('--on',type=Path,required=True)
    parser.add_argument('--actions-out',type=Path)
    args=parser.parse_args()
    a,off=load(args.off)
    b,on=load(args.on)
    if a['skill_route']!='off' or b['skill_route']!='experience':
        raise ValueError('invalid_pair_routes')
    for key in ('inputs','order','protocol','runtime','dataset','defaults',
                'embedding_model','embedding_base_url','implementation_files','implementation_revision','cohort'):
        if a[key]!=b[key]:
            raise ValueError('pair_mismatch:'+key)
    if any(off[q]['source_label']!=on[q]['source_label'] for q in off):
        raise ValueError('pair_reference_mismatch')
    ids=[x['question_id'] for x in a['inputs']]
    side_ids=[row['question_id'] for row in a['inputs'] if laterality(row)]
    if a['cohort']=='openi293' and (len(ids)!=293 or side_ids!=ids):
        raise ValueError('unexpected_openi_laterality_cohort')
    counts, rows=audit_actions(ids,off,on)
    if b['implementation_revision']=='R55-EvolveR-live.2-required-search' and (
        counts['required_pre_answer_checks'] != len(ids)
        or counts['required_pre_answer_lookups'] + counts['required_pre_answer_empty_bank'] != len(ids)
    ):
        raise ValueError('incomplete_required_experience_checks')
    if args.actions_out:
        args.actions_out.parent.mkdir(parents=True,exist_ok=True)
        with args.actions_out.open('w',encoding='utf-8') as stream:
            for row in rows:
                stream.write(json.dumps(row,ensure_ascii=False)+'\n')
    print(json.dumps({'route':b['skill_route'], 'cohort':a['cohort'], 'dataset':a['dataset'],
                      'all_paired_questions':measure(ids,off,on),
                      'openi_laterality_pair':measure(side_ids,off,on),
                      'actions':counts},ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
