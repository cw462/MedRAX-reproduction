"""R1 blind option-discriminating observation and pixel/laterality binding.

No reference labels, D0 answers or D0 reasons are accepted by model payloads.
Orientation markers remain model-reported; geometry checks do not verify that
the marker itself was read correctly. Unresolved laterality never selects a
single anatomical side by convention alone.
"""
from __future__ import annotations
import json
import math
import re

TOOLS = {
    'chest_xray_classifier': 'CXR only; broad class-score hypotheses, not lesion existence, side, size, interval change or rib count.',
    'chest_xray_report_generator': 'CXR only; broad report hypotheses, omissions do not prove absence; not a precise counter.',
    'chest_xray_segmentation': 'CXR only; anatomical masks aid region identification, not pathology truth or calibrated size.',
    'chest_xray_expert': 'CXR only; one open-ended focused visual question; output still requires pixel verification.',
    'llava_med_qa': 'General medical-image focused VQA, including CT; unverified model observation, no guaranteed modality-specific accuracy.',
    'xray_phrase_grounding': 'CXR only; region localization conditional on a neutral anatomical phrase, not proof the proposed finding exists.'}

PLAN_PROMPT = '''Plan ONE independent observation that distinguishes the COMPLETE answer
options. You have no previous answer, reason, clinical model observation or label.
Inspect the original pixels only to select an observation target, image modality,
view and orientation; do not answer the MCQ or assert an expected finding.
Choose visual (paired original images), crop, or ONE suitable listed medical tool.
Tools are optional. Prefer paired originals for side, chronology and spatial
relationships. Derive a neutral open question from option differences, e.g.
"Describe the side and intercostal space of the mass" or "Which named sign is
visible?" Never turn a selected option into "confirm that ...". Do not provide
an expected answer/value, confidence, diagnosis or preferred option.
Only use chronology explicitly stated in the question. An R/L marker must be
visibly present in the CURRENT pixels; record its text and normalized bounding
box. Anatomical patient right is not display right. No unverified PA/CT convention
or lateral/montage view can authorize a unilateral crop. No flips or rotations.
For crop, box=[display-left,top,display-right,bottom], normalized 0..1. The whole
unilateral box must lie on the display half corresponding to the target patient
side, anchored by an R/L marker on a single frontal/axial image. If orientation
is unknown, choose full images or a bilateral/midline/non-sided detail instead.
Return a single JSON object, no answer:
{"attribute":"side|intercostal_space|sign|location|shape|size|count|change|relationship|pattern|other",
 "target_region":"neutral anatomy, no expected finding/value",
 "neutral_question":"open-ended question about the option-discriminating attribute",
 "kind":"visual|crop|tool", "image_ids":["image:1"],
 "target_patient_side":"right|left|bilateral|midline|not_applicable|unknown",
 "box":null, "tool":"", "tool_args":{},
 "image_metadata":[{"image_id":"image:1","modality":"CXR|CT|MRI|US|unknown",
 "view":"frontal|axial|lateral|montage|unknown",
 "marker":{"text":"R|L|unknown","box":null}}]}.
Unknown attributes remain unknown. An uncertain observation is not a reason to
reject the later answer or to copy any earlier answer.'''

OBSERVE_PROMPT = '''Independently inspect all supplied ORIGINAL images, any paired
pixel crop, and the ONE neutral requested attribute. No initial answer or reason
is supplied. Inspect the attribute before selecting the best complete option.
Check patient side versus display coordinates, image/figure identity, the same
object and only explicitly stated chronology. Verify any reported R/L marker
against original pixels; if not readable, retain unknown orientation and do not
treat a crop label as proof of patient side. Full originals remain authoritative.
Tool outputs are unverified hypotheses. Scores and grounded boxes cannot prove
presence, side, size, rib/intercostal count or interval change; errors, isolated
labels or No are not patient facts. Unknown does not mean absent/normal/same.
Evaluate ALL full answer options, including compound side, site, count, sign,
mechanism and change requirements. No confidence threshold, voting or final
re-solving follows this response. Choose your best legal option even when the
target attribute remains uncertain. Return two lines:
Answer: <one legal option letter, option text may follow>
Reason: <one brief decisive visible observation, or explicit unresolved attribute
and why the chosen complete option is still best supported>
Do not output a long reasoning trace or another action plan.'''


