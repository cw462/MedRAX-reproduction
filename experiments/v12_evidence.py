"""V12 figure-bound observations, full-option matching and explicit evidence limits.

This module has no model, label or ledger access. It parses only the outer response
object and never recovers a choice by treating an inner observation as metadata.
All image pixels are the supplied original or already-created crop bytes.
"""
from __future__ import annotations

import base64
import copy
import json
import math
import mimetypes
from pathlib import Path
import re


FIRST_READ_PROMPT = '''Inspect the actual full original images FIRST, then identify
the visible attributes that distinguish ALL complete answer options. Keep every
provided Figure number and distinguish image order from an explicitly stated time
order. A comparison must concern the same anatomical object at the stated views or
times. Infer image modality from the actual pixels; do not call every medical image
a chest radiograph. Do not invent patient conditions, orientation, scale or time.
Separate referenced visual observations from candidate diseases/mechanisms that
remain hypotheses. Unknown is not absent, normal, stable or unchanged.
Copy supplied patient conditions from the QUESTION STEM, not the answer options.
Every patient condition and non-unknown timepoint must have an exact stem quotation;
use the original wording for its value. Include all relevant option discriminators,
not only the first two. No external tool or knowledge is supplied in this first read.
Give a best legal first_answer separately for later scoring. It will NOT be shown
to the action planner or final solver. Do not mention that selection elsewhere.
Return one concise outer JSON object with all these fields:
{"first_answer":"one legal letter","observations":[{"attribute":"...",
"value":"visible feature or explicit uncertainty","status":"observed_present|observed_absent|unresolved|hypothesis",
"evidence_refs":["image:1"]}],
"hypotheses":[{"name":"possible disease or mechanism","basis":"why it is worth verifying, not an established fact",
"evidence_refs":["image:1"]}],
"patient_conditions":[{"name":"age/sex/presentation/history/other supplied condition",
"value":"exact words from stem","source_quote":"exact supporting stem quotation"}],
"discriminators":[{"attribute":"side/location/size/morphology/count/relationship/time/other",
"question":"what visible attribute separates complete options?",
"option_labels":["A","B"],"image_ids":["image:1"],"comparison_object":"specific anatomical object if comparing"}],
"image_metadata":[{"image_id":"image:1","modality":"CXR|CT|MRI|US|Xray|unknown",
"anatomy":"visible region","timepoint":"exact stem wording or unknown",
"timepoint_source_quote":"exact supporting stem quotation or empty","comparison_object":"object or unknown"}],
"uncertainties":["unprovided or unresolved information"]}.
Keep observable evidence concise; do not output hidden chain-of-thought.'''

ACTION_PLAN_PROMPT = '''Choose at most TWO concrete observation actions that can
distinguish the complete options. You receive the original images, question, all
options and a shared first visual report; its selected answer is withheld. The
report is fallible. Separate observed features, hypotheses and unknowns. For B,
supplied knowledge/experience can guide an action but cannot establish a current
patient fact. A has the same model and action/call budget without these assets.
Use the actual image modality and advertised capability. Never use a chest-X-ray
specialist on CT, MRI or an image whose chest-radiograph modality is unconfirmed.
Prefer an action that resolves a specific ambiguity. Do not choose a tool just
because its name sorts first. Step benefit is unknown unless a training record
explicitly supplies it; whole-question success is not step credit.
For comparison, identify the SAME anatomical object in the listed images and use
only question-specified times. Prefer a kind=visual paired full-image read without
an external tool for laterality, time change and spatial relationships when these
pixels already suffice. A free action slot is not a reason to call another tool.
Grounding boxes locate candidate regions only; classifier scores are hypotheses
and cannot prove existence, physical size or interval change.
For a crop, retain the parent original and select
a region with both dimensions greater than 10 pixels. Do not invent scale.
A bare disease label, a single Yes/No, Not matched, or an execution error cannot
be expanded into an observed patient finding. You may select no extra action
if nothing useful is available; final solving still chooses a best legal option.
Return one outer JSON object:
{"actions":[{"kind":"crop|visual|tool","image_id":"image:1",
"image_ids":["image:1"],"target_region":"region in this image",
"tool":"advertised tool name for kind=tool, otherwise empty",
"tool_args":{},
"question":"standalone specific visual question; do not presume the desired finding",
"expected_attribute":"attribute which will distinguish alternatives",
"comparison_object":"same anatomical object if multiple images, otherwise empty",
"box":[0.1,0.1,0.6,0.6]}],
"remaining_uncertainties":["unresolved items"],"applied_context_ids":["only supplied IDs actually used"]}.
box is required only for crop and uses normalized stored pixel coordinates.
For tool_args use only the selected tool's advertised argument names; execution
will bind its image input to the selected current image, not an invented filename.
Do not select an answer or emit hidden chain-of-thought.'''

