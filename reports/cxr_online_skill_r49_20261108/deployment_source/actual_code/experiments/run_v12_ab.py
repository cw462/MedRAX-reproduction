"""V12: shared first image read, then B and A, with full-option solving.

Generation reads only frozen inference inputs and independent training assets.
The first answer is retained for later scoring but never sent to either arm.
Each arm has the same 3-model/2-action ceiling. Existing V10 records are read-only.
"""
from __future__ import annotations
import argparse
import copy
from contextlib import contextmanager
from decimal import Decimal
import hashlib
import json
import math
from pathlib import Path
import sys
import time
from types import SimpleNamespace
import uuid

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE));sys.path.insert(0,str(HERE.parent))
from run_v9_diagnostic import accounting, append, jsonable, now, read_jsonl, saved_context, write_json

CHEST_ONLY={'chest_xray_classifier','chest_xray_report_generator','chest_xray_segmentation',
            'chest_xray_expert','xray_phrase_grounding'}
GENERAL={'llava_med_qa','image_visualizer'}

def modality(value):
    text=str(value or '').lower().replace('_',' ').replace('-',' ')
    if text in {'cxr','chest radiograph','chest x ray','chest xray'}:return 'CXR'
    if text in {'xray','x ray','radiograph','radiography','xr'}:return 'Xray'
    if text in {'ct','computed tomography','computed tomographic'}:return 'CT'
    if text in {'mri','mr','magnetic resonance'}:return 'MRI'
    if text in {'ultrasound','us','sonography'}:return 'US'
    return 'unknown'

def bound_images(originals, observation):
    """Pixel-derived modality remains model reported, never a gold annotation."""
    metadata={x['image_id']:x for x in observation.get('image_metadata',[]) if isinstance(x,dict) and x.get('image_id')}
    images=[]
    for original in originals:
        item=copy.deepcopy(original);m=metadata.get(item['image_id'],{})
        item.update(modality=modality(m.get('modality')),modality_source='shared_first_visual_read_unverified',
                    anatomy=m.get('anatomy','unknown'),timepoint=m.get('timepoint','unknown'),
                    timepoint_source_quote=m.get('timepoint_source_quote',''),
                    comparison_object=m.get('comparison_object','unknown'))
        images.append(item)
    return images

def tool_allowed(name, image):
    if name in CHEST_ONLY:return image.get('modality')=='CXR'
    if name=='dicom_processor':return Path(image['path']).suffix.lower()=='.dcm'
    return name in GENERAL

def prepare_tool_args(action, tool, images):
    by_id={i['image_id']:i for i in images}
    ids=action.get('image_ids') or [action.get('image_id')]
    if not ids or any(i not in by_id for i in ids):raise ValueError('action_image_not_current')
    selected=[by_id[i] for i in ids]
    if any(not tool_allowed(tool.name,i) for i in selected):raise ValueError('tool_modality_mismatch')
    schema=tool.args_schema.model_json_schema()
    props=schema.get('properties',{})
    args={k:v for k,v in action.get('tool_args',{}).items() if k in props and k not in {'image_path','image_paths'}}
    if 'image_path' in props:
        if len(selected)!=1:raise ValueError('single_image_tool_cannot_accept_multi_image_action')
        args['image_path']=str(selected[0]['path'])
    elif 'image_paths' in props:args['image_paths']=[str(i['path']) for i in selected]
    else:raise ValueError('tool_has_no_image_argument')
    for name in ('question','prompt'):
        if name in props:args[name]=action['question']
    if 'phrase' in props:args['phrase']=str(args.get('phrase') or action.get('expected_attribute') or action['question'])
    return args,selected

