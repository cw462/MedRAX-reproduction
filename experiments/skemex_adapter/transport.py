"""Original paid-request worker as the only transport for official memory calls."""
from contextlib import redirect_stdout
from copy import deepcopy
import io
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import run_sampled_vlm as worker
from run_direct_vlm import read,write,now

ID='skemex_a1_20261103'


class Halt(BaseException):
    """Official best-effort RuntimeError handlers must not swallow budget/fatal stops."""


class RequestAdapter:
    def __init__(self,payload,row,actor,images):self.payload=payload;self.row=row;self.actor=actor;self.images=images
    def prepare(self,cfg,out):
        worker.frozen_write(out/'selection.json',{'rows':[self.row]})
        worker.frozen_write(out/'protocol.json',dict(cfg,actor=self.actor,implementation_commit=__import__('os').environ.get('MEDRAX_CODE_COMMIT','unrecorded')))
        return [self.row]
    def legal(self,row):return worker.question_parts(row['question'])[1] if self.actor else None
    def parse(self,text,legal):
        if self.actor:return worker.parse_answer(text,legal)
        return {'answer':'TEXT' if isinstance(text,str) and text.strip() else None,'status':'completed' if isinstance(text,str) and text.strip() else 'unparsed'}
    def request(self,row,cfg,out):return self.payload,self.images


class PaidTransport:
    def __init__(self,cfg,key,base):
        self.cfg=cfg;self.key=key;self.base=Path(base);self.context=None;self.ordinal=0
        self.state=read(self.base/'transport_state.json') if (self.base/'transport_state.json').exists() else {'consecutive_failed':0,'calls':0}
    def set_context(self,name,row,actor=False):self.context=(name,row,actor);self.ordinal=0
    def factory(self,llm_config):
        transport=self
        class Client:
            def generate(self,*,system_prompt,user_prompt,images=None,**kwargs):
                if images:raise Halt('official text memory transport must not silently replace actor images')
                messages=[{'role':'system','content':system_prompt},{'role':'user','content':user_prompt}]
                raw,_=transport.call(messages,max_tokens=llm_config.max_tokens,temperature=llm_config.temperature)
                return SimpleNamespace(content=raw or '{}')
        return Client()
    def call(self,messages,max_tokens=2048,temperature=.2,actor=False,images=None):
        if self.context is None:raise Halt('missing_operation_context')
        context,row,_=self.context;self.ordinal+=1
        job=context+'__'+str(self.ordinal);out=self.base/'calls'/job
        counter=Path(self.cfg['root'])/self.cfg['global_request_counter']
        if counter.exists() and not (out/'status.json').exists():
            counts=read(counter)
            if len(counts['request_ids'])-len(counts['extra_request_ids'])>=5000:raise Halt('normal_request_ceiling_5000')
        cfg=deepcopy(self.cfg);cfg.update(run_id='sa1_'+job,temperature=temperature,max_output_tokens=max_tokens,
            max_requests=2,max_extra_requests=1,question_count=1,case_count=1)
        if len(cfg['run_id'])>64:raise Halt('operation_id_too_long')
        out.mkdir(parents=True,exist_ok=True)
        old_stdin=sys.stdin
        args=SimpleNamespace(prepare_only=False,api_key_stdin=True,resume=True,acknowledge_stop=None)
        try:
            sys.stdin=io.StringIO(self.key+'\n')
            with worker.exclusive_lock(out/'.generation.lock'):
                code=worker.run(args,cfg,out,adapter=RequestAdapter(messages,row,actor,images or []))
        except BaseException as exc:
            if isinstance(exc,Halt):raise
            raise Halt('request_worker_failed:'+type(exc).__name__) from exc
        finally:sys.stdin=old_stdin
        terminal=out/'checkpoints'/row['question_id']/'sample_1/terminal.json'
        if code or not terminal.exists():raise Halt('worker_stopped_preserve_original_event:'+job)
        value=read(terminal)
        self.state['calls']+=1
        self.state['consecutive_failed']=self.state['consecutive_failed']+1 if value['status']=='request_failed' else 0
        write(self.base/'transport_state.json',self.state)
        if self.state['consecutive_failed']>=5:raise Halt('five_consecutive_failed_requests')
        return value.get('raw_response'),value
