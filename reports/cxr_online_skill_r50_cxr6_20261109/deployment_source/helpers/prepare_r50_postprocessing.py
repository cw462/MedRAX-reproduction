"""Prepare local-only scoring from unchanged common R49 metric functions.

No scoring, reference-file reads, API or remote code modification occurs here.
"""
import ast
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'experiments/score_online_skill_r49.py'
TARGET=ROOT/'experiments/score_online_skill_r50.py'
PREP=ROOT/'local_assets/r50_cxr6_preparation'

CUSTOM=r'''
def adapt_saved_r49(inputs, run):
    """Reference-free raw-terminal adaptation only; never invoke the old score()."""
    from score_online_skill_r49 import adapt_current as adapt_old
    from run_online_skill_r49 import ARM as OLD_ARM
    run=Path(run)
    if (run/'generation.exitcode').read_text().strip()!='0':raise ValueError('saved_R49_raw_exit_zero_required')
    manifest=read(run/'manifest.json')
    if manifest.get('inputs')!=inputs:raise ValueError('saved_R49_original_input_order_changed')
    paths={'predictions':members(run/'predictions'/OLD_ARM,{r['question_id'] for r in inputs},'saved_R49_predictions')}
    adapted,predictions,_=adapt_old(inputs,run,paths)
    stops={q:p.get('status') for q,p in predictions.items() if str(p.get('status','')).startswith('repeated_')}
    return adapted,{'raw_archive_only':True,'private_R49_score_invoked':False,'repeated_no_progress_by_saved_status':stops}


def tool_attempt_accounting(run, tools, active_keys):
    root=run/'services/tool_cache'
    folders={p.name:p for p in root.iterdir() if p.is_dir()} if root.exists() else {}
    if set(folders)!=active_keys:raise ValueError('orphan_or_unknown_tool_attempt_requires_specific_preserved_recovery')
    physical=[]
    for key,folder in sorted(folders.items()):
        if any(not (folder/n).is_file() for n in ('request.json','started.json','result.json')):raise ValueError('unclosed_R50_tool_attempt')
        result=read(folder/'result.json');request=read(folder/'request.json');started=read(folder/'started.json')
        if tool_failure_reason(result):raise ValueError('failed_active_R50_backend_attempt')
        identity=result.get('identity',{})
        if (started.get('identity')!=identity or started.get('automatic_retry') is not False
            or request.get('backend')!=result.get('backend') or request.get('args')!=identity.get('args')
            or request.get('image')!=result.get('original_image')):raise ValueError('actual_R50_tool_request_binding_changed')
        if request['tool']=='xray_phrase_grounding':phrase_guarded_backend(run,key,result)
        physical.append(result)
    return {'physical':physical,'healthy':len(physical)}


def resources(run, receipts, tools, attempts):
    if {p.name for p in (run/'services/calls').iterdir() if p.is_dir()}-{'R50-AGENT','R50-META'}:raise ValueError('unexpected_R50_paid_arm')
    meta=[v for folder in (run/'services/calls/R50-META').glob('*') if folder.is_dir() for v in closed_calls(folder)]
    embeds=[]
    for folder in sorted((run/'services/embeddings').glob('*')):
        if not folder.is_dir():continue
        if any(not (folder/n).is_file() for n in ('request.json','started.json','response.json','result.json')):raise ValueError('unclosed_R50_embedding')
        value=read(folder/'result.json')
        if value.get('error') or value.get('response_received') is not True:raise ValueError('failed_R50_embedding')
        embeds.append(value)
    embedding={'requests':len(embeds),'successful_responses':len(embeds),
      'returned_models':sorted({v['model_returned'] for v in embeds if v.get('model_returned')}),
      'total_tokens':sum((v.get('usage') or {}).get('total_tokens',0) or 0 for v in embeds),
      'usage_unknown_count':sum(v.get('usage') is None for v in embeds),
      'usage_cost_cny_proxy_known':str(sum((Decimal(str(v['settlement']['charged_cny'])) for v in embeds if v.get('settlement',{}).get('charged_cny') is not None),Decimal(0))),
      'cost_unknown_count':sum(v.get('settlement',{}).get('charged_cny') is None for v in embeds),
      'elapsed_seconds_known':sum(v.get('elapsed_s') or 0 for v in embeds),
      'elapsed_unknown_count':sum(v.get('elapsed_s') is None for v in embeds),'provider_invoice':False}
    names=('medgemma','llava_rad','chest_xray_expert','llava_med_qa','xray_phrase_grounding','medvlm_r1')
    physical=attempts['physical'];per_tool={}
    for name in names:
        selected=[v for v in tools if v.get('tool')==name];fresh=[v for v in physical if v.get('backend')==name]
        per_tool[name]={'selected_questions':len({v['question_id'] for v in selected}),
          'question_ids':sorted({v['question_id'] for v in selected}),'logical_calls':len(selected),
          'cache_hits':sum(v.get('cache_hit') is True for v in selected),'fresh_backend_attempts':len(fresh),
          'actual_generate_events':sum(e.get('kind')=='generate' for v in fresh for e in v.get('actual_model_events',[])),
          'failed_backend_attempts':sum(tool_failure_reason(v) is not None for v in fresh),
          'backend_elapsed_seconds_known':sum(v.get('elapsed_s') or 0 for v in fresh),
          'backend_compute_seconds_known':sum(v.get('backend_compute_seconds') or 0 for v in fresh),
          'hardware_cost_unknown':bool(fresh),'clinical_verification_claim':False}
    # Actual prescreen requests, not retrieval hits inferred after the fact.
    screens=[]
    screen_calls={p.name for p in (run/'services/calls/R50-META').glob('screen_*') if p.is_dir()}
    events={p.stem:p for p in (run/'prescreen_events').glob('*.json')}
    if screen_calls!={'screen_'+q for q in events}:raise ValueError('actual_prescreen_request_event_membership')
    from run_cxr_action_r41 import parse
    for q,path in sorted(events.items()):
        event=read(path);calls=closed_calls(run/'services/calls/R50-META'/('screen_'+q))
        if len(calls)!=1:raise ValueError('one_actual_prescreen_request_required')
        messages=read(calls[0][0]/'request.json')['messages']
        payload=json.loads(messages[-1]['content'][0]['text']);actual=payload['candidates'];ids=[v['id'] for v in actual]
        chosen=parse(response_text(calls[0][0]))['ids'];ctx=read(run/'contexts'/(q+'.json'))
        if (not ids or event['input_pool_ids']!=ids or event['input_pool_count']!=len(ids)
            or event['returned_ids']!=chosen or event['returned_count']!=len(chosen)
            or event['all_rejected'] is not (not bool(chosen))
            or not {v['id'] for v in ctx['selected_skills']}<=set(chosen)):
            raise ValueError('actual_prescreen_before_after_or_injection_changed')
        screens.append(event)
    lifecycle=Counter();branches=Counter();credits=[]
    for folder in sorted((run/'windows').glob('*')):
        if not folder.is_dir():continue
        event=read(folder/'events.json')
        for value in event['write']:
            if value.get('operation'):lifecycle[value['operation']]+=1
        for value in event['govern']:lifecycle[value[0]]+=1
        credits+=event['credit']
    for value in read(run/'final_repo.json')['skills'].values():branches[value['c']['branch']]+=1
    agent_values=[v for calls in receipts.values() for v in calls]
    starts=[utc(v[1]['utc']) for v in agent_values+meta];ends=[utc(v[2]['utc']) for v in agent_values+meta]
    return {'agent':receipt_resources(agent_values),'R50_META':receipt_resources(meta),'embedding':embedding,
      'tools':{'logical_calls':len(tools),'cache_hits':sum(v.get('cache_hit') is True for v in tools),
        'fresh_backend_attempts':len(physical),'healthy_backend_attempts':attempts['healthy'],
        'failed_backend_attempts':0,'unknown_backend_attempts':0,
        'backend_elapsed_seconds_known':sum(v.get('elapsed_s') or 0 for v in physical),
        'backend_compute_seconds_known':sum(v.get('backend_compute_seconds') or 0 for v in physical),
        'hardware_cost_unknown':bool(physical),'per_tool':per_tool},
      'prescreen':{'requests':len(screens),'input_candidates':sum(v['input_pool_count'] for v in screens),
        'returned_candidates':sum(v['returned_count'] for v in screens),'all_rejected_questions':sum(v['all_rejected'] for v in screens),
        'events':screens},
      'Skill_lifecycle':{'events':dict(lifecycle),'final_branches':{k:branches[k] for k in ('general','task_level','action_level')},'credit_events':credits},
      'request_span_seconds':(max(ends)-min(starts)).total_seconds() if starts and ends else None,
      'request_span_not_total_job_or_provider_billing_time':True,
      'new3_health_probe_cost_time_excluded_from_production_totals':True,
      'old_R49_failure_registrations_imported':False,'uniform_MAIRA_EOS_control_from_start':True}
'''