def checked_crop(action, images, folder):
    from v10_visual import crop_image
    source=next((i for i in images if i['image_id']==action.get('image_id')),None)
    if source is None:raise ValueError('crop_image_not_current')
    box=action.get('box')
    if not isinstance(box,list) or len(box)!=4 or any(type(x) not in (int,float) or not math.isfinite(x) for x in box):raise ValueError('invalid_crop_box')
    if not (0<=box[0]<box[2]<=1 and 0<=box[1]<box[3]<=1):raise ValueError('invalid_crop_bounds')
    width,height=source['size']
    if math.ceil(box[2]*width)-math.floor(box[0]*width)<=10 or math.ceil(box[3]*height)-math.floor(box[1]*height)<=10:
        raise ValueError('crop_below_api_minimum_both_dimensions_must_exceed_10')
    result=crop_image(source['image_id'],box,images,folder,crop_id='crop:'+uuid.uuid4().hex[:12])
    result.update(size=result['crop_size'],modality=source.get('modality','unknown'),
                  figure_label=source.get('figure_label'),source_filename=source.get('source_filename'),
                  timepoint=source.get('timepoint','unknown'),timepoint_source_quote=source.get('timepoint_source_quote',''))
    return result

def evidence_for_model(records):
    """Errors, terse No and isolated labels are kept only in the saved raw audit."""
    out=[]
    for record in records:
        item={k:record[k] for k in ('evidence_ref','action','classification') if k in record}
        if record.get('classification',{}).get('usable'):
            item['unverified_tool_hypothesis']=record.get('result')
            item['instruction']='A tool claim is not a patient fact. Verify it against the attached pixels; unsupported claims remain hypotheses.'
        else:item['patient_evidence']=None
        out.append(item)
    return out

def call(model, ctx, prompt, payload, images, extras, folder, filename):
    from langchain_core.messages import HumanMessage,SystemMessage,messages_to_dict
    from v12_evidence import multimodal_content
    messages=[SystemMessage(content=prompt),HumanMessage(content=multimodal_content(payload,images,extras))]
    write_json(folder/(filename+'_request.json'),messages_to_dict(messages))
    response=model.invoke(messages)
    messages.append(response)
    write_json(folder/(filename+'_messages.json'),messages_to_dict(messages))
    return response.content

def exception_record(exc):
    chain=[];seen=set()
    while exc is not None and id(exc) not in seen:
        seen.add(id(exc));chain.append({'type':type(exc).__name__,'message':str(exc)[:1500]});exc=exc.__cause__
    return chain

def initial_read(runtime,ledger,profile,args,row,images,trace,folder):
    from memory_agent_eval import BudgetedModel
    from run_bc_recovery import new_ctx
    from v12_evidence import FIRST_READ_PROMPT,parse_first_read
    began=time.monotonic();started=now();folder.mkdir(parents=True,exist_ok=True)
    ctx=new_ctx(row['question_id'],str(uuid.uuid4()),[Path(i['path']) for i in images],runtime,args,trace,0,1)
    ctx['run_id'],ctx['arm'],ctx['phase']=args.run_id,'shared_initial','first_visual_read'
    result={'question_id':row['question_id'],'first_answer':None,'status':'failed','error':None}
    write_json(folder/'request_started.json',{'utc':started,'thread_id':ctx['thread_id']})
    try:
        payload={'full_question_and_all_options':row['question'],'image_registry':images,
                 'instruction':'First inspect all supplied originals, then report observations, conditional hypotheses and all relevant option distinctions. Keep your initial answer in first_answer only.'}
        text=call(BudgetedModel(runtime.model,ledger,ctx,profile),ctx,FIRST_READ_PROMPT,payload,images,[],folder,'initial')
        observation=parse_first_read(text,row,images)
        write_json(folder/'observation.json',observation)
        result.update(first_answer=observation.get('first_answer'),status='completed',observation=observation)
    except Exception as exc:
        result.update(error=type(exc).__name__+': '+str(exc),error_chain=exception_record(exc),
                      observation={'observations':[],'hypotheses':[],'patient_conditions':[],
                      'discriminators':[],'image_metadata':[],'uncertainties':['Shared first reading failed; no observation may be inferred.'],'parse_warnings':['initial_read_failed']})
    result.update(accounting=accounting(ctx),stop_run=ctx.get('stop_run',False),
                  stop_reason=ctx.get('stop_reason') or ctx.get('money_status'),
                  timing={'started_utc':started,'ended_utc':now(),'elapsed_s':round(time.monotonic()-began,3)})
    write_json(folder/'context.json',saved_context(ctx));write_json(folder/'terminal.json',result)
    return result

