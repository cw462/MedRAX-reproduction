from copy import deepcopy
import re
from pathlib import Path
from .io import read,write,now


def normalized(text):return re.sub(r'\W+',' ',str(text).casefold()).strip()
def concrete_action(text):
    text=str(text)
    return (len(text.split())>=6 and bool(re.search(r'(?i)\b(compare|inspect|check|trace|count|locali[sz]e|assess|identify|review|examine|measure|follow|look|distinguish|evaluate)\b',text))
            and bool(re.search(r'(?i)\b(lung|pleur\w*|rib\w*|intercostal|bronch\w*|mediast\w*|diaphragm\w*|mass|nodule\w*|cavit\w*|opacity|opacities|heart|cardiac|vein\w*|arter\w*|vessel\w*|airway\w*|wall\w*|lesion\w*|figure\w*|view\w*|contour\w*|border\w*|trache\w*|hil\w*|calcif\w*|lobe\w*|fissure\w*|consolidat\w*)\b',text)))


class MemoryStore:
    def __init__(self,path,*,episodes=(),rules=(),enable_rules=True,capacity=24):
        self.path=Path(path);self.enable_rules=enable_rules;self.capacity=capacity
        if self.path.exists():self.state=read(self.path)
        else:
            self.state={'version':0,'episodes':deepcopy(list(episodes)),'rules':deepcopy(list(rules)) if enable_rules else [],
                        'events':[],'applied_events':[],'next_rule_serial':1+max([int(r['id'].removeprefix('S')) for r in rules if re.fullmatch(r'S\d+',r['id'])]+[0])}
            write(self.path,self.state)
        self.ensure_snapshot()

    def ensure_snapshot(self):
        p=self.path.parent/'versions'/f"v{self.state['version']:04}.json"
        if not p.exists():write(p,self.state)

    def _commit(self,event_id,change):
        if event_id in self.state['applied_events']:self.ensure_snapshot();return False
        state=deepcopy(self.state);details=change(state)
        state['version']+=1;state['applied_events'].append(event_id)
        state['events'].append({'event_id':event_id,'version':state['version'],'utc':now(),'details':details})
        write(self.path,state);self.state=state;self.ensure_snapshot();return True

    def selected_feedback(self,event_id,selected_ids,correct):
        def update(state):
            for rule in state['rules']:
                if rule['id'] in selected_ids:
                    rule['n_selected']+=1;rule['n_correct_when_selected']+=int(correct)
            return {'kind':'selection_association_not_causal_credit','selected_rule_ids':selected_ids,'answer_correct':bool(correct)}
        return self._commit(event_id,update)

    def apply(self,event_id,reflection,*,case_id,qid,phase,step,previous_choice_text,correct_choice_text,allowed_rule_ids=()):
        def update(state):
            raw=reflection['episode'];episode={k:deepcopy(raw.get(k,'')) for k in ('task','modality','case_pattern','error_or_success','decisive_difference','inspection_action','evidence_basis','limitations')}
            if episode['modality'] not in {'CXR','CT','other','unknown'}:episode['modality']='unknown'
            trunc=[]
            for key in ('case_pattern','error_or_success','decisive_difference','inspection_action','limitations'):
                value=str(episode[key]);words=value.split()
                if len(words)>90:value=' '.join(words[:90])+' [truncated]';trunc.append(key)
                episode[key]=value
            episode.update(id=event_id,source_case_id=case_id,source_question_id=qid,source_phase=phase,
                           available_after_step=step,previous_choice_text=previous_choice_text,correct_choice_text=correct_choice_text,
                           modality_source='reflection_model_reported_not_ground_truth',truncated_fields=trunc)
            episode['actionable']=concrete_action(episode['inspection_action']) and len(episode['decisive_difference'].split())>=5
            if not episode['actionable']:episode['non_actionable_reason']='missing_specific_anatomical_inspection_or_discriminating_difference'
            state['episodes'].append(episode)
            patch=reflection.get('procedure_patch');result={'episode_id':event_id,'actionable':episode['actionable'],'patch':'not_applied'}
            if not self.enable_rules:return dict(result,patch='ignored_in_E_arm')
            if not isinstance(patch,dict):return dict(result,patch='none')
            op=patch.get('op');target=patch.get('id');existing=next((r for r in state['rules'] if r['id']==target),None)
            if op in {'revise','retire'} and (existing is None or target not in allowed_rule_ids):return dict(result,patch='rejected_unknown_or_unsupplied_rule_id')
            if op=='retire':state['rules'].remove(existing);return dict(result,patch='retired',rule_id=target,old_rule=existing)
            if op not in {'add','revise'}:return dict(result,patch='rejected_operation')
            condition=str(patch.get('condition','')).strip();action=str(patch.get('action','')).strip();limit=str(patch.get('limitation','')).strip()
            if len(condition.split())<3 or not concrete_action(action) or not limit:return dict(result,patch='non_actionable_rule_archived_only')
            condition=' '.join(condition.split()[:35]);action=' '.join(action.split()[:45]);limit=' '.join(limit.split()[:30])
            try:priority=min(5,max(1,int(patch.get('priority',3))))
            except (ValueError,TypeError):priority=3
            same=next((r for r in state['rules'] if normalized(r['condition'])==normalized(condition) and normalized(r['action'])==normalized(action)),None)
            if same and (op=='add' or same['id']!=target):
                same['source_ids']=list(dict.fromkeys(same['source_ids']+[event_id]));same['source_case_ids']=list(dict.fromkeys(same['source_case_ids']+[case_id]))
                same['source_modalities']=list(dict.fromkeys(same['source_modalities']+[episode['modality']]))
                same['priority']=max(same['priority'],priority);same['available_after_step']=step
                return dict(result,patch='merged_exact_condition_action',rule_id=same['id'])
            if op=='revise':
                old=deepcopy(existing);existing.update(condition=condition,action=action,limitation=limit,priority=priority,
                    source_ids=list(dict.fromkeys(existing['source_ids']+[event_id])),source_case_ids=list(dict.fromkeys(existing['source_case_ids']+[case_id])),
                    source_modalities=list(dict.fromkeys(existing['source_modalities']+[episode['modality']])),available_after_step=step,
                    n_selected=0,n_correct_when_selected=0)
                return dict(result,patch='revised_new_version_counters_reset',rule_id=target,old_rule=old)
            evicted=None
            if len(state['rules'])>=self.capacity:
                evicted=min(state['rules'],key=lambda r:(r['n_selected']!=0,r['priority'],r['created_order'],r['id']))
                state['rules'].remove(evicted)
            serial=state['next_rule_serial'];state['next_rule_serial']+=1
            rule={'id':f'S{serial:04}','condition':condition,'action':action,'limitation':limit,'priority':priority,
                  'source_ids':[event_id],'source_case_ids':[case_id],'source_modalities':[episode['modality']],
                  'available_after_step':step,'n_selected':0,'n_correct_when_selected':0,'created_order':serial}
            state['rules'].append(rule)
            return dict(result,patch='added',rule_id=rule['id'],evicted_rule=evicted)
        return self._commit(event_id,update)

    def visible(self,*,step,current_case,seed_cases,past_cases):
        allowed=set(seed_cases)|set(past_cases)
        episodes=[deepcopy(e) for e in self.state['episodes'] if e.get('actionable') and e['source_case_id']!=current_case
                  and e['source_case_id'] in allowed and e['available_after_step']<step]
        rules=[deepcopy(r) for r in self.state['rules'] if r['available_after_step']<step and current_case not in r['source_case_ids']
               and set(r['source_case_ids'])<=allowed] if self.enable_rules else []
        return episodes,rules
