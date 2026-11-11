"""Only R54 learning/writing META events use DeepSeek. No silent retries/fallback."""
import json,os,urllib.request
from pathlib import Path
from skill_services_r54ds import Services as Original
from skill_policy_r54 import check_analysis
from skill_lifecycle_r49 import validate
from online_memory_r49 import save_once,now
PREFIXES=('analysis_','mutation_','review_','redirect_','merge_','repair_')
def validate_writer(c):
    allowed={'base_url','model','thinking','reasoning_effort','max_tokens','timeout_seconds','api_key_env','expected_returned_models'}
    if set(c)-allowed:raise ValueError('unknown_writer_config_field')
    if not c.get('base_url','').startswith('https://') or not c.get('model'):raise ValueError('explicit_endpoint_model_required')
    if c.get('thinking')!={'type':'enabled'}:raise ValueError('thinking_must_be_enabled')
    if type(c.get('max_tokens'))!=int or c['max_tokens']<2048:raise ValueError('writer_token_budget_required')
    if not c.get('api_key_env'):raise ValueError('key_environment_name_required')

def completion_text(raw,config):
    if config.get('expected_returned_models') and raw.get('model') not in config['expected_returned_models']:raise ValueError('returned_model_mismatch')
    choice=raw['choices'][0];msg=choice['message']
    if choice.get('finish_reason')!='stop':raise ValueError('writer_did_not_finish:'+str(choice.get('finish_reason')))
    if not isinstance(msg.get('reasoning_content'),str) or not msg['reasoning_content'].strip():raise ValueError('thinking_not_observed_no_silent_fallback')
    if not isinstance(msg.get('content'),str) or not msg['content'].strip():raise ValueError('empty_writer_content')
    return msg['content']

def cached_call(folder,config,messages,transport):
    folder=Path(folder)
    request={'model':config['model'],'messages':messages,'thinking':config['thinking'],'max_tokens':config['max_tokens'],'stream':False}
    if config.get('reasoning_effort'):request['reasoning_effort']=config['reasoning_effort']
    save_once(folder/'request.json',request)
    save_once(folder/'endpoint.json',{'base_url':config['base_url']})
    if (folder/'response.json').exists():raw=json.loads((folder/'response.json').read_text())
    else:
        if (folder/'started.json').exists():raise RuntimeError('unknown_writer_send_no_retry')
        save_once(folder/'started.json',{'utc':now(),'response_received':False})
        raw=transport(request);save_once(folder/'response.json',raw)
    try:text=completion_text(raw,config)
    except Exception as e:
        save_once(folder/'result.json',{'response_received':True,'error':str(e),'model_returned':raw.get('model'),'usage':raw.get('usage')});raise
    save_once(folder/'result.json',{'response_received':True,'error':None,'model_returned':raw.get('model'),'usage':raw.get('usage'),'thinking_observed':True})
    return text

def validate_output(event, value, payload, tools):
    if event.startswith('analysis_'):
        check_analysis(value, payload['trajectory'])
        for item in value['skill_adoption']:
            if item.get('status') not in ('ADOPTED_POSITIVE','ADOPTED_NEGATIVE','IGNORED'):
                raise ValueError('invalid_adoption_status')
            if item['status'] != 'IGNORED' and (
                type(item.get('step_index')) is not int
                or not 0 <= item['step_index'] < len(payload['trajectory']['steps'])
                or not item.get('evidence')
            ):
                raise ValueError('invalid_adoption_evidence')
        if value['output_intent']=='PATCH' and value.get('patch_target_id') not in payload['patch_candidates']:
            raise ValueError('invalid_analysis_patch_target')
    elif event.startswith('review_'):
        if type(value.get('quality')) is not bool or not value.get('reason'):
            raise ValueError('invalid_review')
        duplicate=value.get('duplicate_of')
        if duplicate is not None and duplicate not in {x['id'] for x in payload['neighbors']}:
            raise ValueError('invalid_duplicate_id')
    elif event.startswith('merge_'):
        if type(value.get('merge')) is not bool:
            raise ValueError('invalid_merge')
        if value['merge']:
            validate(value['content'],tools)
    else:
        operation=value.get('operation')
        if operation not in ('CREATE','PATCH','NONE'):
            raise ValueError('invalid_mutation')
        if event.startswith('redirect_') and (operation!='PATCH' or value.get('patch_target_id')!=payload['target']):
            raise ValueError('invalid_redirect')
        if event.startswith('repair_') and operation!='NONE' and (
            operation!=payload['operation'] or value.get('patch_target_id')!=payload.get('patch_target_id')
        ):
            raise ValueError('invalid_repair_target')
        if operation=='CREATE':
            validate(value['content'],tools)
        elif operation=='PATCH':
            sections=('description','applicable_conditions','core_action') if event.startswith('redirect_') else (
                'name','description','applicable_conditions','required_tools','risk_level','core_action')
            if value.get('patch_section') not in sections or 'patch_content' not in value:
                raise ValueError('invalid_patch_section')
            target=value.get('patch_target_id')
            if event.startswith('mutation_') and target not in payload['snapshot']:
                raise ValueError('invalid_mutation_patch_target')
            if event.startswith('mutation_'):
                existing=payload['snapshot'][target]['c']
            elif event.startswith('redirect_'):
                existing=payload['existing']
            else:
                existing=payload['candidate']
            validate({**existing,value['patch_section']:value['patch_content']},tools)


class Services(Original):
    def __init__(self,*args,writer=None,**kwargs):
        super().__init__(*args,**kwargs)
        self.writer=writer
        if writer is not None:
            validate_writer(writer)

    def meta(self,event,system,payload,image_row=None,data=None):
        if not event.startswith(PREFIXES):
            return super().meta(event,system,payload,image_row,data)
        if self.writer is None:
            raise RuntimeError('writing_disabled_in_skill_off')
        key=os.environ.get(self.writer['api_key_env'])
        if not key:
            raise ValueError('missing_writer_key_environment')
        content=[{'type':'text','text':json.dumps(payload,ensure_ascii=False)}]
        if image_row is not None:
            content+=self.base.content(image_row,Path(data))
        messages=[{'role':'system','content':system},{'role':'user','content':content}]

        def transport(request):
            url=self.writer['base_url'].rstrip('/')+'/chat/completions'
            req=urllib.request.Request(url,data=json.dumps(request).encode(),
                headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'})
            with urllib.request.urlopen(req,timeout=self.writer.get('timeout_seconds',600)) as response:
                return json.load(response)

        from run_cxr_action_r41 import parse
        root=self.out/'calls/R54DS-WRITER'/event
        tools=self.runtime['arms']['M']['tools']
        for attempt in (1,2):
            folder=root/str(attempt)
            # Transport and provider failures propagate. Only received malformed
            # JSON/schema output is eligible for one separate archived request.
            raw=cached_call(folder,self.writer,messages,transport)
            try:
                value=parse(raw)
                validate_output(event,value,payload,tools)
            except (ValueError,KeyError,TypeError,IndexError,AttributeError) as exc:
                save_once(folder/'validation.json',{'valid':False,'error_type':type(exc).__name__})
                if attempt==2:
                    raise ValueError('writer_schema_invalid_after_one_repair:'+event) from exc
                messages=messages+[
                    {'role':'assistant','content':raw},
                    {'role':'user','content':'Your reply failed the required JSON/schema validation. Return one corrected JSON object matching the system contract. Preserve the evidence and do not add unsupported claims.'}
                ]
            else:
                save_once(folder/'validation.json',{'valid':True})
                return value