FINAL_PROMPT = '''Solve the question afresh by matching ALL complete answer options
to the supplied original pixels, full question, explicit patient conditions and
new observations. No first-answer choice or earlier candidate choice is supplied;
you may select ANY legal option. Do not reconstruct or favor an earlier choice.
Evaluate each relevant component of a multi-attribute option: side, site, size,
shape, count, object relationships and question-specified chronology. An isolated
matching component does not establish the entire option. Missing evidence is
not observed absence, normality, equality, stability or no interval change.
Keep Figure labels and same-object correspondences. A crop must be interpreted
with its parent original. Do not invent centimeter measurements without scale.
Shared and follow-up reader reports are fallible. Tool diagnostic labels and
conditional localization boxes are hypotheses, not existence proofs. Single-word
No/Yes, Not matched and execution errors supply no clinical fact. Never expand
them or imported knowledge into unobserved patient findings. Use pixels to verify.
Classification scores cannot establish presence, physical size or change.
Always choose the best LEGAL option despite uncertainty; record gaps separately.
Return one concise outer JSON object:
{"answer":"one legal option letter","uncertain":true,
"observations":[{"attribute":"...","value":"brief observable support or conflict",
"status":"observed_present|observed_absent|unresolved|hypothesis",
"evidence_refs":["exact supplied image or observation ID"]}],
"option_checks":[{"option":"legal option letter","support":["brief supported components"],
"conflict":["brief conflicting components"],"unknown":["unsupported components"]}],
"missing_evidence":["remaining gaps"]}.
Do not output hidden chain-of-thought or a long rationale.'''

TARGETED_READ_PROMPT = '''Independently inspect the current original images and any
paired local crops to answer the supplied targeted observation questions. No first
answer or earlier selected option is provided. Do not infer an earlier choice or
repeat a presumed finding in the action question as fact. For comparison,
look at the same anatomical object and respect the provided Figure/time mapping.
Keep each crop bound to its parent full image. A crop adds no new source pixels.
Prefer direct same-object paired reading for side, time and spatial relationships.
No current-patient information may be inferred from historical knowledge or a tool
name. Grounding only proposes a region. Classifier scores are hypotheses and cannot
prove presence, size or change. A diagnostic label, conditionally grounded box, single No/Yes, Not matched
or execution error is not an observed finding. Even a detailed tool report remains
a hypothesis until verified in pixels. Omission does not establish absence.
Report supported positive/negative observations, candidate hypotheses and unresolved
attributes separately. Unknown is not normal, stable, absent or equal. Do not infer
centimeters without calibration or time order from the order of image files.
After reporting observations, match ALL supplied complete options to give a best
legal post-observation candidate_answer even when some attributes stay unknown.
Put this choice only in candidate_answer, never in the observation or hypothesis
text. A separate final solver will not see this candidate choice.
Return one concise outer JSON object:
{"candidate_answer":"one legal option letter",
"observations":[{"attribute":"requested visual attribute","value":"specific visible finding or unresolved point",
"status":"observed_present|observed_absent|unresolved|hypothesis",
"evidence_refs":["exact supplied image or crop IDs"]}],
"hypotheses":[{"name":"unverified disease/mechanism, if useful",
"basis":"conditional interpretation, not a patient fact","evidence_refs":["image:1"]}],
"uncertainties":["remaining gaps relevant to the targeted questions"]}.
Never return a first_answer or other answer/choice field. Do not output hidden chain-of-thought.'''

