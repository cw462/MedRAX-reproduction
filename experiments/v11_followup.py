"""One bounded, answer-blind visual follow-up for unresolved V11 comparisons.

Only the action planner receives cached knowledge/experience action advice. The
independent reader sees no answer options, selector choice, or training material.
One optional crop uses original pixels; no model or paid request is made here.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
import re

from v11_selection import _expand_crop, _payload, _sanitize


PLANNER_PROMPT = '''Choose ONE visual observation action that could best resolve the
standalone question. You do not know the competing answers or prior selection.
Choose to reinspect original images, inspect a cached local/tool image, or create
ONE crop from ONE original. All full originals will remain available. Use existing
views for spatial/distribution/time questions; do not infer missing chronology or
anatomical orientation. A crop uses current pixels and adds no new information.
Knowledge and training experiences below are conditional ACTION advice only. They
are not current-patient observations, diagnoses, answers, or validated step credit.
Use them only if applicable to this question; otherwise skip them. Do not copy
historical findings or sidedness. No clinical claim is established by an action.
Return concise JSON: {"action":"reinspect_original|inspect_existing|crop_original",
"image_ids":["one or two supplied IDs"],"box":[left,top,right,bottom],
"reason":"brief reason this view can resolve the visual property"}.
The box is only for crop_original: normalized displayed-pixel coordinates in [0,1],
left<right and top<bottom, not anatomical coordinates. No repeated actions.'''

READER_PROMPT = '''Independently inspect the supplied current images to answer the
single visual question. You have not been given candidate answers or a previous
decision. Report the requested observable attribute, with exact image references.
The question is a hypothesis to investigate, not an assertion of a diagnosis.
Use full originals for orientation/distribution and compare with any selected local
view. A crop adds no information beyond its original pixels. Do not infer absent
timepoints, scale, anatomical laterality, or facts not visible. Do not select an
answer option or guess the hidden candidates. If the property cannot be resolved,
say so explicitly rather than manufacturing certainty.
Return concise JSON: {"observation":"brief visible finding relevant to the question",
"evidence_refs":["supplied image IDs"],"unresolved":["specific remaining limits"]}.
Do not provide hidden reasoning or an extended clinical discussion.'''


def _packet_text(packet):
    first = next(part['text'] for part in packet['content'] if part.get('type') == 'text')
    return json.loads(first)


def _visual_question(question):
    if not isinstance(question, str) or not question.strip():
        raise ValueError('followup_requires_specific_visual_question')
    if re.search(r'(?<![\w-])[XY](?![\w-])|\b(?:option|choice|answer)\s+[A-FXY]\b', question):
        raise ValueError('followup_question_contains_option_identity')
    return question.strip()[:1200]


def _image_content(text, images):
    content = [{'type': 'text', 'text': json.dumps(text, ensure_ascii=False)}]
    for image in images:
        content.append({'type': 'text', 'text': json.dumps({k: v for k, v in image.items() if k != 'path'})})
        content.append(_payload(image['path']))
    return content


def planner_content(packet, question, source_retrieval):
    """No choices/private mapping/selector output enter the action planner."""
    question = _visual_question(question)
    if not isinstance(source_retrieval, dict):
        source_retrieval = {}
    advice = {key: _sanitize(source_retrieval.get(key, ''), {})
              for key in ('k_block', 'e_block')}
    # Training IDs serve retrieval provenance privately, not evidence for this case.
    for key, value in advice.items():
        if not isinstance(value, str):
            advice[key] = ''
        else:
            advice[key] = re.sub(r'\b(?:B10_|memory_)[A-Za-z0-9_:.-]+', '[training_action_card]', value)
    text = {'case_question_without_options': _packet_text(packet)['question'],
            'visual_question': question, 'conditional_action_advice': advice,
            'allowed_actions': ['reinspect_original', 'inspect_existing', 'crop_original'],
            'maximum_new_crop_actions': 1,
            'advice_note': 'Training outcomes do not establish current findings or causal step value.'}
    return _image_content(text, packet['images'])


def _object(text):
    if not isinstance(text, str):
        raise ValueError('non_text_followup_response')
    decoder = json.JSONDecoder()
    for index, character in enumerate(text):
        if character == '{':
            try:
                obj, _ = decoder.raw_decode(text[index:])
                if isinstance(obj, dict):
                    return obj
            except ValueError:
                pass
    raise ValueError('no_followup_json_object')


def parse_plan(text, packet):
    """Invalid optional planning fields cause one recorded full-view fallback."""
    warnings = []
    try:
        obj = _object(text)
    except ValueError:
        obj = {}
        warnings.append('invalid_plan_json_full_view_fallback')
    images = {image['image_id']: image for image in packet['images']}
    originals = [name for name, image in images.items() if image['role'] == 'original']
    action = obj.get('action')
    if action not in ('reinspect_original', 'inspect_existing', 'crop_original'):
        action = 'reinspect_original'
        warnings.append('invalid_action_full_view_fallback')
    raw_ids = obj.get('image_ids', [])
    ids = [name for name in raw_ids if isinstance(name, str) and name in images][:2] if isinstance(raw_ids, list) else []
    if action == 'reinspect_original':
        ids = [name for name in ids if name in originals] or originals[:2]
    elif action == 'inspect_existing' and not ids:
        action, ids = 'reinspect_original', originals[:2]
        warnings.append('no_selected_image_full_view_fallback')
    box = obj.get('box')
    valid_box = (isinstance(box, list) and len(box) == 4
                 and all(type(value) in (int, float) and math.isfinite(value) for value in box)
                 and 0 <= box[0] < box[2] <= 1 and 0 <= box[1] < box[3] <= 1)
    if action == 'crop_original':
        if not ids or ids[0] not in originals or not valid_box:
            action, ids, box = 'reinspect_original', originals[:2], None
            warnings.append('invalid_crop_full_view_fallback')
        else:
            ids = ids[:1]
    else:
        box = None
    return {'action': action, 'image_ids': ids, 'box': box,
            'reason': str(obj.get('reason', ''))[:1000], 'parse_warnings': warnings}


def apply_plan(packet, plan, artifact_dir):
    """Return all originals plus selected views; create at most one pixel crop."""
    originals = [image for image in packet['images'] if image['role'] == 'original']
    registry = {image['image_id']: image for image in packet['images']}
    result = {'action': plan['action'], 'images': list(originals), 'tool_attempts': 0,
              'repairs': [], 'warnings': list(plan.get('parse_warnings', []))}
    selected = [registry[name] for name in plan['image_ids'] if name in registry]
    if plan['action'] == 'crop_original':
        result['tool_attempts'] = 1
        source = selected[0]
        try:
            crop = _expand_crop({'parent_path': source['path'], 'normalized_box': plan['box']},
                                Path(artifact_dir).resolve()/'followup_crop.png',
                                {str(Path(image['path']).resolve()) for image in originals})
            if crop is None:
                result['warnings'].append('crop_unavailable_originals_retained')
            else:
                image = {'image_id': 'followup_image_1', 'path': crop['path'],
                         'role': 'one_targeted_original_pixel_crop',
                         'size': crop['crop_size'], 'parent_image_id': source['image_id'],
                         'pixel_box': crop['pixel_box'], 'source_size': crop['source_size'],
                         'orientation': 'unresolved', 'timepoint': 'unresolved'}
                result['images'].append(image)
                result['repairs'].append({'action': 'bounded_original_pixel_crop_no_interpolation',
                                          'requested_box': plan['box'], 'pixel_box': crop['pixel_box'],
                                          'size': crop['crop_size']})
        except (OSError, ValueError, TypeError) as exc:
            result['warnings'].append('crop_error_originals_retained:'+type(exc).__name__)
    else:
        existing = {image['image_id'] for image in result['images']}
        result['images'].extend(image for image in selected if image['image_id'] not in existing)
    return result


def reader_content(packet, question, action_result):
    """Answer-blind reader input: no choices, S1 result, tool claims, or K/E."""
    text = {'case_question_without_options': _packet_text(packet)['question'],
            'standalone_visual_question': _visual_question(question),
            'selected_action': action_result['action'],
            'observation_instruction': 'Describe only the requested attribute from these pixels; state unresolved limits.'}
    return _image_content(text, action_result['images'])


def parse_observation(text, refs):
    known = set(refs)
    warnings = []
    try:
        obj = _object(text)
    except ValueError:
        obj = {'observation': text if isinstance(text, str) else '', 'unresolved': ['unstructured_reader_output']}
        warnings.append('reader_text_kept_as_unstructured_observation')
    value = obj.get('observation')
    if not isinstance(value, str) or not value.strip():
        raise ValueError('no_reader_observation')
    references = obj.get('evidence_refs', [])
    references = references if isinstance(references, list) else []
    valid = [ref for ref in references if isinstance(ref, str) and ref in known]
    if valid != references:
        warnings.append('unknown_reader_refs_removed')
    if not valid:
        warnings.append('reader_observation_without_explicit_reference')
    unresolved = obj.get('unresolved', [])
    if not isinstance(unresolved, list):
        unresolved = [unresolved] if isinstance(unresolved, str) else []
    return {'observation_id': 'followup_observation_1', 'observation': value[:4000],
            'evidence_refs': valid, 'unresolved': [item[:500] for item in unresolved if isinstance(item, str)],
            'parse_warnings': warnings, 'status': 'independent_visual_report_requires_image_verification'}


def comparison_with_observation(packet, question, observation, action_result):
    """Return original anonymous comparison plus the one independent report."""
    content = list(packet['content'])
    existing = {image['image_id'] for image in packet['images']}
    for image in action_result['images']:
        if image['image_id'] not in existing:
            content.append({'type': 'text', 'text': json.dumps({key: value for key, value in image.items() if key != 'path'})})
            content.append(_payload(image['path']))
    content.append({'type': 'text', 'text': json.dumps({
        'single_targeted_visual_question': _visual_question(question),
        'independent_visual_observation': observation,
        'instruction': 'Recompare X and Y with the same standards using these actual pixels and the new report. The independent report is fallible and not a reference answer. No additional observation round is available; choose the best legal option and state remaining uncertainty.'}, ensure_ascii=False)})
    return content
