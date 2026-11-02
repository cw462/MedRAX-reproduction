"""Freeze authorized tuning phases 1/2/3; never launch, score or read labels.

Each command requires the preceding generation and offline decision to be
complete. Existing anchors/samples are referenced, never copied or regenerated.
Only phases 1, 2, 3a and 3b are materialized; held-out/full-benchmark runs require
a separate later authorization and are deliberately outside this CLI.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from decimal import Decimal
import json
import math
import os
from pathlib import Path

from configure_vote_gain import dump_new
from run_sampled_vlm import validate_cfg
from run_vote_phase import validate_manifest
from score_votes import load_complete_run

NAME='multimodel_vote_gain_20261102'
REL=Path('runs')/NAME
TUNE=REL/'split_inputs/tune.inputs.jsonl'
N=402
DIRECT_IDS=('Qwen_B0','QwenMax_B0','Kimi_B0')
SAMPLE_IDS=('S0','S1','S2')


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def at(root, value):
    if value is None:raise ValueError('required_predecessor_artifact_path_missing')
    path=Path(value)
    return path.resolve() if path.is_absolute() else (root/path).resolve()


def rel(root,path):
    path=Path(path).resolve()
    if not path.is_relative_to(root):raise ValueError('configuration_path_outside_root')
    return path.relative_to(root).as_posix()


def completed(manifest_path, root, expected_n, expected_samples=None):
    manifest=read(manifest_path)
    if Path(manifest['root']).resolve()!=root:raise ValueError('predecessor_root_mismatch')
    state=read(at(root,manifest['out'])/'status.json')
    if state.get('status')!='generation_complete':raise ValueError('predecessor_phase_not_complete')
    arms=validate_manifest(manifest)
    loaded={}
    for arm in arms:
        run=load_complete_run(arm['out']);cfg=read(arm['config'])
        n=expected_n[arm['id']] if isinstance(expected_n,dict) else expected_n
        if len(run['qids'])!=n:raise ValueError('predecessor_coverage_mismatch')
        if expected_samples is not None and run['samples']!=expected_samples:
            raise ValueError('predecessor_sample_count_mismatch')
        if any(run['config'].get(k)!=v for k,v in cfg.items()):
            raise ValueError('predecessor_frozen_configuration_mismatch')
        loaded[arm['id']]={'cfg':cfg,'out':Path(arm['out']),'run':run}
    return manifest,loaded


def metric(path, expected_phase, expected_n):
    value=read(path)
    if value.get('status')!='completed' or value.get('phase')!=expected_phase or value.get('planned_n')!=expected_n:
        raise ValueError('completed_matching_offline_metrics_required')
    if expected_phase!=0 and value.get('split')!='tune':raise ValueError('tuning_metrics_only')
    return value


def phase0_gate(manifest_path, metrics_path, root):
    names={'D_regression60':60,'qwen_max_smoke':2,'kimi_smoke':2,
           'qwen_highres_smoke':2,'qwen_think_smoke':2}
    manifest,arms=completed(manifest_path,root,names,1)
    if set(arms)!=set(names):raise ValueError('exact_phase0_regression_and_capabilities_required')
    values=metric(metrics_path,0,60)
    total=values['totals'][values['baseline']]
    if total.get('planned_n')!=60 or not 40<=total.get('correct',-1)<=44 or total.get('missing')!=0:
        raise ValueError('phase0_regression_gate_requires_40_to_44_and_zero_missing')
    for name,arm in arms.items():
        records=arm['run']['records']
        if any(r['status']!='completed' or not r.get('answer') for r in records):
            raise ValueError('phase0_missing_or_failed_output:'+name)
        if name!='D_regression60' and not arm['cfg'].get('capability_smoke'):
            raise ValueError('explicit_two_question_smoke_required')
    if not arms['qwen_highres_smoke']['cfg'].get('high_resolution') or not arms['qwen_highres_smoke']['cfg'].get('figure_labels'):
        raise ValueError('highres_and_figure_binding_not_smoked')
    if arms['qwen_think_smoke']['cfg'].get('extra_body',{}).get('enable_thinking') is not True:
        raise ValueError('thinking_not_smoked')
    return manifest,arms


def selected_phase1(metrics_path):
    values=metric(metrics_path,1,N)
    decisions=values.get('tuning_decisions',values.get('decisions',{}))
    choice=decisions.get('phase1',{}).get('selected')
    eligible=('D','HiRes','CoT','Think')
    if choice not in eligible:raise ValueError('visual_phase1_decision_required_text_only_is_diagnostic')
    totals=values['totals']
    if any(totals.get(k,{}).get('planned_n')!=N for k in (*eligible,'TextOnly')):
        raise ValueError('all_five_phase1_metrics_required')
    candidates=('HiRes','CoT','Think')
    best=max(candidates,key=lambda key:(totals[key]['correct'],-candidates.index(key)))
    gain=Decimal(100)*Decimal(totals[best]['correct']-totals['D']['correct'])/Decimal(N)
    expected=best if gain>=Decimal('1.5') else 'D'
    if choice!=expected:raise ValueError('phase1_decision_conflicts_with_fixed_1p5_point_gate')
    return choice


def tune_input(root):
    rows=[json.loads(line) for line in (root/TUNE).read_text(encoding='utf-8').splitlines() if line.strip()]
    if len(rows)!=N or len({r['question_id'] for r in rows})!=N:
        raise ValueError('fixed_402_question_tuning_input_required')
    allowed={'question_id','case_id','question','images','figure_labels'}
    if any(set(r)-allowed or not r.get('case_id') or not r.get('images') for r in rows):
        raise ValueError('label_free_case_bound_visual_tuning_input_required')
    return [r['question_id'] for r in rows]


def arm_config(template, phase, arm_id, previous, samples=1, temperature=None):
    cfg=deepcopy(template)
    cfg.update(run_id=f'vote_20261102_p{phase}_{arm_id}',input=TUNE.as_posix(),samples=samples,
        capability_smoke=False,capability_confirmed=True,ledger=(REL/'private_ledgers'/f'p{phase}_{arm_id}.json').as_posix(),
        inherit_ledger=previous,max_requests=N*samples+math.ceil(N*samples*.05),
        max_extra_requests=math.ceil(N*samples*.05),max_attempts_per_sample=2)
    if temperature is not None:cfg['temperature']=temperature
    validate_cfg(cfg)
    return cfg


def cross_model(template, selected):
    """Keep common input/prompt fidelity, omit model-unverified Qwen flags."""
    cfg=deepcopy(template)
    cfg['figure_labels']=selected.get('figure_labels',False)
    cfg['prompt_variant']='cot' if selected['prompt_variant']=='cot' else 'answer'
    cfg['high_resolution']=False
    if cfg['model'].startswith('kimi/'):
        cfg.update(temperature=1.0,top_p=.95,extra_body={'reasoning_effort':'max'},
                   max_output_tokens=8192,stream=False,request_timeout_seconds=300)
    else:
        cfg.update(temperature=.2,extra_body={'enable_thinking':False},
                   max_output_tokens=2048,stream=False,request_timeout_seconds=120)
    cfg['configuration_differences']={
        'full_original_images_and_question_retained':True,
        'figure_labels_retained':cfg['figure_labels'],
        'selected_qwen_prompt_variant':selected['prompt_variant'],
        'cross_model_prompt_variant':cfg['prompt_variant'],
        'highres_flag_not_confirmed_for_this_model_omitted':bool(selected.get('high_resolution')),
        'qwen_thinking_flag_not_confirmed_for_this_model_omitted':selected['prompt_variant']=='think',
        'kimi_always_thinks_at_T1_max_effort':cfg['model'].startswith('kimi/'),
        'no_Qwen_only_parameters_sent_to_Kimi':True}
    return cfg


def save_phase(root, config_dir, phase, inherited_manifest, specifications, previous,
               score_arms, baseline, selection=None, ensemble=None, provenance=None):
    first_ledger=previous;arms=[]
    for arm_id,cfg in specifications:
        cfg['root']=str(root);cfg['inherit_ledger']=previous
        path=config_dir/f'p{phase}_{arm_id}.json';dump_new(path,cfg)
        out=root/REL/f'phase{phase}'/arm_id
        arms.append({'id':arm_id,'config':rel(root,path),'out':rel(root,out)})
        previous=cfg['ledger']
    phase_path=config_dir/f'phase{phase}.json';score_path=config_dir/f'phase{phase}.score.json'
    manifest={k:inherited_manifest[k] for k in ('cap_cny','new_experiment_budget_cny',
        'budget_authorization','global_request_counter')}
    phase_value=int(phase) if str(phase).isdigit() else phase
    manifest.update(root=str(root),out=(REL/f'phase{phase}').as_posix(),phase=phase_value,arms=arms,
        inherit_ledger=first_ledger,authorized_scope='phases 0 through 3 only; no automatic launch',
        reused_runs=[a['id'] for a in score_arms if a.get('reuse')],
        provenance=provenance or {},next_phase='Stop after this phase; score offline and freeze the next configuration separately.')
    validate_manifest(manifest)
    score={'phase':phase_value,'split':'tune','baseline':baseline,'ks':[1,3,5,7,9],
        'seed':20261102,'bootstrap_repeats':2000,'subsample_repeats':200,
        'arms':[{k:v for k,v in a.items() if k not in ('out','reuse')} |
            {'run':Path(os.path.relpath(a['out'],score_path.parent)).as_posix()} for a in score_arms],
        'provenance':provenance or {}}
    if selection is not None:score['selection']=selection
    if ensemble is not None:score['ensemble']=ensemble
    dump_new(phase_path,manifest);dump_new(score_path,score)
    return {'phase_manifest':rel(root,phase_path),'scoring_manifest':rel(root,score_path),
        'new_planned_requests':sum(N*cfg['samples'] for _,cfg in specifications),
        'new_paid_calls_started':0,'cap_cny':manifest['cap_cny']}


def materialize(phase, root, code, phase0_manifest, phase0_metrics=None,
                phase1_metrics=None, phase3a_metrics=None):
    root=Path(root).resolve();code=at(root,code);rel(root,code)
    config_dir=code/'configs'/NAME
    qids=tune_input(root)
    p0,templates=phase0_gate(at(root,phase0_manifest),at(root,phase0_metrics),root)
    last0=templates[p0['arms'][-1]['id']]['cfg']['ledger']
    provenance={'phase0_manifest':rel(root,at(root,phase0_manifest)),
                'phase0_metrics':rel(root,at(root,phase0_metrics)),'labels_read_by_configurator':False}
    if phase=='1':
        definitions=[('D','D_regression60','answer'),('TextOnly','D_regression60','text_only'),
                     ('HiRes','qwen_highres_smoke','answer'),('CoT','D_regression60','cot'),
                     ('Think','qwen_think_smoke','think')]
        specs=[];scoring=[]
        for name,template,variant in definitions:
            base=deepcopy(templates[template]['cfg']);base['prompt_variant']=variant
            cfg=arm_config(base,'1',name,last0);specs.append((name,cfg))
            scoring.append({'id':name,'out':root/REL/'phase1'/name})
        return save_phase(root,config_dir,'1',p0,specs,last0,scoring,'D',
            selection={'candidates':['HiRes','CoT','Think'],'minimum_gain_pp':1.5},provenance=provenance)
    p1,r1=completed(config_dir/'phase1.json',root,N,1)
    chosen=selected_phase1(at(root,phase1_metrics));anchor=r1[chosen]
    if any(x['run']['qids']!=qids for x in r1.values()):raise ValueError('tune_question_order_changed')
    provenance.update(phase1_metrics=rel(root,at(root,phase1_metrics)),selected_phase1=chosen)
    last1=r1[p1['arms'][-1]['id']]['cfg']['ledger']
    qwen_anchor={'id':'Qwen_B0','out':anchor['out'],'reuse':True}
    if phase=='2':
        cfg=arm_config(anchor['cfg'],'2','Qwen_SC9',last1,samples=9,temperature=.7)
        return save_phase(root,config_dir,'2',p0,[('Qwen_SC9',cfg)],last1,
            [qwen_anchor,{'id':'S0','out':root/REL/'phase2/Qwen_SC9','direct_arm':'Qwen_B0'}],
            'Qwen_B0',provenance=provenance)
    p2,r2=completed(config_dir/'phase2.json',root,N,9)
    if set(r2)!={'Qwen_SC9'} or r2['Qwen_SC9']['run']['qids']!=qids:
        raise ValueError('expected_saved_qwen_nine_samples_required')
    last2=r2['Qwen_SC9']['cfg']['ledger']
    if phase=='3a':
        specs=[];scoring=[qwen_anchor]
        for name,template in [('QwenMax_B0','qwen_max_smoke'),('Kimi_B0','kimi_smoke')]:
            base=cross_model(templates[template]['cfg'],anchor['cfg'])
            cfg=arm_config(base,'3a',name,last2);specs.append((name,cfg))
            scoring.append({'id':name,'out':root/REL/'phase3a'/name})
        return save_phase(root,config_dir,'3a',p0,specs,last2,scoring,'Qwen_B0',provenance=provenance)
    if phase!='3b':raise ValueError('only_authorized_phases_1_2_3a_3b')
    p3,r3=completed(config_dir/'phase3a.json',root,N,1)
    if set(r3)!={'QwenMax_B0','Kimi_B0'} or any(x['run']['qids']!=qids for x in r3.values()):
        raise ValueError('three_model_B0_anchors_required')
    values=metric(at(root,phase3a_metrics),'3a',N)
    totals=values['totals']
    if any(totals.get(k,{}).get('planned_n')!=N for k in DIRECT_IDS):
        raise ValueError('all_three_B0_tuning_scores_required')
    strongest=max(DIRECT_IDS,key=lambda key:(totals[key]['correct'],-DIRECT_IDS.index(key)))
    weights={s:totals[d]['correct']/N for d,s in zip(DIRECT_IDS,SAMPLE_IDS)}
    if not any(weights.values()):raise ValueError('positive_B0_ensemble_weights_required')
    provenance.update(phase3a_metrics=rel(root,at(root,phase3a_metrics)),
        strongest_direct=strongest,B0_correct={k:totals[k]['correct'] for k in DIRECT_IDS})
    last3=r3[p3['arms'][-1]['id']]['cfg']['ledger'];specs=[]
    scoring=[qwen_anchor]+[{'id':name,'out':r3[name]['out'],'reuse':True} for name in DIRECT_IDS[1:]]
    scoring.append({'id':'S0','out':r2['Qwen_SC9']['out'],'direct_arm':'Qwen_B0','reuse':True})
    for name,sample_id in zip(DIRECT_IDS[1:],SAMPLE_IDS[1:]):
        sample_name=name.replace('_B0','_samples');sample_n=9 if name==strongest else 3
        base=r3[name]['cfg'];temp=1.0 if base['model'].startswith('kimi/') else .7
        cfg=arm_config(base,'3b',sample_name,last3,samples=sample_n,temperature=temp)
        specs.append((sample_name,cfg));scoring.append({'id':sample_id,'out':root/REL/'phase3b'/sample_name,'direct_arm':name})
    ensemble={'members':list(SAMPLE_IDS),'weights':weights,'strongest_member':SAMPLE_IDS[DIRECT_IDS.index(strongest)],
        'samples_per_model':3,'weights_source':rel(root,at(root,phase3a_metrics)),
        'primary_vote_rule':'tune_accuracy_weighted_model_majorities',
        'Qwen_nine_samples_reused_without_new_requests':True}
    return save_phase(root,config_dir,'3b',p0,specs,last3,scoring,'Qwen_B0',ensemble=ensemble,provenance=provenance)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase',required=True,choices=('1','2','3a','3b'))
    for name in ('root','code','phase0-manifest','phase0-metrics'):
        parser.add_argument('--'+name,required=True)
    parser.add_argument('--phase1-metrics');parser.add_argument('--phase3a-metrics')
    args=parser.parse_args(argv)
    if args.phase!='1' and not args.phase1_metrics:parser.error('--phase1-metrics is required after phase 1')
    if args.phase=='3b' and not args.phase3a_metrics:parser.error('--phase3a-metrics is required for phase 3b')
    print(json.dumps(materialize(**vars(args)),ensure_ascii=False))


if __name__=='__main__':main()
