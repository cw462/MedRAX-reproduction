"""R49 executor retained with explicit R54 Skill activation; unchanged model/tools."""
import json
import re
from pathlib import Path
from skill_services_r49 import Services as R49Services
from cxr_online_primitives_r49 import digest,tool_failure_reason
from skill_prompts_r54ds import ACTIVATE
from online_memory_r49 import save_once
from failure_observation_r54 import delivered_failure
REPAIR_TOOL_CALL = (
    'The proposed tool request was not executed. Resubmit it as one JSON object '
    'with a non-empty calls list and valid registered tool arguments. Do not '
    'include prose outside JSON or give a final answer before receiving a tool observation.'
)
TOOLS=('chest_xray_expert' , 'llava_med_qa', 'medgemma', 'llava_rad', 'medvlm_r1', 'maira2_grounded_report', 'xray_phrase_grounding', 'roi_crop')
def validate_runtime(runtime):
    expected=set(TOOLS)
    names=runtime['arms']['M']['tools']
    if len(names)!=8 or set(names)!=expected:raise ValueError('R54 requires exactly eight interfaces')
    if set(runtime['tools'])!=expected:raise ValueError('removed_tools_still_registered')
    for arm in runtime.get('arms',{}):
        if arm=='R49-AGENT' and runtime['arms'][arm]['tools']!=names:raise ValueError('arm_tool_mismatch')
    for name in expected:
        spec=runtime['tools'][name]
        if not spec.get('revision') or not spec.get('python'):raise ValueError('unbound_tool:'+name)
class Services(R49Services):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        import toolsets_r54
        self.base=toolsets_r54

    def set_candidates(self,skills):
        self.candidates=skills;self.activated=set()
    def activate(self,row,observations,step):
        if not self.candidates:return [],{'ids':[],'reason':'no_candidates'}
        remaining=[s for s in self.candidates if s['id'] in self.activated or len(self.activated)<2]
        obj=self.meta('activation_'+row['question_id']+'_'+str(step),ACTIVATE,
            {'question':row['question'],'options':row.get('options',{}),'observations':observations,
             'candidates':remaining,'previously_activated':sorted(self.activated)})
        ids=obj.get('ids');allowed={s['id'] for s in remaining}
        if not isinstance(ids,list) or len(ids)>1 or not set(ids)<=allowed:raise ValueError('activation_ids')
        decisions=obj.get('decisions',[])
        for sid in ids:
            ds=[x for x in decisions if x.get('id')==sid and x.get('applicable') is True]
            if len(ds)!=1 or not ds[0].get('reason'):raise ValueError('activation_evidence_missing')
            ix=ds[0].get('evidence_observation_indices')
            if not isinstance(ix,list) or any(type(i)!=int or not 0<=i<len(observations) for i in ix):
                raise ValueError('activation_evidence_indices')
        self.activated.update(ids)
        save_once(self.out/'activation_events'/row['question_id']/(str(step)+'.json'),obj)
        return [{'skill_id':s['id'],**s['c']} for s in remaining if s['id'] in ids],obj
    def execute(self,row,policy,data,conditioning):
        # policy retained only as provenance. BOTH new arms use this unbounded executor.
        from run_cxr_action_r41 import parse,answer
        from cxr_task_completion_r43 import prompt
        if self.tools is None:self.tools=self.base.Tools(self.runtime,Path(data),self.out)
        system=self.base.agent_system('M').replace('You may select zero, one or two registered tools, with early stopping when appropriate.',
            'Select useful registered tools as needed; there is no fixed total call-count limit. Stop when sufficient evidence supports an answer.')
        if conditioning or self.candidates:system=system.replace('No cross-case skills, sibling question context or additional patient history is available.',
            'Optional learned procedural skills and previously completed same-image questions with post-prediction dataset feedback may be supplied. Skills are not current-patient facts. No current or future reference answer is supplied.')
        messages=[{'role':'system','content':system},{'role':'user','content':self.base.content(row,Path(data))}]
        if conditioning:messages.append({'role':'user','content':conditioning})
        observations=[];calls=[];seen={};n=0;used=0;invalid=0;next_prompt=None
        repair_pending=False
        action=self.base.ACTION.replace('At most two selectable tool calls total.','No fixed total tool-call count limit.')
        if len(row['images'])>1:action=action.replace('"args":{}','"args":{},"image_index":1').replace('Each call applies only to the bound original.','Select numbered original via image_index.')
        while True:
            n+=1
            active,activation=self.activate(row,observations,n)
            if self.candidates:
                messages.append({'role':'user','content':'R54 activation for THIS decision only. Earlier activation directives expire; only this list is currently active (empty means none): '+json.dumps(active,ensure_ascii=False)})
            messages.append({'role':'user','content':next_prompt or action+json.dumps(self.base.evidence_catalog(self.runtime,'M'))})
            raw=self.call(row,'R49-AGENT',n,messages);calls.append({'step_index':n-1,'response':raw,'skill_activation':activation})
            messages.append({'role':'assistant','content':raw});next_prompt=None
            try:obj=parse(raw)
            except (ValueError,IndexError):
                obj={}
                if re.search(r'"calls"\s*:',raw):repair_pending=True
            # A pending tool request must be repaired and executed before a final answer.
            result=None if repair_pending or 'calls' in obj else answer(obj)
            if result:
                from cxr_task_completion_r43 import unscorable
                if not unscorable(row,result):
                    result.update(activated_skill_ids=sorted(self.activated),main_calls=n,tool_calls=used,observations=observations,terminal_raw=raw)
                    return result,calls
            actions=obj.get('calls')
            if not isinstance(actions,list) or not actions:
                invalid+=1
                if invalid>=3:return {'activated_skill_ids':sorted(self.activated),'answer':None,'reason':None,'status':'repeated_invalid_output','main_calls':n,'tool_calls':used,'observations':observations,'terminal_raw':raw},calls
                next_prompt=REPAIR_TOOL_CALL if repair_pending else prompt(row)
                continue
            try:actions=self.base.validate_actions(obj,self.runtime,'M',len(actions),len(row['images']))
            except (ValueError,TypeError,KeyError):
                invalid+=1
                if invalid>=3:return {'activated_skill_ids':sorted(self.activated),'answer':None,'reason':None,'status':'repeated_invalid_plan','main_calls':n,'tool_calls':used,'observations':observations,'terminal_raw':raw},calls
                repair_pending=True
                next_prompt=REPAIR_TOOL_CALL
                continue
            fresh=[]
            for action_item in actions:
                actual=self.base.resolve_action(action_item,observations);signature=digest(actual);seen[signature]=seen.get(signature,0)+1
                if seen[signature]>=3:
                    return {'activated_skill_ids':sorted(self.activated),'answer':None,'reason':None,'status':'repeated_identical_action_no_progress','main_calls':n,'tool_calls':used,'observations':observations,'terminal_raw':raw},calls
                used+=1;obs=self.tools.call(row,actual,'R49-AGENT',used)
                failure=tool_failure_reason(obs)
                if failure:obs=delivered_failure(self.out,row,used,actual,obs)
                observations.append(obs);fresh.append(obs)
            self.base.append_observations(messages,fresh,self.out,'M')
            repair_pending=False


def conditioning(skills):
    return None  # Candidates are never injected before activation.