def explicit_answer(text, legal):
    if not isinstance(text, str): return None
    clean=text.replace('**','').replace('__','').replace('`','').strip()
    values=[]
    for line in clean.splitlines():
        m=re.match(r'^\s*Answer\s*:\s*(.*?)\s*$',line,re.I)
        if not m:continue
        found=re.fullmatch(r'\(?([A-Z])\)?(?:\s*[).:]\s*.*|\s*)',m[1].strip(),re.I)
        v=found[1].upper() if found else None
        values.append(v if v in legal else None)
    if values:return values[0] if None not in values and len(set(values))==1 else None
    return clean.upper() if len(clean)==1 and clean.upper() in legal else None


def valid_box(box):
    return (isinstance(box,list) and len(box)==4 and all(type(v) in (int,float) and math.isfinite(v) for v in box)
            and 0<=box[0]<box[2]<=1 and 0<=box[1]<box[3]<=1)


def orientation(metadata):
    """Map a declared visible marker to screen half, without assuming convention."""
    if metadata.get('view') not in {'frontal','axial'}:return None
    marker=metadata.get('marker') or {};box=marker.get('box');text=str(marker.get('text','')).upper()
    if text not in {'R','L'} or not valid_box(box):return None
    # A marker crossing the screen midpoint cannot anchor an anatomical half.
    display='left' if box[2]<=0.5 else 'right' if box[0]>=0.5 else None
    if display is None:return None
    return display if text=='R' else ('right' if display=='left' else 'left')


def crop_audit(plan, images):
    ids=plan.get('image_ids') or [];registry={x['image_id']:x for x in images}
    if len(ids)!=1 or ids[0] not in registry:return {'allowed':False,'reason':'crop_requires_one_current_image'}
    box=plan.get('box')
    if not valid_box(box):return {'allowed':False,'reason':'invalid_display_pixel_box'}
    width,height=registry[ids[0]]['size']
    if math.ceil(box[2]*width)-math.floor(box[0]*width)<=10 or math.ceil(box[3]*height)-math.floor(box[1]*height)<=10:
        return {'allowed':False,'reason':'crop_below_pixel_minimum'}
    metadata=next((x for x in plan.get('image_metadata',[]) if x.get('image_id')==ids[0]),{})
    side=plan.get('target_patient_side','unknown');right=orientation(metadata)
    result={'allowed':True,'target_patient_side':side,'patient_right_display_half':right,
            'display_box':box,'orientation_source':'model_reported_visible_RL_marker_not_independently_verified',
            'marker':metadata.get('marker'),'view':metadata.get('view'),'parent_image_id':ids[0],
            'automatic_flip_or_rotation':False}
    if side in {'right','left'}:
        if right is None:return dict(result,allowed=False,reason='unresolved_anatomical_orientation_use_full_images')
        expected=right if side=='right' else ('right' if right=='left' else 'left')
        result['expected_display_half']=expected
        if not (box[2]<=0.5 if expected=='left' else box[0]>=0.5):
            return dict(result,allowed=False,reason='patient_side_and_display_crop_mismatch_use_full_images')
    elif side=='bilateral':
        if not box[0]<0.5<box[2]:return dict(result,allowed=False,reason='bilateral_crop_must_cover_both_display_halves')
    elif side=='midline':
        if not box[0]<0.5<box[2]:return dict(result,allowed=False,reason='midline_crop_without_display_midline_use_full_images')
    elif side in {'unknown','not_applicable'}:
        if re.search(r'(?i)\b(?:right|left)\b|右|左',plan.get('target_region','')):
            return dict(result,allowed=False,reason='unbound_side_claim_in_target_region_use_full_images')
    else:return dict(result,allowed=False,reason='invalid_patient_side_use_full_images')
    return dict(result,reason='declared_marker_side_and_pixel_geometry_consistent')


