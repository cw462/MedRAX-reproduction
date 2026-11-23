"""Original-M-style direct-or-tools loop, equal-budget selected-only paired reruns."""
import argparse,json
from pathlib import Path
from cxr_action_skill_r41 import read,sha,write

def parse(raw):
    text=raw.strip()
    if text.startswith('```') and text.endswith('```'):
        text=text.split('\n',1)[1].rsplit('```',1)[0].strip()
    obj=json.loads(text)
    if not isinstance(obj,dict):raise ValueError('object_required')
    return obj

def answer(obj):
    # Ignore auxiliary fields; preserve explicit answer even when evidence labels are malformed.
    if isinstance(obj.get('answer'),str) and obj['answer'].strip() and len(obj['answer'])<=300:
        return {'answer':obj['answer'],'reason':obj.get('reason') if isinstance(obj.get('reason'),str) else '', 'status':'completed'}
    return None

def system(base,arm):
    s=base.agent_system('M').replace('zero, one or two registered tools','zero to four registered tools')
    if arm=='M-S41':s=s.replace('No cross-case skills, sibling question context or additional patient history is available.',
        'An optional source-derived action skill may be supplied. No sibling questions or additional patient history is available.')
    return s

def episode(base,row,arm,data,protocol,runtime,out,paid,tools,conditioning):
    messages=[{'role':'system','content':system(base,arm)},{'role':'user','content':base.content(row,data)}]
    if conditioning:messages.append({'role':'user','content':conditioning})
    observations=[];used=0;limit=protocol['main_call_limits'][arm];cap=protocol['tool_call_limits'][arm]
    prompt=base.ACTION.replace('At most two selectable tool calls total.',f'At most {cap} selectable tool calls total.')
    if len(row['images'])>1:prompt=prompt.replace('"args":{}','"args":{},"image_index":1').replace('Each call applies only to the bound original.','Select the numbered original for each call via image_index.')
    failure='missing_invalid_final_json'
    for n in range(1,limit+1):
        final_only=n==limit or used>=cap
        text='Return final answer/reason JSON only; no further tools.' if final_only else prompt+json.dumps(base.evidence_catalog(runtime,arm))+f' Remaining selectable calls: {cap-used}.'
        messages.append({'role':'user','content':text});raw=paid.call(row,arm,n,messages);messages.append({'role':'assistant','content':raw})
        try:obj=parse(raw)
        except (ValueError,IndexError):obj={}
        result=answer(obj)
        if result:return dict(result,main_calls=n,tool_calls=used,observations=observations)
        if final_only:break
        try:actions=base.validate_actions(obj,runtime,arm,cap-used,len(row['images']))
        except (ValueError,TypeError,KeyError):failure='missing_invalid_tool_plan';break
        fresh=[]
        for action in actions:
            actual=base.resolve_action(action,observations);used+=1
            obs=tools.call(row,actual,arm,used)
            if obs.get('status')!='completed' or obs.get('observation') is None:raise RuntimeError('tool_unhealthy_stop')
            observations.append(obs);fresh.append(obs)
        base.append_observations(messages,fresh,out,arm)
    return {'answer':None,'reason':None,'status':failure,'main_calls':n,'tool_calls':used,'observations':observations}

def dispatch_frozen(base,frozen,row,arm,data,protocol,runtime,out,paid,tools):
    item=frozen['mask'][row['question_id']]
    if not item['selected_ids']:
        h=frozen['history'][row['question_id']]
        return {'answer':h.get('answer'),'reason':h.get('reason',''),'status':h.get('status','completed'),
                'main_calls':0,'tool_calls':0,'reused_historical_M':True,'historical_sha256':frozen['historical_sha256']}
    result=episode(base,row,arm,data,protocol,runtime,out,paid,tools,item['conditioning'] if arm=='M-S41' else None)
    return dict(result,reused_historical_M=False,selected_skill_ids=item['selected_ids'])

def main(argv=None):
    import run_cxr_vqa_toolsets as base
    p=argparse.ArgumentParser(add_help=False)
    for k in ('config','data','out'):p.add_argument('--'+k,type=Path,required=True)
    p.add_argument('--arms',nargs='+',choices=['M-S41','M-C41'],required=True)
    a,rest=p.parse_known_args(argv);cfg=read(a.config);rt=read(cfg['runtime']);prot=read(cfg['protocol']);frozen=read(cfg['action_r41_frozen'])
    if '--execute' in rest and not any(x['selected_ids'] for x in frozen['mask'].values()):raise ValueError('zero_coverage_no_experiment_to_run')
    if sha(a.data/'inputs.jsonl')!=frozen['inputs_sha256']:raise ValueError('inputs_changed')
    if not prot['experiment_id'].startswith('action_r41_'):raise ValueError('wrong_experiment')
    if prot.get('request_archive')!='image_base64_content_addressed_v1':raise ValueError('request_archive_required')
    if rt['arms']['M-S41']!=rt['arms']['M-C41']:raise ValueError('arm_runtime_differs')
    for arm in ('M-S41','M-C41'):
        if prot['main_call_limits'][arm]!=6 or prot['tool_call_limits'][arm]!=4:raise ValueError('budget_changed')
    sources=[Path(__file__),Path(__file__).with_name('cxr_action_skill_r41.py'),Path(base.__file__)]
    marker={'config':cfg,'runtime':rt,'protocol':prot,'frozen_sha256':sha(cfg['action_r41_frozen']),'code':{x.name:sha(x) for x in sources}}
    fp=a.out/'r41_run.json'
    if fp.exists():
        if read(fp)!=marker:raise ValueError('frozen_run_changed')
    else:
        if a.out.exists() and any(a.out.iterdir()):raise ValueError('new_run_directory_required')
        write(fp,marker)
    def dispatch(row,arm,data,protocol,runtime,out,paid,tools):return dispatch_frozen(base,frozen,row,arm,data,protocol,runtime,out,paid,tools)
    return base.main(['--config',str(a.config),'--data',str(a.data),'--out',str(a.out),'--arms',*a.arms,*rest],arms=('M-S41','M-C41'),episode_fn=dispatch,system_fn=lambda arm:system(base,arm))
if __name__=='__main__':raise SystemExit(main())
