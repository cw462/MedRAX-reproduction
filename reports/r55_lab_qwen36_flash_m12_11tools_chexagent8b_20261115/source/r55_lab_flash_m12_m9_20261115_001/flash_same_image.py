import copy
import json

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
        if not allowed:
            return None, []
        # Preserve the newest prior question and released feedback when bulky
        # observations prevent any whole record from fitting the existing budget.
        record = {key: copy.deepcopy(value) for key, value in eligible[-1].items() if not key.startswith('_')}
        evidence = [value for value in record['tool_evidence'] if len(json.dumps(value, ensure_ascii=False)) <= 4000]
        record['tool_evidence'] = []
        if len(json.dumps(record, ensure_ascii=False)) > max_chars:
            record['previous_model_reason'] = None
        if len(json.dumps(record, ensure_ascii=False)) > max_chars:
            raise ValueError('same_image_required_fields_exceed_context_budget')
        for observation in evidence:
            record['tool_evidence'].append(observation)
            if len(json.dumps(record, ensure_ascii=False)) > max_chars:
                record['tool_evidence'].pop()
        picked = [record]
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
