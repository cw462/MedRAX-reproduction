"""Only source evolution and A1 target episodes; A0 is reused direct D."""
import argparse
from pathlib import Path
import subprocess
import sys
from run_direct_vlm import read,write,now
from run_sampled_vlm import exclusive_lock
from skemex_adapter.transport import ID


def run(root,approval,execute=False):
    root=Path(root);base=root/'runs'/ID;code=Path(__file__).resolve().parents[1]
    if not execute:return
    approved=read(approval)
    if approved.get('status')!='approved' or approved.get('experiment_id')!=ID or approved.get('A0')!='D' or approved.get('model')!='qwen3.7-plus':raise ValueError('user_clarified_A0_D_approval_required')
    cfg=read(base/'config.json')
    if cfg.get('tool_agent') and (approved.get('tool_agent') is not True or approved.get('plan_version')!='tools-v1'):
        raise ValueError('explicit_tools_v1_approval_required')
    key=sys.stdin.buffer.readline().strip()
    if not key:raise ValueError('stdin_key_required')
    with exclusive_lock(base/'.pipeline.lock'):
        try:
            for phase in ('source_A','source_B','target_A','target_B','scoring'):
                write(base/'pipeline_status.json',{'status':'running','phase':phase,'updated_utc':now()})
                if phase.startswith('source'):
                    cmd=[sys.executable,'-u',str(code/'experiments/evolve_skemex_a1.py'),'--root',str(root),'--source-fold',phase[-1]]
                elif phase.startswith('target'):
                    if not all((base/'evolution'/f/'complete.json').exists() for f in ('A','B')):raise ValueError('both_libraries_must_freeze_before_targets')
                    if (ID.endswith('_r1') or cfg.get('tool_agent')) and any(not read(base/'evolution'/f/'complete.json')['active_skill_ids'] for f in ('A','B')):
                        raise ValueError('empty_source_library_no_valid_memory_effect_evaluation')
                    if cfg.get('tool_agent') and any(not any(any(o.get('usable') for o in read(p).get('tool_observations',[])) for p in (base/'source_predictions'/f).glob('*.json')) for f in ('A','B')):
                        raise ValueError('no_usable_real_tool_evidence_in_source_fold')
                    cmd=[sys.executable,'-u',str(code/'experiments/run_skemex_a1.py'),'--root',str(root),'--target-fold',phase[-1]]
                else:cmd=[sys.executable,str(code/'experiments/score_skemex_a1.py'),'--root',str(root)]
                result=subprocess.run(cmd,cwd=code,input=key+b'\n' if phase!='scoring' else b'',check=False)
                if result.returncode:raise RuntimeError('phase_failed:'+phase)
            write(base/'pipeline_status.json',{'status':'completed','updated_utc':now(),'target_n':402,'new_groups':['A1']})
        except BaseException as exc:
            write(base/'pipeline_status.json',{'status':'stopped','phase':phase,'updated_utc':now(),'error_type':type(exc).__name__,'error':str(exc)});raise


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--approval',type=Path);p.add_argument('--execute',action='store_true');a=p.parse_args();run(a.root,a.approval,a.execute)
