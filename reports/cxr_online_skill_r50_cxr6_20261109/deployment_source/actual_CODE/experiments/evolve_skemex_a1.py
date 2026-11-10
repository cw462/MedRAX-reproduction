"""Source-fold-only official evolution. Case predictions precede feedback release."""
import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import shutil
import sys

from run_direct_vlm import read,write,now
from run_sampled_vlm import frozen_write
from skemex_adapter.contracts import case_windows
from skemex_adapter.official import components,budgeted_llm_bindings
from skemex_adapter.embedding import LocalEmbeddings
from skemex_adapter.transport import PaidTransport,Halt,ID
from skemex_adapter.episode import episode


def prohibited(text,row):
    import re
    if row['question_id'] in text or re.search(r'\b(?:case|patient)\s*(?:id|number|#)|\b(?:option|answer|choice)\s*[:=]?\s*[A-Z]\b|\bfig(?:ure)?\s*\.?\s*\d',text,re.I):return True
    a=re.findall('[a-z]+',text.lower());b=' '.join(re.findall('[a-z]+',row['question'].lower()))
    return any(' '.join(a[i:i+12]) in b for i in range(max(0,len(a)-11)))


def run(root,fold,key):
    root=Path(root);base=root/'runs'/ID;cfg=read(base/'config.json');rows=read(base/'inputs'/('source_'+fold+'.json'))
    groups={}
    for r in rows:groups.setdefault(r['case_id'],[]).append(r)
    source_map={r['question_id']:r['case_id'] for r in rows}
    target_cases={c for c,f in read(base/'inputs/folds.json').items() if f!=fold}
    if set(groups)&target_cases:raise Halt('fold_overlap')
    workspace=base/'evolution'/fold/'current';snapshots=base/'evolution'/fold/'snapshots'
    marker=base/'evolution'/fold/'complete.json'
    if marker.exists():return
    transport=PaidTransport(cfg,key,base);emb=LocalEmbeddings(root,base/'embedding_cache'/('source_'+fold+'.json'))
    runtime=components(workspace,fold,emb,transport.factory,model=cfg['model'])
    if cfg.get('tool_agent'):
        from skemex_adapter.tool_episode import RealTools,episode as tool_episode,TOOLS_TEXT,skill_rejection
        tools=RealTools(cfg,base)
        if any(tools.eligible(row) for row in rows):tools.initialize()
    revised=cfg.get('evidence_revision')=='tools-v2'
    if revised:
        from skemex_adapter.evidence_revision import reflection_steps,TOOL_CONTRACT,skill_policy_rejection,require_safe_library
        TOOLS_TEXT+='\n'+TOOL_CONTRACT
    categories=read(base/'inputs/official_categories.json')
    windows=list(case_windows(rows,runtime['config'].buffer.window_size))
    for index,window in enumerate(windows):
        snapshot=snapshots/('w'+str(index))
        if snapshot.exists():continue
        # On any restart, replay only from the last committed source snapshot.
        progress=base/'evolution'/fold/'window_in_progress.json'
        if progress.exists():raise Halt('partial_evolution_window_requires_targeted_snapshot_recovery')
        write(progress,{'window':index,'started_utc':now(),'source_fold':fold})
        trajectories=[];case_groups={}
        for row in window:case_groups.setdefault(row['case_id'],[]).append(row)
        for case,case_rows in case_groups.items():
            predicted={}
            for row in case_rows:
                q=row['question_id'];transport.set_context('s'+fold+'w'+str(index)+'q'+q,row)
                target=base/'source_predictions'/fold/(q+'.json')
                if index==0 and not cfg.get('tool_agent'):
                    old=read(base/'cached_D'/(q+'.json'))
                    prediction=dict(old,task_category=categories[q],injected_skill_ids=[],reused_D=True)
                    frozen_write(target,prediction)
                else:
                    prediction=tool_episode(runtime,transport,row,cfg,target,index,source_map,tools) if cfg.get('tool_agent') else episode(runtime,transport,row,cfg,target,index,source_map)
                predicted[q]=prediction
                write(base/'progress.json',{'phase':'source_evolution','fold':fold,'window':index,'question_id':q,'updated_utc':now()})
            # Only this case's reference file is opened, after all its predictions.
            if not all((base/'source_predictions'/fold/(r['question_id']+'.json')).exists() for r in case_rows):raise Halt('feedback_before_case_predictions')
            refs=read(base/'training'/fold/(case+'.json'))
            frozen_write(base/'feedback_releases'/fold/(case+'.json'),{'case_id':case,'prediction_ids':list(predicted),'released_utc':now(),'all_case_predictions_saved':True})
            for row in case_rows:
                q=row['question_id'];p=predicted[q]
                trajectory=runtime['modules']['types'].Trajectory(id=q,dataset='ChestAgentBench',query=row['question'],images=row['images'],task_category=p['task_category'],
                    steps=p.get('trajectory_steps') or [{'step':1,'action':'answer','reasoning':p.get('raw_response') or '',
                            'observation':'Original input image bindings: '+','.join(row['images']),'answer':p['answer']}],
                    injected_skill_ids=p['injected_skill_ids'],prediction=p['answer'],ground_truth=refs[q],eval_result=float(p['answer']==refs[q]),
                    metadata={'case_id':case,'source_fold':fold,'prediction_saved_before_feedback':True,'reused_D':index==0 and not cfg.get('tool_agent')})
                if revised:
                    raw_tools=[]
                    for observation in p.get('tool_observations',[]):
                        record=read(base/'tool_cache'/observation['record'])
                        raw_tools.append({'tool':observation['tool'],'source_filename':observation['source_filename'],
                                          'status':record['status'],'result':record.get('result'),'error_type':record.get('error_type')})
                    trajectory.steps=reflection_steps(row,p,refs[q],raw_tools)
                    frozen_write(base/'reflection_contexts'/fold/(q+'.json'),trajectory.to_dict())
                trajectories.append(trajectory)
        runtime['buffer'].clear()
        for trajectory in trajectories:runtime['buffer'].add(trajectory)
        encodes={};events=[]
        with budgeted_llm_bindings(runtime['modules'],transport.factory):
            for trajectory in runtime['buffer'].all_items():
                row=next(r for r in window if r['question_id']==trajectory.id)
                transport.set_context('e'+fold+'w'+str(index)+'q'+trajectory.id,row)
                encoded=runtime['encoder'].encode(trajectory,TOOLS_TEXT if cfg.get('tool_agent') else 'No medical tools in this direct-answer baseline. Do not create action/tool skills. General/task skills should state specific checks, evidence requirements and when not applicable.')
                draft=encoded.skill_draft
                rejected=None
                if draft:
                    draft['source_trajectory_ids']=[trajectory.id]
                    if cfg.get('tool_agent'):
                        saved=read(base/'source_predictions'/fold/(trajectory.id+'.json'))
                        rejected=skill_rejection(draft,row,saved.get('executed_tool_names',[]))
                    elif draft.get('branch')=='action_level' or draft.get('required_tools'):rejected='no_real_tool_trajectory'
                    if not str(draft.get('applicable_conditions') or '').strip():rejected='missing_applicability'
                    elif prohibited(' '.join(str(draft.get(k) or '') for k in ('name','description','applicable_conditions','core_action','Core Action')),row):rejected='case_identifier_or_question_copy'
                if encoded.patch_content and prohibited(encoded.patch_content,row):rejected='unsafe_patch_content'
                if revised:
                    candidate=json.dumps(draft or {},ensure_ascii=False)+'\n'+(encoded.patch_content or '')
                    rejected=rejected or skill_policy_rejection(candidate)
                if rejected:encoded.output_action='NONE'
                encodes[trajectory.id]=encoded
                created=runtime['governance'].apply_encode_result(encoded)
                events.append({'trajectory_id':trajectory.id,'encode':asdict(encoded),'admission_rejection':rejected,'created':created.to_dict() if created else None})
            update=runtime['utility'].update_window(trajectories,encodes,index)
            transport.set_context('g'+fold+'w'+str(index),window[-1])
            governed=runtime['governance'].manage() if (index+1)%runtime['config'].governance.manage_every_n_windows==0 else None
        emb.flush()
        frozen_write(base/'window_records'/fold/('w'+str(index)+'.json'),{'index':index,'cases':list(case_groups),'trajectory_n':len(trajectories),'buffer_n':len(runtime['buffer'].all_items()),'events':events,'utility':update,'governance':governed})
        if revised:require_safe_library(runtime['store'])
        snapshot.parent.mkdir(parents=True,exist_ok=True);shutil.copytree(workspace,snapshot)
        progress.unlink()
    # No target-fold answers or feedback have been observed at freeze time.
    active=runtime['store'].list_skills(statuses=['active','mature'])
    for skill in active:
        if skill.branch!='meta_memory' and (not skill.source_trajectory_ids or any(t not in source_map for t in skill.source_trajectory_ids)):raise Halt('unknown_final_skill_provenance')
    freeze={'source_fold':fold,'source_case_ids':list(groups),'target_case_ids':sorted(target_cases),'source_trajectory_to_case':source_map,'active_skill_ids':[s.id for s in active if s.branch!='meta_memory'],
        'files':{str(p.relative_to(workspace)):hashlib.sha256(p.read_bytes()).hexdigest() for p in workspace.rglob('*') if p.is_file() and p.suffix in ('.json','.md')},'frozen_utc':now(),'window_count':len(windows),'target_feedback_used':False}
    frozen_write(marker,freeze)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--source-fold',choices=['A','B'],required=True);a=p.parse_args();run(a.root,a.source_fold,sys.stdin.readline().strip())
