"""Paid request accounting and pure inference inputs for both M1 stages."""
import hashlib
import json
from decimal import Decimal
from pathlib import Path
import sys
import time
from .io import read,write,lines,now,configure_tokenizer


class RunBlocked(RuntimeError):pass


def configure(cfg):configure_tokenizer(Path(cfg['root'])/cfg['context_tokenizer'])


def input_bound(messages):
    chars=0;images=0
    for message in messages:
        content=message['content']
        if isinstance(content,str):chars+=len(content)
        else:
            for item in content:
                if item.get('type')=='text':chars+=len(item.get('text',''))
                elif item.get('type')=='image_url':images+=1
    return int(chars/2.2)+images*1200+2600


def make_messages(system,payload,row,cfg):
    from experiments.v12_evidence import build_images,multimodal_content
    if set(row)!={'question_id','question','images'}:raise ValueError('nonwhitelisted_inference_row')
    images=build_images(row,Path(cfg['root'])/cfg['image_root'])
    return [{'role':'system','content':system},{'role':'user','content':multimodal_content(payload,images)}]


def prepare(cfg,out):
    """One data-role/source selection check, no eval reference values returned."""
    root=Path(cfg['root']);configure(cfg)
    audit={r['question_id']:r for r in lines(root/cfg['case_index'])}
    evaluation=lines(root/cfg['eval_input']);train=lines(root/cfg['seed_input'])
    if len(evaluation)!=60 or len({r['question_id'] for r in evaluation})!=60:raise ValueError('expected_fixed60')
    if any(set(r)!={'question_id','question','images'} for r in evaluation+train):raise ValueError('input_extra_fields')
    d0=Path(cfg['root'])/cfg['d0_source']
    if read(d0/'status.json')['status']!='generation_complete' or read(d0/'selection.json')['rows']!=evaluation:raise ValueError('D0_fixed_input_mismatch')
    case_map={r['question_id']:audit[r['question_id']]['case_hash'] for r in evaluation}
    if any(audit[r['question_id']]['split']!='validation' for r in evaluation):raise ValueError('eval_role_mismatch')
    excluded=set(case_map.values());labels={r['question_id']:r for r in lines(root/cfg['seed_labels'])}
    histories={};source_meta=[]
    from experiments.v12_evidence import question_parts,build_images
    for relative in cfg['seed_predictions_sources']:
        directory=root/relative;manifest=read(directory/'manifest.json');summary=read(directory/'summary.json')
        if summary.get('terminal_count')!=summary.get('planned_arm_results'):raise ValueError('historical_run_not_complete:'+relative)
        source_meta.append({'source_run':relative,'model':manifest['plan']['model'],'terminal_count':summary['terminal_count'],'prediction_type':'original_saved_choice; full response only when retained'})
        for record in lines(directory/'results.jsonl'):
            qid=record.get('question_id');answer=record.get('answer_letter')
            if (record.get('record_type')=='terminal' and record.get('status')=='completed' and qid not in histories
                    and isinstance(answer,str) and len(answer)==1 and answer in 'ABCDEF'):
                histories[qid]={'answer':answer,'raw_response':None,'raw_response_available':False,
                                'original_response_summary':record.get('final_content_summary'),
                                'source_run':relative,'source_model':manifest['plan']['model'],
                                'provenance':'saved_legal_original_prediction; unavailable reasoning is not reconstructed'}
    selected=[];seen=set();skipped=[]
    for row in train:
        qid=row['question_id'];mapping=audit.get(qid)
        if not mapping or mapping['split']!='memory_train':raise ValueError('seed_role_mismatch')
        case=mapping['case_hash']
        if case in excluded or case in seen:continue
        options=question_parts(row['question'])[1];label=labels.get(qid)
        if not label or label.get('answer') not in options:skipped.append({'question_id':qid,'reason':'missing_or_invalid_training_label'});continue
        try:build_images(row,root/cfg['image_root'])
        except (FileNotFoundError,ValueError):skipped.append({'question_id':qid,'reason':'missing_or_invalid_original_images'});continue
        saved=histories.get(qid)
        if saved and saved['answer'] not in options:saved=None
        selected.append({'row':row,'case_id':case,'reference':{'answer':label['answer'],'correct_choice_text':options[label['answer']],
                         'explanation':label.get('explanation') or None},'historical_prediction':saved})
        seen.add(case)
        if len(selected)==cfg['max_seed_cases']:break
    if not selected:raise ValueError('no_eligible_independent_train_seed_cases')
    supplements=sum(x['historical_prediction'] is None for x in selected)
    last_case=case_map[evaluation[-1]['question_id']];last_case_size=sum(c==last_case for c in case_map.values())
    normal=len(selected)+supplements+2*len(evaluation)+2*(len(evaluation)-last_case_size)
    protocol=dict(cfg,implementation_commit=__import__('os').environ.get('MEDRAX_CODE_COMMIT','unrecorded'),
                  seed_n=len(selected),seed_existing_prediction_n=len(selected)-supplements,seed_supplement_n=supplements,
                  expected_normal_requests=normal,eval_case_n=len(set(case_map.values())),
                  feedback_condition='independent_train_label_warmup_and_sequential_completed_case_answer_feedback; not blind no-feedback evaluation',
                  source_case_mapping='prepared_v2 audit_index.case_hash derived from explicit original case_id; not question_id-prefix exclusion',
                  context_tokenizer_role='existing cached MiniLM tokenizer, untruncated/no-special-token length estimate, not Qwen billing tokenizer; no encoder weights loaded',
                  historical_sources=source_meta,seed_selection_skipped=skipped,
                  source_fingerprints={name:hashlib.sha256((root/cfg[name]).read_bytes()).hexdigest() for name in ('seed_input','seed_labels','eval_input','case_index')},
                  implementation_sha256={str(p.relative_to(Path(__file__).resolve().parents[1])):hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in [*Path(__file__).resolve().parent.glob('*.py'),*[Path(__file__).resolve().parents[1]/'experiments'/n for n in ('build_evo_seed.py','run_evo_memory.py','run_evo_pipeline.py')]]})
    from .prompts import BASE_SYSTEM,REFLECT_SYSTEM
    protocol['prompts']={'BASE_SYSTEM':BASE_SYSTEM,'REFLECT_SYSTEM':REFLECT_SYSTEM}
    for name,value in [('protocol.json',protocol),('eval_selection.json',{'rows':evaluation,'case_map':case_map}),('seed_selection.json',selected)]:
        p=out/name
        if p.exists() and read(p)!=value:raise ValueError('frozen_input_or_config_changed:'+name)
        if not p.exists():write(p,value)
    return selected,evaluation,case_map


