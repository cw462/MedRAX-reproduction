"""Prepare the tool-enabled proposal without API, GPU, labels or ledger reads."""
import argparse
from copy import deepcopy
from pathlib import Path
import shutil
from run_direct_vlm import read
from run_sampled_vlm import frozen_write

ID='skemex_tools_20261103'


def configure(root,code,tool_repo):
    root=Path(root);code=Path(code);out=root/'runs'/ID
    repo=Path(tool_repo)
    if repo.is_absolute() or '..' in repo.parts:raise ValueError('relative_existing_tool_repo_required')
    original=root/'runs/skemex_a1_20261103'
    if read(original/'pipeline_status.json')['status']!='completed':raise ValueError('original_must_be_terminal')
    if (out/'config.json').exists():raise ValueError('no_overwrite_or_restart')
    protocol=read(code/'configs/skemex_tools_protocol.json')
    if protocol['status']!='awaiting_user_confirmation':raise ValueError('unexpected_protocol')
    cfg=deepcopy(read(original/'config.json'))
    cfg.update(experiment_id=ID,run_id=ID,plan_version='tools-v1',mode='official_skemex_tool_agent',tool_agent=True,
               tool_repo=repo.as_posix(),tool_device='cuda:0',reuse_original_run='runs/skemex_a1_20261103',
               tool_modality_manifest='runs/'+ID+'/inputs/caption_modalities.json',
               budget_authorization='Tools-v1 requires explicit user approval before execution; same cumulative200 accounting authorization, cap and shared original request counter.',
               shared_public_plan=(code/'configs/skemex_tools_protocol.json').relative_to(root).as_posix())
    # Original global counter, ledger, inherit_ledger, cap and request limits stay unchanged.
    for folder in ('inputs','training'):
        shutil.copytree(original/folder,out/folder)
    shutil.copy2(code/'reports/case_information_20261103/03_E3/caption_modalities.json',out/'inputs/caption_modalities.json')
    shutil.copy2(original/'embedding_version.json',out/'embedding_version.json')
    frozen_write(out/'config.json',cfg)
    return {'status':'prepared_no_execution','experiment_id':ID,'new_api_calls':0,'tool_inference_calls':0,
            'shared_original_counter_and_ledger':True,'approval_required':'tools-v1'}


if __name__=='__main__':
    import json
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--code',type=Path,required=True)
    p.add_argument('--tool-repo',required=True);a=p.parse_args();print(json.dumps(configure(a.root,a.code,a.tool_repo)))
