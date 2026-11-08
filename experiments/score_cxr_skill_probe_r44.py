"""Score the completed R44 paired pilot once, using frozen common metrics."""
import argparse
from collections import Counter
from datetime import datetime
from decimal import Decimal
import json
from pathlib import Path

import numpy as np

from cxr_author_alignment import extract, m4cxr_normalize, m4cxr_recall
from cxr_skill_probe_r44 import ARMS, protocol, rows


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')


def adapted(call, qid):
    message = call['choices'][0]['message']
    final = (call['choices'][0].get('finish_reason') == 'stop'
             and not message.get('tool_calls') and not message.get('function_call'))
    result = extract(message.get('content'), qid) if final else None
    text = message.get('content')
    try:value = json.loads(text)
    except (ValueError,TypeError):valid, old_m = False, False
    else:
        valid = True
        old_m = (isinstance(value,dict) and set(value)=={'answer','reason'}
                 and all(isinstance(v,str) for v in value.values())
                 and bool(value['answer'].strip()) and len(value['answer'])<=300)
    return {'answer':result.answer if result else None,
            'extraction':result.mechanism if result else 'nonterminal_reply',
            'raw_whole_json_valid':valid,'original_M_contract_compliant':old_m}


def paired_interval(details):
    groups = sorted({row['image_id'] for row in details})
    totals = np.array([sum(row['image_id']==group for row in details) for group in groups])
    counts = np.array([[sum(row['image_id']==group and row[arm]['correct'] for row in details)
                        for group in groups] for arm in ARMS])
    draws = np.random.default_rng(0).integers(0,len(groups),size=(10000,len(groups)))
    denominators = totals[draws].sum(axis=1)
    scores = [counts[index][draws].sum(axis=1)/denominators for index in range(2)]
    return {'method':'paired decoded-image cluster bootstrap, percentile, 10000 draws, seed 0',
            'clusters':len(groups),'confidence':0.95,
            'accuracy_percent':{arm:list(np.percentile(scores[i]*100,[2.5,97.5])) for i,arm in enumerate(ARMS)},
            'net_percentage_points':list(np.percentile((scores[1]-scores[0])*100,[2.5,97.5])),
            'limitations':'8 image clusters, one sample per arm; exploratory, not patient-independent or selection-adjusted'}


