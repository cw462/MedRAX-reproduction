"""Two-arm gain experiment, opt-in execution; no paid calls by default."""
import argparse
import hashlib
import json
from pathlib import Path
import run_cxr_vqa_toolsets as base
from run_cxr_skill_v2 import HealthyTools
from cxr_skill_v2 import load_bank,select
from cxr_evidence_v32 import SYSTEM,episode,strip_json_fence

ORIGINAL_SYSTEM=base.agent_system
class MechanicalPaidCalls(base.PaidCalls):
    def call(self,row,arm,ordinal,messages,*,api_tools=None):
        raw=super().call(row,arm,ordinal,messages,api_tools=api_tools)
        normalized=strip_json_fence(raw) if api_tools is None else raw
        if isinstance(raw,str):
            value={'question_id':row['question_id'],'ordinal':ordinal,'changed':raw!=normalized,
                   'raw_sha256':hashlib.sha256(raw.encode()).hexdigest(),
                   'normalized_sha256':hashlib.sha256(normalized.encode()).hexdigest()}
            path=self.out/'mechanical_format'/arm/row['question_id']/(str(ordinal)+'.json')
            if path.exists():
                if base.read(path)!=value:raise ValueError('normalization_changed')
            else:base.save(path,value)
        return normalized

def system(arm):return SYSTEM if arm in ('M-A','M-AS') else ORIGINAL_SYSTEM(arm)

def run(argv=None):
    p=argparse.ArgumentParser(add_help=False)
    for k in ('config','data','out'):p.add_argument('--'+k,type=Path,required=True)
    p.add_argument('--arms',nargs='+',required=True,choices=['M-A','M-AS'])
    a,rest=p.parse_known_args(argv)
    if '--parallel' in rest:raise ValueError('v3_first_round_is_sequential')
    cfg=base.read(a.config);rt=base.read(cfg['runtime']);prot=base.read(cfg['protocol'])
    if not prot['experiment_id'].startswith('gain_v32_'):raise ValueError('new_experiment_id_required')
    if prot.get('request_archive')!='image_base64_content_addressed_v1':raise ValueError('exact_resume_required')
    allowed=rt['gain_v3']['arms']
    if set(a.arms)!=set(allowed) or len(a.arms)!=len(allowed):raise ValueError('run_the_frozen_pair')
    if allowed != ['M-AS','M-A']:raise ValueError('unsupported_pair')
    if a.arms!=allowed:raise ValueError('frozen_execution_order')
    tools=rt['arms'][allowed[0]]['tools']
    for arm in allowed:
        if rt['arms'][arm]['tools']!=tools or prot['main_call_limits'][arm]!=6 or prot.get('tool_call_limits',{}).get(arm)!=4:raise ValueError('unequal_menu_or_budget')
    cards=None;banksha=None;settings={}
    if 'M-AS' in allowed:
        spec=rt['arms']['M-AS'];banksha=spec['bank_sha256'];cards=load_bank(spec['bank_path'],banksha,tools)
        settings=spec['retrieval']
    codefiles=[Path(__file__),Path(base.__file__),Path(__file__).with_name('cxr_evidence_v32.py'),
               Path(__file__).with_name('run_cxr_skill_v2.py'),Path(__file__).with_name('cxr_skill_v2.py'),
               Path(__file__).with_name('cxr_vqa_tool_worker.py')]
    frozen={'config':cfg,'runtime':rt,'protocol':prot,'bank_sha256':banksha,
            'code_sha256':{x.name:hashlib.sha256(x.read_bytes()).hexdigest() for x in codefiles},
            'input_sha256':hashlib.sha256((a.data/'inputs.jsonl').read_bytes()).hexdigest()}
    marker=a.out/'gain_v3_run.json'
    if marker.exists():
        if base.read(marker)!=frozen:raise ValueError('frozen_run_changed')
    else:
        if a.out.exists() and any(a.out.iterdir()):raise ValueError('fresh_output_directory_required')
        base.save(marker,frozen)
    def dispatch(row,arm,data,protocol,runtime,out,paid,tool_backend):
        if arm=='M':return base.episode(row,arm,data,protocol,runtime,out,paid,tool_backend)
        conditioning=None
        if arm=='M-AS':
            conditioning,trace=select(row,cards,tools,**settings)
            path=out/'retrieval'/arm/(row['question_id']+'.json')
            if path.exists():
                if base.read(path)!=trace:raise ValueError('retrieval_changed')
            else:base.save(path,trace)
        return episode(base,row,arm,data,protocol,runtime,out,paid,tool_backend,conditioning=conditioning)
    base.agent_system=system;base.Tools=HealthyTools;base.PaidCalls=MechanicalPaidCalls
    return base.main(['--config',str(a.config),'--data',str(a.data),'--out',str(a.out),'--arms',*a.arms,*rest],
                     arms=tuple(allowed),episode_fn=dispatch,system_fn=system)

if __name__=='__main__':raise SystemExit(run())
