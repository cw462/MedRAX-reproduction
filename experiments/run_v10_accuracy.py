"""Fixed sixty-question V10: shared P0 and blind plan, then V/VK/VKE.

Generation never opens evaluation labels. Shared planning costs one request per
question and occupies one of each branch's four model slots. Each branch has at
most three further requests, two tool attempts, and one disagreement gate.
"""
from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import sys
import time
from types import SimpleNamespace
import uuid

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
from run_v9_diagnostic import (RawEvidence, accounting, append, image_items, jsonable,
    now, options_of, parse_gate, preflight, projection, read_jsonl, saved_context, write_json)

GROUPS = ('V', 'VK', 'VKE')

PLAN_PROMPT = '''Compare ALL options and identify at most TWO questions whose visible
attributes best separate them. Consider side, location, number, morphology, size,
spatial relationship, or combinations. Do not choose an answer. Use current images
and question only; no historical diagnosis or answer is available. Return concise JSON:
{"task":"...","anatomy":"...","option_differences":[{"attribute":"...",
"question":"specific visual question","option_labels":["A","B"],
"image_ids":["image:1"]}],"missing_attributes":["..."],
"recommended_view":"full|crop|compare","uncertain":false}.
Keep full images for distribution and orientation; local pixels help small details.
Patient left/right is not automatically image left/right; do not infer time ordering.'''

ACTION_PROMPT = '''You independently answer a radiology multiple-choice question by
examining actual current images. The P0 final option is deliberately withheld.
Use the shared option-difference questions to choose where to look, which images to
compare, and what targeted tool question to ask. Supplied knowledge and training
experience are conditional action advice, never current-patient observations.
Apply relevant advice BEFORE selecting the next action; skip irrelevant advice.
You have at most TWO tool attempts in total (including crop_current_image).
Make at most ONE tool call per turn. For a subtle local detail, use crop_current_image
to obtain real pixels and inspect the returned crop with the original. For distribution
or view/time relationships, compare full images. Cropping creates no new information.
Tool questions must discriminate current options, not ask for a generic report.
Use exactly the advertised tool argument schema and authorized current image paths.
If no tool would help, state current best option and visible evidence briefly as JSON
with answer, uncertain, evidence_refs, observations. Always choose a legal best answer
even when uncertain; list missing evidence separately. Avoid unsupported precision.
Tool diagnostic assertions need image verification. Omission is not observed absence.
Do not output hidden chain-of-thought; only concise observable evidence and action.'''

FINAL_PROMPT = '''Choose the CURRENT BEST legal option even when evidence is incomplete.
Return concise JSON: {"answer":"ONE legal option letter","uncertain":true/false,
"changed_attributes":["decisive option attributes"],"evidence_refs":["exact known ids"],
"observations":[{"attribute":"...","image_ids":["image:1"],"value":"brief visible finding",
"status":"observed_present|observed_absent|unresolved|hypothesis","evidence_refs":["image:1"]}],
"missing_evidence":["remaining gaps"],"applied_context_ids":["only ids actually used"]}.
Answer must never be null. Uncertainty is separate from selecting your best option.
Use actual pixels. A training result or repeated tool diagnosis is not patient evidence.
Check every distinguishing property of multi-attribute options. Keep the response short.'''

GATE_PROMPT = '''Choose between the initial and new option using attached current
full images, local crops, and tool observations. A candidate assertion is a hypothesis.
Compare ALL properties that differ between the options, including size, contour,
side, site, count and relationships. One supported property does not establish the
other changed properties. Uncertainty alone does not invalidate a best-answer candidate;
select the better supported of these two options. No knowledge or training outcome
can substitute for visible current evidence. Return ONLY concise JSON with exactly:
decision ("accept" or "retain"), changed_attributes (string array), evidence_refs
(exact known ids), unmet_requirements (string array), reason (short observable evidence).
Accept only when references support the changes and no required changed attribute
remains unsupported. Do not output hidden reasoning.'''


