"""S3: observe original images without candidate answers, then match options.

The first request is constructed directly from the inference row. It cannot receive
the S1 comparison packet, tools, crops, earlier selections, plans, or K/E. The second
request retains the frozen anonymous comparison and appends the fallible blind read.
No model request, tool action, image mutation, or label access occurs in this module.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

from v11_selection import _options, _payload


BLIND_READER_PROMPT = '''Independently inspect the full original current images and
the question stem. No candidate answers, existing tool diagnoses, selected regions,
prior decisions, or historical cases have been supplied. Do not infer or invent them.
Report concise observable image attributes relevant to the question before any
answer options are considered. Describe location, side, number, shape, distribution,
and relationships only when actually supported by these pixels. For multiple views,
identify which supplied image supports each observation. Do not infer missing
chronology, scale, orientation, or anatomical laterality. Not described is not absent.
Separate visible findings from uncertainty; an unresolved attribute must stay
unresolved. Do not provide a diagnosis as an established fact, select an option,
guess missing options, or discuss what another answer may have said.
Return concise JSON:
{"observations":[{"attribute":"visual attribute relevant to the question",
"value":"brief visible finding or specific unresolved point",
"status":"observed_present|observed_absent|unresolved|hypothesis",
"evidence_refs":["exact supplied image IDs"]}],
"uncertainties":["specific limits that could affect interpretation"]}.
Provide observable findings only, not hidden reasoning or an extended discussion.'''


def blind_reader_content(row, image_root):
    """Build blind input independently; only question stem and original pixels."""
    from PIL import Image
    stem, _ = _options(row['question'])
    root = Path(image_root).resolve()
    if not isinstance(row.get('images'), list) or not row['images']:
        raise ValueError('blind_read_requires_original_images')
    images = []
    content = [{'type': 'text', 'text': json.dumps({
        'question_stem': stem,
        'instruction': 'Inspect only these full original images and report observable attributes relevant to this question. No answer options are provided.'},
        ensure_ascii=False)}]
    for index, relative in enumerate(row['images']):
        if not isinstance(relative, str):
            raise ValueError('invalid_original_image_path')
        path = (root/relative).resolve()
        if not path.is_relative_to(root):
            raise ValueError('original_image_outside_root')
        with Image.open(path) as original:
            width, height = original.size
        if min(width, height) <= 10:
            raise ValueError('original_image_below_model_minimum')
        # Same original order and neutral IDs as the frozen S1 comparison.
        meta = {'image_id': 'image_'+str(index+1), 'role': 'original',
                'size': [width, height], 'orientation': 'unresolved',
                'timepoint': 'unresolved'}
        images.append(dict(meta, path=str(path)))
        content.append({'type': 'text', 'text': json.dumps(meta)})
        content.append(_payload(path))
    return {'content': content, 'images': images,
            'refs': [image['image_id'] for image in images]}


def _object(text):
    decoder = json.JSONDecoder()
    for index, char in enumerate(text):
        if char != '{':
            continue
        try:
            obj, _ = decoder.raw_decode(text[index:])
        except ValueError:
            continue
        if isinstance(obj, dict):
            return obj
    return None


def parse_blind_observation(text, refs):
    """Keep explicit findings, remove unknown references, never supply new facts."""
    if not isinstance(text, str) or not text.strip():
        raise ValueError('no_blind_reader_output')
    obj = _object(text)
    known, warnings = set(refs), []
    if obj is None:
        # Unstructured output remains a hypothesis with no manufactured citation.
        obj = {'observations': [{'attribute': 'unstructured_visual_report',
                                 'value': text, 'status': 'hypothesis',
                                 'evidence_refs': []}],
               'uncertainties': ['Reader output did not provide structured image references.']}
        warnings.append('unstructured_blind_report_retained_as_hypothesis')
    raw = obj.get('observations', [])
    if not isinstance(raw, list):
        raw = []
        warnings.append('observations_not_a_list')
    # A singular explicit observation is a harmless schema variant.
    if not raw and isinstance(obj.get('observation'), str):
        raw = [{'attribute': 'visual_observation', 'value': obj['observation'],
                'status': obj.get('status', 'hypothesis'),
                'evidence_refs': obj.get('evidence_refs', [])}]
        warnings.append('singular_observation_normalized')
    clean = []
    for item in raw:
        if not isinstance(item, dict):
            warnings.append('nonobject_observation_removed')
            continue
        value = item.get('value')
        if not isinstance(value, str) or not value.strip():
            warnings.append('empty_observation_removed')
            continue
        attribute = item.get('attribute', '')
        if not isinstance(attribute, str):
            attribute = ''
            warnings.append('invalid_attribute_normalized')
        cited = item.get('evidence_refs', [])
        if not isinstance(cited, list):
            cited = []
            warnings.append('evidence_refs_not_a_list')
        valid = list(dict.fromkeys(ref for ref in cited if isinstance(ref, str) and ref in known))
        if cited != valid:
            warnings.append('unknown_or_duplicate_refs_removed')
        status = item.get('status', 'hypothesis')
        if status not in ('observed_present', 'observed_absent', 'unresolved', 'hypothesis'):
            status = 'hypothesis'
            warnings.append('invalid_status_kept_as_hypothesis')
        if status.startswith('observed_') and not valid:
            status = 'hypothesis'
            warnings.append('unreferenced_finding_kept_as_hypothesis')
        clean.append({'attribute': attribute[:400], 'value': value[:1500],
                      'status': status, 'evidence_refs': valid})
    uncertainties = obj.get('uncertainties', obj.get('unresolved', []))
    if isinstance(uncertainties, str):
        uncertainties = [uncertainties]
        warnings.append('uncertainty_string_normalized')
    elif not isinstance(uncertainties, list):
        uncertainties = []
        warnings.append('invalid_uncertainties_removed')
    uncertainties = [value[:800] for value in uncertainties if isinstance(value, str) and value.strip()]
    if not clean and not uncertainties:
        raise ValueError('no_usable_blind_observation_or_uncertainty')
    if not clean:
        warnings.append('blind_read_only_reported_uncertainty')
    return {'observation_id': 'blind_observation_1', 'observations': clean,
            'uncertainties': uncertainties, 'parse_warnings': sorted(set(warnings)),
            'status': 'independent_blind_visual_report_requires_image_verification'}


def matching_content(packet, observation):
    """Keep original S1 evidence identical, then append the answer-blind report."""
    if observation.get('observation_id') != 'blind_observation_1':
        raise ValueError('unexpected_blind_observation_id')
    content = copy.deepcopy(packet['content'])
    content.append({'type': 'text', 'text': json.dumps({
        'independent_blind_observation': observation,
        'instruction': 'This independent reader saw only the full original images and question stem, without any answer options or prior decisions. Its observations are fallible reports, not reference answers. Compare the same X and Y options using the same support standard and the actual images. Do not automatically prioritize this report over the pixels or invent missing facts. Choose the best legal option and state remaining uncertainty.'}, ensure_ascii=False)})
    return content
