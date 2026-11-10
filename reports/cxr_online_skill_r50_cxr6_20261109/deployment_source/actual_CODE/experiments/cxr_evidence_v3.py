"""Question-directed evidence acquisition. No targets, reference answers or memory required."""
import json
import re

SYSTEM = '''You answer chest-image questions using the original pixels and optional tools.
Keep original image numbers, sides and timepoints bound. Read the COMPLETE question and
all options. A finding supporting one clause does not establish every clause of an option.
First give a tentative answer. If one unresolved visual attribute could change it, request
ONE appropriate check of that attribute. Specify the competing interpretations and the
observation that would distinguish them. Tools are optional, never a vote or authority.
Use only registered tool arguments. For a QA tool accepting question or prompt, put the
specific check question in that documented argument; a planning description alone does
not reach the tool. For fixed-output tools, args must stay within their native contract.
Never invent a crop, measurement, view or temporal
comparison capability. A single-image report cannot establish change between timepoints;
classifier scores are not severity. Unknown is distinct from absence or equality.
For laterality/count questions, inspect each relevant side/object; unilateral evidence
cannot support bilateral involvement. For size/severity, use direct visible or valid
measurement evidence, not classifier magnitude. For interval questions, bind each
comparison to the actual supplied originals; never infer time from call order. For
projection/position, distinguish acquisition effects from anatomical disease. These
are question-dependent checks, not a mandatory checklist for every case.
After a check, compare its result with the original and the question. Correct your first
answer when evidence warrants it, even if you initially felt certain. Conversely, a new
unsupported diagnosis, prior example, or repeated opinion is not sufficient evidence to
change. Do NOT automatically preserve the first answer and do NOT require agreement.
If the evidence conflicts, choose a second check ONLY if it can resolve the specific
conflict within the available tools. Otherwise answer as well as the available evidence
allows. Brief evidence statements only; no lengthy reasoning transcript.
No sibling questions, added patient history, or target answers are supplied. Optional
skill cards, when present, are procedural suggestions, not findings in this patient.
Return a JSON object with exactly answer, reason, evidence, check.
answer: an original option letter/full option text, or a short direct answer.
reason: one sentence.
evidence: up to 3 objects {"source":"original:1 or tool:T1","finding":"short observation",
"effect":"supports|contradicts|unknown"}; reference only images/tools actually supplied.
check: null to finish, or {"attribute":"one unresolved property", "alternatives":["one","two"],
"question":"specific observation needed", "tool":"registered name", "args":{}, "image_index":1}.
When finishing, set check=null. Do not use a tool failure as evidence of disease absence.
'''

def unique_object(pairs):
    obj={}
    for k,v in pairs:
        if k in obj: raise ValueError('duplicate_key')
        obj[k]=v
    return obj

def strip_json_fence(raw):
    """One enclosing JSON fence only. No prose extraction, no semantic mapping."""
    if not isinstance(raw,str): return raw
    m=re.fullmatch(r'\s*```(?:json)?\s*\n(.*?)\n```\s*',raw,re.S|re.I)
    if m:
        try: json.loads(m[1],object_pairs_hook=unique_object)
        except (ValueError,TypeError): return raw
        return m[1].strip()
    return raw

def parse_decision(raw,images,events,tools):
    obj=json.loads(strip_json_fence(raw),object_pairs_hook=unique_object)
    if not isinstance(obj,dict) or set(obj)!={'answer','reason','evidence','check'}:raise ValueError('decision_schema')
    if not isinstance(obj['answer'],str) or not 0<len(obj['answer'].strip())<=300:raise ValueError('answer')
    if not isinstance(obj['reason'],str) or not obj['reason'].strip():raise ValueError('reason')
    es=obj['evidence']
    if not isinstance(es,list) or len(es)>3:raise ValueError('evidence')
    allowed={f'original:{i}' for i in range(1,images+1)}|{f'tool:{k}' for k in events}
    for e in es:
        if not isinstance(e,dict) or set(e)!={'source','finding','effect'}:raise ValueError('evidence_schema')
        if not isinstance(e['source'],str) or e['source'] not in allowed:raise ValueError('unseen_evidence_source')
        if e['effect'] not in ('supports','contradicts','unknown') or not isinstance(e['finding'],str) or not e['finding'].strip():raise ValueError('evidence_value')
    c=obj['check']
    if c is not None:
        if not isinstance(c,dict) or set(c)!={'attribute','alternatives','question','tool','args','image_index'}:raise ValueError('check_schema')
        if any(not isinstance(c[k],str) or not c[k].strip() for k in ('attribute','question','tool')):raise ValueError('check_text')
        if not isinstance(c['alternatives'],list) or len(c['alternatives'])!=2 or not all(isinstance(x,str) and x.strip() for x in c['alternatives']):raise ValueError('alternatives')
        if c['tool'] not in tools or not isinstance(c['args'],dict):raise ValueError('tool_or_args')
        if type(c['image_index']) is not int or not 1<=c['image_index']<=images:raise ValueError('image_binding')
    return obj

