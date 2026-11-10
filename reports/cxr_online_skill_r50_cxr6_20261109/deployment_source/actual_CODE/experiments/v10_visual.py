"""Real pixel crops and independent, tolerant candidate decoding for V10.

No function accepts an initial/P0 answer or a reference label. Coordinates refer
to stored image pixels; anatomical side and orientation are never inferred here.
"""
from __future__ import annotations

import base64
from hashlib import sha256
import json
import math
import mimetypes
from pathlib import Path
import re
import uuid


CROP_TOOL_DESCRIPTION = """Crop actual pixels from a currently supplied image. Use only for a
specific option-discriminating local detail. image_id must be one of the supplied
current image IDs. box is [left, top, right, bottom] in normalized displayed pixel
coordinates (0 to 1), not anatomical laterality. Keep the full original image for
distribution/orientation context. The saved crop is returned as an actual image
to the next visual request. A crop magnifies existing pixels; it adds no new data."""

CANDIDATE_PROMPT = """Give your current best answer independently using the current images and
option differences. Return concise JSON: {"answer":"one legal option letter",
"uncertain":false,"changed_attributes":["discriminating attribute"],
"evidence_refs":["exact current reference ID"],"observations":[],
"missing_evidence":["specific remaining uncertainty"]}.
Always choose your best LEGAL option even if uncertain; uncertainty and missing
evidence are separate fields, never reasons for answer=null. Do not invent image
facts. For an option combining side, location, size and morphology, check each
component separately. Tool disease labels and retrieved rules are hypotheses,
not observations of this case. Omission from a report does not mean absence."""


def _image_mapping(images):
    mapping = {}
    for item in images:
        if not isinstance(item, dict) or not isinstance(item.get('image_id'), str):
            raise ValueError('invalid_image_registry')
        if item['image_id'] in mapping:
            raise ValueError('duplicate_image_id')
        path = Path(item['path']).resolve(strict=True)
        if not path.is_file():
            raise ValueError('source_image_not_a_file')
        mapping[item['image_id']] = dict(item, path=str(path))
    return mapping


def crop_image(image_id, box, images, output_dir, *, crop_id=None):
    """Create a crop only from the explicitly supplied current-image registry.

    ``box`` uses normalized [left, top, right, bottom]. The metadata binds the
    exact pixel crop to its parent, with no clinical claim about what it shows.
    """
    from PIL import Image
    mapping = _image_mapping(images)
    if image_id not in mapping:
        raise ValueError('unknown_current_image_id')
    if (not isinstance(box, (list, tuple)) or len(box) != 4
            or any(type(v) not in (int, float) or not math.isfinite(v) for v in box)):
        raise ValueError('invalid_normalized_box')
    left, top, right, bottom = box
    if not (0 <= left < right <= 1 and 0 <= top < bottom <= 1):
        raise ValueError('normalized_box_outside_image')
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    crop_id = crop_id or 'crop:' + uuid.uuid4().hex
    if not isinstance(crop_id, str) or not re.fullmatch(r'[A-Za-z0-9_:\-]{1,100}', crop_id):
        raise ValueError('invalid_crop_id')
    if crop_id in mapping:
        raise ValueError('crop_id_conflicts_with_current_image')
    target = output_dir / (crop_id.replace(':', '_') + '.png')
    if not target.resolve().is_relative_to(output_dir) or target.exists():
        raise ValueError('crop_target_exists_or_outside_output')
    source = Path(mapping[image_id]['path'])
    with Image.open(source) as original:
        original.load()
        width, height = original.size
        pixels = [math.floor(left*width), math.floor(top*height),
                  math.ceil(right*width), math.ceil(bottom*height)]
        if pixels[2]-pixels[0] < 4 or pixels[3]-pixels[1] < 4:
            raise ValueError('crop_too_small')
        crop = original.crop(pixels)
        if crop.mode not in ('L', 'LA', 'RGB', 'RGBA'):
            crop = crop.convert('RGB')
        crop.save(target, format='PNG')
        crop_size = list(crop.size)
    return {'image_id': crop_id, 'path': str(target), 'role': 'current_image_pixel_crop',
            'parent_image_id': image_id, 'parent_path': str(source),
            'source_size': [width, height], 'crop_size': crop_size,
            'normalized_box': list(box), 'pixel_box': pixels,
            'coordinate_system': 'stored_pixel_coordinates_no_anatomical_orientation_inferred',
            'orientation': 'unresolved', 'timepoint': mapping[image_id].get('timepoint', 'unresolved'),
            'source_sha256': sha256(source.read_bytes()).hexdigest(),
            'crop_sha256': sha256(target.read_bytes()).hexdigest(),
            'is_new_usable': None}


