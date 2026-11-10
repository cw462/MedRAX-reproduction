"""M43 policy reconstruction with sequential same-image memory. New arm: M43-IM."""
import argparse,copy,sys,time
from pathlib import Path
from cxr_image_memory_r44 import *

class CapturePaid:
    def __init__(self,paid):self.paid=paid;self.last=None;self.raw=None
    def call(self,row,arm,ordinal,messages,**kw):
        raw=self.paid.call(row,'M43-IM',ordinal,messages,**kw)
        self.last=copy.deepcopy(messages);self.raw=raw
        return raw
class BoundTools:
    def __init__(self,tools):self.tools=tools
    def call(self,row,action,arm,ordinal):
        obs=self.tools.call(row,action,'M43-IM',ordinal)
        failure=tool_failure_reason(obs)
        if failure:raise RuntimeError('tool_unhealthy_stop:'+failure)
        return obs

def run_episode(base,r41,completion,row,policy,data,protocol,runtime,out,paid,tools,conditioning):
    cap=CapturePaid(paid);bound=BoundTools(tools)
    saved=base.agent_system
    def sys_prompt(arm):
        s=saved(arm)
        if conditioning:s=s.replace('No cross-case skills, sibling question context or additional patient history is available.',
             'Earlier same-image model observations and answers may be supplied. No other-case skills or extra patient history are supplied.')
        return s
    base.agent_system=sys_prompt
    try:
        if policy=='C41':
            result=r41.episode(base,row,'M-C41',data,protocol,runtime,out,cap,bound,conditioning)
        else:
            result=base.episode(row,'M',data,protocol,runtime,out,cap,bound,conditioning=conditioning)
        if policy=='M':
            inherited=dict(result,reused_historical_M=True)
            if completion.decision(row,inherited,result)=='complete_once':
                messages=cap.last+[{'role':'assistant','content':cap.raw},{'role':'user','content':completion.prompt(row)}]
                ordinal=result['main_calls']+1;raw=cap.call(row,'M',ordinal,messages)
                result['main_calls']=ordinal
                try:result.update(completion.accepted_reply(row,raw));result['completion_outcome']='accepted'
                except (ValueError,TypeError,IndexError):result['completion_outcome']='invalid_retained'
        result['terminal_raw']=cap.raw
        return result
    finally:base.agent_system=saved