def episode(base,row,arm,data,protocol,runtime,out,paid,tool_backend,*,conditioning=None):
    """Max four main calls and two checks; no automatic voting or revert gate."""
    messages=[{'role':'system','content':SYSTEM},{'role':'user','content':base.content(row,data)}]
    if conditioning:messages.append({'role':'user','content':conditioning})
    catalog=base.evidence_catalog(runtime,arm)
    messages.append({'role':'user','content':'Available tools and exact argument contracts: '+json.dumps(catalog)})
    observations=[];decisions=[];events=[];used=set();last=None;first=None;format_errors=[]
    limit=protocol['main_call_limits'][arm]
    if limit!=4:raise ValueError('v3_requires_four_main_call_budget')
    for turn in range(1,limit+1):
        remaining=2-len(observations)
        prompt=('Answer from the original first; request one check only if useful.' if turn==1 else
                'Use the newly available evidence to keep or revise the answer. Another check is optional.')
        if turn==limit or remaining==0:prompt+=' No more tools. Set check=null and finish now.'
        else:prompt+=f' Remaining tool checks: {remaining}.'
        if format_errors and format_errors[-1]['turn']==turn-1:
            prompt+=' Your last reply was structurally invalid: '+format_errors[-1]['error']+'. Use the exact decision JSON schema.'
        messages.append({'role':'user','content':prompt})
        raw=paid.call(row,arm,turn,messages);messages.append({'role':'assistant','content':raw})
        try:d=parse_decision(raw,len(row['images']),events,catalog)
        except (ValueError,TypeError,KeyError) as exc:
            format_errors.append({'turn':turn,'error':str(exc)[:120]});continue
        if first is None:first=d['answer']
        last=d;decisions.append({'turn':turn,**d})
        c=d['check']
        if c is None:break
        if turn==limit or remaining==0:
            # A valid explicit answer is available; do not invent a fifth call.
            break
        action={'tool':c['tool'],'args':c['args']}
        if len(row['images'])>1:action['image_index']=c['image_index']
        fingerprint=json.dumps(action,sort_keys=True)
        if fingerprint in used:
            messages.append({'role':'user','content':'That exact check was already performed. Use its evidence, choose a different informative check, or finish.'})
            continue
        actual=base.resolve_action(action,observations)
        # Real infrastructure failure propagates to stop the run, preserving all records.
        result=tool_backend.call(row,actual,arm,len(observations)+1)
        if result.get('status')!='completed' or result.get('observation') is None:
            raise RuntimeError('tool_unhealthy_stop:'+c['tool'])
        used.add(fingerprint);event='T'+str(len(observations)+1);events.append(event)
        result={**result,'evidence_id':event,'requested_check':c}
        observations.append(result)
        # Append ONLY this new observation; never re-add the whole history each turn.
        base.append_observations(messages,[result],out,arm)
    result={'main_calls':turn,'tool_calls':len(observations),'observations':observations,
            'first_answer':first,'decisions':decisions,'format_errors':format_errors}
    if last is None or (format_errors and format_errors[-1]['turn']==turn):
        return dict(result,answer=None,reason=None,status='missing_invalid_final_json')
    revised=last['answer']!=first
    return dict(result,answer=last['answer'],reason=last['reason'],status='completed',
                revised=revised,ended_with_check_requested=last['check'] is not None,
                revision_has_nonunknown_citation=bool(revised and any(e['effect']!='unknown' for e in last['evidence'])))
