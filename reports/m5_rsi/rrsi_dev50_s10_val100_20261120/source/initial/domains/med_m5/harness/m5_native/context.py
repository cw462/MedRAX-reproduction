import copy,json

def tool_failure_reason(record):
    """Recognize actual failed MedRAX envelopes, including nested worker errors."""
    if record.get('status')!='completed':return 'outer_status_not_completed'
    if record.get('observation') is None:return 'missing_observation'
    for event in record.get('actual_model_events',[]):
        if event.get('status')!='completed':return 'backend_model_event_not_completed'
    def inspect(value):
        if isinstance(value,dict):
            if 'error' in value and value['error'] is not None and value['error'] is not False:
                return 'nested_backend_error'
            analysis=value.get('analysis_status')
            if analysis is not None and analysis not in ('completed','completed_no_finding','not_applicable','success'):
                return 'analysis_status_not_completed'
            if value.get('status') in ('failed','error','unknown','started_unknown','started'):
                return 'nested_status_not_completed'
            for item in value.values():
                failure=inspect(item)
                if failure:return failure
        elif isinstance(value,(list,tuple)):
            for item in value:
                failure=inspect(item)
                if failure:return failure
        return None
    return inspect(record['observation'])
def model_memory_entry(row, result):
    observations = result.get('observations') or result.get('inherited_observations') or []
    evidence = [{key: copy.deepcopy(value[key]) for key in ('tool', 'image_index', 'observation') if key in value}
                for value in observations if tool_failure_reason(value) is None]
    return {'question_id': row['question_id'], 'question': row['question'], 'options': row.get('options', {}),
            'previous_answer': result.get('answer'), 'previous_model_reason': result.get('reason'),
            'previous_status': result.get('status'), 'tool_evidence': evidence,
            'provenance': 'earlier_model_output_not_ground_truth'}
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