def image_payload(image):
    """Encode actual supplied image bytes, not a file path masquerading as pixels."""
    path = Path(image['path']).resolve(strict=True)
    mime = mimetypes.guess_type(path.name)[0]
    if mime not in ('image/png', 'image/jpeg', 'image/webp'):
        raise ValueError('unsupported_image_payload_type')
    return {'type': 'image_url', 'image_url': {
        'url': f'data:{mime};base64,' + base64.b64encode(path.read_bytes()).decode('ascii'),
        'detail': 'auto'}}


def multimodal_content(text, originals, crops=()):
    """Return full images followed by crops, each explicitly identified in text."""
    originals, crops = list(originals), list(crops)
    images = originals + crops
    mapping = _image_mapping(images)
    if not originals:
        raise ValueError('full_original_context_required')
    for item in crops:
        if item.get('parent_image_id') not in mapping:
            raise ValueError('crop_parent_missing')
    content = [{'type': 'text', 'text': text}]
    for item in images:
        meta = {k: item[k] for k in ('image_id', 'role', 'parent_image_id', 'pixel_box',
                'source_size', 'crop_size', 'orientation', 'timepoint') if k in item}
        content.append({'type': 'text', 'text': 'CURRENT IMAGE: ' + json.dumps(meta)})
        content.append(image_payload(item))
    return content


def make_crop_tool(images, output_dir):
    """Build an adapter compatible with the existing TrackedTool image checks.

    The outer tracker authorizes ``image_path`` and counts this as one tool
    attempt. The closure independently restricts it to this case's registry.
    The runner must attach the returned saved pixels before the next model call.
    """
    from langchain_core.tools import StructuredTool
    from pydantic import BaseModel, Field
    registry = list(_image_mapping(images).values())
    by_path = {Path(item['path']): item['image_id'] for item in registry}

    class CropArgs(BaseModel):
        image_path: str = Field(description='Exact image path from the current image registry.')
        box: list[float] = Field(description='Normalized pixel coordinates [left, top, right, bottom], each 0 to 1.')

    def crop_current_image(image_path: str, box: list[float]):
        image_id = by_path.get(Path(image_path).resolve())
        if image_id is None:
            raise ValueError('crop_source_not_in_current_case')
        return crop_image(image_id, box, registry, output_dir)

    return StructuredTool.from_function(crop_current_image, name='crop_current_image',
        description=CROP_TOOL_DESCRIPTION, args_schema=CropArgs)


def _legal_letter(value, options):
    if not isinstance(value, str):
        return None
    # An explicit answer value may include its option text, e.g. "B. ...".
    match = re.match(r'^\s*([A-Z])(?:\s*$|[).:\s])', value.upper())
    return match.group(1) if match and match.group(1) in options else None