def tolerant_object(text):
    if not isinstance(text, str):
        raise ValueError('non_text_json')
    decoder = json.JSONDecoder()
    for index, ch in enumerate(text):
        if ch == '{':
            try:
                value, _ = decoder.raw_decode(text[index:])
                if isinstance(value, dict):
                    return value
            except ValueError:
                pass
    raise ValueError('no_json_object')


def normalize_plan(text, row, image_ids):
    """Malformed metadata cannot discard the visual reasoning opportunity."""
    issues = []
    try:
        obj = tolerant_object(text)
    except ValueError:
        obj = {}
        issues.append('plan_json_fallback')
    differences = []
    def string_list(value):
        return [x for x in value if isinstance(x,str)] if isinstance(value,list) else []
    for raw in obj.get('option_differences', []) if isinstance(obj.get('option_differences'), list) else []:
        if isinstance(raw, dict) and isinstance(raw.get('question'), str):
            differences.append({'attribute': str(raw.get('attribute', 'option_difference'))[:300],
                'question': raw['question'][:800],
                'option_labels': [x for x in string_list(raw.get('option_labels')) if x in options_of(row['question'])],
                'image_ids': [x for x in string_list(raw.get('image_ids')) if x in image_ids] or image_ids})
    if not differences:
        issues.append('plan_difference_fallback')
        differences = [{'attribute': 'option_difference',
            'question': 'Compare the visible properties that distinguish all supplied options.',
            'option_labels': list(options_of(row['question'])), 'image_ids': image_ids}]
    gaps = obj.get('missing_attributes', [])
    return {'task': str(obj.get('task', row.get('official_group', 'visual discrimination')))[:300],
        'anatomy': str(obj.get('anatomy', 'current imaged anatomy'))[:300],
        'option_differences': differences[:2],
        'missing_attributes': [x[:300] for x in gaps if isinstance(x, str)][:4] if isinstance(gaps, list) else [],
        'recommended_view': obj.get('recommended_view') if obj.get('recommended_view') in ('full','crop','compare') else 'full',
        'uncertain': bool(obj.get('uncertain', True)), 'normalization_issues': issues}


def fixed_sixty(rows, mapping):
    if len(rows) != 60 or len({r['question_id'] for r in rows}) != 60:
        raise ValueError('expected_original_fixed_sixty_unique_inputs')
    if any(set(r) != {'question_id','question','images'} for r in rows):
        raise ValueError('inference_input_has_extra_fields')
    if any(r['question_id'] not in mapping for r in rows):
        raise ValueError('missing_official_category')
    return {'planned_n': 60, 'method': 'original_fixed60_source_order_no_resampling_no_labels',
        'rows': [dict(r, official_group=mapping[r['question_id']]) for r in rows]}


def run_plan(runtime, ledger, profile, args, row, paths, trace, folder):
    import memory_agent_eval as mae
    from run_bc_recovery import new_ctx
    from langchain_core.messages import HumanMessage, SystemMessage, messages_to_dict
    folder.mkdir(parents=True, exist_ok=True)
    ctx = new_ctx(row['question_id'], str(uuid.uuid4()), paths, runtime, args, trace, 0, 1)
    ctx['run_id'], ctx['arm'] = args.run_id, 'shared_plan'
    began, started = time.monotonic(), now()
    base, images = projection(row, paths, [])
    messages = [SystemMessage(content=PLAN_PROMPT)] + base
    error, text = None, ''
    try:
        response = mae.BudgetedModel(runtime.model, ledger, ctx, profile).invoke(messages)
        messages.append(response)
        text = response.content
    except Exception as exc:
        error = type(exc).__name__ + ': ' + str(exc)
    plan = normalize_plan(text, row, [i['image_id'] for i in images])
    result = {'question_id': row['question_id'], 'plan': plan, 'error': error,
        'accounting': accounting(ctx), 'stop_run': ctx.get('stop_run', False),
        'stop_reason': ctx.get('stop_reason') or ctx.get('money_status'),
        'path': str(folder/'messages.json'),
        'timing': {'started_utc': started, 'ended_utc': now(), 'elapsed_s': round(time.monotonic()-began,3)}}
    write_json(folder/'messages.json', messages_to_dict(messages))
    write_json(folder/'context.json', saved_context(ctx))
    write_json(folder/'terminal.json', result)
    return result


