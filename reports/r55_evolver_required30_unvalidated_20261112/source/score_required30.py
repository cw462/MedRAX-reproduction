"""Score the finished 30-case pilot and audit its required search receipts."""
import csv
import json
import random
import sys
from pathlib import Path

from compare_r55live import select_laterality, step_searches
from cxr_online_primitives_r49 import tool_failure_reason
from online_memory_r49 import read, save_once
from r54_author_metrics import outcomes
from report_skill_r54 import adapt_run, resources
from skill_policy_r54 import windows


def main(run, predecessor):
    e=run/'generation/E'
    d=predecessor/'generation/D/chexbench'
    em,dm=read(e/'manifest.json'),read(d/'manifest.json')
    selected,filtered=select_laterality(dm['inputs'],dm['order'])
    assert em['inputs']==selected[:30] and em['order']==filtered[:30]
    for key in ('config','protocol','runtime','new_tool_model_policy'):
        assert em[key]==dm[key],key
    assert read(e/'complete.json')['questions']==30
    assert (e/'generation.exitcode').read_text().strip()=='0'
    adapted=adapt_run(e)
    rng=random.Random(0)
    d_indices={x['question_id']:i for i,x in enumerate(dm['inputs'])}
    d_windows={i:wi for wi,(start,end) in enumerate(windows(len(d_indices))) for i in range(start,end)}
    rows=[]
    for i,row in enumerate(em['inputs']):
        q=row['question_id']
        p=read(e/'predictions/R55-E-EvolveR'/(q+'.json'))
        feedback=read(e/'feedback'/(q+'.json'))
        assert feedback['saved_prediction']==p
        reference=feedback['reference_annotation']['answer']
        value=outcomes(row,adapted[q],reference,rng)
        steps=read(e/'steps'/(q+'.json'))
        receipt=read(e/'services/experience_searches'/q/'pre_answer.json')
        assert steps[0]['pre_answer_experience_search']==receipt
        assert receipt['trigger']=='required_pre_answer' and receipt['status'] in ('retrieved','empty_bank')
        assert bool(receipt['active_card_count'])==bool(receipt['results'])==(receipt['status']=='retrieved')
        followups=[v for step in steps for v in step_searches(step) if v.get('trigger')=='model_followup']
        assert len(followups)<=1
        di=d_indices[q]
        path=d/'windows'/f'{d_windows[di]:04d}'/'trajectories'/(q+'.json')
        prior=read(path) if path.is_file() else None
        if prior is not None:
            assert prior['id']==q and prior['source_label']==reference and prior['reward'] in (0,1)
        rows.append({'ordinal':i+1,'question_id':q,'E_answer':adapted[q]['explicit_answer'],
                     'E_correct':value['aligned_correct'],
                     'D_online_correct':bool(prior['reward']) if prior else None,
                     'same_previous_image_ids':dm['order'][di]['previous_ids']==em['order'][i]['previous_ids'],
                     'required_pre_answer_search':receipt,'followup_searches':followups,
                     'E_tool_calls':p['tool_calls'],
                     'E_failed_tool_calls':sum(bool(tool_failure_reason(x)) for x in p['observations'])})
    total=sum(x['E_correct'] for x in rows)
    paired=[x for x in rows if x['D_online_correct'] is not None]
    summary={'questions':30,'correct':total,'accuracy_pct':100*total/30,
             'required_pre_answer_checks':len(rows),
             'required_pre_answer_lookups':sum(x['required_pre_answer_search']['status']=='retrieved' for x in rows),
             'required_pre_answer_empty_bank':sum(x['required_pre_answer_search']['status']=='empty_bank' for x in rows),
             'experience_delivered_questions':sum(bool(x['required_pre_answer_search']['results']) for x in rows),
             'model_followup_searches':sum(len(x['followup_searches']) for x in rows),
             'D_saved_online_pair':{'n':len(paired),'D_correct':sum(x['D_online_correct'] for x in paired),
                'E_correct':sum(x['E_correct'] for x in paired)},
             'resources':resources(e)}
    assert summary['required_pre_answer_checks']==summary['required_pre_answer_lookups']+summary['required_pre_answer_empty_bank']==30
    out=e/'analysis'
    save_once(out/'summary.json',summary)
    save_once(out/'per_question.json',rows)
    keys=('ordinal','question_id','E_answer','E_correct','D_online_correct','same_previous_image_ids','E_tool_calls','E_failed_tool_calls')
    with (out/'per_question.csv').open('x',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=keys,extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps(summary,ensure_ascii=False))


if __name__=='__main__':
    main(*(Path(x) for x in sys.argv[1:]))