STATES = {'observed_present', 'observed_absent', 'unresolved', 'hypothesis'}
_SELECTION_CLAIM = re.compile(
    r'(?i)\b(?:my|initial|first|selected|chosen|final|best|correct|preferred)\s+(?:answer|choice|option)\b|'
    r'\b(?:I\s+(?:choose|select)|(?:answer|choice)\s*(?:is|=|:)\s*[A-Z]|option\s+[A-Z]\s+is\s+(?:correct|best))\b')


def question_parts(question):
    """Preserve the complete stem and every complete option without truncation."""
    stem, options, current = [], {}, None
    for line in str(question).splitlines():
        match = re.match(r'^\s*([A-Z])[).]\s*(.*)$', line)
        if match:
            current = match[1]
            if current in options:
                raise ValueError('duplicate_option_label')
            options[current] = match[2].strip()
        elif current and line.strip():
            options[current] += '\n' + line.strip()
        elif current is None:
            stem.append(line)
    if len(options) < 2 or any(not v for v in options.values()):
        raise ValueError('options_parse_failed')
    return '\n'.join(stem).strip(), options


def _outer_object(text, required):
    """Read only the first outer object; malformed outer JSON never scans inward."""
    if not isinstance(text, str) or not text.strip():
        raise ValueError('empty_json_response')
    raw = text.strip()
    if raw.startswith('```'):
        raw = re.sub(r'^```(?:json)?\s*\n?', '', raw, count=1, flags=re.I)
        if not raw.rstrip().endswith('```'):
            raise ValueError('unclosed_json_fence')
        raw = raw.rstrip()[:-3].strip()
    start = raw.find('{')
    if start < 0:
        raise ValueError('outer_json_missing')
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('duplicate_json_key:' + key)
            result[key] = value
        return result
    def constant(value):
        raise ValueError('nonfinite_json_value:' + value)
    try:
        value, end = json.JSONDecoder(strict=False, object_pairs_hook=pairs,
                                     parse_constant=constant).raw_decode(raw[start:])
    except (json.JSONDecodeError, ValueError) as exc:
        raise ValueError('invalid_outer_json') from exc
    if raw[start+end:].strip():
        raise ValueError('trailing_json_response_content')
    if not isinstance(value, dict) or not required <= set(value):
        raise ValueError('missing_outer_fields:' + ','.join(sorted(required - set(value) if isinstance(value,dict) else required)))
    return value


def _strings(value):
    if isinstance(value, str):
        return [value] if value.strip() else []
    if not isinstance(value, list):
        return []
    return [v for v in value if isinstance(v, str) and v.strip()]


def _text(value, default=''):
    return value.strip() if isinstance(value, str) else default


def _quote_supported(quote, stem):
    normalize = lambda v: re.sub(r'\s+', ' ', v).strip().casefold()
    return bool(_text(quote)) and normalize(quote) in normalize(stem)


def _refs(value, known, warnings, field):
    proposed = _strings(value)
    result = list(dict.fromkeys(v for v in proposed if v in known))
    if result != proposed:
        warnings.append(field + ':unknown_or_duplicate_refs_removed')
    return result


def normalize_modality(value):
    compact = re.sub(r'[^a-z0-9]+', '', str(value).lower())
    if compact in {'cxr','chestxray','chestxrayimage','chestradiograph','chestradiography'}:
        return 'CXR'
    if compact in {'ct','computedtomography','chestct','thoracicct'}:
        return 'CT'
    if compact in {'mri','mr','magneticresonance','magneticresonanceimaging'}:
        return 'MRI'
    if compact in {'us','ultrasound','sonography'}:
        return 'US'
    if compact in {'xray','radiograph','radiography'}:
        return 'Xray'
    return 'unknown'


def build_images(row, image_root):
    from PIL import Image
    root = Path(image_root).resolve()
    if not isinstance(row.get('images'), list) or not row['images']:
        raise ValueError('original_images_required')
    result = []
    for index, relative in enumerate(row['images'], 1):
        if not isinstance(relative, str):
            raise ValueError('invalid_image_path')
        path = (root/relative).resolve(strict=True)
        if not path.is_relative_to(root) or not path.is_file():
            raise ValueError('image_outside_current_root')
        with Image.open(path) as image:
            size = list(image.size)
        if min(size) <= 10:
            raise ValueError('image_below_model_minimum')
        match = re.search(r'(?i)(?:figure|fig)[_\- ]*([0-9]+[a-z]?)', path.stem)
        figure = 'Figure ' + match[1] if match else path.name
        result.append({'image_id':f'image:{index}', 'path':str(path),
                       'source_filename':relative.replace('\\','/'), 'figure_label':figure,
                       'role':'original', 'size':size, 'modality':'unknown',
                       'timepoint':'unknown', 'timepoint_source_quote':'',
                       'comparison_object':'unknown'})
    return result