def verify_smoke(out, qids):
    """No labels: verify real multimodal messages and legal answers before expansion."""
    p0s={r['question_id']:r for r in read_jsonl(out/'p0_results.jsonl')}
    branches=[r for r in read_jsonl(out/'candidate_results.jsonl') if r['question_id'] in qids]
    if any(p0s[q]['initial'] is None for q in qids) or len(branches)!=len(qids)*3:
        raise RuntimeError('smoke_missing_p0_or_branches')
    image_counts=[]
    crop_count=0
    for r in branches:
        if r.get('candidate') is None or r.get('candidate_error') or r.get('gate_error') or r.get('retrieval_error'):
            raise RuntimeError('smoke_candidate_or_gate_failure:'+r['question_id']+':'+r['group'])
        messages=json.loads(Path(r['evidence_package']).read_text())
        count=sum(isinstance(p,dict) and p.get('type')=='image_url'
            and p.get('image_url',{}).get('url','').startswith('data:image/')
            for m in messages for p in (m.get('data',{}).get('content') if isinstance(m.get('data',{}).get('content'),list) else []))
        if not count:
            raise RuntimeError('smoke_no_actual_image_payload')
        image_counts.append(count)
        crop_count+=sum(o.get('tool_name')=='crop_current_image' for o in r.get('new_observations',[]))
    result={'status':'passed','question_ids':qids,'branches':len(branches),
        'actual_image_payload_counts':image_counts,'actual_crop_returns':crop_count,
        'labels_opened':False,'checked_utc':now()}
    write_json(out/'smoke_check.json',result)
    print(json.dumps({'event':'smoke_passed',**result}),flush=True)