def run_branch(runtime,ledger,profile,args,row,originals,observation,trace,retriever,group,folder,*,initial_answer=None):
    from memory_agent_eval import BudgetedModel,TrackedTool
    from run_bc_recovery import new_ctx
    from run_v9_diagnostic import result_images
    from v12_evidence import (ACTION_PLAN_PROMPT,TARGETED_READ_PROMPT,FINAL_PROMPT,
        parse_action_plan,parse_targeted_read,parse_final,classify_tool_return)
    from v11_selection import _options
    began=time.monotonic();started=now();folder.mkdir(parents=True,exist_ok=True)
    images=bound_images(originals,observation)
    tools={n:t for n,t in runtime.tools.items() if any(tool_allowed(n,i) for i in images)}
    permitted={i['image_id']:[n for n in tools if tool_allowed(n,i)] for i in images}
    ctx=new_ctx(row['question_id'],str(uuid.uuid4()),[Path(i['path']) for i in images],runtime,args,trace,2,3)
    ctx['run_id'],ctx['arm']=args.run_id,group
    result={'question_id':row['question_id'],'group':group,'answer':None,'status':'failed','error':None,
            'shared_observation_source':'shared_initial','first_answer_visible':False,
            'tool_attempts':[],'additional_observations':None,'candidate_answer':None,
            'solver_answer':None,'fallback_to_initial':False,'k_ids':[],'e_ids':[]}
    write_json(folder/'request_started.json',{'utc':started,'thread_id':ctx['thread_id']})
    model=BudgetedModel(runtime.model,ledger,ctx,profile)
    records=[];extras=[];plan={}
    try:
        ctx['phase']='retrieval'
        retrieval=retriever.retrieve(row,copy.deepcopy(observation),images,set(tools),group)
        write_json(folder/'retrieval.json',retrieval)
        result.update(k_ids=retrieval.get('k_ids',[]),e_ids=retrieval.get('e_ids',[]),
                      action_suggestions=retrieval.get('action_suggestions',[]))
        payload={'full_question_and_all_options':row['question'],'shared_first_observation':observation,
                 'image_registry':images,'tools_allowed_per_image':permitted,
                 'tool_schemas':{n:t.args_schema.model_json_schema() for n,t in tools.items()},
                 'knowledge_rules':retrieval.get('k_block',''),'training_action_experience':retrieval.get('e_block',''),
                 'action_suggestions':retrieval.get('action_suggestions',[]),
                 'max_actions':2,'crop_rule':'Use normalized box [left,top,right,bottom]; both crop dimensions must exceed 10 pixels; full parent stays visible.'}
        ctx['phase']='action_planning'
        text=call(model,ctx,ACTION_PLAN_PROMPT,payload,images,[],folder,'plan')
        try:plan=parse_action_plan(text,images,set(tools)|{'crop_current_image'})
        except ValueError as exc:
            plan={'actions':[],'parse_warnings':['invalid_action_plan:'+str(exc)],'fallback':'targeted_full_image_read_without_new_tool'}
        write_json(folder/'action_plan.json',plan)
        for index,action in enumerate(plan['actions']):
            ctx['phase']='targeted_action_'+str(index+1)
            entry={'evidence_ref':f'{group}:tool:{index+1}','action':action,'started_utc':now()}
            try:
                if action['kind']=='crop' or action.get('tool')=='crop_current_image':
                    ctx['budget'].reserve('tool','crop_current_image');ctx['actual_tool_attempts']+=1
                    returned=checked_crop(action,images,folder/'artifacts')
                    extras.append(returned);entry.update(result=returned,classification={'evidence_kind':'image_pixels','usable':True,'reason':'Crop retains parent; not a clinical finding.'})
                elif action['kind']=='visual':
                    # This selects full pixels for the single targeted reader call below.
                    entry.update(result={'selected_images':action.get('image_ids') or [action['image_id']]},
                                 classification={'evidence_kind':'image_pixels','usable':True,'reason':'View selection, no independent tool inference.'})
                else:
                    name=action['tool']
                    if name not in tools:raise ValueError('tool_not_available_for_current_modalities')
                    params,selected=prepare_tool_args(action,tools[name],images)
                    returned=TrackedTool(tools[name],runtime.tool_provenance[name],ctx).invoke(params)
                    entry.update(arguments=params,result=jsonable(returned),classification=classify_tool_return(returned))
                    # Saved derived pixels stay bound to the exact tool input object.
                    for j,p in enumerate(result_images(returned,args.artifact_root)):
                        from PIL import Image
                        with Image.open(p) as im:size=list(im.size)
                        if min(size)<=10:continue
                        parent=selected[0]
                        extras.append({'image_id':f'{group}:artifact:{index+1}:{j+1}','path':str(p),'role':'tool_derived',
                            'parent_image_id':parent['image_id'],'parent_path':parent['path'],'size':size,
                            'figure_label':parent['figure_label'],'modality':parent.get('modality','unknown'),
                            'timepoint':parent.get('timepoint','unknown'),'evidence_ref':entry['evidence_ref']})
                entry['status']='returned'
            except Exception as exc:
                entry.update(status='error',error=type(exc).__name__+': '+str(exc),
                    classification={'evidence_kind':'execution_error','usable':False,'reason':'No patient evidence from execution failure.'})
            entry['ended_utc']=now();records.append(entry);append(folder/'tool_records.jsonl',entry)
        result['tool_attempts']=records
        write_json(folder/'images.json',{'originals':images,'derived':extras})
        # Independent targeted observation receives no first answer or selected option.
        stem,_=_options(row['question'])
        targeted_payload={'question_stem':stem,'full_question_and_all_options':row['question'],
             'patient_conditions':observation.get('patient_conditions',[]),
             'image_registry':images,'actions':plan.get('actions',[]),
             'all_option_discriminators':observation.get('discriminators',[]),
             'tool_evidence':evidence_for_model(records),
             'instruction':'Independently inspect requested attributes in actual pixels. Validate time and object matching from source question only. No prior selected answer is available.'}
        ctx['phase']='targeted_visual_read'
        text=call(model,ctx,TARGETED_READ_PROMPT,targeted_payload,images,extras,folder,'targeted_read')
        try:new_observation=parse_targeted_read(text,row,images+extras)
        except ValueError as exc:
            new_observation={'observations':[],'hypotheses':[],'uncertainties':['Targeted reader output could not be parsed; no factual finding recovered.'],
                             'parse_warnings':[str(exc)],'failed':True}
        result['candidate_answer']=new_observation.pop('candidate_answer',None)
        result['additional_observations']=new_observation
        write_json(folder/'new_observation.json',new_observation)
        final_payload={'full_question_and_all_options':row['question'],'image_registry':images,
             'shared_first_observation':observation,'new_observation':new_observation,
             'tool_evidence':evidence_for_model(records),
             'instruction':'Solve the complete question anew, evaluating all original options. No initial answer is supplied. Choose any legal best option; unknown is not absent/normal/unchanged.'}
        ctx['phase']='full_option_solving'
        text=call(model,ctx,FINAL_PROMPT,final_payload,images,extras,folder,'final')
        final=parse_final(text,row,{i['image_id'] for i in images+extras})
        result.update(answer=final['answer'],solver_answer=final['answer'],decision=final,status='completed',action_plan=plan)
    except Exception as exc:
        result.update(error=type(exc).__name__+': '+str(exc),error_phase=ctx.get('phase'),error_chain=exception_record(exc))
        if ctx.get('phase')=='retrieval':ctx.update(stop_run=True,stop_reason='retrieval_wiring_error')
    if result['status']=='failed' and initial_answer in _options(row['question'])[1]:
        result.update(answer=initial_answer,status='fallback_initial',fallback_to_initial=True,
            fallback_reason='Downstream solving failed; retained existing legal initial answer without exposing it to the model.')
    result.update(accounting=accounting(ctx),stop_run=ctx.get('stop_run',False),
                  stop_reason=ctx.get('stop_reason') or ctx.get('money_status'),
                  timing={'started_utc':started,'ended_utc':now(),'elapsed_s':round(time.monotonic()-began,3)})
    write_json(folder/'context.json',saved_context(ctx));write_json(folder/'terminal.json',result)
    return result

