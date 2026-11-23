"""Make isolated paired-run configs from the deployed config; no API calls."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
from cxr_skill_v2 import load_bank

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--base-config',type=Path,required=True)
    p.add_argument('--bank',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--experiment-id',required=True)
    a=p.parse_args()
    if not a.experiment_id.startswith('skill_v2_'): raise ValueError('experiment_id_prefix')
    cfg=json.loads(a.base_config.read_text(encoding='utf-8'))
    # Existing configs resolve paths in the launch working directory; run from repo root.
    protocol=json.loads(Path(cfg['protocol']).read_text(encoding='utf-8'))
    runtime=json.loads(Path(cfg['runtime']).read_text(encoding='utf-8'))
    sha=hashlib.sha256(a.bank.read_bytes()).hexdigest()
    load_bank(a.bank,sha,runtime['arms']['M']['tools'])
    spec=copy.deepcopy(runtime['arms']['M'])
    runtime['arms']={'M':copy.deepcopy(spec),'M-S':copy.deepcopy(spec)}
    runtime['arms']['M-S'].update(bank_path=str(a.bank.resolve()),bank_sha256=sha,
                                 retrieval={'max_cards':2,'min_overlap':2,'max_chars':2200})
    protocol.update(experiment_id=a.experiment_id,request_archive='image_base64_content_addressed_v1')
    protocol['main_call_limits']={'M':4,'M-S':4}
    # All provider/accounting options, model and sampling settings are inherited.
    # Each data set gets a separate generated config and fresh output directory.
    if a.out.exists() and any(a.out.iterdir()): raise ValueError('new_config_directory_required')
    a.out.mkdir(parents=True,exist_ok=True)
    for name,value in [('runtime.json',runtime),('protocol.json',protocol)]:
        (a.out/name).write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
    cfg.update(runtime=str((a.out/'runtime.json').resolve()),protocol=str((a.out/'protocol.json').resolve()))
    (a.out/'config.json').write_text(json.dumps(cfg,ensure_ascii=False,indent=2),encoding='utf-8')
    print(a.out/'config.json')

if __name__=='__main__': main()
