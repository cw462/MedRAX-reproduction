"""Archive and validate DeepSeek distillation. Qwen judges equivalence."""
import json,os,urllib.request
from pathlib import Path
from skill_services_r55live import Services as Original
from online_memory_r49 import save_once,now
DISTILL_PREFIX = 'exp_distill_'
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
    if not isinstance(msg.get('content'),str) or not msg['content'].strip():raise ValueError('empty_writer_content')
    return msg['content']

class ReceivedInvalid(ValueError):
    pass


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
    except (ValueError,KeyError,IndexError,TypeError,AttributeError) as e:
        model_mismatch = str(e)=='returned_model_mismatch'
        response_fields = raw if isinstance(raw, dict) else {}
        # A received malformed completion has a closed request receipt and can
        # use the separate correction attempt. An identity mismatch still stops.
        save_once(folder/'result.json',{'response_received':True,
                  'error':str(e) if model_mismatch else None,
                  'invalid_output':None if model_mismatch else str(e),
                  'model_returned':response_fields.get('model'),'usage':response_fields.get('usage')})
        if model_mismatch:
            raise
        raise ReceivedInvalid(str(e)) from e
    save_once(folder/'result.json',{'response_received':True,'error':None,'model_returned':raw.get('model'),'usage':raw.get('usage'),'thinking_observed':bool((raw['choices'][0]['message'].get('reasoning_content') or '').strip())})
    return text

def validate_output(event, value, payload):
    from experience_r55live import valid_principle
    from experience_feedback_r54 import copies_source

    if not isinstance(value, dict) or 'principle' not in value:
        raise ValueError('missing_experience_principle')
    if value['principle'] is not None:
        card = valid_principle(value, payload['steps'])
        if card is None:
            raise ValueError('invalid_experience_principle')
        if copies_source(card, payload, event.removeprefix(DISTILL_PREFIX)):
            raise ValueError('experience_principle_copies_source')


class Services(Original):
    def __init__(self,*args,writer=None,**kwargs):
        super().__init__(*args,**kwargs)
        self.writer=writer
        if writer is not None:
            validate_writer(writer)

    def meta(self,event,system,payload,image_row=None,data=None):
        if not event.startswith(DISTILL_PREFIX):
            if not event.startswith('exp_equiv_'):
                raise ValueError('unsupported_r55_meta_event')
            from run_cxr_action_r41 import parse
            messages = [
                {'role':'system','content':system},
                {'role':'user','content':[{'type':'text','text':json.dumps(payload,ensure_ascii=False)}]},
            ]
            raw = self.call({'question_id':event},'R49-META',1,messages)
            try:
                return parse(raw)
            except (ValueError, IndexError, TypeError, AttributeError):
                return {}
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
                headers={'Authorization':'[REDACTED]'+key,'Content-Type':'application/json'})
            with urllib.request.urlopen(req,timeout=self.writer.get('timeout_seconds',600)) as response:
                return json.load(response)

        from run_cxr_action_r41 import parse
        root=self.out/'calls/R54DS-WRITER'/event
        for attempt in (1,2):
            folder=root/str(attempt)
            # Transport and provider failures propagate. Only received malformed
            # JSON/schema output is eligible for one separate archived request.
            raw=''
            try:
                raw=cached_call(folder,self.writer,messages,transport)
            except ReceivedInvalid as exc:
                error=type(exc).__name__
            else:
                try:
                    value=parse(raw)
                    validate_output(event,value,payload)
                except (ValueError,KeyError,TypeError,IndexError,AttributeError) as exc:
                    error=type(exc).__name__
                else:
                    save_once(folder/'validation.json',{'valid':True})
                    return value
            save_once(folder/'validation.json',{'valid':False,'error_type':error})
            if attempt==2:
                save_once(root/'skip.json',{'event':event,'reason':error,'attempts':2})
                return {'principle':None}
            correction = ('Return a generic procedure and an observed evidence_step, or return {"principle":null}. '
                          'Remove source identifiers, option text or letters, and case-specific findings.')
            messages=messages+[
                {'role':'assistant','content':raw or '(No usable structured content received.)'},
                {'role':'user','content':correction},
            ]
