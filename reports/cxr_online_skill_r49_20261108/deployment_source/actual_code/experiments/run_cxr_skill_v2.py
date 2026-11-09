"""New-run M/M-S paired experiment; original runners/results remain untouched."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import run_cxr_vqa_toolsets as base
from cxr_skill_v2 import load_bank, select

ORIGINAL_SYSTEM = base.agent_system
NO_MEMORY = 'No cross-case skills, sibling question context or additional patient history is available.'

def system(arm):
    text = ORIGINAL_SYSTEM(arm)
    if arm == 'M-S':
        if NO_MEMORY not in text: raise ValueError('upstream_system_changed')
        text=text.replace(NO_MEMORY, 'Optional source-derived skill checks may be supplied. They are not observations of this patient. No sibling questions or additional patient history are available.')
    return text

class HealthyTools(base.Tools):
    """Never pass a failed/unknown tool observation to a paid continuation."""
    def call(self,row,call,arm,ordinal):
        result=super().call(row,call,arm,ordinal)
        if result.get('status')!='completed' or result.get('observation') is None:
            # The existing runner retains raw result, selected action and send markers.
            # No retry, no alternate answer, no continuing the rest of the dataset.
            raise RuntimeError('tool_unhealthy_stop:'+call['tool']+':'+str(result.get('status')))
        return result

def run(argv=None):
    p=argparse.ArgumentParser(add_help=False)
    p.add_argument('--config',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--data',type=Path,required=True)
    p.add_argument('--arms',nargs='+',choices=['M','M-S'],required=True)
    args,rest=p.parse_known_args(argv)
    cfg=base.read(args.config); runtime=base.read(cfg['runtime']); protocol=base.read(cfg['protocol'])
    if not protocol['experiment_id'].startswith('skill_v2_'): raise ValueError('new_experiment_id_required')
    if protocol.get('request_archive')!='image_base64_content_addressed_v1': raise ValueError('exact_request_resume_required')
    for arm in ('M','M-S'):
        if protocol['main_call_limits'][arm]!=4: raise ValueError('must_use_four_call_limit')
    if runtime['arms']['M']['tools']!=runtime['arms']['M-S']['tools']: raise ValueError('tool_menus_differ')
    spec=runtime['arms']['M-S']; tools=runtime['arms']['M']['tools']
    cards=load_bank(spec['bank_path'],spec['bank_sha256'],tools)
    settings=spec.get('retrieval',{'max_cards':2,'min_overlap':2,'max_chars':2200})
    source_paths=[Path(__file__),Path(__file__).with_name('cxr_skill_v2.py'),Path(base.__file__)]
    frozen={'implementation':{x.name:hashlib.sha256(x.read_bytes()).hexdigest() for x in source_paths},
            'bank_sha256':spec['bank_sha256'],'settings':settings,'config':cfg,'runtime':runtime,'protocol':protocol,
            'inputs_sha256':hashlib.sha256((args.data/'inputs.jsonl').read_bytes()).hexdigest()}
    marker=args.out/'skill_v2_run.json'
    if marker.exists():
        if base.read(marker)!=frozen: raise ValueError('frozen_run_changed')
    else:
        if args.out.exists() and any(args.out.iterdir()): raise ValueError('new_empty_run_directory_required')
        base.save(marker,frozen)
    def dispatch(row,arm,data,protocol,runtime,out,paid,tool_backend):
        conditioning,trace=(select(row,cards,tools,**settings) if arm=='M-S' else
                            (None,{'question_id':row['question_id'],'selected_ids':[]}))
        path=out/'retrieval'/arm/(row['question_id']+'.json')
        if path.exists():
            if base.read(path)!=trace: raise ValueError('retrieval_changed')
        else: base.save(path,trace)
        return base.episode(row,arm,data,protocol,runtime,out,paid,tool_backend,conditioning=conditioning)
    base.agent_system=system
    base.Tools=HealthyTools
    return base.main(['--config',str(args.config),'--data',str(args.data),'--out',str(args.out),
                      '--arms',*args.arms,*rest],arms=('M','M-S'),episode_fn=dispatch,system_fn=system)

if __name__=='__main__': raise SystemExit(run())
