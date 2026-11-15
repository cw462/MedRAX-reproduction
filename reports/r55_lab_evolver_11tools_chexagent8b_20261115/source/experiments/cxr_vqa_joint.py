"""Joint D-Q/M-Q inference for frozen groups of related CXR questions."""

import json

from run_cxr_vqa_toolsets import (
    append_observations, content, evidence_catalog, parse_final, validate_actions,
)


FINAL = ('Return one JSON object with an answers field. In answers, use each exact question ID as a key '
         'and give an object with two strings, answer and reason. For an option question, use an original '
         'option letter or the complete original option text. Answer every question from its bound images.')
SYSTEM = ('Review the labeled original chest images. Answer the related questions jointly, while checking '
          'each claim against the images bound to that question. Do not treat another question or its options '
          'as established findings. Tool observations may be wrong. Classifier scores cannot establish '
          'severity, and single-image reports cannot establish temporal change.')


def bind_group(group, rows_by_id):
    ids = group['question_ids']
    if len(ids) < 2 or len(set(ids)) != len(ids):
        raise ValueError('Joint group must contain distinct questions')
    images = {}
    questions = []
    for qid in ids:
        row = rows_by_id[qid]
        indices = [images.setdefault(relative, len(images) + 1) for relative in row['images']]
        if not indices:
            raise ValueError('A joint question has no bound original')
        question = {'question_id': qid, 'question': row['question'], 'image_indices': indices}
        if 'options' in row:
            question['options'] = row['options']
        questions.append(question)
    return {'question_id': group['group_id'], 'question': json.dumps(questions, ensure_ascii=False),
            'images': list(images)}, ids


def as_object(raw):
    try:
        value = json.loads(raw)
    except (TypeError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def joint_episode(group, rows_by_id, arm, data_root, runtime, out, paid, tools):
    row, ids = bind_group(group, rows_by_id)
    messages = [{'role': 'system', 'content': SYSTEM}, {'role': 'user', 'content': content(row, data_root)}]
    tool_limit = 2 * len(ids) if arm == 'M-Q' else 0
    call_limit = 4 * len(ids) if arm == 'M-Q' else 1
    observations = []
    image_count = len(row['images'])
    catalog = evidence_catalog(runtime, arm) if tool_limit else {}
    final = {}
    for ordinal in range(1, call_limit + 1):
        remaining = tool_limit - len(observations)
        prompt = FINAL
        if remaining and ordinal < call_limit:
            action = {'tool': 'registered name', 'args': {}}
            if image_count > 1:
                action['image_index'] = 1
            prompt += (f' If you need auxiliary evidence, instead return {json.dumps({"calls": [action]})}. '
                       f'You may select up to {remaining} more tools. Use the bound original for each call. '
                       'Tool catalog: ' + json.dumps(catalog))
        messages.append({'role': 'user', 'content': prompt})
        raw = paid.call(row, arm, ordinal, messages)
        messages.append({'role': 'assistant', 'content': raw})
        value = as_object(raw)
        if 'answers' in value:
            final = value['answers'] if isinstance(value['answers'], dict) else {}
            break
        if not remaining or ordinal == call_limit:
            break
        try:
            actions = validate_actions(value, runtime, arm, remaining, image_count)
        except (ValueError, TypeError, KeyError):
            break
        if not actions:
            tool_limit = len(observations)
            continue
        for action in actions:
            observations.append(tools.call(row, action, arm, len(observations) + 1))
        append_observations(messages, observations[-len(actions):], out, arm)
    return {'group_id': row['question_id'], 'main_calls': ordinal, 'tool_calls': len(observations),
            'observations': observations,
            'answers': {qid: parse_final(json.dumps(final.get(qid))) for qid in ids}}