def main(argv=None):
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--config',type=Path,required=True)
    ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--prepare-only',action='store_true')
    ap.add_argument('--api-key-stdin',action='store_true')
    ap.add_argument('--smoke-only',action='store_true')
    a=ap.parse_args(argv)
    cfg=json.loads(a.config.read_text(encoding='utf-8'))
    root,out=Path(cfg['root']),a.out.resolve()
    out.mkdir(parents=True,exist_ok=True)
    source=root/cfg['input']
    selection=fixed_sixty(read_jsonl(source),json.loads((root/cfg['official_groups']).read_text()))
    image_root=(root/'data/memory_v1/images').resolve()
    for row in selection['rows']:
        preflight(row,image_root)
    implementation_files=['run_v10_accuracy.py','v10_visual.py','v10_retrieval.py','run_v9_diagnostic.py',
        'v9_retrieval.py','memory_agent_eval.py','run_bc_recovery.py','tool_registry_ext.py','provider_ledger.py','provider_profile.py']
    effective=dict(cfg,input_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        implementation_sha256={n:hashlib.sha256((HERE/n).read_bytes()).hexdigest() for n in implementation_files},
        baseline_implementation='memory_agent_eval.run_arm',
        gold_loaded_by_generation=False,provider_snapshot='unavailable',
        checkpoint_reuse='only_same_V10_run_complete_config',
        shared_plan_accounting='one_call_once_per_question_one_slot_in_each_branch',
        v91_provenance='equivalent_modules_reimplemented_bundle_unavailable_locally')
    for filename,value in [('selection.json',selection),('effective_config.json',effective)]:
        path=out/filename
        if path.exists() and json.loads(path.read_text())!=value:
            raise ValueError('frozen_run_configuration_changed:'+filename)
        write_json(path,value)
    # Reuse the already authorized ledger, including its identity/inheritance policy.
    state=json.loads((root/cfg['ledger']).read_text())
    if Decimal(state['policy']['cap_cny'])!=Decimal(cfg['cap_cny']) or state.get('blocked'):
        raise ValueError('existing_ledger_policy_mismatch_or_blocked')
    if a.prepare_only:
        print(json.dumps({'status':'prepared','planned_n':60,'ledger_committed_cny':state['committed_cny'],
            'existing_cap_cny':state['policy']['cap_cny']}),flush=True)
        return 0
    key=sys.stdin.readline().strip() if a.api_key_stdin else ''
    if not key:
        raise ValueError('missing_api_key')
    import memory_agent_eval as mae
    import diagnostic_eval as diag
    from provider_ledger import ProviderLedger
    from provider_profile import get_profile
    from v10_retrieval import V10Retriever
    from langchain_core.messages import messages_to_dict
    args=SimpleNamespace(repo=root/'source/MedRAX',model_cache=root/'models/hf_full',
        classifier_checkpoint=root/'models/home/.torchxrayvision/models_data/nih-pc-chex-mimic_ch-google-openi-kaggle-densenet121-d121-tw-lr001-rot45-tr15-sc15-seed0-best.pt',
        segmentation_checkpoint=root/'models/home/.torchxrayvision/models_data/pspnet_chestxray_best_model_4.pth',
        report_cache=root/'models/hf_report',temperature=cfg['temperature'],top_p=cfg['top_p'],
        max_output_tokens=cfg['max_output_tokens'],request_timeout_seconds=cfg['request_timeout_seconds'],
        tools=cfg['tools'],image_detail=cfg['image_detail'],max_case_seconds=cfg['max_case_seconds'],
        max_tool_calls=cfg['p0_tool_calls'],max_model_calls=cfg['p0_model_calls'],
        recursion_limit=cfg['recursion_limit'],run_id=out.name,artifact_root=out/'artifacts')
    retriever=V10Retriever(root/cfg['knowledge_pack'],root/cfg['pool'],root/cfg['skills'],
        dense_model_path=root/cfg['dense_cache'],questions_path=root/cfg['training_questions'],
        max_chars=cfg['experience_max_chars'],top_k=cfg['knowledge_top_k'])
    utils=diag.smoke.module_from_file('_v10_utils',args.repo/'medrax/utils/utils.py')
    prompt=utils.load_prompts_from_file(str(args.repo/'medrax/docs/system_prompts.txt'))['MEDICAL_ASSISTANT']
    profile=get_profile(cfg['model'])
    runtime=mae.build_runtime(args,profile,key,prompt,out/'artifacts'/('runtime_'+uuid.uuid4().hex))
    write_json(out/'runtime_tools.json',runtime.tool_provenance)
    p0s={r['question_id']:r for r in read_jsonl(out/'p0_results.jsonl')}
    plans={r['question_id']:r for r in read_jsonl(out/'shared_plans.jsonl')}
    completed={(r['question_id'],r['group']) for r in read_jsonl(out/'candidate_results.jsonl')}
    for row in selection['rows']:
        qid=row['question_id']; folder=out/'checkpoints'/qid
        for mapping,rel,dest in [(p0s,'p0_terminal.json','p0_results.jsonl'),
                                 (plans,'shared_plan/terminal.json','shared_plans.jsonl')]:
            if qid not in mapping and (folder/rel).exists():
                mapping[qid]=json.loads((folder/rel).read_text())
                append(out/dest,mapping[qid])
        for group in GROUPS:
            terminal=folder/group/'terminal.json'
            if (qid,group) not in completed and terminal.exists():
                append(out/'candidate_results.jsonl',json.loads(terminal.read_text()))
                completed.add((qid,group))
    def status(state,**extra):
        write_json(out/'status.json',dict(status=state,updated_utc=now(),planned_n=60,
            p0_completed=len(p0s),plans_completed=len(plans),branches_completed=len(completed),
            group_completed={g:sum(x[1]==g for x in completed) for g in GROUPS},**extra))
    status('initializing')
    smoke_n=cfg['smoke_questions']
    stages=[('smoke',selection['rows'][:smoke_n],('VKE','V','VK')),
            ('primary',selection['rows'],('VKE',)),
            ('ablations',selection['rows'],('V','VK'))]
    with ProviderLedger(root/cfg['ledger'],profile,cap_cny=cfg['cap_cny'],
            inherit_ledger_path=root/cfg['inherit_ledger']) as ledger, (out/'execution.trace.jsonl').open('a',encoding='utf-8') as trace:
        try:
            for stage,selected_rows,groups in stages:
                status('running',stage=stage)
                for index,row in enumerate(selected_rows):
                    qid=row['question_id']; folder=out/'checkpoints'/qid
                    folder.mkdir(parents=True,exist_ok=True)
                    if all((qid,g) in completed for g in groups):
                        continue
                    paths=preflight(row,image_root)
                    if qid not in p0s:
                        print(json.dumps({'event':'p0_started','qid':qid,'index':index+1,'stage':stage,'utc':now()}),flush=True)
                        attempt=folder/'p0'/uuid.uuid4().hex
                        attempt.mkdir(parents=True)
                        raw=RawEvidence(attempt/'raw_tools.jsonl','p0',args.artifact_root)
                        began,started=time.monotonic(),now()
                        captured={}
                        def capture(messages,ctx,report):
                            checkpoint={'question_id':qid,'messages':messages_to_dict(messages),
                                'tool_context':saved_context(ctx),'raw_observations':raw.rows,
                                'system_prompt':runtime.agent_system,
                                'tool_schemas':{n:t.args_schema.model_json_schema() for n,t in runtime.tools.items()},
                                'effective_config':effective,'implementation_version':cfg['implementation_version'],
                                'status':report['status'],'initial':report['answer_letter']}
                            write_json(attempt/'checkpoint.json',checkpoint)
                            captured.update(accounting=accounting(ctx))
                        report=mae.run_arm(runtime,ledger,profile,row,paths,'V10_P0',
                            {'thread_id':str(uuid.uuid4())},args.run_id,args,trace,semantic=raw,checkpoint_callback=capture)
                        initial=report['answer_letter'] if report['status']=='completed' else None
                        if initial not in options_of(row['question']):initial=None
                        p0=dict(question_id=qid,initial=initial,status=report['status'],report=report,
                            checkpoint=str(attempt/'checkpoint.json'),raw_tools=str(raw.path),accounting=captured.get('accounting'),
                            timing={'started_utc':started,'ended_utc':now(),'elapsed_s':round(time.monotonic()-began,3)})
                        write_json(folder/'p0_terminal.json',p0)
                        append(out/'p0_results.jsonl',p0);p0s[qid]=p0
                        if report.get('stop_run'):
                            raise RuntimeError('provider_or_ledger_stop:'+str(report.get('stop_reason')))
                    if qid not in plans:
                        plans[qid]=run_plan(runtime,ledger,profile,args,row,paths,trace,folder/'shared_plan')
                        append(out/'shared_plans.jsonl',plans[qid])
                        if plans[qid].get('stop_run'):
                            raise RuntimeError('provider_or_ledger_stop:'+str(plans[qid].get('stop_reason')))
                    shared=read_jsonl(p0s[qid]['raw_tools'])
                    for group in groups:
                        if (qid,group) in completed:continue
                        print(json.dumps({'event':'branch_started','qid':qid,'group':group,'utc':now()}),flush=True)
                        result=run_branch(runtime,ledger,profile,args,row,paths,p0s[qid]['initial'],
                            copy.deepcopy(shared),plans[qid]['plan'],trace,retriever,group,folder/group/uuid.uuid4().hex)
                        write_json(folder/group/'terminal.json',result)
                        append(out/'candidate_results.jsonl',result);completed.add((qid,group))
                        print(json.dumps({'event':'branch_finished','qid':qid,'group':group,
                            'candidate':result['candidate'],'final':result['final'],
                            'candidate_error':result.get('candidate_error'),'gate_error':result.get('gate_error'),
                            'elapsed_s':result['timing']['elapsed_s']}),flush=True)
                        status('running',stage=stage)
                        if result.get('stop_run'):
                            raise RuntimeError('provider_or_ledger_stop:'+str(result.get('stop_reason')))
                if stage=='smoke':
                    verify_smoke(out,[r['question_id'] for r in selected_rows])
                    if a.smoke_only:
                        status('smoke_complete',stage=stage)
                        return 0
            status('generation_complete')
        except Exception as exc:
            status('stopped',error=type(exc).__name__+': '+str(exc))
            raise
    return 0


