"""Conservative, reference-free binary answer-domain continuation policy."""
import json
import re
import unicodedata

RESTATE = ('The original question is a yes/no question. Restate your last answer as exactly one '
           'JSON object with "answer" equal to "Yes" or "No" and "reason" one short sentence. '
           'Preserve your interpretation of the original question and image; do not add new '
           'clinical assumptions. Do not request tools or add text outside the JSON object.')


def normalize(text):
    if not isinstance(text, str):
        return None
    text = unicodedata.normalize('NFKC', text).casefold()
    text = ' '.join(''.join(' ' if unicodedata.category(c).startswith('P') else c for c in text).split())
    return {'true': 'yes', 'false': 'no'}.get(text, text)


def binary_domain(row):
    """Explicit alternatives take precedence over an auxiliary-verb opening."""
    if row.get('options'):
        return False
    question = row['question'].strip()
    if re.search(r'\bor\b', question, re.I):
        return False
    return re.match(r'^(?:is|are|was|were|do|does|did|can|could|has|have|had|will|would|should)\b', question, re.I) is not None


def decision(row, prediction, main_limit=4, tool_limit=2):
    if not binary_domain(row):
        return 'outside_binary_scope'
    if prediction.get('status') != 'completed' or not isinstance(prediction.get('answer'), str):
        return 'no_legal_explicit_answer'
    if normalize(prediction['answer']) in ('yes', 'no'):
        return 'already_in_domain'
    if type(prediction.get('main_calls')) is not int or prediction['main_calls'] >= main_limit:
        return 'main_budget_exhausted'
    if type(prediction.get('tool_calls')) is not int or prediction['tool_calls'] > tool_limit:
        return 'invalid_historical_tool_budget'
    observations = prediction.get('observations', [])
    if len(observations) != prediction['tool_calls'] or any(
            x.get('status') != 'completed' or x.get('observation') is None for x in observations):
        return 'unhealthy_historical_tool'
    return 'continue_once'


def parse_restatement(raw):
    """Preserve original M's exact two-string-field JSON contract."""
    value = json.loads(raw)
    if (not isinstance(value, dict) or set(value) != {'answer', 'reason'}
            or not all(isinstance(value[k], str) for k in ('answer', 'reason'))
            or len(value['answer']) > 300
            or normalize(value['answer']) not in ('yes', 'no')):
        raise ValueError('explicit_binary_answer_required')
    return {'answer': value['answer'], 'reason': value['reason'], 'status': 'completed'}
