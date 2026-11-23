"""Synthetic E2 contracts; no API, filesystem images, references or ledgers."""
import json
from copy import deepcopy
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import case_answering as ca


def row(qid='q1', case='case_a', images=None):
    sources = images or ['figures/a.png']
    return {'question_id': qid, 'case_id': case,
        'question': f'Complete stem for {qid}. Compare initial and follow-up.\nA) First complete option\n    continued text\nB) Second complete option',
        'images': sources, 'figure_labels': [f'Figure {i+1}' for i in range(len(sources))]}


def bank():
    return {source: {'metadata': {'source_filename': source, 'image_id': 'image:1',
                                 'figure_label': f'Figure {index}', 'size': [1, 1], 'role': 'original'},
                     'image_url': {'url': f'data:image/png;base64,{data}', 'detail': 'auto'}}
            for index, (source, data) in enumerate(
                [('figures/a.png', 'YQ=='), ('figures/b.png', 'Yg=='), ('figures/c.png', 'Yw==')], 1)}


def image_urls(payload):
    return [block['image_url']['url'] for message in payload['messages']
            if isinstance(message['content'], list) for block in message['content']
            if block['type'] == 'image_url']


def test_grouping_preserves_frozen_first_case_and_within_case_source_order():
    rows = [row('a1'), row('b1', 'case_b'), row('a2'), row('c1', 'case_c')]
    groups = ca.group_cases(rows)
    assert [group['case_id'] for group in groups] == ['case_a', 'case_b', 'case_c']
    assert [q['question_id'] for q in groups[0]['rows']] == ['a1', 'a2']
    groups[0]['rows'][0]['question'] = 'caller mutation'
    assert rows[0]['question'].startswith('Complete stem')


@pytest.mark.parametrize('field', ['answer', 'reference', 'label', 'ground_truth', 'prior_predictions'])
def test_label_or_prediction_fields_are_rejected_in_input(field):
    bad = dict(row(), **{field: 'B'})
    with pytest.raises(ValueError, match='label_free'):
        ca.group_cases([bad])
    with pytest.raises(ValueError, match='label_free'):
        ca.build_batch_request([bad], bank())


def test_batch_retains_all_text_and_options_with_unique_source_union():
    rows = [row('q1', images=['figures/a.png', 'figures/b.png']),
            row('q2', images=['figures/b.png', 'figures/c.png'])]
    original_rows, original_bank = deepcopy(rows), bank()
    payload = ca.build_batch_request(rows, original_bank)
    text = payload['messages'][1]['content'][0]['text']
    assert all(item['question'] in text and 'QUESTION_ID: '+item['question_id'] in text for item in rows)
    assert len(image_urls(payload)) == 3
    assert payload['max_tokens'] == 8192 and payload['model'] == 'qwen3.7-plus'
    assert payload['extra_body'] == {'enable_thinking': False}
    assert payload['temperature'] == .2 and payload['top_p'] == .95
    assert rows == original_rows and original_bank == bank()
    metadata = [json.loads(b['text'][len(ca.BOUND):]) for b in payload['messages'][1]['content']
                if b['type'] == 'text' and b['text'].startswith(ca.BOUND)]
    assert [m['source_filename'] for m in metadata] == ['figures/a.png', 'figures/b.png', 'figures/c.png']
    assert [m['image_id'] for m in metadata] == ['case_image:1', 'case_image:2', 'case_image:3']


def test_requests_reject_mixed_cases_and_missing_or_labelled_image_bank():
    with pytest.raises(ValueError, match='one_case'):
        ca.build_batch_request([row('q1'), row('q2', 'case_b')], bank())
    with pytest.raises(ValueError, match='image_bank'):
        ca.build_batch_request([row()], {})
    labelled = bank(); labelled['figures/a.png']['metadata']['answer'] = 'A'
    with pytest.raises(ValueError, match='label_free'):
        ca.build_batch_request([row()], labelled)


def test_sequential_retains_only_prior_case_outputs_and_deduplicates_images():
    rows = [row('q1'), row('q2', images=['figures/a.png', 'figures/b.png']),
            row('future', images=['figures/c.png'])]
    raw = 'Unexpected but original output.\nAnswer: Z\nReason: Preserve me verbatim.'
    history = [{'case_id': 'case_a', 'question_id': 'q1', 'raw_response': raw, 'status': 'unparsed'}]
    payload = ca.build_sequential_request(rows, 1, bank(), history)
    assert [m['role'] for m in payload['messages']] == ['system', 'user', 'assistant', 'user']
    assert payload['messages'][2]['content'] == raw
    assert len(image_urls(payload)) == 2 and payload['max_tokens'] == 2048
    text = json.dumps(payload)
    assert 'future' not in text and 'figures/c.png' not in text
    assert history[0]['raw_response'] == raw