def _json_object(text):
    def reject_duplicates(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise ValueError('duplicate_candidate_json_key')
            value[key] = item
        return value
    decoder = json.JSONDecoder(object_pairs_hook=reject_duplicates)
    values = []
    position = 0
    while position < len(text):
        start = text.find('{', position)
        if start < 0:
            break
        try:
            value, consumed = decoder.raw_decode(text[start:])
        except json.JSONDecodeError:
            position = start+1
            continue
        if isinstance(value, dict):
            values.append(value)
        position = start+consumed
    if len(values) > 1:
        raise ValueError('multiple_candidate_json_objects')
    return values[0] if values else None


def parse_candidate(text, options, refs):
    """Keep a legal independent best answer despite noncritical schema defects.

    Uncertainty is independent of answer availability. Unknown evidence IDs are
    removed and audited, never promoted to real evidence. An absent/ambiguous
    answer remains a failure; this function never guesses or copies P0.
    """
    if not isinstance(text, str):
        raise ValueError('non_text_candidate')
    options, refs = set(options), set(refs)
    if not options:
        raise ValueError('no_legal_options')
    warnings = []
    obj = _json_object(text.strip())
    answer = None
    if obj is not None:
        keys = ('answer', 'candidate', 'best_answer', 'final_answer', 'best_option')
        choices = {_legal_letter(obj[k], options) for k in keys if k in obj}
        choices.discard(None)
        if len(choices) > 1:
            raise ValueError('conflicting_candidate_answers')
        answer = next(iter(choices)) if choices else None
        if answer and obj.get('answer') != answer:
            warnings.append('answer_field_normalized')
    else:
        # Explicit labels or a bare answer only. Do not mine arbitrary option
        # letters from prose, because those may describe rejected alternatives.
        bare = re.fullmatch(r'\s*([A-Z])\s*[.)]?\s*', text, re.I)
        explicit = re.findall(r'(?im)^\s*(?:final\s+answer|answer|best\s+option)\s*[:=]\s*([A-Z])(?:\s*$|[).:\s])', text)
        choices = {v.upper() for v in explicit if v.upper() in options}
        if bare and bare.group(1).upper() in options:
            choices.add(bare.group(1).upper())
        if len(choices) == 1:
            answer = next(iter(choices))
            warnings.append('explicit_answer_recovered_without_json')
        elif len(choices) > 1:
            raise ValueError('conflicting_candidate_answers')
        obj = {}
    if answer is None:
        raise ValueError('no_recoverable_legal_candidate')
    uncertain = obj.get('uncertain', True)
    if type(uncertain) is not bool:
        uncertain = True
        warnings.append('uncertainty_normalized_to_true')
    def string_list(key):
        value = obj.get(key, [])
        if not isinstance(value, list):
            warnings.append(key+'_not_a_list')
            return []
        return [x for x in value if isinstance(x, str) and x.strip()]
    known = string_list('evidence_refs')
    unknown = [x for x in known if x not in refs]
    if unknown:
        warnings.append('unknown_evidence_refs_removed')
    observations = obj.get('observations', [])
    if not isinstance(observations, list):
        observations = []
        warnings.append('observations_not_a_list')
    clean_observations = []
    for observation in observations:
        if not isinstance(observation, dict):
            warnings.append('nonobject_observation_removed')
            continue
        entry = dict(observation)
        for key in ('evidence_refs', 'image_ids'):
            values = entry.get(key, [])
            values = values if isinstance(values, list) else []
            kept = [x for x in values if isinstance(x, str) and x in refs]
            if values != kept:
                warnings.append('unknown_observation_references_removed')
            entry[key] = kept
        status = entry.get('status')
        if isinstance(status, str) and status.startswith('observed_') and not entry['evidence_refs']:
            entry['status'] = 'hypothesis'
            warnings.append('unreferenced_observation_kept_as_hypothesis')
        clean_observations.append(entry)
    payload = {'answer': answer, 'uncertain': uncertain,
               'changed_attributes': string_list('changed_attributes'),
               'evidence_refs': list(dict.fromkeys(x for x in known if x in refs)),
               'observations': clean_observations, 'missing_evidence': string_list('missing_evidence'),
               'parse_warnings': sorted(set(warnings)), 'discarded_evidence_refs': unknown}
    return answer, payload