def normalize_plan(text, images):
    text=str(text).strip()
    if text.startswith('```'):text=re.sub(r'^```(?:json)?\s*','',text,flags=re.I);text=re.sub(r'\s*```$','',text)
    raw=json.loads(text)
    if not isinstance(raw,dict):raise ValueError('plan_not_object')
    known={i['image_id'] for i in images}
    ids=raw.get('image_ids');ids=list(dict.fromkeys(i for i in ids if i in known)) if isinstance(ids,list) else []
    attribute=raw.get('attribute')
    if attribute not in {'side','intercostal_space','sign','location','shape','size','count','change','relationship','pattern','other'}:attribute='other'
    region=str(raw.get('target_region') or 'the relevant anatomy')[:250]
    question=str(raw.get('neutral_question') or '')[:700]
    warnings=[]
    if attribute in {'intercostal_space','count','size'} and re.search(r'\d',region):
        region='the relevant lesion/anatomical region in the complete options'
        warnings.append('expected_numeric_value_removed_from_target_region')
    if (not question or re.search(r'(?i)\b(?:confirm|prove|expected|must be|option\s+[A-F]|answer\s*[:=])\b',question)
            or re.match(r'(?i)^\s*(?:is|are|does|do|can|could|would)\b',question)):
        question=f'Describe the {attribute} of {region} from the original pixels, including uncertainty. Compare the full options without assuming a proposed finding.'
        warnings.append('leading_or_missing_question_replaced_with_open_attribute_question')
    plan={'attribute':attribute,'target_region':region,'neutral_question':question,
          'kind':raw.get('kind') if raw.get('kind') in {'visual','crop','tool'} else 'visual',
          'image_ids':ids or [i['image_id'] for i in images],
          'target_patient_side':raw.get('target_patient_side','unknown'),'box':raw.get('box'),
          'tool':raw.get('tool') if raw.get('tool') in TOOLS else '',
          'tool_args':raw.get('tool_args') if isinstance(raw.get('tool_args'),dict) else {},
          'image_metadata':[],'warnings':warnings}
    for item in raw.get('image_metadata',[]) if isinstance(raw.get('image_metadata'),list) else []:
        if isinstance(item,dict) and item.get('image_id') in known:
            from v12_evidence import normalize_modality
            plan['image_metadata'].append({'image_id':item['image_id'],'modality':normalize_modality(item.get('modality')),
                'view':item.get('view','unknown'),'marker':item.get('marker') if isinstance(item.get('marker'),dict) else {}})
    return plan


def fallback_plan(images, reason):
    return {'attribute':'other','target_region':'the option-discriminating anatomy',
            'neutral_question':'Describe the visible side, location, morphology, count, sign or interval change that differentiates the full options. Retain unknown attributes explicitly.',
            'kind':'visual','image_ids':[i['image_id'] for i in images],
            'target_patient_side':'unknown','box':None,'tool':'','tool_args':{},'image_metadata':[],
            'warnings':[reason]}


def planning_payload(row, images):
    return {'full_question_and_all_options':row['question'],'image_registry':images,
            'available_medical_tools':TOOLS,'action_limit':1,
            'coordinate_convention':'normalized displayed/stored pixel coordinates; never anatomical side coordinates'}


def observer_payload(row, images, plan, action):
    # Project only neutral scope. Planner guesses/expected findings never enter.
    return {'full_question_and_all_options':row['question'],'image_registry':images,
            'requested_attribute':plan['attribute'],'target_region':plan['target_region'],
            'neutral_question':plan['neutral_question'],'selected_image_ids':plan['image_ids'],
            'observation_action':action,
            'instruction':'No previous answer or reason is supplied. Inspect the requested attribute independently, then give a single best complete option and one key observation.'}