def test_case_change_starts_fresh_and_cross_case_history_cannot_be_injected():
    old = [{'case_id': 'case_a', 'question_id': 'q1', 'raw_response': 'OLD CASE ANSWER'}]
    new_rows = [row('new1', 'case_b'), row('new2', 'case_b')]
    first = ca.build_sequential_request(new_rows, 0, bank(), [])
    assert len(first['messages']) == 2 and 'OLD CASE' not in json.dumps(first)
    with pytest.raises(ValueError, match='history_prefix'):
        ca.build_sequential_request(new_rows, 0, bank(), old)
    with pytest.raises(ValueError, match='cross_case'):
        ca.build_sequential_request(new_rows, 1, bank(), old)
    contaminated = [{'case_id': 'case_b', 'question_id': 'new1', 'raw_response': 'A', 'reference': 'B'}]
    with pytest.raises(ValueError, match='cross_case'):
        ca.build_sequential_request(new_rows, 1, bank(), contaminated)


def test_failed_prior_request_does_not_invent_assistant_text():
    rows = [row('q1'), row('q2')]
    prior = [{'case_id': 'case_a', 'question_id': 'q1', 'raw_response': None, 'status': 'request_failed'}]
    payload = ca.build_sequential_request(rows, 1, bank(), prior)
    assert [m['role'] for m in payload['messages']] == ['system', 'user', 'user']
    assert len(image_urls(payload)) == 1
    prior[0]['status'] = 'completed'
    with pytest.raises(ValueError, match='saved_assistant'):
        ca.build_sequential_request(rows, 1, bank(), prior)


def test_existing_request_adapter_deduplicates_without_mutation_or_history():
    original = ca.build_batch_request([row()], bank())
    before = deepcopy(original)
    adapted = ca.image_bank_from_requests({'q1': original, 'q2': original['messages']})
    assert len(adapted) == 1 and original == before
    conflicting = deepcopy(original)
    conflicting['messages'][1]['content'][-1]['image_url']['url'] = 'data:image/png;base64,Yg=='
    with pytest.raises(ValueError, match='conflicting_image'):
        ca.image_bank_from_requests([original, conflicting])
    original['messages'].append({'role': 'assistant', 'content': 'Old answer'})
    with pytest.raises(ValueError, match='without_history'):
        ca.image_bank_from_requests([original])


def test_batch_projection_keeps_question_order_and_legal_answers_when_reason_missing():
    rows = [row('q1'), row('q2')]
    raw = '{"q2":{"answer":"B","reason":"Second finding"},"q1":{"answer":"A"}}'
    parsed = ca.parse_case_response(raw, rows)
    assert [r['question_id'] for r in parsed['records']] == ['q1', 'q2']
    assert [r['answer'] for r in parsed['records']] == ['A', 'B']
    assert parsed['records'][0]['reason_missing'] is True
    assert all(r['status'] == 'completed' and r['raw_response'] == raw for r in parsed['records'])
    assert ca.project_case_response(rows, raw) == parsed['records']


def test_missing_illegal_and_unexpected_questions_are_never_reassigned_or_salvaged():
    rows = [row('q1'), row('q2'), row('q3')]
    raw = json.dumps({'q1': {'answer': 'A or B', 'reason': 'The answer is A'},
                      'q3': {'answer': 'B', 'reason': 'A finding'},
                      'not_our_question': {'answer': 'A', 'reason': 'Do not map me'}})
    parsed = ca.parse_case_response(raw, rows)
    assert parsed['unexpected_question_ids'] == ['not_our_question']
    assert [r['answer'] for r in parsed['records']] == [None, None, 'B']
    assert parsed['records'][1]['missing'] is True
    assert parsed['records'][1]['parser_rule'] == 'missing_question_id'
    assert parsed['records'][0]['raw_item']['answer'] == 'A or B'


@pytest.mark.parametrize('raw', [
    '```json\n{"q1":{"answer":"A"}}\n```',
    '{"q1":{"answer":"A"},"q1":{"answer":"B"}}',
    '{"q1":{"answer":"A","answer":"B"}}',
    '{"q1":{"answer":"A"}} extra prose',
    '[{"question_id":"q1","answer":"A"}]',
    '{"q1":{"answer":"A","confidence":NaN}}',
    'Answer: A', None,
])
def test_invalid_json_is_preserved_without_regex_salvage(raw):
    parsed = ca.parse_case_response(raw, [row()])
    assert parsed['json_error'] and parsed['records'][0]['answer'] is None
    assert parsed['records'][0]['status'] == 'unparsed'
    assert parsed['raw_response'] == raw


def test_request_failure_and_single_answer_projection_keep_original_ids():
    rows = [row('q1'), row('q2')]
    records = ca.project_case_response(rows, None, request_failed=True)
    assert all(r['status'] == 'request_failed' and r['answer'] is None for r in records)
    assert [r['question_id'] for r in records] == ['q1', 'q2']
    raw = 'Answer: B\nReason: A short observed finding.'
    projected = ca.project_sequential_response(rows[0], raw)
    assert projected['answer'] == 'B' and projected['question_id'] == 'q1'
    assert projected['raw_response'] == raw