def budget_preflight(cfg,out,selected,evaluation):
    p=out/'budget_preflight.json'
    if p.exists():return read(p)
    from experiments.provider_profile import get_profile
    from .prompts import BASE_SYSTEM,REFLECT_SYSTEM,reflection_payload
    from experiments.run_direct_vlm import SYSTEM_PROMPT
    profile=get_profile(cfg['model']);root=Path(cfg['root'])
    # Required one-time cap/remaining metadata read, not a ledger audit/scan.
    state=read(root/cfg['ledger']);remaining=Decimal(state['policy']['cap_cny'])-Decimal(state['committed_cny'])
    total=Decimal(0);phase_costs={'seed_predict':Decimal(0),'seed_reflect':Decimal(0),'stream_answer':Decimal(0),'stream_reflect':Decimal(0)}
    def charge(messages):
        bound=min(input_bound(messages),profile.max_input_tokens)
        return Decimal(bound)*profile.input_cny_per_million/1000000+Decimal(cfg['max_tokens'])*profile.output_cny_per_million/1000000
    for item in selected:
        row=item['row']
        if item['historical_prediction'] is None:phase_costs['seed_predict']+=charge(make_messages(SYSTEM_PROMPT,row['question'],row,cfg))
        placeholder={'saved_choice_or_response':'X'*1400,'original_reasoning_unavailable':False}
        phase_costs['seed_reflect']+=charge(make_messages(REFLECT_SYSTEM,reflection_payload(row,placeholder,item['reference'],[]),row,cfg))
    for row in evaluation:
        messages=make_messages(BASE_SYSTEM,{'MEMORY_CONTEXT':'X'*7000,'current_question_and_all_options':row['question']},row,cfg)
        phase_costs['stream_answer']+=2*charge(messages)
    # Conservative expected-size reflections at max requested output, not a bill
    # guarantee or the profile's theoretical 32k input hard ceiling for every call.
    reflection_cost=max(phase_costs['seed_reflect']/max(len(selected),1),Decimal('0.05'))
    expected=read(out/'protocol.json')['expected_normal_requests']
    online=expected-len(selected)-sum(x['historical_prediction'] is None for x in selected)-120
    phase_costs['stream_reflect']=reflection_cost*online
    total=sum(phase_costs.values(),Decimal(0))
    value={'estimated_normal_requests':expected,'estimated_normal_cny':str(total),
           'phase_estimated_cny':{k:str(v) for k,v in phase_costs.items()},'existing_cap_preserved':True,
           'remaining_sufficient_for_estimate':remaining>=total,'method':'legacy conservative input character/image estimate and max requested 2048 output, 7000-character memory allowance; actual usage/unknown reservations governed by original ledger',
           'price_basis':profile.price_basis,'estimate_not_invoice_or_guarantee':True,'utc':now()}
    write(p,value)
    if state.get('blocked') or remaining<total:raise RunBlocked('existing_budget_cannot_cover_normal_protocol_estimate')
    return value


