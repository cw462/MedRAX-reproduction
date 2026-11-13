"""Store the writer's returned text directly in the R55 experience bank."""

from copy import deepcopy
from hashlib import sha256
import json
import os
import urllib.request

from experience_feedback_r54 import DISTILL, distillation_payload
from experience_r55live import score
from online_memory_r49 import now, save_once
from skill_policy_r54 import buffer_select


TEXT_DISTILL = DISTILL[:DISTILL.index('Never store')].rstrip() + (
    '\nWrite the experience in plain text. Use the supplied case and observed '
    'steps as needed to explain the lesson.'
)


def write_experience(self, event, system, payload):
    writer = self.writer
    folder = self.out / 'calls/R54DS-WRITER' / event / '1'
    request = {
        'model': writer['model'],
        'messages': [
            {'role': 'system', 'content': system},
            {'role': 'user', 'content': [{'type': 'text', 'text': json.dumps(payload, ensure_ascii=False)}]},
        ],
        'thinking': writer['thinking'],
        'max_tokens': writer['max_tokens'],
        'stream': False,
    }
    if writer.get('reasoning_effort'):
        request['reasoning_effort'] = writer['reasoning_effort']
    save_once(folder / 'request.json', request)
    save_once(folder / 'endpoint.json', {'base_url': writer['base_url']})

    response_path = folder / 'response.json'
    if response_path.is_file():
        response = json.loads(response_path.read_text(encoding='utf-8'))
    else:
        if (folder / 'started.json').exists():
            raise RuntimeError('unknown_writer_send_no_retry')
        key = os.environ[writer['api_key_env']]
        transport = urllib.request.Request(
            writer['base_url'].rstrip('/') + '/chat/completions',
            data=json.dumps(request).encode('utf-8'),
            headers={'Authorization': '[REDACTED]' + key, 'Content-Type': 'application/json'},
        )
        save_once(folder / 'started.json', {'utc': now(), 'response_received': False})
        with urllib.request.urlopen(transport, timeout=writer.get('timeout_seconds', 600)) as received:
            response = json.load(received)
        save_once(response_path, response)

    choices = response.get('choices', []) if isinstance(response, dict) else []
    choice = choices[0] if isinstance(choices, list) and choices else None
    message = choice.get('message') if isinstance(choice, dict) else None
    content = message.get('content') if isinstance(message, dict) else None
    text = content if isinstance(content, str) and content.strip() else json.dumps(content, ensure_ascii=False)
    metadata = response if isinstance(response, dict) else {}
    save_once(folder / 'result.json', {
        'response_received': True,
        'error': None,
        'model_returned': metadata.get('model'),
        'usage': metadata.get('usage'),
        'finish_reason': choice.get('finish_reason') if isinstance(choice, dict) else None,
        'admission_policy': 'returned_text_without_validation',
    })
    return text


def evolve(service, snapshot, batch, window_index, window, data, tools, config):
    repo = deepcopy(snapshot)
    repo['clock'] += len(batch)
    repo['window'] = window_index + 1
    for trajectory in batch:
        for skill_id in set(trajectory.get('activated_skill_ids', [])):
            card = repo['skills'][skill_id]
            card['uses'] += 1
            card['successes'] += int(trajectory['reward'] > 0)

    events = []
    for trajectory in buffer_select(batch, config):
        question = trajectory['id']
        text = service.write_experience('exp_distill_' + question, TEXT_DISTILL,
                                        distillation_payload(trajectory, tools))
        skill_id = 'exp_' + sha256(question.encode('utf-8')).hexdigest()[:24]
        # The embedding provider has an input limit. The bank and retrieval carry
        # the full text, even when its search index uses just the prefix.
        vector = service.embed(text[:2000])
        repo['skills'][skill_id] = {'c': {'text': text}, 'vector': vector, 'status': 'active',
                                    'sources': [question], 'uses': 0, 'successes': 0}
        events.append({'question': question, 'operation': 'add', 'id': skill_id})

    if repo['clock'] // 60 > snapshot['clock'] // 60:
        for skill_id, card in repo['skills'].items():
            if card['status'] == 'active' and score(card) < .30:
                card['status'] = 'pruned'
                events.append({'operation': 'prune', 'id': skill_id, 'score': score(card)})
    save_once(window / 'experience_events.json', events)
    return repo