def multimodal_content(payload, originals, extras=()):
    """Attach real pixels and bind each crop to its supplied parent original."""
    from PIL import Image
    originals, extras = list(originals), list(extras)
    if not originals:
        raise ValueError('full_original_context_required')
    ids = [i['image_id'] for i in originals + extras]
    if len(set(ids)) != len(ids):
        raise ValueError('duplicate_image_id')
    original_ids = {i['image_id'] for i in originals}
    for item in extras:
        if item.get('parent_image_id') not in original_ids:
            raise ValueError('crop_parent_original_missing')
    text = payload if isinstance(payload, str) else json.dumps(payload,ensure_ascii=False)
    content = [{'type':'text','text':text}]
    for item in originals + extras:
        path = Path(item['path']).resolve(strict=True)
        with Image.open(path) as image:
            if min(image.size) <= 10:
                raise ValueError('image_below_model_minimum')
            fmt = image.format
        mime = {'PNG':'image/png','JPEG':'image/jpeg','WEBP':'image/webp'}.get(fmt)
        if not mime:
            raise ValueError('unsupported_image_payload_type')
        metadata = {key:copy.deepcopy(item[key]) for key in (
            'image_id','path','source_filename','figure_label','role','size','modality',
            'timepoint','timepoint_source_quote','comparison_object','parent_image_id',
            'parent_path','pixel_box','normalized_box','crop_size','source_size') if key in item}
        content += [{'type':'text','text':'BOUND CURRENT IMAGE: '+json.dumps(metadata,ensure_ascii=False)},
                    {'type':'image_url','image_url':{'url':'data:'+mime+';base64,'+
                        base64.b64encode(path.read_bytes()).decode('ascii'),'detail':'auto'}}]
    return content


def _observations(value, known, warnings):
    if not isinstance(value, list):
        raise ValueError('observations_must_be_list')
    result = []
    for item in value:
        if not isinstance(item, dict) or not _text(item.get('value')):
            warnings.append('invalid_observation_removed'); continue
        refs = _refs(item.get('evidence_refs', []), known, warnings, 'observation')
        status = item.get('status','hypothesis')
        if status not in STATES:
            status='hypothesis'; warnings.append('invalid_observation_status_as_hypothesis')
        if status.startswith('observed_') and not refs:
            status='hypothesis'; warnings.append('unreferenced_observation_as_hypothesis')
        result.append({'attribute':_text(item.get('attribute')), 'value':item['value'],
                       'status':status,'evidence_refs':refs})
    return result


