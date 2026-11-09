"""Pure, label-free E2 case-batch and within-case conversation contracts.

Input rows retain the existing fields question_id, case_id, question, images,
and optional figure_labels. `question` contains the complete stem and options.
An image_bank maps source_filename to {metadata, image_url}; image_url contains
the already encoded original bytes. This module performs no file/network I/O.
Use image_bank_from_requests() to adapt existing request_for() messages.

Batch: one request for all questions of one case, strict JSON keyed by original
question ID, output limit 8192. Sequential: one request per question, the exact
earlier assistant texts of this case only, output limit 2048. Neither mode uses
reference answers. All calls use qwen3.7-plus, T=.2, top_p=.95, thinking=False.
"""
from __future__ import annotations

from copy import deepcopy
import json
import re

try:
    from .run_direct_vlm import SYSTEM_PROMPT
    from .v12_evidence import question_parts
except ImportError:
    from run_direct_vlm import SYSTEM_PROMPT
    from v12_evidence import question_parts


MODEL = 'qwen3.7-plus'
ROW_FIELDS = {'question_id', 'case_id', 'question', 'images', 'figure_labels'}
METADATA_FIELDS = {'source_filename', 'image_id', 'figure_label', 'role', 'size',
    'modality', 'timepoint', 'timepoint_source_quote', 'comparison_object', 'path'}
BOUND = 'BOUND CURRENT IMAGE: '
DATA_URI = re.compile(r'data:image/(?:png|jpeg|webp);base64,[A-Za-z0-9+/]+={0,2}', re.I)
BATCH_SYSTEM_PROMPT = '''You answer medical image multiple-choice questions belonging to one case. Inspect the supplied original images and the complete text and options of every question. Use a consistent interpretation of the case, while choosing each question's answer from its own options; option letters from different questions are unrelated. Respect the explicit figure bindings and only the chronology stated in the questions. Give the best option even when details remain uncertain. Return only one JSON object keyed by every supplied question_id, with each value exactly {"answer": "<one legal option letter>", "reason": "<one or two brief sentences>"}. Do not include Markdown fences or a long reasoning trace.'''


def _identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_-]+', value):
        raise ValueError('explicit_safe_question_and_case_identifiers_required')
    return value


def _source(value):
    if (not isinstance(value, str) or not value or '\\' in value or ':' in value
            or value.startswith('/') or any(part in ('', '.', '..') for part in value.split('/'))):
        raise ValueError('relative_original_image_source_required')
    return value


def validate_rows(rows, *, one_case=False):
    """Reject attached answer/reference fields rather than silently dropping them."""
    if not isinstance(rows, (list, tuple)) or not rows:
        raise ValueError('nonempty_input_rows_required')
    seen, case_ids = set(), set()
    for row in rows:
        if not isinstance(row, dict) or set(row) - ROW_FIELDS or not (ROW_FIELDS - {'figure_labels'}) <= set(row):
            raise ValueError('label_free_question_schema_required')
        qid, case_id = _identifier(row['question_id']), _identifier(row['case_id'])
        if qid in seen:
            raise ValueError('duplicate_question_id')
        seen.add(qid); case_ids.add(case_id)
        if not isinstance(row['question'], str) or not row['question'].strip():
            raise ValueError('complete_question_text_required')
        question_parts(row['question'])
        if not isinstance(row['images'], list) or not row['images']:
            raise ValueError('original_question_images_required')
        for source in row['images']:
            _source(source)
        if 'figure_labels' in row and (not isinstance(row['figure_labels'], list)
                or len(row['figure_labels']) != len(row['images'])
                or any(not isinstance(value, str) for value in row['figure_labels'])):
            raise ValueError('figure_labels_must_match_image_sources')
    if one_case and len(case_ids) != 1:
        raise ValueError('one_case_per_request_required')
    return rows


def group_cases(rows):
    """Preserve first-seen case order and original question order within each case."""
    validate_rows(rows)
    groups = {}
    for row in rows:
        groups.setdefault(row['case_id'], []).append(deepcopy(row))
    return [{'case_id': case_id, 'rows': case_rows} for case_id, case_rows in groups.items()]


