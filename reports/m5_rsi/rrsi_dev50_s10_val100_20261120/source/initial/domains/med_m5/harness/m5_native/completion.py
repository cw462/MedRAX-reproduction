import re,unicodedata

def unscorable(row, prediction):
    raw_answer = prediction.get('answer')
    if prediction.get('status') != 'completed' or not isinstance(raw_answer, str):
        return True
    answer = normalize(raw_answer)
    options = row.get('options')
    if not options:
        return answer is None
    if answer and answer.upper() in options:
        return False
    matching = [letter for letter, text in options.items() if answer == normalize(text)]
    if len(matching) == 1:
        return False
    labeled = re.fullmatch(r'([a-z])[.)] (.+)', option_text_key(raw_answer))
    if labeled:
        letter = labeled[1].upper()
        if letter in options and labeled[2] == option_text_key(options[letter]):
            return False
    return True

def binary_domain(row):
    """Explicit alternatives take precedence over an auxiliary-verb opening."""
    if row.get('options'):
        return False
    question = row['question'].strip()
    if re.search(r'\bor\b', question, re.I):
        return False
    return re.match(r'^(?:is|are|was|were|do|does|did|can|could|has|have|had|will|would|should)\b', question, re.I) is not None
def normalize(value):
    if not isinstance(value, str): return None
    value = unicodedata.normalize('NFKC', value).lower()
    value = ''.join(' ' if unicodedata.category(c).startswith('P') else c for c in value)
    value = ' '.join(value.split())
    return {'true': 'yes', 'false': 'no'}.get(value, value) or None
def option_text_key(text):
    return ' '.join(unicodedata.normalize('NFKC', text).casefold().split())
def prompt(row):
    if row.get('options'):
        domain = 'The answer must be one supplied option letter: ' + ', '.join(row['options']) + '.'
    elif binary_domain(row):
        domain = 'The original question is binary; the answer must be Yes or No.'
    else:
        domain = 'The answer must be a short direct response to the original question.'
    return ('Your previous response did not complete the ORIGINAL task in the required output form. '
            'Re-examine the original question, supplied images and only tool observations actually returned. '
            'An unexecuted tool plan is not an observation. Return exactly one JSON object containing only '
            'string fields "answer" and "reason"; reason is one short sentence. ' + domain +
            ' Choose an answer only when supported by that question and evidence; do not invent findings. '
            'If unable to support a supplied answer, retain your previous answer in that JSON instead. '
            'No tools, code fences, or text outside the JSON.')
