"""Dataset-qualified same-image feedback, released after an immutable prediction.

R47's atomic JSON publication is reused, while grouping, cohorts and policy
validation are specific to the two new datasets. No image bytes are inspected.
"""
import copy
import json
from pathlib import Path, PurePosixPath

from cxr_image_memory_gt_r47 import now, safe_qid, save_once, validate_protocol
from cxr_image_memory_r44 import read, rows, memory_entry as model_memory_entry, tool_failure_reason

SCHEMA = 'same_image_ground_truth_feedback_r48_20261108'
DATASETS = {
    'slake': {'questions': 114, 'baseline_arm': 'M43', 'arm': 'M43-IM-GT-SLAKE'},
    'vqarad': {'questions': 116, 'baseline_arm': 'M42', 'arm': 'M42-IM-GT-VQARAD'},
}
POLICY_LIMITS = {'M': (4, 2), 'M-S41': (6, 4)}
INPUT_FIELDS = {'question_id', 'question', 'images', 'image_id', 'source', 'options'}
BASELINE_FIELDS = {'question_id', 'answer', 'reason', 'status', 'observations',
                   'inherited_observations', 'technical_failure'}


def relative_image(name):
    if not isinstance(name, str) or not name:
        raise ValueError('invalid_image_path_identity')
    value = PurePosixPath(name.replace('\\', '/'))
    if value.is_absolute() or '..' in value.parts or ':' in str(value):
        raise ValueError('image_path_must_be_relative')
    return str(value)


def schedule(inputs, dataset):
    """Use the published canonical ID, falling back to ordered relative paths."""
    if dataset not in DATASETS:
        raise ValueError('unsupported_dataset')
    seen, bindings, result = {}, {}, []
    for row in inputs:
        qid = safe_qid(row['question_id'])
        images = [relative_image(name) for name in row['images']]
        if not images:
            raise ValueError('no_original_images')
        image_id = row.get('image_id')
        identity = ['image_id', image_id] if image_id is not None else ['relative_paths', images]
        key = dataset + ':' + json.dumps(identity, ensure_ascii=False, separators=(',', ':'), sort_keys=True)
        if key in bindings and bindings[key] != images:
            raise ValueError('canonical_image_identity_path_conflict')
        bindings[key] = images
        prior = seen.setdefault(key, [])
        result.append({'dataset': dataset, 'question_id': qid, 'image_key': key, 'previous_ids': list(prior)})
        prior.append(qid)
    return result


def baseline_record(row):
    return {key: copy.deepcopy(value) for key, value in row.items() if key in BASELINE_FIELDS}


def summary(frozen):
    repeats = [item for item in frozen['order'] if item['previous_ids']]
    groups = len(frozen['order']) - len(repeats)
    return {'dataset': frozen['dataset'], 'arm': frozen['arm'], 'questions': len(frozen['inputs']),
            'image_groups': groups, 'reused_baseline': groups, 'repeat_questions': len(repeats),
            'repeat_policy_counts': {kind: sum(frozen['policy'][item['question_id']]['kind'] == kind for item in repeats)
                                     for kind in sorted(POLICY_LIMITS)},
            'new_main_ceiling': sum(POLICY_LIMITS[frozen['policy'][item['question_id']]['kind']][0] for item in repeats),
            'new_tool_ceiling': sum(POLICY_LIMITS[frozen['policy'][item['question_id']]['kind']][1] for item in repeats)}


def validate_frozen(frozen):
    dataset = frozen['dataset']
    spec = DATASETS.get(dataset)
    if spec is None or frozen.get('schema') != SCHEMA or frozen.get('arm') != spec['arm'] or frozen.get('baseline_arm') != spec['baseline_arm']:
        raise ValueError('invalid_dataset_arm_contract')
    inputs = frozen['inputs']
    ids = [safe_qid(row['question_id']) for row in inputs]
    if len(ids) != spec['questions'] or len(set(ids)) != len(ids):
        raise ValueError('full_dataset_cohort_required')
    for row in inputs:
        if set(row) - INPUT_FIELDS or not isinstance(row.get('question'), str):
            raise ValueError('unexpected_inference_fields')
    if frozen['order'] != schedule(inputs, dataset):
        raise ValueError('original_semantic_order_required')
    if set(frozen['baseline']) != set(ids) or set(frozen['policy']) != set(ids):
        raise ValueError('cohort_mismatch')
    for qid in ids:
        prior = frozen['baseline'][qid]
        if set(prior) - BASELINE_FIELDS or prior.get('question_id') != qid:
            raise ValueError('unexpected_baseline_fields')
        policy = frozen['policy'][qid]
        if set(policy) != {'kind', 'conditioning', 'selected_skill_ids'}:
            raise ValueError('invalid_frozen_policy')
        if policy['kind'] not in POLICY_LIMITS or (dataset == 'vqarad' and policy['kind'] != 'M'):
            raise ValueError('invalid_dataset_policy')
        if policy['kind'] == 'M-S41':
            if not policy['selected_skill_ids'] or not isinstance(policy['conditioning'], str) or not policy['conditioning'].strip():
                raise ValueError('original_selected_S41_skill_required')
        elif policy['conditioning'] is not None or policy['selected_skill_ids']:
            raise ValueError('original_M_policy_required')
    if (frozen['memory_max_chars'], frozen['memory_max_entries']) != (12000, 8):
        raise ValueError('original_memory_budget_required')
    validate_protocol(frozen['protocol'])
    counts = summary(frozen)
    for key in ('new_main_ceiling', 'new_tool_ceiling'):
        if frozen[key] != counts[key]:
            raise ValueError('derived_cohort_budget_changed')
    if set(frozen['reference_files']) != set(ids):
        raise ValueError('invalid_feedback_manifest')
    for qid, item in frozen['reference_files'].items():
        if item != {'dataset': dataset, 'question_id': qid, 'file': qid + '.json'}:
            raise ValueError('invalid_reference_file_manifest')
    return ids