def _image_entry(source, image_bank):
    entry = image_bank.get(source)
    if not isinstance(entry, dict) or set(entry) != {'metadata', 'image_url'}:
        raise ValueError('explicit_original_image_bank_entry_required')
    metadata, image = entry['metadata'], entry['image_url']
    if (not isinstance(metadata, dict) or set(metadata) - METADATA_FIELDS
            or metadata.get('source_filename') != source):
        raise ValueError('label_free_source_bound_image_metadata_required')
    if (not isinstance(image, dict) or not {'url'} <= set(image) or set(image) - {'url', 'detail'}
            or not isinstance(image['url'], str) or not DATA_URI.fullmatch(image['url'])
            or image.get('detail', 'auto') not in ('auto', 'low', 'high')):
        raise ValueError('saved_original_image_bytes_required')
    return deepcopy(entry)


def image_bank_from_requests(requests):
    """Adapt original system/user requests; reject assistant/history contamination.

    `requests` is an iterable of payload dictionaries or of message lists. A
    mapping question_id -> payload/messages is also accepted. Equal source names
    must have equal encoded pixels. Per-question image IDs are not reused as
    case-level IDs; question-specific figure labels remain in the input rows.
    """
    values = requests.values() if isinstance(requests, dict) else requests
    bank = {}
    for request in values:
        messages = request['messages'] if isinstance(request, dict) else request
        if not isinstance(messages, list) or [m.get('role') for m in messages] != ['system', 'user']:
            raise ValueError('original_system_user_request_without_history_required')
        content = messages[1]['content']
        if not isinstance(content, list):
            raise ValueError('original_multimodal_request_required')
        metadata = None
        for block in content:
            if block.get('type') == 'text' and str(block.get('text', '')).startswith(BOUND):
                if metadata is not None:
                    raise ValueError('image_binding_without_pixels')
                metadata = json.loads(block['text'][len(BOUND):])
            elif block.get('type') == 'image_url':
                if metadata is None:
                    raise ValueError('image_pixels_without_source_binding')
                source = _source(metadata.get('source_filename'))
                image = block['image_url']
                image = {'url': image} if isinstance(image, str) else image
                entry = _image_entry(source, {source: {'metadata': metadata, 'image_url': image}})
                if source in bank and bank[source]['image_url'] != entry['image_url']:
                    raise ValueError('same_source_has_conflicting_image_bytes_or_detail')
                if source not in bank:
                    bank[source] = entry
                metadata = None
        if metadata is not None:
            raise ValueError('image_binding_without_pixels')
    return bank


def _case_images(rows, image_bank):
    result = {}
    for row in rows:
        for source in row['images']:
            if source not in result:
                entry = _image_entry(source, image_bank)
                entry['metadata']['image_id'] = f'case_image:{len(result) + 1}'
                result[source] = entry
    return result


def _question_text(row, images):
    bindings = [{'source_filename': source,
                 'image_id': images[source]['metadata']['image_id'],
                 'figure_label': row.get('figure_labels', [images[s]['metadata'].get('figure_label', '')
                     for s in row['images']])[index]} for index, source in enumerate(row['images'])]
    return ('QUESTION_ID: ' + row['question_id'] + '\n' + row['question']
            + '\nIMAGE_BINDINGS: ' + json.dumps(bindings, ensure_ascii=False))


def _image_blocks(images, sources):
    blocks = []
    for source in sources:
        blocks.extend([{'type': 'text', 'text': BOUND + json.dumps(images[source]['metadata'], ensure_ascii=False)},
                       {'type': 'image_url', 'image_url': deepcopy(images[source]['image_url'])}])
    return blocks


def _payload(messages, max_tokens):
    return {'model': MODEL, 'messages': messages, 'temperature': .2, 'top_p': .95,
            'max_tokens': max_tokens, 'extra_body': {'enable_thinking': False}, 'stream': False}


def build_batch_request(case_rows, image_bank):
    validate_rows(case_rows, one_case=True)
    images = _case_images(case_rows, image_bank)
    text = 'CASE_ID: ' + case_rows[0]['case_id'] + '\n\n' + '\n\n'.join(
        _question_text(row, images) for row in case_rows)
    return _payload([{'role': 'system', 'content': BATCH_SYSTEM_PROMPT},
        {'role': 'user', 'content': [{'type': 'text', 'text': text}] + _image_blocks(images, images)}], 8192)


