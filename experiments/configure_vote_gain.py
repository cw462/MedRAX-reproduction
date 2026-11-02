"""Materialize the first frozen sampling phase after a concrete budget is supplied.

This program never opens labels, credentials, or account ledgers and never calls
an API. The parent ledger's last observed committed total is an explicit input;
the original ledger interface will read actual inherited spend on first open.
"""
from __future__ import annotations

import argparse
from decimal import Decimal
import json
import os
from pathlib import Path


def dump_new(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(value, ensure_ascii=False, indent=2)+'\n'
    if path.exists() and path.read_text(encoding='utf-8') != text:
        raise ValueError('refusing_to_replace_frozen_config:' + str(path))
    if not path.exists():path.write_text(text, encoding='utf-8')


def profile(model, output=8192):
    rates = {'qwen3-vl-plus':('4','12'), 'qwen3.8-max-0902':('12','36'),
             'kimi/kimi-k3.1-pro':('13','68')}
    inp, out = rates[model]
    identities = ['kimi/kimi-k3.1-pro', 'kimi-k3.1-pro'] if model.startswith('kimi/') else [model]
    return {'base_url':'https://dashscope.aliyuncs.com/compatible-mode/v1',
        'identity_prefixes':identities,'input_cny_per_million':inp,
        'output_cny_per_million':out,'max_input_tokens':131072,'max_output_tokens':output,
        'price_basis':'2026-11-02 official Beijing list rates; qwen3-vl-plus retains historical conservative 4/12 accounting; cache discounts not assumed; reasoning counted in completion_tokens'}


def phase0(args):
    root = Path(args.root).resolve(); experiment = 'multimodel_vote_gain_20261102'
    relative = f'runs/{experiment}'; parent = root/relative
    code = Path(args.code)
    if not code.is_absolute():code=root/code
    code=code.resolve();config_dir = code/'configs'/experiment
    if not code.is_relative_to(root):raise ValueError('code_directory_must_be_inside_root')
    budget = Decimal(args.new_budget_cny)
    baseline = Decimal(args.inherited_committed_cny)
    cap = baseline+budget
    original_cap=Decimal(args.original_cap_cny)
    if not all(x.is_finite() for x in (budget,baseline,original_cap)) or baseline < 0 or budget <= 0 or cap > original_cap or not args.budget_authorization.strip():
        raise ValueError('explicit_positive_new_budget_within_existing_cap_required')
    # Old60 is authorized regression only; neither scores nor labels are read.
    old = [json.loads(line) for line in (root/'runs/v4_validation60/inputs.jsonl').read_text(encoding='utf-8').splitlines() if line.strip()]
    if len(old) != 60:raise ValueError('regression_requires_original60')
    rows = [{k:r[k] for k in ('question_id','case_id','question','images','figure_labels') if k in r} for r in old]
    if any(not r.get('case_id') for r in rows):
        # Authoritative source question_id/full_question_id aliases supply
        # clustering only; historical inputs use the former explicit field.
        # No answer/reference fields are copied into inference or logs.
        metadata=root/'data/chest-agent-bench/metadata.jsonl.new'
        mapping={}
        with metadata.open(encoding='utf-8') as handle:
            for line in handle:
                if not line.strip():continue
                item=json.loads(line);case=item.get('case_id')
                if isinstance(case,bool) or case is None or not str(case).strip():continue
                for field in ('question_id','full_question_id'):
                    qid=item.get(field)
                    if qid is None:continue
                    qid=str(qid);case=str(case).strip()
                    if qid in mapping and mapping[qid]!=case:raise ValueError('ambiguous_source_case_binding')
                    mapping[qid]=case
        for row in rows:
            case=mapping.get(str(row['question_id']))
            if case is None:raise ValueError('missing_explicit_case_binding')
            if row.get('case_id') is not None and str(row['case_id'])!=case:raise ValueError('source_case_binding_conflict')
            row['case_id']=case
    for name, selection in [('regression60',rows), ('capabilities2',rows[:2])]:
        path = parent/'inputs'/f'{name}.jsonl'; path.parent.mkdir(parents=True,exist_ok=True)
        text=''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in selection)
        if path.exists() and path.read_text(encoding='utf-8') != text:raise ValueError('immutable_regression_input')
        if not path.exists():path.write_text(text,encoding='utf-8')
    definitions = [
        ('D_regression60','qwen3-vl-plus','answer',False,False,60),
        ('qwen_max_smoke','qwen3.8-max-0902','answer',False,False,2),
        ('kimi_smoke','kimi/kimi-k3.1-pro','answer',False,False,2),
        ('qwen_highres_smoke','qwen3-vl-plus','answer',True,True,2),
        ('qwen_think_smoke','qwen3-vl-plus','think',False,False,2),
    ]
    previous = args.inherit_ledger
    arms=[]
    for arm_id, model, variant, hires, labels, count in definitions:
        run_id = f'vote_20261102_p0_{arm_id}'
        thinking = variant == 'think' or model.startswith('kimi/')
        output = 8192 if thinking else 2048
        extra = {'reasoning_effort':'max'} if model.startswith('kimi/') else {'enable_thinking':variant=='think'}
        if hires:extra['vl_high_resolution_images']=True
        if variant=='think':extra['thinking_budget']=4096
        ledger=f'{relative}/private_ledgers/{arm_id}.json'
        cfg={'root':str(root),'run_id':run_id,'model':model,'prompt_variant':variant,
            'input':f'{relative}/inputs/{"regression60" if count==60 else "capabilities2"}.jsonl',
            'image_root':'data/memory_v1/images','samples':1,
            'temperature':1.0 if model.startswith('kimi/') else 0.2,'top_p':0.95,
            'max_output_tokens':output,'request_timeout_seconds':300 if thinking else 120,
            'stream':variant=='think','extra_body':extra,'figure_labels':labels,'high_resolution':hires,
            'capability_smoke':count==2,'capability_confirmed':False,
            'profile':profile(model,16384 if thinking else 8192),'ledger':ledger,'inherit_ledger':previous,
            'cap_cny':str(cap),'new_experiment_budget_cny':str(budget),
            'budget_authorization':args.budget_authorization,
            'max_requests':count+(6 if count==60 else 1),'max_extra_requests':6 if count==60 else 1,
            'max_attempts_per_sample':2,'global_max_requests':59082,'global_max_extra_requests':2814,
            'global_request_counter':f'{relative}/global_requests.json'}
        config_path=config_dir/f'{arm_id}.json'
        dump_new(config_path,cfg)
        arms.append({'id':arm_id,'config':str(config_path),'out':str(parent/'phase0'/arm_id)})
        previous=ledger
    manifest={'root':str(root),'out':str(parent/'phase0'),'phase':0,'arms':arms,
        'cap_cny':str(cap),'new_experiment_budget_cny':str(budget),
        'inherited_committed_snapshot_cny':str(baseline),'original_cap_cny':str(original_cap),
        'inherit_ledger':args.inherit_ledger,'budget_authorization':args.budget_authorization,
        'global_request_counter':f'{relative}/global_requests.json',
        'next_phase':'stop after generation for regression score and capability assessment; freeze phase1 separately'}
    dump_new(config_dir/'phase0.json',manifest)
    score_arms=[{'id':a['id'],'run':os.path.relpath(a['out'],config_dir).replace('\\','/')} for a in arms]
    dump_new(config_dir/'phase0.score.json',{'phase':0,'split':'regression',
        'baseline':'D_regression60','arms':score_arms[:1],
        'generation_gate':os.path.relpath(parent/'phase0/status.json',config_dir).replace('\\','/')})
    dump_new(config_dir/'phase0.smokes.export.json',{'phase':0,'split':'capability_smoke',
        'arms':score_arms[1:]})
    print(json.dumps({'phase_manifest':str(config_dir/'phase0.json'),'new_budget_cny':str(budget),
        'planned_requests':68,'paid_calls_started':0}))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',required=True)
    parser.add_argument('--code',required=True)
    parser.add_argument('--new-budget-cny',required=True)
    parser.add_argument('--inherited-committed-cny',required=True)
    parser.add_argument('--original-cap-cny',required=True)
    parser.add_argument('--inherit-ledger',required=True)
    parser.add_argument('--budget-authorization',required=True)
    phase0(parser.parse_args())


if __name__=='__main__':main()
