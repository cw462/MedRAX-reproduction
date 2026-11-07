"""Create M-AS then M-A only. Reuse historical M externally; never schedule M."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
from cxr_skill_v2 import load_bank

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--base-config',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--experiment-id',required=True)
    p.add_argument('--bank',type=Path,required=True)
    a=p.parse_args()
    if not a.experiment_id.startswith('gain_v31_'):raise ValueError('experiment_id_prefix')
    cfg=json.loads(a.base_config.read_text(encoding='utf-8'))
    rt=json.loads(Path(cfg['runtime']).read_text(encoding='utf-8'))
    prot=json.loads(Path(cfg['protocol']).read_text(encoding='utf-8'))
    spec=copy.deepcopy(rt['arms']['M']);arms=['M-AS','M-A']
    sha=hashlib.sha256(a.bank.read_bytes()).hexdigest()
    cards=load_bank(a.bank,sha,spec['tools'])
    if not cards:raise ValueError('empty_skill_bank')
    rt['arms']={arm:copy.deepcopy(spec) for arm in arms}
    rt['gain_v3']={'phase':'skill','arms':arms,'historical_M':'reuse_only',
                  'format_rule':'single_enclosing_json_fence_v1','tool_failure_policy':'stop_run_no_automatic_retry'}
    rt['arms']['M-AS'].update(bank_path=str(a.bank.resolve()),bank_sha256=sha,
                             retrieval={'max_cards':2,'min_overlap':2,'max_chars':2200})
    prot.update(experiment_id=a.experiment_id,request_archive='image_base64_content_addressed_v1',
                main_call_limits={arm:4 for arm in arms})
    if a.out.exists() and any(a.out.iterdir()):raise ValueError('fresh_config_directory_required')
    a.out.mkdir(parents=True,exist_ok=True)
    for name,obj in [('runtime.json',rt),('protocol.json',prot)]:
        (a.out/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')
    cfg.update(runtime=str((a.out/'runtime.json').resolve()),protocol=str((a.out/'protocol.json').resolve()))
    (a.out/'config.json').write_text(json.dumps(cfg,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'config':str(a.out/'config.json'),'arms':arms,'paid_calls':0,'rerun_M':False}))
if __name__=='__main__':main()