def build_sequential_request(case_rows, question_index, image_bank, prior_outputs):
    """Rebuild a case-local conversation from the exact earlier saved outputs.

    prior_outputs must contain exactly the preceding rows, with case_id,
    question_id, raw_response, and optional status. A None response is allowed
    only for request_failed or unparsed: no invented assistant response is injected. Images
    enter when first needed and appear only once in the complete conversation.
    """
    validate_rows(case_rows, one_case=True)
    if type(question_index) is not int or not 0 <= question_index < len(case_rows):
        raise ValueError('valid_current_question_index_required')
    if not isinstance(prior_outputs, list) or len(prior_outputs) != question_index:
        raise ValueError('exact_case_local_history_prefix_required')
    for row, output in zip(case_rows[:question_index], prior_outputs):
        if (not isinstance(output, dict) or set(output) - {'case_id', 'question_id', 'raw_response', 'status'}
                or output.get('question_id') != row['question_id'] or output.get('case_id') != row['case_id']):
            raise ValueError('cross_case_or_out_of_order_assistant_history_rejected')
        raw = output.get('raw_response')
        if not isinstance(raw, str) and not (raw is None and output.get('status') in {'request_failed', 'unparsed'}):
            raise ValueError('saved_assistant_text_or_explicit_failed_request_required')
    current_rows = case_rows[:question_index + 1]
    images = _case_images(current_rows, image_bank)
    messages, presented = [{'role': 'system', 'content': SYSTEM_PROMPT}], set()
    for index, row in enumerate(current_rows):
        newly_needed = list(dict.fromkeys(source for source in row['images'] if source not in presented))
        text = 'CASE_ID: ' + row['case_id'] + '\n' + _question_text(row, images)
        messages.append({'role': 'user', 'content': [{'type': 'text', 'text': text}] + _image_blocks(images, newly_needed)})
        presented.update(newly_needed)
        if index < question_index and prior_outputs[index]['raw_response'] is not None:
            messages.append({'role': 'assistant', 'content': prior_outputs[index]['raw_response']})
    return _payload(messages, 2048)


def _strict_object(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('duplicate_json_key')
            result[key] = value
        return result
    def constant(_):
        raise ValueError('nonfinite_json_value')
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError('empty_or_non_text_json_response')
    value = json.loads(raw, object_pairs_hook=pairs, parse_constant=constant)
    if not isinstance(value, dict):
        raise ValueError('question_id_mapping_required')
    return value


def parse_case_response(raw_response, case_rows, *, request_failed=False):
    """Parse one whole JSON object; never salvage letters from explanations.

    Missing questions remain missing; extras cannot be mapped onto another ID.
    An explicit legal answer remains valid if its brief reason is absent, with
    reason_missing recorded separately. Invalid JSON is retained verbatim.
    """
    validate_rows(case_rows, one_case=True)
    values, error = {}, None
    if not request_failed:
        try:
            values = _strict_object(raw_response)
        except (ValueError, TypeError):
            error = 'invalid_or_non_object_json'
    expected = {row['question_id'] for row in case_rows}
    records = []
    for row in case_rows:
        qid = row['question_id']; item = values.get(qid)
        legal = question_parts(row['question'])[1]
        answer = item.get('answer') if isinstance(item, dict) else None
        answer = answer if isinstance(answer, str) and answer in legal else None
        reason = item.get('reason') if isinstance(item, dict) and isinstance(item.get('reason'), str) else None
        missing = qid not in values
        if request_failed: status, rule = 'request_failed', 'case_request_failed'
        elif error: status, rule = 'unparsed', error
        elif missing: status, rule = 'unparsed', 'missing_question_id'
        elif answer is None: status, rule = 'unparsed', 'explicit_legal_answer_required'
        else: status, rule = 'completed', 'strict_json_question_id_and_legal_option'
        records.append({'question_id': qid, 'case_id': row['case_id'], 'answer': answer,
            'reason': reason, 'reason_missing': not bool(reason and reason.strip()),
            'status': status, 'missing': missing, 'parser_rule': rule,
            'raw_item': deepcopy(item), 'raw_response': raw_response})
    return {'case_id': case_rows[0]['case_id'], 'raw_response': raw_response,
        'json_error': error, 'unexpected_question_ids': sorted(set(values) - expected), 'records': records}


def project_case_response(case_rows, raw_response, *, request_failed=False):
    """Return one immutable-ready prediction per original question, in input order."""
    return parse_case_response(raw_response, case_rows, request_failed=request_failed)['records']


def project_sequential_response(row, raw_response, *, request_failed=False):
    """Use the same explicit single-answer parser as the independent baseline."""
    validate_rows([row], one_case=True)
    try:
        from .run_sampled_vlm import parse_answer
    except ImportError:
        from run_sampled_vlm import parse_answer
    result = ({'answer': None, 'status': 'request_failed', 'parser_rule': 'question_request_failed'}
              if request_failed else parse_answer(raw_response, question_parts(row['question'])[1]))
    return {'question_id': row['question_id'], 'case_id': row['case_id'],
            **result, 'raw_response': raw_response}
