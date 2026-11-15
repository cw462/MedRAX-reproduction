"""Post-prediction dataset feedback for the exact same-image processed prefix.

Inference memory never opens the reference corpus or reference vault. Only the
post-save callback opens one raw reference record, then journals its annotation.
"""
import copy
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import uuid

from cxr_image_memory_r44 import (
    memory_entry as model_memory_entry, read, rows, tool_failure_reason,
)

ARM = 'M43-IM-GT'
SCHEMA = 'M43_same_image_ground_truth_feedback_r47_20261108'


def now():
    return datetime.now(timezone.utc).isoformat()


def save_once(path, value):
    """Atomically publish JSON once; identical restarts never rewrite a file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if read(path) != value:
            raise ValueError('immutable_artifact_changed:' + path.name)
        return False
    temporary = path.with_name('.' + path.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        with temporary.open('x', encoding='utf-8') as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2)
            handle.write('\n')
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary, path)
        except FileExistsError:
            if read(path) != value:
                raise ValueError('immutable_artifact_changed:' + path.name) from None
            return False
    finally:
        if temporary.exists():
            temporary.unlink()
    return True


def safe_qid(qid):
    if not isinstance(qid, str) or not qid or Path(qid).name != qid or '/' in qid or '\\' in qid or qid in ('.', '..'):
        raise ValueError('unsafe_question_id')
    return qid


def validate_protocol(protocol):
    expected = {'model': 'qwen3.7-plus', 'temperature': 0.2, 'top_p': 0.95,
                'enable_thinking': False, 'max_output_tokens': 2048}
    for key, value in expected.items():
        if protocol.get(key) != value or (key == 'enable_thinking' and protocol[key] is not False):
            raise ValueError('original_model_setting_required:' + key)


def validate_frozen(frozen, *, require_reference_manifest=True):
    inputs = frozen['inputs']
    ids = [safe_qid(row['question_id']) for row in inputs]
    if len(ids) != 618 or len(set(ids)) != 618:
        raise ValueError('full_CheXbench618_required')
    allowed = {'question_id', 'question', 'images', 'image_id', 'source', 'options'}
    if any(set(row) - allowed for row in inputs):
        raise ValueError('unexpected_inference_fields')
    if [item['question_id'] for item in frozen['order']] != ids:
        raise ValueError('original_order_required')
    seen = {}
    for item in frozen['order']:
        prior = seen.setdefault(item['image_key'], [])
        if item['previous_ids'] != prior:
            raise ValueError('invalid_same_image_prefix')
        prior.append(item['question_id'])
    if len(seen) != 488 or sum(bool(x['previous_ids']) for x in frozen['order']) != 130:
        raise ValueError('original_488groups_130fresh_required')
    if set(frozen['baseline']) != set(ids) or set(frozen['policy']) != set(ids):
        raise ValueError('cohort_mismatch')
    allowed_baseline = {'question_id', 'answer', 'reason', 'status', 'observations', 'inherited_observations', 'technical_failure'}
    if any(set(value) - allowed_baseline for value in frozen['baseline'].values()):
        raise ValueError('unexpected_baseline_fields')
    if any(value not in ('M', 'C41') for value in frozen['policy'].values()):
        raise ValueError('invalid_frozen_policy')
    counts = {name: sum(frozen['policy'][item['question_id']] == name for item in frozen['order'] if item['previous_ids']) for name in ('M', 'C41')}
    if counts != {'M': 68, 'C41': 62} or frozen['repeated_policy_counts'] != counts:
        raise ValueError('original_policy_counts_required')
    if (frozen['new_main_ceiling'], frozen['new_tool_ceiling']) != (644, 384):
        raise ValueError('original_cohort_budget_required')
    if (frozen['memory_max_chars'], frozen['memory_max_entries']) != (12000, 8):
        raise ValueError('original_memory_budget_required')
    validate_protocol(frozen['protocol'])
    if require_reference_manifest:
        if frozen.get('schema') != SCHEMA or set(frozen['reference_files']) != set(ids):
            raise ValueError('invalid_feedback_manifest')
        for qid, item in frozen['reference_files'].items():
            if set(item) != {'file'} or item['file'] != qid + '.json':
                raise ValueError('invalid_reference_file_manifest')
    return ids


class ReferenceVault:
    """One reference-file read, permitted only after its prediction is on disk."""
    def __init__(self, directory, manifest):
        self.directory = Path(directory)
        self.manifest = manifest

    def after_prediction(self, qid, prediction_path):
        safe_qid(qid)
        prediction_path = Path(prediction_path)
        if not prediction_path.is_file():
            raise ValueError('reference_before_prediction_save')
        prediction = read(prediction_path)
        if prediction.get('question_id') != qid:
            raise ValueError('prediction_identity_changed')
        item = self.manifest[qid]
        if item['file'] != qid + '.json':
            raise ValueError('invalid_reference_file_manifest')
        path = self.directory / item['file']
        reference = read(path)
        if reference.get('question_id') != qid or not isinstance(reference.get('answer'), str) or not reference['answer'].strip():
            raise ValueError('invalid_reference_record')
        if 'answer_text' in reference and not isinstance(reference['answer_text'], str):
            raise ValueError('invalid_reference_answer_text')
        return reference


def feedback_after_save(out, item, ordinal, reference_manifest, load_reference):
    """Commit or validate one immutable feedback event; never grade a prediction."""
    out = Path(out)
    qid = safe_qid(item['question_id'])
    prediction_path = out / 'predictions' / ARM / (qid + '.json')
    if not prediction_path.is_file():
        raise ValueError('feedback_before_prediction_save')
    prediction = read(prediction_path)
    if prediction.get('question_id') != qid:
        raise ValueError('prediction_identity_changed')
    reference_file = reference_manifest[qid]['file']
    if reference_file != qid + '.json':
        raise ValueError('invalid_reference_file_manifest')
    binding = {
        'schema': 'post_prediction_dataset_feedback_v1', 'question_id': qid,
        'ordinal': ordinal, 'image_key': item['image_key'],
        'saved_prediction': {key: copy.deepcopy(prediction.get(key)) for key in
                             ('answer', 'reason', 'status', 'prediction_saved_at')},
        'reference_file': reference_file,
        'provenance': 'dataset_annotation_feedback_not_patient_history',
        'timing': 'reference_loaded_only_after_immutable_prediction_save',
    }
    path = out / 'feedback_events' / (qid + '.json')
    if path.exists():
        event = read(path)
        if set(event) != set(binding) | {'reference_annotation', 'released_at'} or any(event.get(k) != value for k, value in binding.items()):
            raise ValueError('immutable_feedback_binding_changed')
        if not isinstance(event['reference_annotation'].get('answer'), str):
            raise ValueError('invalid_saved_feedback')
        if 'answer_text' in event['reference_annotation'] and not isinstance(event['reference_annotation']['answer_text'], str):
            raise ValueError('invalid_saved_feedback')
        return event
    reference = load_reference(qid, prediction_path)
    annotation = {key: copy.deepcopy(reference[key]) for key in ('answer', 'answer_text') if key in reference}
    if reference.get('question_id') != qid or not isinstance(annotation.get('answer'), str) or not annotation['answer'].strip():
        raise ValueError('invalid_reference_callback')
    event = dict(binding, reference_annotation=annotation, released_at=now())
    save_once(path, event)
    return event


def memory_entry(row, result, event):
    qid = row['question_id']
    if event['question_id'] != qid or result.get('question_id') != qid:
        raise ValueError('memory_identity_changed')
    entry = model_memory_entry(row, result)
    annotation = copy.deepcopy(event['reference_annotation'])
    options = row.get('options') or {}
    if annotation['answer'] in options:
        annotation['option_text'] = options[annotation['answer']]
    entry['reference_annotation'] = annotation
    entry['provenance'] = 'unchanged_prior_model_output_with_post_prediction_dataset_feedback'
    # Internal binding is omitted from the model-facing serialization.
    entry['_feedback_event'] = copy.deepcopy(event)
    return entry


def context(entries, current_item, ordinal, max_chars=12000, max_entries=8):
    """Select whole records from exactly this image's already-processed prefix."""
    allowed = set(current_item['previous_ids'])
    eligible = []
    for entry in entries:
        event = entry['_feedback_event']
        if (entry['question_id'] in allowed and entry['question_id'] != current_item['question_id']
                and event['image_key'] == current_item['image_key'] and event['ordinal'] < ordinal):
            eligible.append(entry)
    # Expected order is authoritative; reject duplicates and omit unrelated/future entries.
    by_id = {entry['question_id']: entry for entry in eligible}
    if len(by_id) != len(eligible):
        raise ValueError('duplicate_memory_entry')
    eligible = [by_id[qid] for qid in current_item['previous_ids'] if qid in by_id]
    if set(by_id) != allowed:
        raise ValueError('incomplete_committed_same_image_prefix')
    picked, used = [], 0
    for entry in reversed(eligible[-max_entries:]):
        displayed = {key: copy.deepcopy(value) for key, value in entry.items() if not key.startswith('_')}
        displayed['tool_evidence'] = [value for value in displayed['tool_evidence'] if len(json.dumps(value, ensure_ascii=False)) <= 4000]
        size = len(json.dumps(displayed, ensure_ascii=False))
        if used + size > max_chars:
            continue
        picked.append(displayed)
        used += size
    picked.reverse()
    if not picked:
        if allowed:
            raise ValueError('repeat_question_has_empty_memory')
        return None, []
    prompt = (
        'Earlier questions about the EXACT SAME supplied original image(s), in chronological order. '
        'The prior model answers, reasons and statuses are unchanged fallible model judgments. '
        'reference_annotation contains the dataset reference answer released AFTER that earlier prediction was saved. '
        'These are feedback annotations for their originating questions, not additional patient history or clinical adjudication. '
        'Bind each reference answer to its own earlier question and options; never copy an earlier option letter to the CURRENT question. '
        'Tool observations are auxiliary evidence. Reinspect the original pixels and answer the CURRENT wording and options. '
        'No current or future reference answer, future question/options, correctness flag, or other-image memory is supplied.\n'
        + json.dumps(picked, ensure_ascii=False)
    )
    return prompt, [entry['question_id'] for entry in picked]


