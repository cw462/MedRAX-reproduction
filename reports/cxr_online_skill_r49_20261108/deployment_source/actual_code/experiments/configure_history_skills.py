"""Prepare only the user-authorized Plus H1/S1/HS round, no paid calls."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import run_sampled_vlm as worker
from history_skills import ID,VERSION,folds_and_reflections,clinical_record
from run_direct_vlm import read,read_lines


def freeze(path,value):worker.frozen_write(path,value)


def configure(root,code):
    root=Path(root);code=Path(code);out=root/'runs'/ID
    old=read(root/'code_case_information/configs/case_information_20261103/E0_Heldout.json')
    if old['model']!='qwen3.7-plus' or old['new_experiment_budget_cny']!='200':raise ValueError('inherited_config_required')
    rows=read_lines(root/'runs/case_information_20261103/inputs/tune.inputs.jsonl')
    baseline_rows=read(root/'reports/qwen37_token_plan_20261102/phase1/per_question.json')['records']
    baseline={r['question_id']:{'answer':r['answers']['D'],'correct':r['answers']['D']==r['reference']} for r in baseline_rows}
    if len(rows)!=402 or len({r['case_id'] for r in rows})!=99:raise ValueError('tune_scope_required')
    folds,reflection_ids=folds_and_reflections(rows,baseline)
    if len(reflection_ids)!=205:raise ValueError('expected_107_wrong_plus_98_correct')
    # This preparation-only metadata reader never supplies diagnosis to workers.
    metadata=read(root/'source/MedRAX/data/eurorad_metadata.json')
    policy=read(code/'configs/history_skills_protocol.json')['history']
    histories={};flags={}
    for case in sorted(folds):
        if case not in metadata:raise ValueError('missing_official_case_metadata')
        histories[case],flags[case]=clinical_record(metadata[case],policy)
    cats={r['question_id']:[x.strip() for x in r['categories'].split(',') if x.strip()] for r in read(code/'configs/history_skills_categories.json')['rows']}
    if set(cats)!=set(r['question_id'] for r in rows):raise ValueError('official_categories_required')
    inputs=out/'inputs';inputs.mkdir(parents=True,exist_ok=True)
    frozen_text=''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows)
    p=inputs/'tune.inputs.jsonl'
    if p.exists() and p.read_text()!=frozen_text:raise ValueError('frozen_inputs_conflict')
    if not p.exists():p.write_text(frozen_text,encoding='utf-8')
    freeze(inputs/'histories.json',histories)
    freeze(inputs/'history_flags.json',{'rules':policy,'cases':flags})
    freeze(inputs/'folds.json',folds);freeze(inputs/'categories.json',cats)
    # Isolated source-example training data; only the reflection adapter opens it.
    source={r['question_id']:r for r in rows}
    refs={r['question_id']:r['reference'] for r in baseline_rows}
    training={}
    for q in reflection_ids:
        terminal=read(root/'runs/qwen37_token_plan_20261102/phase1/D/checkpoints'/q/'sample_1/terminal.json')
        training[q]={'reference':refs[q],'saved_D_answer':terminal['answer'],'saved_D_rationale':terminal['raw_response']}
    freeze(out/'training/source_examples.json',training)
    freeze(out/'training/reflection_ids.json',reflection_ids)
    freeze(inputs/'baseline_answers.json',baseline)
    inherited='runs/case_information_20261103/private_ledgers/E0_Heldout.json'
    configs=[]
    for arm,n,extra in [('H1',402,21),('Reflection',205,11),('S1',402,21),('HS',402,21)]:
        cfg=deepcopy(old)
        cfg.update(experiment_id=ID,plan_version=VERSION,run_id=ID+'_'+arm,arm=arm,
            root=str(root),input=str(p.relative_to(root)),question_count=n,case_count=99,
            max_requests=n+extra,max_extra_requests=extra,global_max_requests=1485,global_max_extra_requests=74,
            global_request_counter='runs/'+ID+'/global_requests.json',
            ledger='runs/'+ID+'/private_ledgers/'+arm+'.json',inherit_ledger=inherited,
            budget_authorization='User authorized Plus-only H1 S1 HS and source-fold reflection on 402 tuning questions; original cumulative 200 authorization and cap retained.',
            shared_public_plan=str((code/'configs/history_skills_plus_protocol.json').relative_to(root)),
            mode='reflection' if arm=='Reflection' else 'independent_history_skills',
            first_real_image_gate=False,additional_budget_granted_cny='0')
        worker.validate_cfg(cfg)
        conf=code/'configs'/ID/(arm+'.json');freeze(conf,cfg);configs.append({'id':arm,'config':str(conf.relative_to(root)),'out':'runs/'+ID+'/arms/'+arm})
        inherited=cfg['ledger']
    frozen={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs.glob('*.json*')}
    freeze(out/'input_freeze.json',{'artifacts':frozen,'diagnosis_not_in_answer_inputs':True,'one_time_input_freeze_not_ledger_check':True})
    manifest={'experiment_id':ID,'plan_version':VERSION,'root':str(root),'arms':configs,'normal_requests':1411,'hard_requests':1485,'model':'qwen3.7-plus','fold_case_counts':{f:sum(v==f for v in folds.values()) for f in ('A','B')},'reflection_n':205,'new_api_calls':0}
    freeze(code/'configs'/ID/'pipeline.json',manifest)
    print(json.dumps({'prepared':True,'normal_requests':1411,'reflection_requests':205,'flagged_cases':sum(x['flagged'] for x in flags.values()),'new_api_calls':0}))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path,required=True);p.add_argument('--code',type=Path,required=True)
    a=p.parse_args();configure(a.root,a.code)
