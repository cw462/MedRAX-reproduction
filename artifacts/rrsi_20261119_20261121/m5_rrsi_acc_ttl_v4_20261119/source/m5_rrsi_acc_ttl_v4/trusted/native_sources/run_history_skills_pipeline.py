"""Approved Plus-only tuning round; no controls, heldout, full benchmark or Flash."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

from run_direct_vlm import read,write,now,read_lines
from run_sampled_vlm import exclusive_lock,frozen_write
from history_skills import ID,VERSION,filter_reason,merge_skills


def build_stores(root,out):
    target=out/'skills/crossfit_stores.json'
    if target.exists():return
    run=out/'arms/Reflection'
    if read(run/'status.json')['status']!='generation_complete':raise ValueError('complete_reflections_required')
    rows={r['question_id']:r for r in read(run/'selection.json')['rows']}
    folds=read(out/'inputs/folds.json');by={'A':[],'B':[]};audit=[]
    for line in (run/'predictions.jsonl').read_text().splitlines():
        record=json.loads(line);q=record['question_id'];row=rows[q]
        if record['status']!='completed':audit.append({'question_id':q,'reason':record['status']});continue
        for i,s in enumerate(record['skills']):
            reason=filter_reason(s,row)
            skill=dict(s,skill_id=q+'__'+str(i+1),source_question_id=q,source_case_id=row['case_id'],source_fold=folds[row['case_id']])
            if reason:audit.append({'skill':skill,'reason':reason})
            else:by[skill['source_fold']].append(skill)
    stores={}
    for f in by:
        stores[f],rejected=merge_skills(by[f],40);audit+=rejected
    frozen_write(out/'skills/filter_audit.json',{'records':audit})
    frozen_write(target,{'stores':stores,'source_references_not_in_answer_store':True,'created_utc':now(),'utility_not_used_before_crossfit_answers':True})
    frozen_write(out/'skills/crossfit_freeze.json',{'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'before_S1_HS':True})


def execute(manifest_path,approval_path,execute=False):
    m=read(manifest_path);root=Path(m['root']);out=root/'runs'/ID;code=Path(__file__).resolve().parents[1]
    if m['experiment_id']!=ID or m['model']!='qwen3.7-plus':raise ValueError('plus_only_manifest')
    if not execute:return {'status':'prepared_only','new_api_calls':0}
    approval=read(approval_path)
    if approval.get('experiment_id')!=ID or approval.get('plan_version')!=VERSION or approval.get('models')!=['qwen3.7-plus'] or approval.get('status')!='approved':raise ValueError('matching_user_approval_required')
    key=sys.stdin.buffer.readline().strip()
    if not key:raise ValueError('stdin_key_required')
    completed=[];active=None
    out.mkdir(parents=True,exist_ok=True)
    with exclusive_lock(out/'.pipeline.lock'):
        try:
            for arm in m['arms']:
                active=arm['id'];run=root/arm['out'];state=read(run/'status.json') if (run/'status.json').exists() else {}
                if state.get('status')=='generation_complete':completed.append(active);continue
                if state.get('status')=='stopped':raise RuntimeError('stopped_arm_requires_targeted_review:'+active)
                if active in ('S1','HS'):build_stores(root,out)
                write(out/'pipeline_status.json',{'status':'running','active_arm':active,'completed_arms':completed,'updated_utc':now()})
                command=[sys.executable,'-u',str(code/'experiments/run_history_skills.py'),'--config',str(root/arm['config']),'--out',str(run),'--approval',str(approval_path),'--api-key-stdin','--resume']
                result=subprocess.run(command,cwd=code,input=key+b'\n',check=False)
                if result.returncode or read(run/'status.json')['status']!='generation_complete':raise RuntimeError('worker_failed:'+active)
                completed.append(active)
            active='isolated_scoring'
            write(out/'pipeline_status.json',{'status':'running','step':active,'completed_arms':completed,'updated_utc':now()})
            result=subprocess.run([sys.executable,str(code/'experiments/score_history_skills.py'),'--root',str(root)],cwd=code,check=False)
            if result.returncode:raise RuntimeError('isolated_scoring_failed')
            write(out/'pipeline_status.json',{'status':'completed','completed_arms':completed,'updated_utc':now(),'report':'reports/'+ID,'no_heldout_or_flash_started':True})
        except Exception as exc:
            write(out/'pipeline_status.json',{'status':'stopped','active_arm':active,'completed_arms':completed,'error_type':type(exc).__name__,'error':str(exc),'updated_utc':now()});raise


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--manifest',type=Path,required=True);p.add_argument('--approval',type=Path);p.add_argument('--execute',action='store_true')
    a=p.parse_args();execute(a.manifest,a.approval,a.execute)
