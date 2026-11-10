"""R1: reuse D0, blind option-difference planning, one observation/answer.

Inference input is the fixed three-field question list. D0 raw Answer lines are
parsed only for an immutable baseline/controller fallback, never sent to models.
No scorer, reference labels or public per-question outcomes are imported here.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from decimal import Decimal
import os
from pathlib import Path
import sys
import time

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE));sys.path.insert(0,str(HERE.parent))
from run_direct_vlm import read,write,read_lines,now,retryable
from r1_evidence import (PLAN_PROMPT,OBSERVE_PROMPT,TOOLS,explicit_answer,normalize_plan,
                         crop_audit,fallback_plan,planning_payload,observer_payload)
from v12_evidence import build_images,multimodal_content,question_parts,classify_tool_return


class StopGeneration(RuntimeError):pass


def prepare(cfg,out):
    root=Path(cfg['root']);rows=read_lines(root/cfg['input'])
    if len(rows)!=60 or len({r['question_id'] for r in rows})!=60:raise ValueError('fixed60_unique_questions_required')
    if any(set(r)!={'question_id','question','images'} for r in rows):raise ValueError('inference_input_has_extra_fields')
    source=root/cfg['source_d0_run']
    if read(source/'status.json')['status']!='generation_complete':raise ValueError('D0_source_incomplete')
    if read(source/'selection.json')['rows']!=rows:raise ValueError('fixed_D0_question_or_image_order_changed')
    baseline={};fingerprints=[]
    for row in rows:
        qid=row['question_id']
        if not qid or any(c not in '0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_-' for c in qid):raise ValueError('unsafe_question_id')
        legal=question_parts(row['question'])[1]
        record=read(source/'checkpoints'/qid/'terminal.json')
        raw=next((a.get('raw_content') for a in reversed(record['attempts']) if a.get('response_received')),None)
        answer=explicit_answer(raw,legal)
        if answer is None:raise ValueError('cached_D0_has_no_unambiguous_answer:'+qid)
        baseline[qid]={'answer':answer,'source_original_answer':record['answer'],
                       'source_original_status':record['status'],'source':'existing_D0_raw_explicit_Answer_line',
                       'source_raw_sha256':hashlib.sha256(str(raw).encode('utf-8')).hexdigest()}
        for image in build_images(row,root/cfg['image_root']):
            fingerprints.append({'question_id':qid,'image_id':image['image_id'],'source_filename':image['source_filename'],
                                 'sha256':hashlib.sha256(Path(image['path']).read_bytes()).hexdigest()})
    if (cfg['max_normal_central_requests'],cfg['max_requests'],cfg['max_extra_requests'],cfg['max_observation_actions_per_question'])!=(120,132,12,1):raise ValueError('fixed_R1_call_limits_changed')
    protocol=dict(cfg,implementation_commit=os.environ.get('MEDRAX_CODE_COMMIT','unrecorded'),
                  prompts={'plan':PLAN_PROMPT,'observe_and_answer':OBSERVE_PROMPT},
                  image_fingerprints=fingerprints,labels_read_by_generation=False,
                  D0_raw_reasons_sent_to_models=False,baseline_answers_sent_to_models=False,
                  marker_limitation='Orientation anchor is model-reported visible marker, not independent OCR verification; reject geometrically inconsistent/unknown single-side crops, keep originals authoritative.',
                  implementation_sha256={n:hashlib.sha256((HERE/n).read_bytes()).hexdigest() for n in
                     ('run_r1_targeted.py','r1_evidence.py','run_direct_vlm.py','v12_evidence.py','v10_visual.py','run_v12_ab.py','provider_ledger.py','v12_ledger.py','tool_registry_ext.py')})
    for name,value in [('selection.json',{'planned_n':60,'rows':rows}),('baseline_cache.json',baseline),('protocol.json',protocol)]:
        p=out/name
        if p.exists() and read(p)!=value:raise ValueError('frozen_input_or_config_conflict:'+name)
        if not p.exists():write(p,value)
    return rows,baseline


def tokens(messages):
    chars=0;images=0
    for m in messages:
        if isinstance(m['content'],str):chars+=len(m['content'])
        else:
            for p in m['content']:
                if p.get('type')=='text':chars+=len(p.get('text',''))
                elif p.get('type')=='image_url':images+=1
    return int(chars/2.2)+1200*images+2600


class PaidCalls:
    def __init__(self,model,ledger,profile,cfg,out,status):
        self.model,self.ledger,self.profile,self.cfg,self.out,self.status=model,ledger,profile,cfg,out,status
        starts=list((out/'checkpoints').glob('*/*/attempt_*/started.json'))
        self.used=len(starts);self.extra=sum(p.parent.name!='attempt_1' for p in starts)
        if self.used>132 or self.extra>12:raise ValueError('persistent_request_limit_exceeded')

    def invoke(self,qid,phase,messages,folder):
        write(folder/'request.json',{'model':self.profile.model,'temperature':self.cfg['temperature'],
             'top_p':self.cfg['top_p'],'max_tokens':self.cfg['max_output_tokens'],'messages':messages})
        for ordinal in (1,2):
            attempt_dir=folder/f'attempt_{ordinal}';result_path=attempt_dir/'result.json';start_path=attempt_dir/'started.json'
            if result_path.exists():result=read(result_path)
            elif start_path.exists():
                raw_path=attempt_dir/'response.json'
                result=dict(read(start_path),response_received=raw_path.exists(),retryable=False,
                            error_type='InterruptedUnknown',settlement=None,recovery='no_blind_reissue_of_paid_request')
                if raw_path.exists():result.update(content=read(raw_path).get('content'),error_type=None)
                write(result_path,result)
            else:
                if ordinal==2 and self.extra>=12:return None
                if self.used>=132:raise StopGeneration('persistent_total_request_cap')
                request_id=f'{self.out.name}:{qid}:{phase}:{ordinal}'
                try:
                    reservation=self.ledger.reserve(request_id=request_id,model=self.profile.model,
                        estimated_input_tokens=min(tokens(messages),self.profile.max_input_tokens),
                        max_output_tokens=self.cfg['max_output_tokens'],
                        metadata={'question_id':qid,'arm':'R1','phase':phase,'model_call':ordinal})
                except Exception as exc:
                    write(folder/f'reserve_error_{ordinal}.json',{'error_type':type(exc).__name__,'message':str(exc),'utc':now(),'request_sent':False})
                    raise StopGeneration(type(exc).__name__+':'+str(exc)) from exc
                self.used+=1;self.extra+=int(ordinal==2)
                result={'question_id':qid,'phase':phase,'ordinal':ordinal,'request_id':request_id,
                        'started_utc':now(),'response_received':False,'retryable':False}
                write(start_path,result);self.status('running',active_question=qid,phase=phase,active_started_utc=now(),requests_used=self.used,extra_requests_used=self.extra)
                began=time.monotonic();response=None;usage=None;error=None;stop=None
                try:
                    response=self.model.invoke(messages)
                    write(attempt_dir/'response.json',response.model_dump(mode='json'))
                    usage=getattr(response,'usage_metadata',None)
                    result.update(response_received=True,content=response.content,usage=usage,response_metadata=response.response_metadata)
                    if not self.profile.identity_ok(response.response_metadata.get('model_name')):
                        stop='returned_model_identity_mismatch';error=RuntimeError(stop)
                except Exception as exc:
                    error=exc
                    result.update(error_type=type(exc).__name__,error_message=str(exc)[:1600],
                                  status_code=getattr(exc,'status_code',None),retryable=retryable(exc))
                    if not retryable(exc):stop=type(exc).__name__
                finally:
                    result['elapsed_s']=round(time.monotonic()-began,3)
                    billed={'prompt_tokens':usage['input_tokens'],'completion_tokens':usage['output_tokens']} if usage and 'input_tokens' in usage and 'output_tokens' in usage and error is None else None
                    try:result['settlement']=self.ledger.settle(reservation,usage=billed,response_received=response is not None,error_type=type(error).__name__ if error else None)
                    except Exception as exc:
                        result['settlement_error']={'error_type':type(exc).__name__,'message':str(exc)};stop=type(exc).__name__+':'+str(exc)
                    if stop:result['stop_reason']=stop
                    write(result_path,result)
                if stop:raise StopGeneration(stop)
            if result.get('stop_reason'):raise StopGeneration(result['stop_reason'])
            if result.get('response_received'):return result.get('content')
            if not result.get('retryable') or ordinal==2:return None
            time.sleep(2)
        return None


class ToolPool:
    def __init__(self,root,out):self.root,self.out,self.tools,self.provenance=root,out,{},{}
    def get(self,name):
        if name not in self.tools:
            from tool_registry_ext import build_tools
            r=self.root
            built,provenance=build_tools(r/'source/MedRAX',cache_dir=r/'models/hf_full',
                classifier_checkpoint=r/'models/home/.torchxrayvision/models_data/nih-pc-chex-mimic_ch-google-openi-kaggle-densenet121-d121-tw-lr001-rot45-tr15-sc15-seed0-best.pt',
                report_cache=r/'models/hf_report',segmentation_checkpoint=r/'models/home/.torchxrayvision/models_data/pspnet_chestxray_best_model_4.pth',
                temp_dir=self.out/'tool_runtime'/name,tools=[name])
            self.tools.update(built);self.provenance.update(provenance);write(self.out/'runtime_tools.json',self.provenance)
        return self.tools[name]


def execute_action(plan,images,pool,folder):
    from run_v9_diagnostic import jsonable,result_images
    from run_v12_ab import prepare_tool_args,tool_allowed
    record={'requested_kind':plan['kind'],'executed_kind':'visual','selected_image_ids':plan['image_ids'],
            'started_utc':now(),'status':'returned','crop_audit':None,'medical_tool_calls':0,'crop_calls':0}
    extras=[]
    try:
        if plan['kind']=='crop':
            audit=crop_audit(plan,images);record['crop_audit']=audit
            if audit['allowed']:
                from v10_visual import crop_image
                result=crop_image(plan['image_ids'][0],plan['box'],images,folder/'artifacts',crop_id='crop:R1')
                parent=next(i for i in images if i['image_id']==plan['image_ids'][0])
                result.update(size=result['crop_size'],figure_label=parent['figure_label'],source_filename=parent['source_filename'],modality=parent['modality'])
                extras.append(result);record.update(executed_kind='crop',crop_calls=1,result=result)
            else:record.update(action_fallback='full_originals_after_crop_binding_rejection')
        elif plan['kind']=='tool':
            name=plan['tool'];selected=[i for i in images if i['image_id'] in plan['image_ids']]
            if name not in TOOLS or len(selected)!=1 or not tool_allowed(name,selected[0]):raise ValueError('tool_not_suited_to_current_image_modality_or_count')
            tool=pool.get(name)
            action={'image_ids':plan['image_ids'],'image_id':plan['image_ids'][0],
                    'tool_args':{},'question':plan['neutral_question'],
                    'expected_attribute':plan['target_region']}
            if name=='xray_phrase_grounding':action['tool_args']['phrase']=plan['target_region']
            params,selected=prepare_tool_args(action,tool,images)
            record.update(tool=name,arguments=params,medical_tool_calls=1,executed_kind='tool')
            result=jsonable(tool.invoke(params));classification=classify_tool_return(result)
            record.update(result=result,classification=classification)
            from PIL import Image
            for index,path in enumerate(result_images(result,pool.out)):
                with Image.open(path) as image:size=list(image.size)
                if min(size)<=10:continue
                import shutil
                target=folder/'artifacts'/('tool_'+str(index+1)+Path(path).suffix)
                target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,target);path=target
                parent=selected[0]
                extras.append({'image_id':f'R1:tool_image:{index+1}','path':str(path),'size':size,'role':'tool_derived',
                    'parent_image_id':parent['image_id'],'parent_path':parent['path'],'figure_label':parent['figure_label'],'modality':parent['modality']})
    except Exception as exc:
        record.update(status='error',error_type=type(exc).__name__,error_message=str(exc)[:1200],
                      classification={'usable':False,'evidence_kind':'execution_error','reason':'Failure is not a patient finding.'},
                      action_fallback='full_originals_after_action_error')
    record['ended_utc']=now();write(folder/'action.json',record)
    # The observer gets raw output only when it is a usable unverified hypothesis.
    projected={k:record[k] for k in ('executed_kind','selected_image_ids','status','crop_audit','action_fallback') if k in record}
    if record.get('classification',{}).get('usable'):projected['unverified_tool_hypothesis']=record.get('result')
    elif record.get('classification'):projected['patient_evidence']=None
    return record,projected,extras


def run(args,cfg,out):
    rows,baseline=prepare(cfg,out);root=Path(cfg['root']);records={}
    for row in rows:
        p=out/'checkpoints'/row['question_id']/'terminal.json'
        if p.exists():records[row['question_id']]=read(p)
    def status(state,**extra):
        value=dict(status=state,updated_utc=now(),planned_n=60,completed_n=len(records),
                   solver_completed_n=sum(r.get('solver_answer') is not None for r in records.values()),
                   fallback_n=sum(r.get('fallback_to_D0',False) for r in records.values()),
                   medical_tool_calls=sum(r.get('action',{}).get('medical_tool_calls',0) for r in records.values()),
                   crop_calls=sum(r.get('action',{}).get('crop_calls',0) for r in records.values()))
        value.update(extra);write(out/'status.json',value)
    def aggregate():
        (out/'predictions.jsonl').write_text(''.join(json.dumps(records[r['question_id']],ensure_ascii=False)+'\n' for r in rows),encoding='utf-8')
    if args.prepare_only:status('prepared');print(json.dumps({'status':'prepared','planned_n':60,'new_model_calls':0}));return 0
    if len(records)==60:aggregate();status('generation_complete');return 0
    from provider_profile import get_profile
    from v12_ledger import V12ProviderLedger
    from langchain_openai import ChatOpenAI
    key=sys.stdin.readline().strip() if args.api_key_stdin else ''
    if not key:raise ValueError('missing_API_key_on_stdin')
    profile=get_profile(cfg['model'])
    model=ChatOpenAI(model=profile.model,base_url=profile.base_url,api_key=key,temperature=cfg['temperature'],top_p=cfg['top_p'],
                     max_tokens=cfg['max_output_tokens'],max_retries=0,timeout=cfg['request_timeout_seconds'])
    del key
    state=read(root/cfg['ledger'])
    if state.get('blocked'):raise ValueError('existing_ledger_blocked')
    cap=state['policy']['cap_cny'];pool=ToolPool(root,out)
    with V12ProviderLedger(root/cfg['ledger'],profile,cap_cny=cap,inherit_ledger_path=root/cfg['inherit_ledger']) as ledger:
        if not (out/'ledger_start.json').exists():write(out/'ledger_start.json',{'committed_cny':str(Decimal(cap)-ledger.remaining),'cap_cny':cap,'utc':now()})
        def finish_money():
            try:
                increment=Decimal(cap)-ledger.remaining-Decimal(read(out/'ledger_start.json')['committed_cny'])
                write(out/'ledger_final_summary.json',{'run_increment_cny':str(increment),'provider_invoice':False,'price_basis':profile.price_basis,'utc':now()})
            except Exception as exc:write(out/'ledger_final_summary.json',{'run_increment_cny':None,'error_type':type(exc).__name__,'utc':now()})
        caller=PaidCalls(model,ledger,profile,cfg,out,status)
        for index,row in enumerate(rows,1):
            qid=row['question_id'];folder=out/'checkpoints'/qid
            if qid in records:continue
            began=time.monotonic();started=now();images=build_images(row,root/cfg['image_root']);plan=fallback_plan(images,'not_yet_planned')
            terminal={'question_id':qid,'answer':None,'solver_answer':None,'fallback_to_D0':False,
                      'baseline_D0':baseline[qid]['answer'],'status':'failed','D0_exposed_to_model':False,
                      'started_utc':started,'action':{}};stop=None
            try:
                plan_path=folder/'action_plan.json'
                if plan_path.exists():plan=read(plan_path)
                else:
                    messages=[{'role':'system','content':PLAN_PROMPT},{'role':'user','content':multimodal_content(planning_payload(row,images),images)}]
                    text=caller.invoke(qid,'plan',messages,folder/'plan')
                    try:plan=normalize_plan(text,images)
                    except Exception as exc:plan=fallback_plan(images,'plan_parse_or_request_failure:'+type(exc).__name__)
                    write(plan_path,plan)
                metadata={m['image_id']:m for m in plan['image_metadata']}
                for image in images:image['modality']=metadata.get(image['image_id'],{}).get('modality','unknown')
                if (folder/'action.json').exists() and (folder/'images.json').exists() and (folder/'observer_action.json').exists():
                    action=read(folder/'action.json');extras=read(folder/'images.json')['derived'];projected=read(folder/'observer_action.json')
                else:
                    status('running',active_index=index,active_question=qid,phase='one_observation_action',requests_used=caller.used,extra_requests_used=caller.extra)
                    action,projected,extras=execute_action(plan,images,pool,folder)
                    write(folder/'images.json',{'originals':images,'derived':extras});write(folder/'observer_action.json',projected)
                terminal['action']=action
                messages=[{'role':'system','content':OBSERVE_PROMPT},
                          {'role':'user','content':multimodal_content(observer_payload(row,images,plan,projected),images,extras)}]
                text=caller.invoke(qid,'observe',messages,folder/'observe')
                answer=explicit_answer(text,question_parts(row['question'])[1])
                terminal.update(solver_answer=answer,answer=answer,status='completed' if answer else 'invalid_answer',raw_response_saved='observe/attempt_*/response.json')
            except StopGeneration as exc:
                stop=str(exc);terminal.update(error_type=type(exc).__name__,error=stop)
            except Exception as exc:
                terminal.update(error_type=type(exc).__name__,error=str(exc)[:1600])
            if terminal['solver_answer'] is None:
                terminal.update(answer=baseline[qid]['answer'],fallback_to_D0=True,status='fallback_D0',
                    fallback_reason='No legal independent observation answer; controller retained cached legal D0 outside model input.')
            terminal.update(ended_utc=now(),elapsed_s=round(time.monotonic()-began,3),
                            requested_action=plan['kind'],attribute=plan['attribute'],target_region=plan['target_region'])
            write(folder/'terminal.json',terminal);records[qid]=terminal
            print(json.dumps({'event':'R1_terminal','index':index,'status':terminal['status'],
                              'executed_action':terminal['action'].get('executed_kind'),'elapsed_s':terminal['elapsed_s'],'requests_used':caller.used}),flush=True)
            if stop:
                write(out/'fatal_error.json',{'error':stop,'question_id':qid,'utc':now()})
                status('stopped',error=stop,requests_used=caller.used,extra_requests_used=caller.extra,not_run_n=60-len(records))
                finish_money();return 2
            status('running',requests_used=caller.used,extra_requests_used=caller.extra)
        aggregate();finish_money();status('generation_complete',requests_used=caller.used,extra_requests_used=caller.extra)
        return 0


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--prepare-only',action='store_true');p.add_argument('--api-key-stdin',action='store_true');p.add_argument('--resume',action='store_true')
    args=p.parse_args(argv);out=args.out.resolve();out.mkdir(parents=True,exist_ok=True)
    import fcntl
    with (out/'.generation.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        try:return run(args,read(args.config),out)
        except Exception as exc:
            write(out/'fatal_error.json',{'error_type':type(exc).__name__,'message':str(exc)[:2000],'utc':now()})
            old=read(out/'status.json') if (out/'status.json').exists() else {}
            write(out/'status.json',dict(old,status='stopped',error_type=type(exc).__name__,updated_utc=now()))
            print(json.dumps({'status':'stopped','error_type':type(exc).__name__}));return 2


if __name__=='__main__':raise SystemExit(main())