def parse_first_read(text, row, images):
    required={'first_answer','observations','hypotheses','patient_conditions',
              'discriminators','image_metadata','uncertainties'}
    obj=_outer_object(text,required)
    stem,options=question_parts(row['question'])
    answer=_text(obj['first_answer']).upper()
    if answer not in options:
        raise ValueError('first_answer_not_legal_option')
    for field in required-{'first_answer'}:
        if not isinstance(obj[field],list):
            raise ValueError(field+'_must_be_list')
    known={i['image_id'] for i in images};warnings=[]
    observations=_observations(obj['observations'],known,warnings)
    hypotheses=[]
    for item in obj['hypotheses']:
        if isinstance(item,str):item={'name':item}
        if not isinstance(item,dict) or not _text(item.get('name')):
            warnings.append('invalid_hypothesis_removed');continue
        hypotheses.append({'name':item['name'],'basis':_text(item.get('basis')),
                           'status':'hypothesis','evidence_refs':_refs(item.get('evidence_refs',[]),known,warnings,'hypothesis')})
    conditions=[]
    for item in obj['patient_conditions']:
        if not isinstance(item,dict):warnings.append('invalid_patient_condition_removed');continue
        quote=_text(item.get('source_quote'));value=_text(item.get('value'))
        if not _quote_supported(quote,stem) or not value or not _quote_supported(value,quote):
            warnings.append('patient_condition_without_literal_stem_support_removed');continue
        conditions.append({'name':_text(item.get('name')),'value':value,'source_quote':quote,
                           'source':'question_stem_explicit_text'})
    discriminators=[]
    for item in obj['discriminators']:
        if not isinstance(item,dict) or not _text(item.get('question')):
            warnings.append('invalid_discriminator_removed');continue
        discriminators.append({'attribute':_text(item.get('attribute')),'question':item['question'],
            'option_labels':_refs(item.get('option_labels',[]),set(options),warnings,'discriminator_options'),
            'image_ids':_refs(item.get('image_ids',[]),known,warnings,'discriminator_images'),
            'comparison_object':_text(item.get('comparison_object'))})
    raw_meta={}
    for item in obj['image_metadata']:
        if not isinstance(item,dict) or item.get('image_id') not in known:
            warnings.append('unknown_image_metadata_removed');continue
        if item['image_id'] in raw_meta:
            raise ValueError('duplicate_image_metadata')
        raw_meta[item['image_id']]=item
    metadata=[]
    for image in images:
        item=raw_meta.get(image['image_id'],{})
        if not item:warnings.append('missing_image_metadata_left_unknown:'+image['image_id'])
        timepoint=_text(item.get('timepoint'),'unknown') or 'unknown'
        quote=_text(item.get('timepoint_source_quote'))
        if timepoint.casefold() not in {'unknown','unresolved','not provided'}:
            if not _quote_supported(quote,stem) or not _quote_supported(timepoint,quote):
                warnings.append('unsupported_timepoint_left_unknown:'+image['image_id'])
                timepoint,quote='unknown',''
        else:timepoint,quote='unknown',''
        metadata.append({'image_id':image['image_id'],'figure_label':image['figure_label'],
            'source_filename':image['source_filename'],'modality':normalize_modality(item.get('modality')),
            'anatomy':_text(item.get('anatomy'),'unknown') or 'unknown',
            'timepoint':timepoint,'timepoint_source_quote':quote,
            'comparison_object':_text(item.get('comparison_object'),'unknown') or 'unknown',
            'modality_source':'first_visual_reader_report_not_clinically_adjudicated'})
    return {'first_answer':answer,'observations':observations,'hypotheses':hypotheses,
            'patient_conditions':conditions,'discriminators':discriminators,
            'image_metadata':metadata,'uncertainties':_strings(obj['uncertainties']),
            'parse_warnings':sorted(set(warnings))}


def observation_projection(first):
    """Allowlist evidence only; selected-answer fields and claims cannot pass."""
    result={key:copy.deepcopy(first.get(key,[])) for key in (
        'observations','hypotheses','patient_conditions','discriminators','image_metadata','uncertainties')}
    warnings=[]
    for key in ['observations','hypotheses','discriminators']:
        retained=[]
        for item in result[key]:
            if _SELECTION_CLAIM.search(json.dumps(item,ensure_ascii=False)):
                warnings.append('selection_statement_removed_from_'+key)
            else:retained.append(item)
        result[key]=retained
    result['uncertainties']=[s for s in result['uncertainties'] if not _SELECTION_CLAIM.search(str(s))]
    # This states only the interface, never which option was selected.
    result['selected_answer_withheld']=True
    result['projection_warnings']=sorted(set(warnings))
    return result