def prediction_binding(prediction):
    """Semantic JSON binding, with no file, pixel or byte digest."""
    return copy.deepcopy(prediction)


def commit_prediction_event(out, arm, item, ordinal):
    out = Path(out)
    qid = safe_qid(item['question_id'])
    path = out / 'predictions' / arm / (qid + '.json')
    if not path.is_file():
        raise ValueError('event_before_prediction_save')
    prediction = read(path)
    if prediction.get('question_id') != qid or prediction.get('arm') != arm or prediction.get('dataset') != item['dataset']:
        raise ValueError('prediction_identity_changed')
    event_path = out / 'prediction_events' / (qid + '.json')
    event = {'schema': 'immutable_saved_prediction_r48', 'dataset': item['dataset'], 'arm': arm,
             'question_id': qid, 'ordinal': ordinal, 'image_key': item['image_key'],
             'saved_prediction': prediction_binding(prediction)}
    save_once(event_path, event)
    return path, event_path, event


class ReferenceVault:
    """Only the current single-file annotation can open after prediction + event."""
    def __init__(self, directory, dataset, arm, manifest):
        self.directory, self.dataset, self.arm, self.manifest = Path(directory), dataset, arm, manifest

    def after_prediction(self, qid, prediction_path, prediction_event_path):
        safe_qid(qid)
        prediction_path, prediction_event_path = Path(prediction_path), Path(prediction_event_path)
        if not prediction_path.is_file() or not prediction_event_path.is_file():
            raise ValueError('reference_before_prediction_and_event_save')
        prediction, event = read(prediction_path), read(prediction_event_path)
        if (prediction.get('question_id') != qid or prediction.get('dataset') != self.dataset
                or prediction.get('arm') != self.arm or event.get('question_id') != qid
                or event.get('dataset') != self.dataset or event.get('arm') != self.arm
                or event.get('saved_prediction') != prediction_binding(prediction)):
            raise ValueError('saved_prediction_event_binding_changed')
        if self.manifest[qid] != {'dataset': self.dataset, 'question_id': qid, 'file': qid + '.json'}:
            raise ValueError('invalid_reference_file_manifest')
        reference = read(self.directory / (qid + '.json'))
        if (reference.get('dataset') != self.dataset or reference.get('question_id') != qid
                or not isinstance(reference.get('answer'), str) or not reference['answer'].strip()
                or ('answer_text' in reference and not isinstance(reference['answer_text'], str))):
            raise ValueError('invalid_reference_record')
        return reference


def feedback_after_save(out, arm, item, ordinal, manifest, load_reference):
    prediction_path, prediction_event_path, saved = commit_prediction_event(out, arm, item, ordinal)
    qid, dataset = item['question_id'], item['dataset']
    if manifest[qid] != {'dataset': dataset, 'question_id': qid, 'file': qid + '.json'}:
        raise ValueError('invalid_reference_file_manifest')
    binding = {'schema': 'post_prediction_dataset_feedback_r48', 'dataset': dataset, 'arm': arm,
               'question_id': qid, 'ordinal': ordinal, 'image_key': item['image_key'],
               'saved_prediction': saved['saved_prediction'], 'reference_file': qid + '.json',
               'provenance': 'dataset_annotation_feedback_not_patient_history',
               'timing': 'reference_loaded_only_after_immutable_prediction_and_event_save'}
    path = Path(out) / 'feedback_events' / (qid + '.json')
    if path.exists():
        event = read(path)
        if (set(event) != set(binding) | {'reference_annotation', 'released_at'}
                or any(event.get(key) != value for key, value in binding.items())):
            raise ValueError('immutable_feedback_binding_changed')
    else:
        reference = load_reference(qid, prediction_path, prediction_event_path)
        if reference.get('dataset') != dataset or reference.get('question_id') != qid:
            raise ValueError('reference_callback_identity_changed')
        annotation = {key: copy.deepcopy(reference[key]) for key in ('answer', 'answer_text') if key in reference}
        event = dict(binding, reference_annotation=annotation, released_at=now())
        _validate_annotation(annotation)
        save_once(path, event)
    _validate_annotation(event['reference_annotation'])
    return event