def validate_resume_prefix(out, order):
    """A crash may leave the last prediction awaiting feedback or next context."""
    out = Path(out)
    ids = [item['question_id'] for item in order]
    predictions = {path.stem for path in (out / 'predictions' / ARM).glob('*.json')}
    feedback = {path.stem for path in (out / 'feedback_events').glob('*.json')}
    contexts = {path.stem for path in (out / 'memory_context').glob('*.json')}
    count = len(predictions)
    if predictions != set(ids[:count]):
        raise ValueError('saved_predictions_not_processed_prefix')
    if feedback not in (set(ids[:count]), set(ids[:max(0, count - 1)])):
        raise ValueError('saved_feedback_not_committed_prefix')
    if contexts not in (set(ids[:count]), set(ids[:min(len(ids), count + 1)])):
        raise ValueError('saved_context_not_processed_prefix')


def assert_no_unknown_sends(out):
    for sent in (Path(out) / 'calls' / ARM).glob('*/*/started.json'):
        if not (sent.parent / 'response.json').exists():
            raise RuntimeError('unknown_sent_no_reissue:' + sent.parent.parent.name)
        receipt_path = sent.parent / 'result.json'
        if receipt_path.exists():
            receipt = read(receipt_path)
            if receipt.get('error') or receipt.get('response_received') is not True:
                raise RuntimeError('unhealthy_request_receipt_no_reissue:' + sent.parent.parent.name)