def branch_runtime(runtime, images, crop_dir):
    from langchain_core.tools import StructuredTool
    from v10_visual import crop_image
    def crop_current_image(image_path: str, box: list[float]):
        """Crop actual current image pixels. box is normalized left,top,right,bottom (0..1).
        Use image coordinates, not inferred patient side; retain full image for orientation.
        """
        path = Path(image_path).resolve()
        match = next((i for i in images if Path(i['path']).resolve() == path), None)
        if match is None:
            raise ValueError('crop_source_not_in_current_images')
        return crop_image(match['image_id'], box, images, crop_dir,
                          crop_id='crop:'+uuid.uuid4().hex[:12])
    crop = StructuredTool.from_function(crop_current_image)
    tools = dict(runtime.tools, crop_current_image=crop)
    provenance = dict(runtime.tool_provenance, crop_current_image={
        'kind': 'utility', 'implementation': 'v10_visual.crop_image',
        'version': 'v10-crop-1', 'clinical_evidence': 'unadjudicated'})
    return SimpleNamespace(model=runtime.model, tools=tools, tool_provenance=provenance)


def run_branch(runtime, ledger, profile, args, row, paths, initial, shared, plan, trace, retriever, group, folder):
    import memory_agent_eval as mae
    from run_bc_recovery import new_ctx
    from v10_visual import parse_candidate
    from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage, messages_to_dict
    began, started = time.monotonic(), now()
    folder.mkdir(parents=True, exist_ok=True)
    base, images = projection(row, paths, shared)
    bruntime = branch_runtime(runtime, images, args.artifact_root/'crops'/row['question_id']/group/folder.name)
    ctx = new_ctx(row['question_id'], str(uuid.uuid4()), paths, bruntime, args, trace, 2, 3)
    ctx['run_id'], ctx['arm'] = args.run_id, group
    ctx['allowed_images'].update(Path(i['path']) for i in images)
    raw = RawEvidence(folder/'raw_tools.jsonl', group, args.artifact_root)
    ctx['semantic_writer'] = raw
    refs = {i['image_id'] for i in images} | {e['evidence_ref'] for e in shared}
    result = dict(question_id=row['question_id'], group=group, initial=initial, candidate=None,
        final=initial, candidate_error=None, gate_error=None, gate={'decision':'not_called'},
        fallback=None, k_ids=[], e_ids=[], new_observations=[],
        original_observation_refs=sorted(refs), evidence_package=str(folder/'messages.json'),
        shared_plan_slot=1, additional_model_cap=3)
    try:
        retrieval = retriever.retrieve(row, shared, set(bruntime.tools), group, plan=plan)
    except Exception as exc:
        result['retrieval_error'] = type(exc).__name__+': '+str(exc)
        retrieval = {'k_block':'','e_block':'','k_ids':[],'e_ids':[],
            'k_audit':{'abstained':True},'e_audit':{'abstained':True},
            'error':result['retrieval_error'],'fallback':'visual_only_after_retrieval_error'}
    write_json(folder/'retrieval.json', retrieval)
    result.update({k: retrieval.get(k, []) for k in ('k_ids','e_ids')})
    result['memory_tokens'] = {k: retrieval.get(k) for k in ('k_token_estimate','e_token_estimate','token_count_method')}
    messages = [SystemMessage(content=ACTION_PROMPT)] + base + [HumanMessage(content=
        'SHARED OPTION DIFFERENCES (no P0 final answer):\n'+json.dumps(plan,ensure_ascii=False)+
        '\nCONDITIONAL KNOWLEDGE ACTION RULES:\n'+retrieval['k_block']+
        '\nTRAINING ACTION EXPERIENCES (weak supervision):\n'+retrieval['e_block']+
        '\nKnown current evidence ids: '+json.dumps(sorted(refs)))]
    model = mae.BudgetedModel(runtime.model, ledger, ctx, profile)
    bound = mae.BudgetedModel(runtime.model.bind_tools(list(bruntime.tools.values())), ledger, ctx, profile)
    tracked = {n: mae.TrackedTool(t, bruntime.tool_provenance[n], ctx) for n,t in bruntime.tools.items()}
    candidate_obj, prior_candidate = {}, None
    try:
        for phase in (1, 2):
            if ctx['budget'].counts['tool'] >= 2:
                break
            ctx['phase'] = phase
            response = bound.invoke(messages)
            messages.append(response)
            calls = response.tool_calls or []
            if not calls:
                try:
                    prior_candidate = parse_candidate(response.content, options_of(row['question']), refs)
                except ValueError:
                    pass
                break
            for call in calls:
                attempt = {'requested_utc':now(),'name':call['name'],'args':call['args'],'id':call['id']}
                try:
                    if ctx['budget'].counts['tool'] >= 2:
                        raise ValueError('total_two_tool_attempt_limit')
                    if call['name'] not in tracked:
                        ctx['budget'].reserve('tool',call['name'])
                        raise ValueError('unknown_tool')
                    returned = tracked[call['name']].invoke(call['args'])
                    content = json.dumps(jsonable(returned),ensure_ascii=False)
                    attempt['status'] = 'rejected' if isinstance(returned,str) and returned.startswith('TOOL_CALL_REJECTED') else 'returned'
                except Exception as exc:
                    content=json.dumps({'error':type(exc).__name__,'detail':str(exc)})
                    attempt.update(status='error',error=content)
                append(folder/'tool_attempts.jsonl',attempt)
                messages.append(ToolMessage(content=content,tool_call_id=call['id'],name=call['name']))
            refs.update(e['evidence_ref'] for e in raw.rows)
            fresh=[i for e in raw.rows for i in e.get('artifacts',[]) if i['image_id'] not in refs]
            if fresh:
                refs.update(i['image_id'] for i in fresh)
                images.extend(fresh)
                ctx['allowed_images'].update(Path(i['path']) for i in fresh)
                messages.append(HumanMessage(content=[{'type':'text','text':
                    'ACTUAL NEW IMAGE PIXELS. Compare with full originals, which remain above. '+json.dumps(fresh)}]
                    +image_items([i['path'] for i in fresh])))
            messages.append(HumanMessage(content='Inspect the actual returned pixels. Known evidence ids: '+
                json.dumps(sorted(refs))+'. If useful, take one remaining targeted action; otherwise give current best answer.'))
        ctx['phase']=3
        messages.append(HumanMessage(content=FINAL_PROMPT+'\nLegal options: '+
            json.dumps(list(options_of(row['question'])))+'\nKnown evidence ids: '+json.dumps(sorted(refs))))
        response=model.invoke(messages)
        messages.append(response)
        try:
            candidate,candidate_obj=parse_candidate(response.content,options_of(row['question']),refs)
        except ValueError as exc:
            if ctx['actual_model_calls'] < 3:
                messages.append(HumanMessage(content='Return ONLY the single letter of your current best option. Legal letters: '+
                    ','.join(options_of(row['question']))+'. Do not abstain.'))
                response=model.invoke(messages)
                messages.append(response)
                candidate,candidate_obj=parse_candidate(response.content,options_of(row['question']),refs)
                result['candidate_recovery']='letter_only_within_cap'
            elif prior_candidate is not None:
                candidate,candidate_obj=prior_candidate
                result['candidate_recovery']='previous_independent_model_answer'
            else:
                raise exc
        result.update(candidate=candidate,candidate_payload=candidate_obj,
            changed_attributes=candidate_obj.get('changed_attributes',[]),
            candidate_observations=candidate_obj.get('observations',[]))
    except Exception as exc:
        if prior_candidate is not None and not ctx.get('stop_run'):
            candidate,candidate_obj=prior_candidate
            result.update(candidate=candidate,candidate_payload=candidate_obj,
                changed_attributes=candidate_obj.get('changed_attributes',[]),
                candidate_observations=candidate_obj.get('observations',[]),
                candidate_recovery='previous_independent_model_answer_after_error',
                recovery_error=type(exc).__name__+': '+str(exc))
        else:
            result['candidate_error']=type(exc).__name__+': '+str(exc)
    write_json(folder/'messages.json',messages_to_dict(messages))
    write_json(folder/'context.json',saved_context(ctx))
    result['new_observations']=raw.rows
    result['candidate_accounting']=accounting(ctx)
    result['candidate_timing']={'started_utc':started,'ended_utc':now(),'elapsed_s':round(time.monotonic()-began,3)}
    result['stop_run']=ctx.get('stop_run',False)
    result['stop_reason']=ctx.get('stop_reason') or ctx.get('money_status')
    candidate=result['candidate']
    if candidate is not None and initial is not None and candidate!=initial and not result['stop_run']:
        gtime,gstarted=time.monotonic(),now()
        gctx=new_ctx(row['question_id'],str(uuid.uuid4()),paths,bruntime,args,trace,0,1)
        gctx['run_id'],gctx['arm']=args.run_id,group+'_gate'
        gate_base,_=projection(row,paths,shared+raw.rows)
        gate_messages=[SystemMessage(content=GATE_PROMPT)]+gate_base+[HumanMessage(content=json.dumps({
            'initial':initial,'candidate':candidate,'candidate_claims':candidate_obj,
            'option_differences':plan,'evidence_refs':sorted(refs)},ensure_ascii=False))]
        try:
            response=mae.BudgetedModel(runtime.model,ledger,gctx,profile).invoke(gate_messages)
            gate_messages.append(response)
            result['gate']=parse_gate(response.content,refs)
        except Exception as exc:
            result['gate_error']=type(exc).__name__+': '+str(exc)
            result['gate']={'decision':'gate_error'}
        write_json(folder/'gate_messages.json',messages_to_dict(gate_messages))
        result['gate_accounting']=accounting(gctx)
        result['gate_timing']={'started_utc':gstarted,'ended_utc':now(),'elapsed_s':round(time.monotonic()-gtime,3)}
        if gctx.get('stop_run'):
            result.update(stop_run=True,stop_reason=gctx.get('stop_reason') or gctx.get('money_status'))
    if candidate is None:
        result.update(final=initial,fallback='candidate_error')
    elif initial is None:
        result.update(final=candidate,gate={'decision':'p0_missing_use_independent_candidate'})
    elif candidate==initial:
        result.update(final=initial,gate={'decision':'no_change'})
    elif result.get('gate_error'):
        result.update(final=initial,fallback='gate_error')
    else:
        result['final']=candidate if result['gate'].get('decision')=='accept' else initial
    result['status']='completed' if candidate is not None else 'candidate_failed'
    total=dict(result['candidate_accounting'])
    ga=result.get('gate_accounting',{})
    for k in ('model_calls','tool_calls','input_tokens','output_tokens','total_tokens'):
        total[k]=total[k]+ga.get(k,0) if total[k] is not None and ga.get(k,0) is not None else None
    for k in ('logical_cost_cny','incremental_cost_cny'):
        total[k]=str(Decimal(total[k])+Decimal(ga.get(k,'0')))
    total['usage_complete']=total['usage_complete'] and ga.get('usage_complete',True)
    result['accounting']=total
    result['timing']={'started_utc':started,'ended_utc':now(),'elapsed_s':round(time.monotonic()-began,3)}
    return result


if __name__=='__main__':
    raise SystemExit(main())