def main():
    p=argparse.ArgumentParser();p.add_argument('--frozen',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--execute',action='store_true');p.add_argument('--api-key-stdin',action='store_true');a=p.parse_args()
    f=read(a.frozen);data=Path(f['data']);inputs=f['inputs']
    if sha(data/'inputs.jsonl')!=f['inputs_sha256'] or schedule(inputs,data)!=f['order']:raise ValueError('inputs_or_pixels_changed')
    if not a.execute:
        print({'questions':len(inputs),'repeat_questions':sum(bool(x['previous_ids']) for x in f['order']),'paid_calls':0});return
    import run_cxr_vqa_toolsets as base
    import run_cxr_action_r41 as r41
    import cxr_task_completion_r43 as completion
    if not a.api_key_stdin:raise ValueError('stdin_key_required')
    key=sys.stdin.readline().strip()
    if not key:raise ValueError('missing_key')
    protocol=copy.deepcopy(f['protocol']);protocol.update(experiment_id='m43_image_memory_r45_20261108',request_archive='image_base64_content_addressed_v1',
      main_call_limits={'M':4,'M-C41':6,'M43-IM':6},tool_call_limits={'M':2,'M-C41':4,'M43-IM':4})
    runtime=copy.deepcopy(f['runtime']);spec=runtime['arms'].get('M') or runtime['arms'].get('M-C41')
    if spec is None or not spec.get('ready'):raise ValueError('original_tools_not_ready')
    runtime['arms']={name:copy.deepcopy(spec) for name in ('M','M-C41','M43-IM')}
    a.out.mkdir(parents=True,exist_ok=True)
    with base.exclusive_lock(a.out/'.generation.lock'):
        code=[Path(__file__),Path(__file__).with_name('cxr_image_memory_r44.py'),Path(base.__file__),Path(r41.__file__),Path(completion.__file__)]
        marker={'frozen':sha(a.frozen),'code':{x.name:sha(x) for x in code},'protocol':protocol,'runtime':runtime}
        path=a.out/'run.json'
        if path.exists():
            if read(path)!=marker:raise ValueError('frozen_execution_changed')
        else:
            if any(a.out.iterdir()) and any(x.name!='.generation.lock' for x in a.out.iterdir()):raise ValueError('fresh_output_required')
            write(path,marker)
        paid=base.PaidCalls(f['config'],protocol,a.out,key);tools=base.Tools(runtime,data,a.out)
        memories={};rowmap={x['question_id']:x for x in inputs}
        for index,item in enumerate(f['order'],1):
            q=item['question_id'];row=rowmap[q];entries=memories.setdefault(item['image_key'],[])
            conditioning,used=context(entries,f['memory_max_chars'],f['memory_max_entries'])
            trace={'question_id':q,'previous_ids':item['previous_ids'],'included_ids':used,'memory':conditioning,'prefix_hash':digest(entries)}
            dest=a.out/'predictions/M43-IM'/(q+'.json');tp=a.out/'memory_context'/(q+'.json')
            if tp.exists():
                if read(tp)!=trace:raise ValueError('memory_prefix_changed')
            else:write(tp,trace)
            if dest.exists():result=read(dest)
            elif not conditioning:
                result=dict(f['baseline'][q],main_calls=0,tool_calls=0,new_main_calls=0,new_tool_calls=0,reused_M43=True)
                write(dest,result)
            else:
                base.write(a.out/'progress.json',{'status':'running','index':index,'total':618,'question_id':q,
                           'policy':f['policy'][q],'included_ids':used,'utc':base.now()})
                tick=time.monotonic()
                try:
                    result=run_episode(base,r41,completion,row,f['policy'][q],data,protocol,runtime,a.out,paid,tools,conditioning)
                except Exception as exc:
                    base.write(a.out/'progress.json',{'status':'stopped','index':index,'question_id':q,
                        'error':base.safe_error(exc,key),'error_type':type(exc).__name__,'utc':base.now()})
                    raise RuntimeError('image_memory_generation_stopped:'+type(exc).__name__) from None
                result.update(question_id=q,arm='M43-IM',reused_M43=False,new_main_calls=result['main_calls'],new_tool_calls=result['tool_calls'])
                result.update(elapsed_s=time.monotonic()-tick,utc=base.now())
                write(dest,result)
            entries.append(memory_entry(row,result))
        write_once=a.out/'complete_M43-IM.json'
        expected=set(rowmap)
        if {p.stem for p in (a.out/'predictions/M43-IM').glob('*.json')}!=expected:raise ValueError('incomplete_prediction_membership')
        sends=list((a.out/'calls/M43-IM').glob('*/*/started.json'))
        for sent in sends:
            folder=sent.parent
            if not (folder/'response.json').exists() or not (folder/'result.json').exists():raise ValueError('unresolved_sent_request')
            receipt=read(folder/'result.json')
            if receipt.get('error') or receipt.get('response_received') is not True:raise ValueError('unhealthy_request_receipt')
        selections=list((a.out/'tool_selections/M43-IM').glob('*/*.json'))
        for selection in selections:
            obs=read(selection)
            if tool_failure_reason(obs):raise ValueError('unhealthy_tool_selection')
        if len(sends)>f['new_main_ceiling'] or len(selections)>f['new_tool_ceiling']:raise ValueError('cohort_budget_exceeded')
        if not write_once.exists():write(write_once,{'questions':len(inputs),'status':'generation_complete','references_read':False,
             'new_main_sends':len(sends),'new_logical_tool_calls':len(selections),'utc':base.now()})
        base.write(a.out/'progress.json',{'status':'complete','questions':618,'utc':base.now()})
        print({'status':'complete','questions':len(inputs)})
if __name__=='__main__':main()