@contextmanager
def run_lock(out):
    import fcntl
    with (out/'.generation.lock').open('a') as f:
        fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
        try:yield
        finally:fcntl.flock(f,fcntl.LOCK_UN)

def prepare(cfg,out):
    if (cfg['shared_initial_model_calls'],cfg['branch_model_calls'],cfg['branch_tool_action_limit'],cfg['execution_order'])!=(1,3,2,['B','A']):
        raise ValueError('fixed_v12_call_budget_or_execution_order_changed')
    root=Path(cfg['root'])
    # Use the original inference-only list, never a public retrospective case export.
    from run_v10_accuracy import fixed_sixty
    selection=fixed_sixty(read_jsonl(root/cfg['input']),json.loads((root/cfg['official_groups']).read_text()))
    from v12_evidence import build_images,FIRST_READ_PROMPT,ACTION_PLAN_PROMPT,TARGETED_READ_PROMPT,FINAL_PROMPT
    for row in selection['rows']:build_images(row,root/cfg['image_root'])
    effective=dict(cfg,labels_loaded_by_generation=False,initial_answer_hidden_from_both_arms=True,
       provider_cost_basis='existing_profile_assumed_rates_not_invoice',
       implementation_sha256={n:hashlib.sha256((HERE/n).read_bytes()).hexdigest() for n in
          ('run_v12_ab.py','v12_evidence.py','v12_retrieval.py','memory_agent_eval.py','provider_ledger.py')},
       prompts={'initial':FIRST_READ_PROMPT,'plan':ACTION_PLAN_PROMPT,'targeted_read':TARGETED_READ_PROMPT,'final':FINAL_PROMPT})
    for name,value in [('selection.json',selection),('effective_config.json',effective)]:
        p=out/name
        if p.exists() and json.loads(p.read_text())!=value:raise ValueError('frozen_run_changed:'+name)
        if not p.exists():write_json(p,value)
    return selection

