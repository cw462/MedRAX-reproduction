"""Render frozen retrieval hits into a bounded prompt block.

The block is the only channel through which cross-case memory reaches the Agent.
It is derived exclusively from `FrozenPool.search` output, which already excludes
answers, options, patient identifiers, case ids and thread ids. This module adds
no lookup of its own: it cannot widen the retrieval boundary.

Rendered content is deliberately structural (features, tool order, execution
validity, whitelisted output shapes). It is not medical evidence and it never
states a diagnosis, a laterality or a conclusion.
"""
from __future__ import annotations

import hashlib

MAX_DEFAULT_CHARS = 1400

HEADER = (
    'Prior tool-use trajectories retrieved from other training cases '
    '(structured execution facts only: no answers, no options, no clinical evidence). '
    'They show which tools succeeded on similar task features; they are not medical '
    'ground truth. Confirm every finding on the current image yourself.'
)

FAILURE_HEADER = (
    'Prior tool-use trajectories retrieved from other training cases, including '
    'whole-question failures (structured execution facts only: no answers, no options, '
    'no clinical evidence). They show which tool sequences were and were not followed by '
    'a correct final answer; they are not medical ground truth. Confirm every finding on '
    'the current image yourself.'
)


def _shape_text(shape):
    if not isinstance(shape, dict) or not shape:
        return '{}'
    return '{' + ', '.join(f'{k}={shape[k]}' for k in sorted(shape)) + '}'


def _card(index, context):
    features = ', '.join(context.get('task_features') or [])
    if 'steps' in context:
        parts = []
        for step in context['steps']:
            parts.append(f"{step['tool']}({step['execution']}, {_shape_text(step.get('output_structure'))})")
        body = ' -> '.join(parts)
    else:
        sequence = ' -> '.join(context.get('observed_tool_sequence') or []) or '(none)'
        validity = ', '.join(context.get('execution_validity') or []) or 'unknown'
        body = f'tool sequence: {sequence}; execution: {validity}'
    outcome = context.get('task_outcome')
    suffix = f' | whole-question outcome: {outcome}' if outcome else ''
    return f'{index}) features=[{features}] {body}{suffix}'


def build_memory_block(hits, *, max_chars=MAX_DEFAULT_CHARS):
    """Return (text, audit). `text` is '' when there is nothing to inject."""
    if type(max_chars) is not int or max_chars < 200:
        raise ValueError('max_chars must be an int >= 200')
    if not isinstance(hits, list):
        raise ValueError('hits must be the list returned by FrozenPool.search')
    include_failures = any(isinstance(hit.get('context'), dict) and hit['context'].get('task_outcome')
                           in ('incorrect', 'invalid', 'error') for hit in hits)
    header = FAILURE_HEADER if include_failures else HEADER
    lines, used = [header], len(header)
    kept = 0
    for hit in hits:
        context = hit.get('context') if isinstance(hit, dict) else None
        if not isinstance(context, dict) or context.get('representation') is None:
            raise ValueError('Retrieval hit lacks a validated context structure')
        card = _card(kept + 1, context)
        if used + len(card) + 1 > max_chars:
            break
        lines.append(card)
        used += len(card) + 1
        kept += 1
    text = '\n'.join(lines) if kept else ''
    audit = {
        'returned': len(hits),
        'rendered': kept,
        'memory_ids': [hit['memory_id'] for hit in hits[:kept]],
        'scores': [round(float(hit['score']), 6) for hit in hits[:kept]],
        'injected_chars': len(text),
        'injected_sha256': hashlib.sha256(text.encode('utf-8')).hexdigest() if text else None,
        'header_kind': 'failure_aware' if include_failures else 'success_only',
        'medical_evidence': 'unknown',
    }
    return text, audit
