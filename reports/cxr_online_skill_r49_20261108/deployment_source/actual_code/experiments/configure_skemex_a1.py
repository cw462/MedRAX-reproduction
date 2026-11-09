"""Prepare the user-clarified A0=D experiment; no generation or ledger reads."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from run_direct_vlm import read,read_lines
from run_sampled_vlm import frozen_write
ID='skemex_a1_20261103'


def configure(root,code):
    root=Path(root);code=Path(code);out=root/'runs'/ID;out.mkdir(parents=True,exist_ok=True)
    old=read(root/'code_history_skills_plus/configs/history_skills_plus_20261103/HS.json')
    cfg=deepcopy(old);cfg.update(experiment_id=ID,plan_version='1',arm='A1',run_id=ID,mode='official_skemex_single_answer',
        global_request_counter='runs/'+ID+'/global_requests.json',global_max_requests=5250,global_max_extra_requests=250,
        ledger='runs/'+ID+'/private_ledgers/shared.json',inherit_ledger='runs/history_skills_plus_20261103/private_ledgers/HS.json',
        shared_public_plan=str((code/'configs/skemex_a1_protocol.json').relative_to(root)),
        budget_authorization='User clarified A0 is direct D295/402; replace S1 memory with official SkeMex, only new A1 plus necessary source-fold evolution; original cumulative200 budget retained.')
    rows=read_lines(root/'runs/history_skills_plus_20261103/inputs/tune.inputs.jsonl')
    folds=read(root/'runs/history_skills_plus_20261103/inputs/folds.json')
    cats=read(root/'runs/history_skills_plus_20261103/inputs/categories.json')
    gold={r['question_id']:r['reference'] for r in read(root/'reports/qwen37_token_plan_20261102/phase1/per_question.json')['records']}
    frozen_write(out/'config.json',cfg);frozen_write(out/'inputs/rows.json',rows);frozen_write(out/'inputs/folds.json',folds)
    frozen_write(out/'inputs/official_categories.json',cats)
    for fold in ('A','B'):
        selected=[r for r in rows if folds[r['case_id']]==fold]
        frozen_write(out/'inputs'/('source_'+fold+'.json'),selected)
        by={}
        for row in selected:by.setdefault(row['case_id'],[]).append(row)
        for case,group in by.items():
            frozen_write(out/'training'/fold/(case+'.json'),{r['question_id']:gold[r['question_id']] for r in group})
        for r in selected:
            q=r['question_id'];terminal=read(root/'runs/qwen37_token_plan_20261102/phase1/D/checkpoints'/q/'sample_1/terminal.json')
            frozen_write(out/'cached_D'/ (q+'.json'),{k:terminal.get(k) for k in ('question_id','case_id','answer','status','raw_response')})
    folder=root/'models/medrax_embeddings/sentence-transformers--all-MiniLM-L6-v2'
    frozen_write(out/'embedding_version.json',{'model':'sentence-transformers/all-MiniLM-L6-v2','backend':'existing_cpu_onnx','adaptation_from':'text-embedding-3-large','files':{name:hashlib.sha256((folder/name).read_bytes()).hexdigest() for name in ('model.onnx','tokenizer.json')},'no_model_download_or_paid_probe':True})
    print(json.dumps({'prepared':True,'A0':'D295/402','model':cfg['model'],'target_episodes':len(rows),'new_api_calls':0,'cap_cny':cfg['cap_cny'],'normal_request_ceiling':5000,'hard_request_ceiling':5250}))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--code',type=Path,required=True);a=p.parse_args();configure(a.root,a.code)
