"""Cached API services and adapted M43 components for online R49; no automatic retries."""
import copy,json,math,os,time
from pathlib import Path
from cxr_online_primitives_r49 import read,digest,tool_failure_reason
from online_memory_r49 import save_once as write,now
from skill_lifecycle_r49 import category
class Services:
    @staticmethod
    def text_semantics(value):
        """Compare text/control flow while explicitly excluding image payloads."""
        if isinstance(value,list):return [Services.text_semantics(item) for item in value]
        if isinstance(value,dict):
            if value.get('type')=='image_url':
                image=value.get('image_url')
                parameters={key:item for key,item in image.items() if key!='url'} if isinstance(image,dict) else {}
                return {**{key:Services.text_semantics(item) for key,item in value.items() if key!='image_url'},'image_url':parameters}
            return {key:Services.text_semantics(item) for key,item in value.items()}
        return value
    def call(self,row,arm,ordinal,messages):
        folder=self.out/'calls'/arm/row['question_id']/str(ordinal)
        if (folder/'response.json').is_file():
            if not (folder/'request.json').is_file():raise ValueError('saved_response_without_request')
            request=read(folder/'request.json')
            if self.text_semantics(request.get('messages'))!=self.text_semantics(messages):
                raise ValueError('saved_request_text_semantics_changed')
            for key,value in (('model',self.protocol['model']),('temperature',self.protocol['temperature']),
                              ('top_p',self.protocol['top_p']),('max_tokens',self.protocol['max_output_tokens'])):
                if request.get(key)!=value:raise ValueError('saved_request_model_parameter_changed:'+key)
        return self.paid.call(row,arm,ordinal,messages)
    def __init__(self,cfg,protocol,runtime,out,key,embedding_model,embedding_base_url=None):
        import run_cxr_vqa_toolsets as base
        self.base=base;self.runtime=runtime;self.protocol=copy.deepcopy(protocol);self.out=Path(out);self.embed_model=embedding_model
        self.protocol.update(experiment_id='skill_lifecycle_r49',request_archive='inline_original_images_semantic_restart_r49')
        self.protocol['main_call_limits']={}  # No numerical per-question ceiling; local ledger disabled below.
        self.protocol['budget']={'existing_shared_ledger':False,'enforce_money_cap':False}
        self.protocol['tool_call_limits']={}
        self.paid=base.PaidCalls(cfg,self.protocol,self.out,key)
        from openai import OpenAI
        self.embedding_client = OpenAI(api_key=os.environ.get('R49_EMBEDDING_API_KEY') or key,
            base_url=embedding_base_url or self.paid.profile.base_url,max_retries=0,
            timeout=cfg.get('request_timeout_seconds',120))
        self.tools=None
    def embed(self,text):
        request={'model':self.embed_model,'input':text}
        root=self.out/'embeddings';root.mkdir(parents=True,exist_ok=True)
        folder=None
        for candidate in sorted(root.iterdir()):
            if candidate.is_dir() and (candidate/'request.json').is_file() and read(candidate/'request.json')==request:
                folder=candidate;break
        if folder is None:folder=root/f'{len(list(root.iterdir()))+1:06d}'
        path=folder/'response.json'
        if path.is_file():
            response=read(path)
            if not (folder/'result.json').exists():
                write(folder/'result.json',{'response_received':True,'model_returned':response.get('model'),
                    'usage':response.get('usage'),'elapsed_s':None,'error':None,'recovered_from_saved_response':True,
                    'accounting':'embedding_provider_usage_record_only_not_invoice','utc':now()})
        else:
            if (folder/'started.json').exists():raise RuntimeError('unknown_embedding_send_no_retry')
            write(folder/'request.json',request);write(folder/'started.json',{'sent_intent':True,'utc':now()})
            tick=time.monotonic()
            try:
                response=self.embedding_client.embeddings.create(**request).model_dump();write(path,response)
            except Exception as exc:
                write(folder/'result.json',{'response_received':False,'error_type':type(exc).__name__,
                    'elapsed_s':time.monotonic()-tick,'usage':None,'utc':now()})
                raise RuntimeError('embedding_api_failure_no_automatic_retry:'+type(exc).__name__) from None
            write(folder/'result.json',{'response_received':True,'model_returned':response.get('model'),
                'usage':response.get('usage'),'elapsed_s':time.monotonic()-tick,'error':None,
                'accounting':'embedding_provider_usage_record_only_not_invoice','utc':now()})
        if response.get('model')!=self.embed_model:raise RuntimeError('embedding_returned_model_identity_mismatch')
        data=response.get('data')
        if not isinstance(data,list) or len(data)!=1:raise ValueError('invalid_embedding_response')
        vector=data[0].get('embedding')
        if not isinstance(vector,list) or not vector or any(type(x) not in (int,float) or not math.isfinite(x) for x in vector):raise ValueError('invalid_embedding_vector')
        return vector
    def meta(self,event,system,payload,image_row=None,data=None):
        content=[{'type':'text','text':json.dumps(payload,ensure_ascii=False)}]
        if image_row is not None:content+=self.base.content(image_row,Path(data))
        messages=[{'role':'system','content':system},{'role':'user','content':content}]
        raw=self.call({'question_id':event},'R49-META',1,messages)
        # Preserve raw failure; no unbudgeted JSON repair.
        from run_cxr_action_r41 import parse
        return parse(raw)
    def execute(self,row,policy,data,conditioning):
        # policy retained only as provenance. BOTH new arms use this unbounded executor.
        from run_cxr_action_r41 import parse,answer
        from cxr_task_completion_r43 import prompt
        if self.tools is None:self.tools=self.base.Tools(self.runtime,Path(data),self.out)
        system=self.base.agent_system('M').replace('You may select zero, one or two registered tools, with early stopping when appropriate.',
            'Select useful registered tools as needed; there is no fixed total call-count limit. Stop when sufficient evidence supports an answer.')
        if conditioning:system=system.replace('No cross-case skills, sibling question context or additional patient history is available.',
            'Optional learned procedural skills and previously completed same-image questions with post-prediction dataset feedback may be supplied. Skills are not current-patient facts. No current or future reference answer is supplied.')
        messages=[{'role':'system','content':system},{'role':'user','content':self.base.content(row,Path(data))}]
        if conditioning:messages.append({'role':'user','content':conditioning})
        observations=[];calls=[];seen={};n=0;used=0;invalid=0;next_prompt=None
        action=self.base.ACTION.replace('At most two selectable tool calls total.','No fixed total tool-call count limit.')
        if len(row['images'])>1:action=action.replace('"args":{}','"args":{},"image_index":1').replace('Each call applies only to the bound original.','Select numbered original via image_index.')
        while True:
            n+=1
            messages.append({'role':'user','content':next_prompt or action+json.dumps(self.base.evidence_catalog(self.runtime,'M'))})
            raw=self.call(row,'R49-AGENT',n,messages);calls.append({'step_index':n-1,'response':raw})
            messages.append({'role':'assistant','content':raw});next_prompt=None
            try:obj=parse(raw)
            except (ValueError,IndexError):obj={}
            result=answer(obj)
            if result:
                from cxr_task_completion_r43 import unscorable
                if not unscorable(row,result):
                    result.update(main_calls=n,tool_calls=used,observations=observations,terminal_raw=raw)
                    return result,calls
            actions=obj.get('calls')
            if not isinstance(actions,list) or not actions:
                invalid+=1
                if invalid>=3:return {'answer':None,'reason':None,'status':'repeated_invalid_output','main_calls':n,'tool_calls':used,'observations':observations,'terminal_raw':raw},calls
                next_prompt=prompt(row);continue
            try:actions=self.base.validate_actions(obj,self.runtime,'M',len(actions),len(row['images']))
            except (ValueError,TypeError,KeyError):
                invalid+=1
                if invalid>=3:return {'answer':None,'reason':None,'status':'repeated_invalid_plan','main_calls':n,'tool_calls':used,'observations':observations,'terminal_raw':raw},calls
                next_prompt='Use only registered tool names and valid arguments, or give final answer/reason JSON.';continue
            fresh=[]
            for action_item in actions:
                actual=self.base.resolve_action(action_item,observations);signature=digest(actual);seen[signature]=seen.get(signature,0)+1
                if seen[signature]>=3:
                    return {'answer':None,'reason':None,'status':'repeated_identical_action_no_progress','main_calls':n,'tool_calls':used,'observations':observations,'terminal_raw':raw},calls
                used+=1;obs=self.tools.call(row,actual,'R49-AGENT',used)
                failure=tool_failure_reason(obs)
                if failure:raise RuntimeError('tool_failure_stop_no_automatic_retry:'+failure)
                observations.append(obs);fresh.append(obs)
            self.base.append_observations(messages,fresh,self.out,'M')


def conditioning(skills):
    if not skills:return None
    return ('Source-derived procedural skills, not observations or answers about the current patient. '
      'Use only when their conditions are met; unsupported prior conclusions must not override current pixels. '
      'Tool use remains optional.\n'+json.dumps([{'skill_id':x['id'],**x['c']} for x in skills],ensure_ascii=False))
