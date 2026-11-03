"""Matched one-answer D episode, adding official memory context only."""
import json
import re
from run_sampled_vlm import request_for,frozen_write
from .official import budgeted_llm_bindings


def episode(runtime,transport,row,cfg,dest,window,source_map):
    modules=runtime['modules'];store=runtime['store']
    # Skill provenance belongs wholly to this source fold, including utility.
    skills=store.list_skills(statuses=['active','mature'])
    for skill in skills:
        if skill.branch=='meta_memory':continue
        if not skill.source_trajectory_ids or any(t not in source_map for t in skill.source_trajectory_ids):
            raise ValueError('unknown_skill_source_not_allowed')
        if row['case_id'] in {source_map[t] for t in skill.source_trajectory_ids}:raise ValueError('same_patient_skill_not_allowed')
    with budgeted_llm_bindings(modules,transport.factory):
        registry=modules['categories'].DynamicTaskCategoryRegistry(store,runtime['config'])
        categories=registry.classify(row['question'])
        retrieval=runtime['retriever'].retrieve(row['question'],categories,window,available_tools=[])
    messages,images=request_for(row,cfg)
    if retrieval.retrieved_skills_block:
        messages[0]['content']+='\n\nExperience from other source-fold patients; may not apply. Check the conditions before use; these are not patient facts. If a skill is used, mention its ID briefly in Reason.\n'+retrieval.retrieved_skills_block
    raw,terminal=transport.call(messages,actor=True,images=images)
    declared=[sid for sid in retrieval.injected_skill_ids if sid in (raw or '')]
    result={'question_id':row['question_id'],'case_id':row['case_id'],'answer':terminal['answer'],'status':terminal['status'],'raw_response':raw,
        'task_category':categories,'injected_skill_ids':retrieval.injected_skill_ids,'declared_applied_skill_ids':declared,
        'adoption_note':'Explicit IDs in short response only; absence is unknown, not proof of non-adoption. Source-window official analyzer supplies utility adoption feedback.',
        'action':'independent_visual_answer','evidence_target':row['images'],
        'retrieval_candidates':[c.__dict__ for c in retrieval.candidates]}
    frozen_write(dest,result)
    return result