def parse_final(text,row,known_refs):
    obj=_outer_object(text,{'answer','uncertain','observations','option_checks','missing_evidence'})
    _,options=question_parts(row['question'])
    answer=_text(obj['answer']).upper()
    if answer not in options:raise ValueError('final_answer_not_legal_option')
    if type(obj['uncertain']) is not bool:raise ValueError('uncertain_must_be_boolean')
    if not isinstance(obj['option_checks'],list) or not isinstance(obj['missing_evidence'],list):
        raise ValueError('final_check_fields_must_be_lists')
    warnings=[];checks=[];seen=set()
    for item in obj['option_checks']:
        if not isinstance(item,dict) or _text(item.get('option')).upper() not in options:
            warnings.append('unknown_option_check_removed');continue
        label=item['option'].strip().upper()
        if label in seen:raise ValueError('duplicate_option_check')
        seen.add(label)
        checks.append({'option':label,'support':_strings(item.get('support')),
                       'conflict':_strings(item.get('conflict')),'unknown':_strings(item.get('unknown'))})
    missing_checks=[label for label in options if label not in seen]
    if missing_checks:warnings.append('incomplete_full_option_checks')
    return {'answer':answer,'uncertain':obj['uncertain'],
            'observations':_observations(obj['observations'],set(known_refs),warnings),
            'option_checks':checks,'missing_option_checks':missing_checks,
            'missing_evidence':_strings(obj['missing_evidence']),
            'parse_warnings':sorted(set(warnings))}


def parse_targeted_read(text,row,images):
    """Keep a separate post-observation candidate; bad choice cannot erase observations."""
    obj=_outer_object(text,{'observations','hypotheses','uncertainties'})
    if set(obj)&{'answer','first_answer','choice','selected_option','final_answer'}:
        raise ValueError('targeted_read_contains_answer_selection')
    if not isinstance(obj['hypotheses'],list) or not isinstance(obj['uncertainties'],list):
        raise ValueError('targeted_read_fields_must_be_lists')
    known={i['image_id'] for i in images};warnings=[]
    _,legal_options=question_parts(row['question'])
    candidate=_text(obj.get('candidate_answer')).upper()
    if candidate not in legal_options:
        candidate=None
        warnings.append('targeted_candidate_missing_or_invalid')
    observations=_observations(obj['observations'],known,warnings)
    hypotheses=[]
    for item in obj['hypotheses']:
        if isinstance(item,str):item={'name':item}
        if not isinstance(item,dict) or not _text(item.get('name')):
            warnings.append('invalid_hypothesis_removed');continue
        hypotheses.append({'name':item['name'],'basis':_text(item.get('basis')),
            'status':'hypothesis','evidence_refs':_refs(item.get('evidence_refs',[]),known,warnings,'hypothesis')})
    for field,items in [('observations',observations),('hypotheses',hypotheses)]:
        if any(_SELECTION_CLAIM.search(json.dumps(item,ensure_ascii=False)) for item in items):
            raise ValueError('targeted_read_contains_answer_selection_statement')
    return {'candidate_answer':candidate,'observations':observations,'hypotheses':hypotheses,
            'uncertainties':_strings(obj['uncertainties']),
            'parse_warnings':sorted(set(warnings)),
            'kind':'targeted_image_read_requires_independent_verification'}


def parse_action_plan(text,images,tool_names):
    obj=_outer_object(text,{'actions'})
    if not isinstance(obj['actions'],list):raise ValueError('actions_must_be_list')
    if len(obj['actions'])>2:raise ValueError('action_budget_exceeded')
    known={i['image_id'] for i in images};tools=set(tool_names);actions=[];warnings=[]
    for item in obj['actions']:
        if not isinstance(item,dict):warnings.append('invalid_action_removed');continue
        kind=item.get('kind');main=item.get('image_id')
        if kind not in {'crop','visual','tool'} or main not in known:
            warnings.append('invalid_action_kind_or_image_removed');continue
        ids=_refs(item.get('image_ids',[main]),known,warnings,'action_images')
        ids=list(dict.fromkeys([main]+ids))
        if not _text(item.get('question')) or not _text(item.get('expected_attribute')):
            warnings.append('nonspecific_action_removed');continue
        comparison=_text(item.get('comparison_object'))
        if len(ids)>1 and not comparison:
            warnings.append('multi_image_action_without_same_object_removed');continue
        tool=_text(item.get('tool')) if kind=='tool' else ''
        if kind=='tool' and tool not in tools:
            warnings.append('unavailable_tool_action_removed');continue
        action={'kind':kind,'image_id':main,'image_ids':ids,'target_region':_text(item.get('target_region')),
                'tool':tool,'question':item['question'],'expected_attribute':item['expected_attribute'],
                'comparison_object':comparison}
        # The execution layer still binds image paths and validates the real tool
        # schema. This dictionary is data, not permission to use arbitrary paths.
        args=item.get('tool_args',{})
        if not isinstance(args,dict):
            args={};warnings.append('invalid_tool_args_replaced_with_empty')
        action['tool_args']=copy.deepcopy(args)
        if kind=='crop':
            box=item.get('box')
            if (not isinstance(box,list) or len(box)!=4 or any(type(x) not in (int,float) or not math.isfinite(x) for x in box)
                or not 0<=box[0]<box[2]<=1 or not 0<=box[1]<box[3]<=1):
                warnings.append('invalid_crop_box_removed');continue
            action['box']=box
        actions.append(action)
    return {'actions':actions,'remaining_uncertainties':_strings(obj.get('remaining_uncertainties')),
            'applied_context_ids':_strings(obj.get('applied_context_ids')),
            'parse_warnings':sorted(set(warnings)),'issues':sorted(set(warnings))}