def _validate_annotation(annotation):
    if (set(annotation) - {'answer', 'answer_text'} or not isinstance(annotation.get('answer'), str)
            or not annotation['answer'].strip()
            or ('answer_text' in annotation and not isinstance(annotation['answer_text'], str))):
        raise ValueError('invalid_saved_feedback')


def memory_entry(row, result, event):
    if (result.get('question_id') != row['question_id'] or event['question_id'] != row['question_id']
            or result.get('dataset') != event['dataset'] or result != event['saved_prediction']):
        raise ValueError('memory_prediction_binding_changed')
    entry = model_memory_entry(row, result)
    entry['dataset'] = event['dataset']
    entry['reference_annotation'] = copy.deepcopy(event['reference_annotation'])
    if entry['reference_annotation']['answer'] in (row.get('options') or {}):
        entry['reference_annotation']['option_text'] = row['options'][entry['reference_annotation']['answer']]
    entry['provenance'] = 'unchanged_prior_model_output_with_post_prediction_dataset_feedback'
    entry['_feedback_event'] = copy.deepcopy(event)
    return entry


def context(entries, item, ordinal, max_chars=12000, max_entries=8):
    allowed = set(item['previous_ids'])
    eligible = []
    for entry in entries:
        event = entry['_feedback_event']
        if (entry['question_id'] in allowed and entry['question_id'] != item['question_id']
                and entry['dataset'] == item['dataset'] == event['dataset']
                and event['image_key'] == item['image_key'] and event['ordinal'] < ordinal):
            eligible.append(entry)
    by_id = {entry['question_id']: entry for entry in eligible}
    if len(by_id) != len(eligible):
        raise ValueError('duplicate_memory_entry')
    if set(by_id) != allowed:
        raise ValueError('incomplete_committed_same_image_prefix')
    eligible = [by_id[qid] for qid in item['previous_ids']]
    picked, used = [], 0
    for entry in reversed(eligible[-max_entries:]):
        displayed = {key: copy.deepcopy(value) for key, value in entry.items() if not key.startswith('_')}
        displayed['tool_evidence'] = [value for value in displayed['tool_evidence'] if len(json.dumps(value, ensure_ascii=False)) <= 4000]
        size = len(json.dumps(displayed, ensure_ascii=False))
        if used + size <= max_chars:
            picked.append(displayed)
            used += size
    picked.reverse()
    if not picked:
        if allowed:
            raise ValueError('repeat_question_has_empty_memory')
        return None, []
    prompt = ('Earlier questions about the EXACT SAME supplied original image(s), in chronological order. '
              'Prior model answers, reasons and statuses remain unchanged fallible judgments. '
              'reference_annotation is the dataset answer released AFTER its own earlier prediction and saved event. '
              'These annotations are feedback for their originating questions, not patient history or clinical adjudication. '
              'Bind every reference answer to its own question and options; never transfer an earlier option letter to the CURRENT question. '
              'Healthy tool observations are auxiliary evidence. Reinspect the original image and answer the CURRENT wording. '
              'No current or future reference, future question/options, correctness flag, other-image or other-dataset memory is supplied.\n'
              + json.dumps(picked, ensure_ascii=False))
    return prompt, [entry['question_id'] for entry in picked]


def validate_resume_prefix(out, order, arm):
    out, ids = Path(out), [item['question_id'] for item in order]
    predictions = {path.stem for path in (out / 'predictions' / arm).glob('*.json')}
    count = len(predictions)
    if predictions != set(ids[:count]):
        raise ValueError('saved_predictions_not_processed_prefix')
    for directory in ('prediction_events', 'feedback_events'):
        actual = {path.stem for path in (out / directory).glob('*.json')}
        if actual not in (set(ids[:count]), set(ids[:max(0, count - 1)])):
            raise ValueError('saved_' + directory + '_not_committed_prefix')
    events = {path.stem for path in (out / 'prediction_events').glob('*.json')}
    feedback = {path.stem for path in (out / 'feedback_events').glob('*.json')}
    if not feedback <= events:
        raise ValueError('feedback_without_prediction_event')
    contexts = {path.stem for path in (out / 'memory_context').glob('*.json')}
    if contexts not in (set(ids[:count]), set(ids[:min(len(ids), count + 1)])):
        raise ValueError('saved_context_not_processed_prefix')


def assert_closed_sends(out, arm, *, allow_missing_receipt=False):
    for sent in (Path(out) / 'calls' / arm).glob('*/*/started.json'):
        folder = sent.parent
        if not (folder / 'response.json').is_file():
            raise RuntimeError('unknown_sent_no_reissue:' + folder.parent.name)
        receipt = folder / 'result.json'
        if not receipt.is_file():
            if allow_missing_receipt:
                continue
            raise RuntimeError('sent_request_receipt_missing:' + folder.parent.name)
        value = read(receipt)
        if value.get('error') or value.get('response_received') is not True:
            raise RuntimeError('unhealthy_request_receipt_no_reissue:' + folder.parent.name)
