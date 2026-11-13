from cxr_online_primitives_r49 import digest,tool_failure_reason
from failure_observation_r54 import delivered_failure
"""EvolveR policy on the live R55 D tool transport."""
import json
from pathlib import Path

from online_memory_r49 import save_once
from skill_services_r54 import validate_runtime
from skill_services_r55 import NEW_TOOLS, Services as SharedServices, Tools, UPSTREAM_COMMIT
from r55_unvalidated_experience import write_experience
from writer_r55live import validate_writer


def register_r55_tools(runtime):
    validate_runtime(runtime)
    for name, (backend, description) in NEW_TOOLS.items():
        runtime['tools'][name] = {'backend': backend, 'description': description,
                                  'revision': 'SkeMex@' + UPSTREAM_COMMIT}
    runtime['arms']['M']['tools'] = [*runtime['arms']['M']['tools'], *NEW_TOOLS]


from r55_full848_e_slake_main_recovery import MainUnavailable, ORDINAL, QID, ROLE, retry_main


class Services(SharedServices):
    def call(self, row, arm, ordinal, messages):
        if (self.out.parent.name == 'slake' and self.out.parent.parent.name == 'E'
                and (row['question_id'], arm, ordinal) == (QID, ROLE, ORDINAL)):
            return retry_main(self, messages)
        return super().call(row, arm, ordinal, messages)

    write_experience = write_experience

    def __init__(self, *args, writer=None, **kwargs):
        super().__init__(*args, **kwargs)
        validate_writer(writer)
        self.writer = writer
        self.experience_snapshot = None

    def retrieve_experience(self, row, query, filename, trigger):
        from experience_r55live import search

        experience = self.experience_snapshot
        active_count = sum(card['status'] == 'active' for card in experience['skills'].values())
        hits = search(experience, self.embed(query), 3) if active_count else []
        visible = [{'id': hit['id'], **hit['c'], 'score': hit['score'],
                    'source_question_ids': experience['skills'][hit['id']]['sources'],
                    'source_scope': 'historical_case_not_current_image'} for hit in hits]
        record = {
            'trigger': trigger,
            'status': 'retrieved' if active_count else 'empty_bank',
            'active_card_count': active_count,
            'query': query,
            'results': visible,
        }
        save_once(self.out/'experience_searches'/row['question_id']/filename, record)
        self.activated.update(hit['id'] for hit in hits)
        return record

    def execute(self,row,policy,data,conditioning):
        # policy retained only as provenance. BOTH new arms use this unbounded executor.
        from run_cxr_action_r41 import parse,answer
        from cxr_task_completion_r43 import prompt
        if self.tools is None:self.tools=Tools(self.runtime,Path(data),self.out,self.call,self.verifier)
        system=self.base.agent_system('M').replace('You may select zero, one or two registered tools, with early stopping when appropriate.',
            'Select useful registered tools as needed; there is no fixed total call-count limit. Stop when sufficient evidence supports an answer.')
        system += (' Retrieved experience may quote an earlier question and its released answer. '
                   'Use source_question_ids to distinguish those examples from the current case. '
                   'Do not use any historical answer as evidence about the current image.')
        self.activated=set()
        self.candidates=[]
        snapshot=self.experience_snapshot
        can_search=any(card['status']=='active' for card in snapshot['skills'].values())
        if conditioning or can_search:system=system.replace('No cross-case skills, sibling question context or additional patient history is available.',
            'Optional learned procedural skills and previously completed same-image questions with post-prediction dataset feedback may be supplied. Skills are not current-patient facts. No current or future reference answer is supplied.')
        messages=[{'role':'system','content':system},{'role':'user','content':self.base.content(row,Path(data))}]
        if conditioning:messages.append({'role':'user','content':conditioning})
        experience=snapshot
        pre_answer = None
        if experience is not None:
            query = row['question']
            if row.get('options'):
                query += '\nCandidate findings or answers: ' + '\n'.join(row['options'].values())
            pre_answer = self.retrieve_experience(row, query, 'pre_answer.json', 'required_pre_answer')
            if pre_answer['results']:
                messages.append({'role':'user','content':(
                    'Retrieved procedural experience. Apply a principle only when its trigger '
                    'matches this question and current observations. Check original image evidence '
                    'and ignore irrelevant principles.\n'+json.dumps(pre_answer['results'],ensure_ascii=False)
                )})
        observations=[];calls=[];seen={};n=0;used=0;invalid=0;next_prompt=None
        action=self.base.ACTION.replace('At most two selectable tool calls total.','No fixed total tool-call count limit.')
        if len(row['images'])>1:action=action.replace('"args":{}','"args":{},"image_index":1').replace('Each call applies only to the bound original.','Select numbered original via image_index.')
        followup_searched=False
        if can_search:
            action += (' You may instead return {"search_experience":"short procedural query"} '
                       'for one follow-up search, up to 3 past principles. Ask about a strategy, not a patient or answer. '
                       'Retrieved principles are not image evidence. ')
        while True:
            n+=1
            active,activation=self.activate(row,observations,n)
            if self.candidates:
                messages.append({'role':'user','content':'R54 activation for THIS decision only. Earlier activation directives expire; only this list is currently active (empty means none): '+json.dumps(active,ensure_ascii=False)})
            messages.append({'role':'user','content':next_prompt or action+json.dumps(self.base.evidence_catalog(self.runtime,'M'))})
            try:
                raw = self.call(row, 'R49-AGENT', n, messages)
            except MainUnavailable:
                calls.append({'step_index': n-1, 'response': None, 'skill_activation': activation,
                              'main_response_status': 'unavailable_after_two_attempts'})
                return ({'activated_skill_ids': sorted(self.activated), 'answer': None, 'reason': None,
                         'status': 'main_response_unavailable_after_retry', 'main_calls': n,
                         'tool_calls': used, 'observations': observations, 'terminal_raw': None}, calls)
            calls.append({'step_index':n-1,'response':raw,'skill_activation':activation})
            if n == 1:
                calls[-1]['pre_answer_experience_search'] = pre_answer
            messages.append({'role':'assistant','content':raw});next_prompt=None
            try:obj=parse(raw)
            except (ValueError,IndexError):obj={}
            if (
                can_search and not followup_searched
                and isinstance(obj,dict) and set(obj)=={'search_experience'} and isinstance(obj['search_experience'],str)
                and 0<len(obj['search_experience'].strip())<=500
            ):
                followup_searched = True
                record = self.retrieve_experience(row, obj['search_experience'].strip(), str(n)+'.json', 'model_followup')
                calls[-1]['experience_search']=record
                messages.append({'role':'user','content':'Experience principles (strategy only): '+json.dumps(record['results'],ensure_ascii=False)})
                continue
            result=answer(obj)
            if result:
                from cxr_task_completion_r43 import unscorable
                if not unscorable(row,result):
                    result.update(activated_skill_ids=sorted(self.activated),main_calls=n,tool_calls=used,observations=observations,terminal_raw=raw)
                    return result,calls
            actions=obj.get('calls')
            if not isinstance(actions,list) or not actions:
                invalid+=1
                if invalid>=3:return {'activated_skill_ids':sorted(self.activated),'answer':None,'reason':None,'status':'repeated_invalid_output','main_calls':n,'tool_calls':used,'observations':observations,'terminal_raw':raw},calls
                next_prompt=prompt(row);continue
            try:actions=self.base.validate_actions(obj,self.runtime,'M',len(actions),len(row['images']))
            except (ValueError,TypeError,KeyError):
                invalid+=1
                if invalid>=3:return {'activated_skill_ids':sorted(self.activated),'answer':None,'reason':None,'status':'repeated_invalid_plan','main_calls':n,'tool_calls':used,'observations':observations,'terminal_raw':raw},calls
                next_prompt='Use only registered tool names and valid arguments, or give final answer/reason JSON.';continue
            fresh=[]
            for action_item in actions:
                actual=self.base.resolve_action(action_item,observations);signature=digest(actual);seen[signature]=seen.get(signature,0)+1
                if seen[signature]>=3:
                    return {'activated_skill_ids':sorted(self.activated),'answer':None,'reason':None,'status':'repeated_identical_action_no_progress','main_calls':n,'tool_calls':used,'observations':observations,'terminal_raw':raw},calls
                used+=1;obs=self.tools.call(row,actual,'R49-AGENT',used)
                failure=tool_failure_reason(obs)
                if failure:obs=delivered_failure(self.out,row,used,actual,obs)
                observations.append(obs);fresh.append(obs)
                calls[-1].setdefault('executed_calls',[]).append({
                    'action':actual,'tool_ordinal':used,'observation_index':len(observations)-1,
                    'status':obs.get('status'),'failed':bool(failure)})
            self.base.append_observations(messages,fresh,self.out,'M')

