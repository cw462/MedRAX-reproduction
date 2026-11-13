"""One post-window Read/Write/Assess/Govern transition; no future input access."""
import copy,json
from skill_lifecycle_r49 import *
from skill_prompts_r54 import *
from skill_policy_r54 import buffer_select,eligibility,check_analysis
from online_memory_r49 import save_once as write

def evolve(service,snapshot,batch,wi,window,data,tools,config):
    analyses={}
    retained=buffer_select(batch,config);retained_ids={t['id'] for t in retained};writepath=window/'buffer.json'
    if not writepath.exists():write(writepath,{'retained':sorted(retained_ids),'all':[t['id'] for t in batch],
        'eligibility':{t['id']:eligibility(t) for t in batch}})
    # Analyze all eligible injected episodes for utility, including trivial successes excluded from writing.
    for t in batch:
        if t['id'] in retained_ids or t['injected']:
            analyses[t['id']]=service.meta('analysis_'+t['id'],ANALYZE,{'trajectory':t,'available_tools':tools},t['row'],data)
    # Persist all outputs including NONE so a zero library has an auditable explanation.
    for t in batch:
        if t['id'] in analyses:check_analysis(analyses[t['id']],t)
    write(window/'analyses.json',analyses)
    changes=[];repo=copy.deepcopy(snapshot);repo['clock']+=len(batch);repo['window']=wi+1
    repo.setdefault('hypotheses',[])

    for t in retained:
        analysis=analyses[t['id']];intent=analysis['output_intent']
        if intent=='NONE':
            changes.append({'source':t['id'],'operation':'NONE','reason':analysis['none_reason']});continue
        if analysis['support_level']!='observed':
            repo['hypotheses'].append({'source':t['id'],'analysis':analysis})
            repo['hypotheses']=repo['hypotheses'][-100:]
            changes.append({'source':t['id'],'operation':'HYPOTHESIS','reason':'not_executed_not_eligible_for_activation'});continue
        draft=service.meta('mutation_'+t['id'],MUTATE,{'analysis':analysis,'trajectory':t,'snapshot':snapshot['skills'],'tools':tools})
        op=draft['operation'];target=draft.get('patch_target_id')
        if op=='NONE':continue
        if op=='PATCH':
            if target not in snapshot['skills']:raise ValueError('patch_not_in_window_snapshot')
            section=draft['patch_section']
            if section not in ('name','description','applicable_conditions','required_tools','risk_level','core_action'):raise ValueError('invalid_patch_section')
            # A second local patch in this window must preserve the first one's
            # unrelated fields. Eligibility is bound to the read snapshot;
            # applying the patch uses the current write-side record.
            content=copy.deepcopy(repo['skills'][target]['c']);content[section]=draft['patch_content']
        else:content=draft['content']
        validate(content,tools);vector=service.embed(json.dumps(content,sort_keys=True))
        neighbors=[{'id':sid,'c':m['c']} for sid,m in repo['skills'].items() if scope(m['c'])==scope(content) and m['status'] in ('active','mature') and cosine(vector,m['vector'])>=config['merge_similarity']]
        review=service.meta('review_'+t['id'],REVIEW,{'candidate':content,'source':t,'neighbors':neighbors,'tools':tools},t['row'],data)
        if review.get('quality') is not True:
            changes.append({'source':t['id'],'initial_rejection':review})
            repair=service.meta('repair_'+t['id'],MUTATE,{'analysis':analysis,'trajectory':t,
                'candidate':content,'review':review,'operation':op,'patch_target_id':target,
                'instruction':'One narrow evidence-preserving repair; NONE if unsupported.','tools':tools})
            if repair.get('operation')=='NONE':continue
            if repair.get('operation')!=op or repair.get('patch_target_id')!=target:
                changes.append({'source':t['id'],'rejected':'repair_changed_operation_or_target'});continue
            if op=='CREATE':content=repair['content']
            else:
                section=repair['patch_section']
                if section not in ('name','description','applicable_conditions','required_tools','risk_level','core_action'):
                    raise ValueError('repair_patch_section')
                content=copy.deepcopy(repo['skills'][target]['c']);content[section]=repair['patch_content']
            validate(content,tools);vector=service.embed(json.dumps(content,sort_keys=True))
            neighbors=[{'id':sid,'c':m['c']} for sid,m in repo['skills'].items()
                if scope(m['c'])==scope(content) and m['status'] in ('active','mature')
                and cosine(vector,m['vector'])>=config['merge_similarity']]
            review=service.meta('review_repair_'+t['id'],REVIEW,
                {'candidate':content,'source':t,'neighbors':neighbors,'tools':tools},t['row'],data)
            if review.get('quality') is not True:changes.append({'source':t['id'],'rejected':review});continue
        duplicate=review.get('duplicate_of')
        if op=='CREATE' and duplicate:
            if duplicate not in [x['id'] for x in neighbors]:raise ValueError('invalid_novelty_target')
            patch=service.meta('redirect_'+t['id'],MUTATE,{'instruction':'PATCH only the duplicate skill, preserving unrelated fields','target':duplicate,'existing':repo['skills'][duplicate]['c'],'candidate':content,'source':t})
            if patch.get('operation')!='PATCH' or patch.get('patch_target_id')!=duplicate:raise ValueError('redirect_not_patch')
            section=patch['patch_section']
            if section not in ('description','applicable_conditions','core_action'):raise ValueError('redirect_scope')
            content=copy.deepcopy(repo['skills'][duplicate]['c']);content[section]=patch['patch_content'];validate(content,tools)
            second=service.meta('review_redirect_'+t['id'],REVIEW,{'candidate':content,'source':t,'neighbors':[],'tools':tools},t['row'],data)
            if second.get('quality') is not True:continue
            vector=service.embed(json.dumps(content,sort_keys=True));op='PATCH';target=duplicate
        sid=commit(repo,op,content,vector,[t['id']],tools,target);changes.append({'source':t['id'],'operation':op,'id':sid})
    credits=assess(repo,batch,analyses,config)
    def merge(aid,x,bid,y):
        value=service.meta(f'merge_{wi}_{aid}_{bid}',MERGE,{'a':x['c'],'b':y['c'],'tools':tools})
        if value.get('merge') is not True:return None
        c=value['content'];validate(c,tools)
        if scope(c)!=scope(x['c']):raise ValueError('merge_scope_changed')
        return c,service.embed(json.dumps(c,sort_keys=True))
    governance=govern(repo,config,merge) if repo['clock']//60 > snapshot['clock']//60 else []
    if not (window/'events.json').exists():write(window/'events.json',{'write':changes,'credit':credits,'govern':governance})
    return repo
