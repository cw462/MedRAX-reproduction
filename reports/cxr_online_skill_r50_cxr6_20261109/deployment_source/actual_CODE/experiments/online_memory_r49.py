"""R47 same-image memory primitives, preserved for the R49 online composition."""
import copy,json,os,uuid
from datetime import datetime,timezone
from pathlib import Path
from cxr_online_primitives_r49 import memory_entry as model_memory_entry,read
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
        event_path = prediction_path.parents[2] / 'prediction_events' / (qid + '.json')
        if not event_path.is_file():
            raise ValueError('reference_before_prediction_event_save')
        event = read(event_path)
        if event.get('question_id') != qid or event.get('saved_prediction') != prediction:
            raise ValueError('saved_prediction_event_binding_changed')
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
        'This same-image section contains no current or future reference answer, future question/options, or other-image episodes. Separately supplied procedural skills may derive from earlier completed cases.\n'
        + json.dumps(picked, ensure_ascii=False)
    )
    return prompt, [entry['question_id'] for entry in picked]