class Client:
    def __init__(self,cfg,out,key,status):
        from experiments.provider_profile import get_profile
        from experiments.v12_ledger import V12ProviderLedger
        from langchain_openai import ChatOpenAI
        self.cfg,self.out,self.status=cfg,Path(out),status;self.profile=get_profile(cfg['model'])
        state=read(Path(cfg['root'])/cfg['ledger']);self.cap=state['policy']['cap_cny']
        self.ledger=V12ProviderLedger(Path(cfg['root'])/cfg['ledger'],self.profile,cap_cny=self.cap,inherit_ledger_path=Path(cfg['root'])/cfg['inherit_ledger'])
        self.model=ChatOpenAI(model=self.profile.model,base_url=self.profile.base_url,api_key=key,
            temperature=cfg['temperature'],top_p=cfg['top_p'],max_tokens=cfg['max_tokens'],max_retries=0,timeout=cfg['timeout_seconds'])
        starts=list(self.out.rglob('attempt_*/started.json'));self.used=len(starts);self.extra=sum(p.parent.name!='attempt_1' for p in starts)
        saved=read(self.out/'request_budget.json') if (self.out/'request_budget.json').exists() else {}
        self.used=max(self.used,saved.get('used',0));self.extra=max(self.extra,saved.get('extra',0))
        if self.used>cfg['max_requests'] or self.extra>cfg['max_extra_requests']:raise RunBlocked('persistent_call_budget_exceeded')
        if not (self.out/'ledger_start.json').exists():write(self.out/'ledger_start.json',{'committed_cny':str(Decimal(self.cap)-self.ledger.remaining),'utc':now()})
    def close(self):
        try:
            increment=Decimal(self.cap)-self.ledger.remaining-Decimal(read(self.out/'ledger_start.json')['committed_cny'])
            write(self.out/'ledger_final_summary.json',{'run_increment_cny':str(increment),'price_basis':self.profile.price_basis,'provider_invoice':False,'utc':now()})
        finally:self.ledger.close()
    def invoke(self,key,phase,messages,folder):
        from experiments.run_direct_vlm import retryable
        folder=Path(folder)
        request=folder/'request.json'
        if not request.exists():write(request,{'model':self.profile.model,'temperature':self.cfg['temperature'],'top_p':self.cfg['top_p'],'max_tokens':self.cfg['max_tokens'],'messages':messages})
        else:messages=read(request)['messages']
        for ordinal in (1,2):
            d=folder/f'attempt_{ordinal}';result_path=d/'result.json';started=d/'started.json'
            if result_path.exists():result=read(result_path)
            elif started.exists():
                raw=d/'response.json';result=dict(read(started),response_received=raw.exists(),retryable=False,settlement=None,recovery='saved_response_reused_or_unknown_call_not_reissued')
                if raw.exists():result['content']=read(raw).get('content')
                else:result['error_type']='InterruptedUnknown'
                write(result_path,result)
            else:
                if ordinal==2 and self.extra>=self.cfg['max_extra_requests']:return None
                if self.used>=self.cfg['max_requests']:raise RunBlocked('persistent_global_request_cap')
                request_id=f'm1:{key}:{phase}:{ordinal}'
                try:reservation=self.ledger.reserve(request_id=request_id,estimated_input_tokens=min(input_bound(messages),self.profile.max_input_tokens),max_output_tokens=self.cfg['max_tokens'],model=self.profile.model,
                    metadata={'question_id':key[:128],'arm':phase[:30],'phase':phase[:60],'model_call':ordinal})
                except Exception as exc:write(folder/f'reserve_error_{ordinal}.json',{'type':type(exc).__name__,'message':str(exc),'request_sent':False});raise RunBlocked(type(exc).__name__+':'+str(exc)) from exc
                self.used+=1;self.extra+=int(ordinal==2)
                result={'key':key,'phase':phase,'ordinal':ordinal,'request_id':request_id,'started_utc':now(),'response_received':False,'retryable':False}
                write(started,result);write(self.out/'request_budget.json',{'used':self.used,'extra':self.extra,'utc':now()})
                self.status(active_key=key,active_phase=phase,requests_used=self.used,extra_requests_used=self.extra)
                response=None;usage=None;error=None;stop=None;began=time.monotonic()
                try:
                    response=self.model.invoke(messages);write(d/'response.json',response.model_dump(mode='json'));usage=getattr(response,'usage_metadata',None)
                    result.update(response_received=True,content=response.content,usage=usage,response_metadata=response.response_metadata)
                    if not self.profile.identity_ok(response.response_metadata.get('model_name')):stop='returned_model_mismatch';error=RuntimeError(stop)
                except Exception as exc:
                    error=exc;result.update(error_type=type(exc).__name__,error_message=str(exc)[:1400],retryable=retryable(exc),status_code=getattr(exc,'status_code',None))
                    if not result['retryable']:stop=type(exc).__name__
                finally:
                    result.update(ended_utc=now(),elapsed_s=round(time.monotonic()-began,3))
                    billed={'prompt_tokens':usage['input_tokens'],'completion_tokens':usage['output_tokens']} if usage and 'input_tokens' in usage and 'output_tokens' in usage and error is None else None
                    try:result['settlement']=self.ledger.settle(reservation,usage=billed,response_received=response is not None,error_type=type(error).__name__ if error else None)
                    except Exception as exc:result['settlement_error']={'type':type(exc).__name__,'message':str(exc)};stop=type(exc).__name__+':'+str(exc)
                    if stop:result['stop_reason']=stop
                    write(result_path,result)
                if stop:raise RunBlocked(stop)
            if result.get('stop_reason'):raise RunBlocked(result['stop_reason'])
            if result.get('response_received'):return result.get('content')
            if not result.get('retryable') or ordinal==2:return None
            time.sleep(2)
        return None
