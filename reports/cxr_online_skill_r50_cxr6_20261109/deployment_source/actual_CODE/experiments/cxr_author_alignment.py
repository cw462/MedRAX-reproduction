"""Reference-free explicit-answer adapter and source-attributed answer metrics.

The adapter is project integration, not an official universal parser.  M4CXR
text normalization/recall follow author commit 4dd62e6; MCQ comparison uses
the supplied choices.  Neither reference answers nor reasons enter extraction.
"""
from dataclasses import dataclass
import json
import re


def m4cxr_normalize(text):
    for token in ['<s>', '</s>', '[INST]', '[/INST]']:
        text = text.replace(token, '')
    return text.strip().replace('.', '').lower()


def m4cxr_recall(answer, reference):
    tokenize = lambda value: set(re.findall(r'\w+|[^\w\s]+', m4cxr_normalize(value)))
    expected = tokenize(reference)
    return len(tokenize(answer) & expected) / len(expected) if expected else None


def choice(answer, options):
    """Resolve explicit letters or exact option text, never infer a finding."""
    value = answer.strip()
    letter = re.fullmatch(r'\(?([A-Za-z])\)?[.)]?', value)
    if letter and letter[1].upper() in options:
        return letter[1].upper()
    norm = lambda text: ' '.join(text.casefold().split())
    matches = [key for key, text in options.items() if norm(value) == norm(text)]
    if len(matches) == 1:
        return matches[0]
    labeled = re.fullmatch(r'\(?([A-Za-z])\)?[.):]?\s+(.+)', value, flags=re.S)
    if labeled:
        key = labeled[1].upper()
        if key in options and norm(labeled[2]) == norm(options[key]):
            return key
    return None


class Object(dict):
    """Keep duplicate answer keys visible instead of silently taking the last."""
    def __init__(self, pairs):
        super().__init__(pairs)
        self.pairs = pairs
        self.answer_values = [value for key, value in pairs if key == 'answer']


@dataclass(frozen=True)
class Extracted:
    answer: str | None
    mechanism: str
    explicit_candidates: tuple[str, ...] = ()


def object_answers(obj, qid):
    if not isinstance(obj, Object):
        return []
    values = list(obj.answer_values)
    # Both actual joint-Q forms explicitly key answers by question ID.  Keep
    # duplicate qid/answers keys visible; never search arbitrary nested fields.
    for key, item in obj.pairs:
        if key == qid and isinstance(item, Object):
            values.extend(item.answer_values)
        elif key == 'answers' and isinstance(item, Object):
            for nested_key, nested_item in item.pairs:
                if nested_key == qid and isinstance(nested_item, Object):
                    values.extend(nested_item.answer_values)
    return values


def object_spans(text):
    """Consume outer structured blocks, including malformed/truncated ones.

    Do not rediscover a nested reason/example as a standalone answer after
    an outer object's JSON parsing failed.
    """
    offset = 0
    while (start := text.find('{', offset)) != -1:
        depth, quoted, escaped = 0, False, False
        end = len(text)
        for index in range(start, len(text)):
            char = text[index]
            if quoted:
                if escaped:
                    escaped = False
                elif char == '\\':
                    escaped = True
                elif char == '"':
                    quoted = False
            elif char == '"':
                quoted = True
            elif char == '{':
                depth += 1
            elif char == '}':
                depth -= 1
                if depth == 0:
                    end = index + 1
                    break
        yield text[start:end]
        offset = end


def is_tool_plan(obj):
    """Outer repository action envelopes are control flow, not final answers."""
    return isinstance(obj, dict) and any(bool(obj.get(key)) for key in ['calls','actions','tool_calls'])


def extract(raw, qid, options=None):
    """Extract explicit answer fields or a directly stated final answer.

    Multiple inconsistent explicit answers remain ambiguous.  Valid outer JSON
    is consumed as one object, so reason strings and nested examples are never
    searched for an answer.  No answer is inferred from an observation/reason.
    """
    if not isinstance(raw, str) or not raw.strip():
        return Extracted(None, 'empty_reply')
    text = raw.strip()
    fenced = re.fullmatch(r'```(?:json)?\s*\n?(.*?)\n?```', text, flags=re.I | re.S)
    if fenced:
        text = fenced[1].strip()
    decoder = json.JSONDecoder(object_pairs_hook=Object)

    def finish(values, mechanism):
        if not values or any(not isinstance(v, str) or not v.strip() for v in values):
            return Extracted(None, 'no_explicit_string_answer')
        values = tuple(v.strip() for v in values)
        keys = [choice(v, options) or ('unmatched', m4cxr_normalize(v))
                if options else m4cxr_normalize(v) for v in values]
        if any(key != keys[0] for key in keys[1:]):
            return Extracted(None, 'conflicting_explicit_answers', values)
        return Extracted(values[0], mechanism, values)

    try:
        whole = decoder.decode(text)
    except ValueError:
        whole = None
    else:
        if is_tool_plan(whole):
            return Extracted(None, 'structured_tool_plan_not_final')
        return finish(object_answers(whole, qid), 'whole_json_answer')

    candidates, found_object, pending_plan = [], False, False
    for block in object_spans(text):
        found_object = True
        try:
            obj = decoder.decode(block)
        except ValueError:
            continue
        pending_plan = pending_plan or is_tool_plan(obj)
        candidates.extend(object_answers(obj, qid))
    if pending_plan:
        return Extracted(None, 'structured_tool_plan_not_final')
    if candidates:
        return finish(candidates, 'embedded_json_answer')
    if found_object:
        return Extracted(None, 'structured_reply_without_answer')
    labels = re.findall(r'^\s*(?:final\s+answer|answer)\s*:\s*(.+?)\s*$', text, flags=re.I | re.M)
    if labels:
        return finish(labels, 'labeled_answer_line')
    # Free text is retained in full, as an answer-string metric expects.
    # MCQ legality and exact-match scoring are separate, not prose inference.
    return Extracted(text, 'plain_reply')


def legacy_choice(answer, options, rng=None):
    """CheXagent BaseLM semantics on the explicit answer, excluding reason.

    With rng=None, failure is unscored/incorrect.  A provided seeded RNG gives
    the separately disclosed author-style random-fallback sensitivity.
    """
    if not isinstance(answer, str) or not answer.strip():
        return None, True
    matches = re.findall(r'\(([A-Z])\)', answer)
    if matches:
        return matches[0], False
    if rng is None:
        return None, True
    return chr(ord('A') + rng.choice(list(range(len(options))))), True