def classify_tool_return(value):
    """Classify usability without converting a return into clinical ground truth."""
    strings=[];errors=[];has_box=False;has_scores=False
    metadata_keys={'tool','tool_name','name','model','model_name','device','image_path','path',
        'status','analysis_status','clinical_evidence','step_credit','execution','version','timestamp'}
    def visit(v,key=''):
        nonlocal has_box,has_scores
        if isinstance(v,dict):
            for k,x in v.items():
                low=str(k).lower()
                if low in {'error','exception','error_type','api_error','traceback'} and x not in (None,'',False,[],{}):
                    errors.append(low)
                if low in {'status','analysis_status','execution'} and str(x).lower() in {'error','failed','exception','timed_out','returned_invalid','rejected'}:
                    errors.append('failure_status')
                if re.search(r'box|bbox|coordinate',low) and isinstance(x,(list,tuple)) and x:has_box=True
                if low in {'score','scores','probability','probabilities','class_scores','classification_scores','predictions'} and isinstance(x,(int,float,list,tuple,dict)) and x:
                    has_scores=True
                if low not in metadata_keys:visit(x,low)
        elif isinstance(v,(list,tuple)):
            for x in v:visit(x,key)
        elif isinstance(v,str) and v.strip():strings.append(v.strip())
    visit(value)
    joined='\n'.join(strings)
    if errors or re.search(r'(?i)CUDA out of memory|Traceback \(most recent call last\)|TOOL_CALL_REJECTED|\b(?:RuntimeError|MairaWorkerError|APITimeoutError)\b',joined):
        return {'evidence_kind':'execution_error','usable':False,'reason':'recorded_execution_failure_not_patient_evidence'}
    if has_box:
        return {'evidence_kind':'hypothesis','usable':True,'reason':'conditional_localization_requires_pixel_verification_not_presence_proof'}
    if has_scores:
        return {'evidence_kind':'hypothesis','usable':True,'reason':'class_scores_cannot_establish_presence_size_or_change'}
    meaningful=[s for s in strings if s.casefold() not in {'unknown','none','null','n/a','not available','completed','hypothesis'}]
    if not meaningful or all(re.fullmatch(r'(?i)\s*(?:yes|no|not matched|unknown|n/?a|none)\s*[.!]?\s*',s) for s in meaningful):
        return {'evidence_kind':'uninformative','usable':False,'reason':'bare_response_or_no_content_not_patient_evidence'}
    # A short isolated disease name is not a localized, attributed observation.
    diagnosis=re.compile(r'(?i)^(?:pneumothorax|pneumonia|pleural effusion|cardiomegaly|atelectasis|'
                         r'emphysema|tuberculosis|pulmonary edema|lung cancer|sarcoidosis|pneumomediastinum|'
                         r'hydropneumothorax|hemothorax|pulmonary embolism|normal|no finding)[.!]?$')
    if len(meaningful)==1 and (diagnosis.fullmatch(meaningful[0]) or
        (re.fullmatch(r'[A-Za-z][A-Za-z -]{0,70}[.!]?',meaningful[0]) and len(meaningful[0].split())<=2)):
        return {'evidence_kind':'uninformative','usable':False,'reason':'isolated_label_not_a_patient_observation'}
    return {'evidence_kind':'hypothesis','usable':True,'reason':'tool_report_requires_independent_pixel_verification'}