def main():
    assert not TARGET.exists(),'R50_postprocessor_already_prepared_inspect_not_repeat'
    source=SOURCE.read_text(encoding='utf-8-sig');tree=ast.parse(source)
    functions={n.name:ast.get_source_segment(source,n) for n in tree.body if isinstance(n,ast.FunctionDef)}
    names=['rows','utc','members','completed_gate','closed_calls','response_text','adapt_current','adapt_historical','adapt_r47',
           'phrase_guarded_backend','check_semantics','receipt_resources','score','main']
    header=source[:source.index('EXPECTED =')].replace('r49','r50').replace('R49','R50')
    constants="EXPECTED={'chexbench':(618,'M43',466),'slake':(114,'M43',108),'vqarad':(116,'M42',100)}\n"
    for name in ('PHRASE_POLICY','PHRASE_TOOL','PHRASE_REVISION','PHRASE_MODEL_REVISION','PHRASE_TOKENS'):
        node=next(n for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id==name for t in n.targets))
        constants+=ast.get_source_segment(source,node)+'\n'
    parts=[]
    for name in names:
        text=functions[name].replace('r49','r50').replace('R49','R50')
        if name=='check_semantics':text=text.replace('tool_values.append(selection)',"tool_values.append(dict(selection,question_id=qid))")
        if name=='score':
            text=text.replace('r47_run=None):','r47_run=None, r49_run=None):')
            marker='    # Reference-free adaptation of EVERY compared raw arm is now complete.'
            assert marker in text
            text=text.replace(marker,"    if r49_run is None:raise ValueError('saved_R49_raw_comparator_required')\n    comparisons['R49_online_GT_Skill'],r49_provenance=adapt_saved_r49(inputs,r49_run)\n"+marker)
            a=text.index('    meta_repairs = registered_meta_schema_repairs(run)')
            b=text.index('    reference_rows = rows(references)',a)
            text=text[:a]+"    resource = resources(run,receipts,tools,attempts)\n"+text[b:]
            marker='    subsets = np.array'
            text=text.replace(marker,"    if counts['R49_online_GT_Skill']!={'chexbench':465,'slake':113,'vqarad':97}[dataset]:raise ValueError('fixed_R49_saved_common_metric_count_changed')\n"+marker)
            marker='    return summary, detail'
            text=text.replace(marker,"    summary.update(R49_saved_comparator_provenance=r49_provenance,\n      R50_combined_changes=manifest.get('r50_method_changes'),\n      R50_uniform_inherited_controls=manifest.get('r50_baseline_controls'),\n      repeated_no_progress_by_saved_status={q:p.get('status') for q,p in predictions.items() if str(p.get('status','')).startswith('repeated_')})\n    groups={}\n    for label,field in [('same_image_followup','same_image_hit'),('skill_injected','skill_hit')]:\n        groups[label]={}\n        for flag in (False,True):\n            selected=[d for d in detail if d[field] is flag]\n            groups[label][str(flag)]={'n':len(selected),'correct':sum(d['arms'][ARM]['aligned_correct'] for d in selected),'descriptive_not_randomized':True}\n    summary['descriptive_groups']=groups\n"+marker)
            text=text.replace("'Historical differences combine Skill learning, changed executor/call budgets, sampling and time.'", "'Historical differences combine six tools and applicability gate plus onlineGT, executor/call budgets, prompts, inherited EOS policy, sampling and time.'")
        if name=='main':
            text=text.replace("parser.add_argument('--r47-run', type=Path)","parser.add_argument('--r47-run', type=Path); parser.add_argument('--r49-run', required=True, type=Path)")
            text=text.replace('r47_run=args.r47_run)','r47_run=args.r47_run, r49_run=args.r49_run)')
        parts.append(text)
    text=header+constants+'\n\n'+CUSTOM+'\n\n'+'\n\n'.join(parts)+"\n\nif __name__=='__main__':main()\n"
    ast.parse(text)
    with TARGET.open('x',encoding='utf-8') as f:f.write(text)
    receipt={'status':'local_postprocessing_source_prepared_not_executed','source':TARGET.relative_to(ROOT).as_posix(),
      'reused_common_functions':names,'old_R49_recovery_registration_functions_copied':False,
      'original_metric_and_adapter_formulas_changed':False,'new_R49_private_scoring_run':False,
      'all_raw_compared_arms_reference_free_adapted_before_labels':True,
      'production_remote_code_modified':False,'new_inference_reference_reads_or_hash_checks':0,
      'not_yet_model_reviewed':'postprocessing was prepared during generation; actual full result review must include this new code'}
    with (PREP/'SCORE_PREPARATION.json').open('x',encoding='utf-8') as f:json.dump(receipt,f,indent=2);f.write('\n')
    print(json.dumps({'prepared':TARGET.name,'AST':'passed','actual_scoring_or_reference_reads':0,'producer_code_changed':False}))


if __name__=='__main__':main()