def run(a,cfg,out):
    selection=prepare(cfg,out);root=Path(cfg['root']);rows=selection['rows']
    initials={r['question_id']:r for r in read_jsonl(out/'initial_results.jsonl')}
    branches={(r['question_id'],r['group']):r for r in read_jsonl(out/'branch_results.jsonl')}
    if len(initials)!=len(read_jsonl(out/'initial_results.jsonl')) or len(branches)!=len(read_jsonl(out/'branch_results.jsonl')):raise ValueError('duplicate_terminal_records')
    expected={r['question_id'] for r in rows}
    def validate_cache():
        if not set(initials)<=expected or not set(branches)<=set((qid,g) for qid in expected for g in ('B','A')):
            raise ValueError('terminal_records_outside_frozen_selection')
        if any(k!=(r.get('question_id'),r.get('group')) for k,r in branches.items()):raise ValueError('terminal_identity_mismatch')
        if any(qid!=r.get('question_id') for qid,r in initials.items()):raise ValueError('initial_identity_mismatch')
        if any(r.get('status') not in {'completed','failed'} for r in initials.values()):raise ValueError('initial_not_terminal')
        if any(r.get('status') not in {'completed','failed','fallback_initial'} for r in branches.values()):raise ValueError('branch_not_terminal')
        if any(g=='A' for _,g in branches) and any((qid,'B') not in branches for qid in expected):raise ValueError('cached_A_precedes_completion_of_B')
        order=[g for _,g in branches]
        if 'A' in order and 'B' in order[order.index('A'):]:raise ValueError('cached_branch_order_is_not_B_then_A')
    validate_cache()
    def status(state,**kw):
        write_json(out/'status.json',dict(status=state,updated_utc=now(),planned_n=60,
            initial_completed=len(initials),branch_completed=len(branches),
            group_completed={g:sum(k[1]==g for k in branches) for g in ('B','A')},**kw))
    if a.prepare_only:status('prepared');print(json.dumps({'status':'prepared','planned_n':60,'new_model_calls':0}));return 0
    if len(initials)==60 and len(branches)==120:status('generation_complete');return 0
    # A terminal is committed before its append. Recover that boundary without a model call.
    for row in rows:
        qid=row['question_id']
        p=out/'checkpoints'/qid/'initial'/'terminal.json'
        if qid not in initials and p.exists():initials[qid]=json.loads(p.read_text());append(out/'initial_results.jsonl',initials[qid])
    for group in ('B','A'):
        for row in rows:
            k=row['question_id'],group;p=out/'checkpoints'/k[0]/group/'terminal.json'
            if k not in branches and p.exists():branches[k]=json.loads(p.read_text());append(out/'branch_results.jsonl',branches[k])
    validate_cache()
    if len(initials)==60 and len(branches)==120:status('generation_complete');return 0
    key=sys.stdin.readline().strip() if a.api_key_stdin else ''
    if not key:raise ValueError('missing_api_key')
    from provider_profile import get_profile
    from provider_ledger import ProviderLedger
    from v12_retrieval import V12Retriever
    from v12_evidence import build_images,observation_projection
    import memory_agent_eval as mae
    profile=get_profile(cfg['model'])
    ledger_path=root/cfg['ledger']
    state=json.loads(ledger_path.read_text())
    if state.get('blocked'):raise ValueError('existing_ledger_blocked')
    cap=state['policy']['cap_cny']
    args=SimpleNamespace(repo=root/'source/MedRAX',model_cache=root/'models/hf_full',
        classifier_checkpoint=root/'models/home/.torchxrayvision/models_data/nih-pc-chex-mimic_ch-google-openi-kaggle-densenet121-d121-tw-lr001-rot45-tr15-sc15-seed0-best.pt',
        segmentation_checkpoint=root/'models/home/.torchxrayvision/models_data/pspnet_chestxray_best_model_4.pth',
        report_cache=root/'models/hf_report',temperature=cfg['temperature'],top_p=cfg['top_p'],
        max_output_tokens=cfg['max_output_tokens'],request_timeout_seconds=cfg['request_timeout_seconds'],
        tools=cfg['tools'],image_detail='auto',max_case_seconds=cfg['max_case_seconds'],
        run_id=out.name,artifact_root=out/'artifacts')
    status('initializing')
    retriever=V12Retriever(root/cfg['knowledge_pack'],root/cfg['pool'],root/cfg['skills'],
        dense_model_path=root/cfg['dense_cache'],questions_path=root/cfg['training_questions'],
        max_chars=cfg['experience_max_chars'],top_k=2)
    runtime=mae.build_runtime(args,profile,key,'V12 explicit phase prompts override this unused agent prompt.',out/'artifacts'/('runtime_'+uuid.uuid4().hex))
    write_json(out/'runtime_tools.json',runtime.tool_provenance)
    write_json(out/'retrieval_runtime.json',retriever.describe())
    with ProviderLedger(ledger_path,profile,cap_cny=cap,inherit_ledger_path=root/cfg['inherit_ledger']) as ledger, (out/'execution.trace.jsonl').open('a',encoding='utf-8') as trace:
        if not (out/'ledger_start.json').exists():write_json(out/'ledger_start.json',{'committed_cny':state['committed_cny'],'cap_cny':cap,'utc':now()})
        consecutive_api_failures=0
        for group in ('B','A'):
            for index,row in enumerate(rows,1):
                qid=row['question_id'];folder=out/'checkpoints'/qid
                if (qid,group) in branches:continue
                images=build_images(row,root/cfg['image_root'])
                if qid not in initials:
                    stage=folder/'initial'
                    if (stage/'request_started.json').exists():raise RuntimeError('interrupted_initial_requires_targeted_recovery:'+qid)
                    status('running',stage='initial',active_question=qid,active_started_utc=now())
                    print(json.dumps({'event':'initial_started','index':index,'utc':now()}),flush=True)
                    initial=initial_read(runtime,ledger,profile,args,row,images,trace,stage)
                    append(out/'initial_results.jsonl',initial);initials[qid]=initial
                    if initial['stop_run']:raise RuntimeError('provider_or_ledger_stop:'+str(initial['stop_reason']))
                stage=folder/group
                if (stage/'request_started.json').exists():raise RuntimeError('interrupted_branch_requires_targeted_recovery:'+qid+':'+group)
                observed=observation_projection(initials[qid]['observation'])
                status('running',stage=group,active_question=qid,active_started_utc=now())
                print(json.dumps({'event':'branch_started','group':group,'index':index,'utc':now()}),flush=True)
                result=run_branch(runtime,ledger,profile,args,row,images,observed,trace,retriever,group,stage,
                                  initial_answer=initials[qid].get('first_answer'))
                append(out/'branch_results.jsonl',result);branches[qid,group]=result
                status('running',stage=group)
                print(json.dumps({'event':'branch_finished','group':group,'index':index,'status':result['status'],
                    'elapsed_s':result['timing']['elapsed_s'],'model_calls':result['accounting']['model_calls'],
                    'tool_calls':result['accounting']['tool_calls'],'error':result['error'],'utc':now()}),flush=True)
                if result['stop_run']:raise RuntimeError('provider_or_ledger_stop:'+str(result['stop_reason']))
                is_api='model_exception' in result['accounting'].get('issues',[])
                consecutive_api_failures=consecutive_api_failures+1 if is_api else 0
                if consecutive_api_failures>=3:raise RuntimeError('three_consecutive_api_failures_no_blind_retry')
        final=json.loads(ledger_path.read_text());start=json.loads((out/'ledger_start.json').read_text())
        write_json(out/'ledger_final_summary.json',{'start_committed_cny':start['committed_cny'],
           'end_committed_cny':final['committed_cny'],'run_increment_cny':str(Decimal(final['committed_cny'])-Decimal(start['committed_cny'])),
           'basis':'existing_assumed_rate_ledger_not_invoice','utc':now()})
    status('generation_complete');return 0

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--config',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--prepare-only',action='store_true');p.add_argument('--api-key-stdin',action='store_true');a=p.parse_args(argv)
    cfg=json.loads(a.config.read_text(encoding='utf-8'));out=a.out.resolve();out.mkdir(parents=True,exist_ok=True)
    with run_lock(out):
        try:return run(a,cfg,out)
        except Exception as exc:
            write_json(out/'fatal_error.json',{'utc':now(),'error_chain':exception_record(exc)})
            prior=json.loads((out/'status.json').read_text()) if (out/'status.json').exists() else {}
            write_json(out/'status.json',dict(prior,status='stopped',updated_utc=now(),error=type(exc).__name__+': '+str(exc)))
            raise
if __name__=='__main__':raise SystemExit(main())
