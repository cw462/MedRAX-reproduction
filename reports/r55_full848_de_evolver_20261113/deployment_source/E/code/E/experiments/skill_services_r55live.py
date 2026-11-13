"""R55 live executor with the eight deployed imaging tools and three R55 extensions."""
import json
import re
from pathlib import Path
from skill_services_r49 import Services as R49Services
from cxr_online_primitives_r49 import digest,tool_failure_reason
from online_memory_r49 import save_once
from failure_observation_r54 import delivered_failure
from tools_r55live import CATALOG, LiveTools, validate_extension_args
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
def register_r55_tools(runtime):
    validate_runtime(runtime)
    for name, description in CATALOG.items():
        runtime['tools'][name] = {'description':description, 'backend':'r55_'+name,
                                  'revision':'R55-EvolveR-live.1'}
    runtime['arms']['M']['tools'] = [*runtime['arms']['M']['tools'], *CATALOG]


class Services(R49Services):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        import toolsets_r54
        self.base=toolsets_r54
        self.experience_snapshot=None

    def execute(self,row,policy,data,conditioning):
        # policy retained only as provenance. BOTH new arms use this unbounded executor.
        from run_cxr_action_r41 import parse,answer
        from cxr_task_completion_r43 import prompt
        if self.tools is None:
            settings = self.runtime['r55_retrieval']
            self.tools = LiveTools(self, data, settings['provider'], settings['medrag_url'])
        system=self.base.agent_system('M').replace('You may select zero, one or two registered tools, with early stopping when appropriate.',
            'Select useful registered tools as needed; there is no fixed total call-count limit. Stop when sufficient evidence supports an answer.')
        self.activated = set()
        experience = self.experience_snapshot
        can_search = experience is not None and any(c['status']=='active' for c in experience['skills'].values())
        if conditioning or can_search:system=system.replace('No cross-case skills, sibling question context or additional patient history is available.',
            'Optional learned procedural skills and previously completed same-image questions with post-prediction dataset feedback may be supplied. Skills are not current-patient facts. No current or future reference answer is supplied.')
        system += (' For case-specific findings use bound image evidence. Reflect and Verify return advisory '
                   'observations. When they disagree with a candidate, compare the cited evidence and exact '
                   'question scope before revising. Do not change an answer solely because of disagreement.')
        messages=[{'role':'system','content':system},{'role':'user','content':self.base.content(row,Path(data))}]
        if conditioning:messages.append({'role':'user','content':conditioning})
        observations=[];calls=[];seen={};n=0;used=0;invalid=0;next_prompt=None
        repair_pending=False
        action=self.base.ACTION.replace('At most two selectable tool calls total.','No fixed total tool-call count limit.')
        if len(row['images'])>1:action=action.replace('"args":{}','"args":{},"image_index":1').replace('Each call applies only to the bound original.','Select numbered original via image_index.')
        searches=0
        if can_search:
            action += (' You may instead return {"search_experience":"short procedural query"} '
                       'to retrieve up to 3 past principles. Ask about a strategy, not a patient or answer. '
                       'You may search at most twice. Retrieved principles are not image evidence. ')
        while True:
            n+=1
            messages.append({'role':'user','content':next_prompt or action+json.dumps(self.base.evidence_catalog(self.runtime,'M'))})
            raw=self.call(row,'R49-AGENT',n,messages);calls.append({'step_index':n-1,'response':raw})
            messages.append({'role':'assistant','content':raw});next_prompt=None
            try:obj=parse(raw)
            except (ValueError,IndexError):
                obj={}
                if re.search(r'"calls"\s*:',raw):repair_pending=True
            if (
                not repair_pending and can_search and searches<2
                and set(obj)=={'search_experience'} and isinstance(obj['search_experience'],str)
                and 0<len(obj['search_experience'].strip())<=500
            ):
                from experience_r55live import search
                query=obj['search_experience'].strip()
                hits=search(experience,self.embed(query),3)
                searches+=1
                self.activated.update(hit['id'] for hit in hits)
                visible=[{'id':hit['id'], **hit['c'], 'score':hit['score']} for hit in hits]
                record={'query':query,'results':visible}
                calls[-1]['experience_search']=record
                save_once(self.out/'experience_searches'/row['question_id']/(str(n)+'.json'),record)
                messages.append({'role':'user','content':'Experience principles (strategy only): '+json.dumps(visible,ensure_ascii=False)})
                continue
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
            try:
                actions=self.base.validate_actions(obj,self.runtime,'M',len(actions),len(row['images']))
                for requested in actions:
                    if requested['tool'] in CATALOG:
                        validate_extension_args(requested)
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
                used+=1;obs=self.tools.call(row,actual,'R49-AGENT',used,observations)
                failure=tool_failure_reason(obs)
                if failure:obs=delivered_failure(self.out,row,used,actual,obs)
                observations.append(obs);fresh.append(obs)
                calls[-1].setdefault('executed_calls',[]).append({
                    'action':actual,
                    'tool_ordinal':used,
                    'observation_index':len(observations)-1,
                    'status':obs.get('status'),
                    'failed':bool(failure),
                })
            self.base.append_observations(messages,fresh,self.out,'M')
            repair_pending=False