def score(source, data, skill_path, out):
    assert not out.exists(), 'new_output_directory_required'
    assert (source/'pilot.exitcode').read_text().strip() == '0'
    inputs = rows(data/'inputs.jsonl'); ids = {x['question_id'] for x in inputs}
    assert len(ids) == len(inputs) == 27
    assert read(source/'protocol.json') == protocol(skill_path.read_text(encoding='utf-8').strip(), inputs)
    assert read(source/'inputs.json') == inputs
    completion = read(source/'complete.json')
    assert completion['pairs'] == 27 and completion['new_main_sends'] == 54
    evidence, resources = {}, {}
    # All transport, membership and reference-free answer adaptation completes
    # for BOTH arms before the reference file is opened below.
    for arm in ARMS:
        assert {p.stem for p in (source/'predictions'/arm).glob('*.json')} == ids
        assert read(source/('complete_'+arm+'.json'))['questions'] == 27
        assert len(list((source/'calls'/arm).glob('*/1/started.json'))) == 27
        assert len(list((source/'calls'/arm).glob('*/1/response.json'))) == 27
        costs, prompt_tokens, completion_tokens, elapsed = [], 0, 0, 0.0
        for row in inputs:
            qid=row['question_id'];folder=source/'calls'/arm/qid/'1'
            call=read(folder/'response.json');receipt=read(folder/'result.json')
            assert receipt['error'] is None and receipt['response_received'] is True
            assert receipt['model_returned'] == call['model']
            prediction=read(source/'predictions'/arm/(qid+'.json'))
            assert prediction['status'] != 'technical_stop'
            value=adapted(call,qid);assert prediction['answer'] == value['answer']
            evidence[qid,arm]=value
            usage=receipt['usage'];prompt_tokens+=usage['prompt_tokens'];completion_tokens+=usage['completion_tokens']
            costs.append(Decimal(receipt['settlement']['charged_cny']))
            elapsed+=receipt['elapsed_s']
        resources[arm]={'new_main_sends':27,'new_tools':0,'prompt_tokens':prompt_tokens,
                        'completion_tokens':completion_tokens,'cost_cny_proxy':str(sum(costs)),
                        'sum_request_elapsed_s':elapsed,'provider_invoice':False}
    references=rows(data/'references.jsonl')
    assert len(references) == 27 and {x['question_id'] for x in references} == ids
    refs={x['question_id']:x for x in references}
    details=[]
    for row in inputs:
        qid=row['question_id'];ref=refs[qid]
        record={'question_id':qid,'question':row['question'],'image_id':row['image_id'],
                'images':row['images'],'reference':ref['answer'],'content_type':ref['content_type']}
        for arm in ARMS:
            value=dict(evidence[qid,arm]);answer=value['answer']
            value.update(correct=bool(answer is not None and m4cxr_normalize(answer)==m4cxr_normalize(ref['answer'])),
                         word_recall=m4cxr_recall(answer,ref['answer']) if answer is not None else 0.0)
            record[arm]=value
        record['change']='correction' if not record['P0']['correct'] and record['P1']['correct'] else (
            'harm' if record['P0']['correct'] and not record['P1']['correct'] else 'unchanged')
        details.append(record)
    n=len(details);arm_summary={}
    for arm in ARMS:
        values=[row[arm] for row in details]
        correct=sum(x['correct'] for x in values);missing=sum(x['answer'] is None for x in values)
        arm_summary[arm]={'questions':n,'correct':correct,'accuracy_pct':100*correct/n,
             'word_recall_mean':sum(x['word_recall'] for x in values)/n,'missing_explicit_answers':missing,
             'explicit_wrong_by_label_EM':n-correct-missing,'raw_whole_json_valid':sum(x['raw_whole_json_valid'] for x in values),
             'original_M_contract_compliant':sum(x['original_M_contract_compliant'] for x in values),
             'by_content_type':{category:{'n':sum(x['content_type']==category for x in details),
                 'correct':sum(x['content_type']==category and x[arm]['correct'] for x in details)}
                 for category in sorted({x['content_type'] for x in details})}}
    changes=Counter(x['change'] for x in details)
    corrections=changes['correction'];harms=changes['harm'];net=corrections-harms
    summary={'protocol':'author answer metrics + existing common explicit-answer adapter',
             'new_inference_on_official_test':0,'pilot':'official SLAKE validation, 27 questions / 8 images',
             'arms':arm_summary,'paired':{'corrections':corrections,'harms':harms,'net_correct':net,
                 'net_percentage_points':100*net/n,'correction_ids':[x['question_id'] for x in details if x['change']=='correction'],
                 'harm_ids':[x['question_id'] for x in details if x['change']=='harm']},
             'interval':paired_interval(details),'resources':resources,
             'new_cost_cny_proxy':str(sum(Decimal(x['cost_cny_proxy']) for x in resources.values())),
             'wall_seconds':(datetime.fromisoformat(completion['completed_at'])-datetime.fromisoformat(completion['started_at'])).total_seconds(),
             'priority_gate_passed':net>=2 and harms<=1,'not_statistical_confirmation':True,
             'overall_best_target_goal_achieved':False}
    out.mkdir(parents=True)
    write(out/'summary.json',summary)
    (out/'per_question.jsonl').write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in details),encoding='utf-8')
    return summary


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    for name in ['source','data','skill','out']:
        parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args()
    print(json.dumps(score(args.source,args.data,args.skill,args.out),ensure_ascii=False))
