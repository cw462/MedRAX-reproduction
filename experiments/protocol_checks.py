"""Pure checks for completed chat/tool messages; never edits or repairs history.

This is NOT wired into diagnostic_eval or the running baseline. A future explicit
variant may run check_response before accepting a model turn and check_history
before another model request. No fake ToolMessage, answer, JSON suffix or retries
are generated. Content, argument values and parser exception text are not emitted.

Source audit (fixed versions, checked 2026-10-27):
* MedRAX dae30e2f: agent.py has_tool_calls tests only response.tool_calls.
* langchain-openai 0.2.14 base.py 123-140 preserves failed parsed calls in
  invalid_tool_calls; 214-220 serializes valid AND invalid calls on a later request;
  2113-2122 preserves invalid arguments verbatim in that outgoing representation.
* langchain-core 0.3.86 openai_tools.py 54-65 uses json.loads for non-streaming
  calls; 89-94 preserves the original arguments when constructing InvalidToolCall.
These checks can identify a risky history, not diagnose the exact cause of a 400.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import json


SOURCE_AUDIT = {
    'medrax_agent': 'https://github.com/bowang-lab/MedRAX/blob/dae30e2f136ef0b2a40885a4c335386e9ffad052/medrax/agent/agent.py#L119-L131',
    'langchain_openai': 'https://github.com/langchain-ai/langchain/blob/langchain-openai%3D%3D0.2.14/libs/partners/openai/langchain_openai/chat_models/base.py',
    'langchain_openai_wheel_sha256': 'd232496662f79ece9a11caf7d798ba863e559c771bc366814f7688e0fe664fe8',
    'langchain_openai_base_sha256': '54d716a7d8cf0f1bd03767d7f295e4e5c3213ec465d640a0b9d2749a2a64fb08',
    'langchain_core_wheel_sha256': '7d2a1c50d2d2a139dbc6465cd339f32d14aa43db5ac9bd232e5b567a238709e8',
    'langchain_core_parser_sha256': 'db306eb3096512efe0c0dee201ddd8be27ebe9720972fc8c2156b5111ebcfbf9',
}


@dataclass(frozen=True)
class ProtocolIssue:
    code: str
    severity: str
    message_index: int
    call_index: int | None = None
    tool_call_id: str | None = None

    def to_dict(self):
        return {'code': self.code, 'severity': self.severity, 'message_index': self.message_index,
                'call_index': self.call_index, 'tool_call_id': self.tool_call_id}


@dataclass(frozen=True)
class ProtocolReport:
    issues: tuple[ProtocolIssue, ...]
    pending_tool_call_ids: tuple[str, ...]
    declared_tool_call_count: int
    invalid_tool_call_count: int

    @property
    def ready_for_model(self):
        """Protocol readiness only; does not certify content or tool correctness."""
        return not self.pending_tool_call_ids and not any(x.severity == 'error' for x in self.issues)

    @property
    def length_terminated(self):
        return any(x.code == 'length_termination' for x in self.issues)

    @property
    def pending_calls_well_formed(self):
        """Structural status only; tool availability/schema/budget still unchecked."""
        return (bool(self.pending_tool_call_ids) and self.invalid_tool_call_count == 0
                and not any(x.severity == 'error' and x.code != 'pending_tool_reply' for x in self.issues))

    def to_dict(self):
        return {'ready_for_model': self.ready_for_model, 'length_terminated': self.length_terminated,
                'pending_calls_well_formed': self.pending_calls_well_formed,
                'pending_tool_call_ids': list(self.pending_tool_call_ids),
                'declared_tool_call_count': self.declared_tool_call_count,
                'invalid_tool_call_count': self.invalid_tool_call_count,
                'issues': [x.to_dict() for x in self.issues]}


def _get(value, key, default=None):
    return value.get(key, default) if isinstance(value, Mapping) else getattr(value, key, default)


def _role(message):
    role = _get(message, 'role') or _get(message, 'type')
    if not isinstance(role, str):
        return None
    return {'ai': 'assistant', 'human': 'user'}.get(role, role)


def _identifier(value):
    return (value if isinstance(value, str) and value.strip() and len(value) <= 256
            and all(ord(c) >= 32 for c in value) else None)


def _as_calls(value, index, issues, field):
    if value is None:
        return []
    if not isinstance(value, (list, tuple)):
        issues.append(ProtocolIssue(field + '_not_sequence', 'error', index))
        return []
    return list(value)


def _arguments_valid(value, *, wire):
    try:
        if wire:
            if not isinstance(value, str):
                return False, 'arguments_not_json_string'
            def unique_pairs(pairs):
                result = {}
                for key, item in pairs:
                    if key in result:
                        raise ValueError('duplicate key')
                    result[key] = item
                return result
            def reject_constant(_):
                raise ValueError('nonfinite JSON')
            decoded = json.loads(value, object_pairs_hook=unique_pairs, parse_constant=reject_constant)
        else:
            decoded = value
        if not isinstance(decoded, dict):
            return False, 'arguments_not_object'
        json.dumps(decoded, allow_nan=False)
        return True, None
    except (ValueError, TypeError, RecursionError):
        return False, 'invalid_arguments_json'


def _declared_calls(message, index, issues):
    """Mirror 0.2.14 outbound precedence without rewriting any original object."""
    valid = _as_calls(_get(message, 'tool_calls'), index, issues, 'tool_calls')
    invalid = _as_calls(_get(message, 'invalid_tool_calls'), index, issues, 'invalid_tool_calls')
    # For LangChain messages, populated normalized lists take precedence over raw.
    # For wire dictionaries, their tool_calls entries already contain function.
    if valid or invalid:
        return [(call, False) for call in valid] + [(call, True) for call in invalid]
    extra = _get(message, 'additional_kwargs', {})
    if not isinstance(extra, Mapping):
        issues.append(ProtocolIssue('additional_kwargs_not_object', 'error', index))
        return []
    raw = _as_calls(extra.get('tool_calls'), index, issues, 'raw_tool_calls')
    return [(call, False) for call in raw]


def check_history(messages, *, reject_length=False):
    """Inspect complete messages before a NEW model request.

    Accepts OpenAI-style dicts and LangChain-style objects/dicts. Outstanding
    function calls make ready_for_model false until actual tool replies exist.
    A well-formed length-terminated text turn is only a warning by default;
    reject_length=True is an explicit stricter experiment policy. This is not a
    streaming-chunk parser or a validator for arbitrary provider message schemas.
    """
    if not isinstance(messages, Sequence) or isinstance(messages, (str, bytes)):
        raise TypeError('messages must be a sequence of complete messages')
    if type(reject_length) is not bool:
        raise TypeError('reject_length must be bool')
    issues, pending, seen_ids, replied_ids = [], {}, set(), set()
    declared_count = invalid_count = 0
    for index, message in enumerate(messages):
        role = _role(message)
        if role not in ('system', 'developer', 'user', 'assistant', 'tool'):
            issues.append(ProtocolIssue('unsupported_message_role', 'error', index))
            continue
        if pending and role != 'tool':
            for call_id in pending:
                issues.append(ProtocolIssue('non_tool_message_before_tool_replies', 'error', index, tool_call_id=call_id))
        extra = _get(message, 'additional_kwargs', {})
        if isinstance(extra, Mapping) and extra.get('function_call'):
            issues.append(ProtocolIssue('legacy_function_call_not_supported', 'error', index))
        if isinstance(message, Mapping) and message.get('function_call'):
            issues.append(ProtocolIssue('legacy_function_call_not_supported', 'error', index))
        if role == 'tool':
            call_id = _identifier(_get(message, 'tool_call_id'))
            if call_id is None:
                issues.append(ProtocolIssue('missing_tool_reply_id', 'error', index))
            elif call_id in pending:
                pending.pop(call_id); replied_ids.add(call_id)
            else:
                code = 'duplicate_tool_reply' if call_id in replied_ids else 'orphan_tool_reply'
                issues.append(ProtocolIssue(code, 'error', index, tool_call_id=call_id))
            continue
        if role != 'assistant':
            if _get(message, 'tool_calls') or _get(message, 'invalid_tool_calls'):
                issues.append(ProtocolIssue('tool_calls_on_non_assistant', 'error', index))
            continue
        metadata = _get(message, 'response_metadata', {})
        finish = _get(message, 'finish_reason') or (metadata.get('finish_reason') if isinstance(metadata, Mapping) else None)
        if finish == 'length':
            issues.append(ProtocolIssue('length_termination', 'error' if reject_length else 'warning', index))
        declared = _declared_calls(message, index, issues)
        if finish == 'tool_calls' and not declared:
            issues.append(ProtocolIssue('tool_finish_without_calls', 'error', index))
        for call_index, (call, explicitly_invalid) in enumerate(declared):
            declared_count += 1
            bad = explicitly_invalid
            call_id = _identifier(_get(call, 'id'))
            if explicitly_invalid:
                issues.append(ProtocolIssue('invalid_tool_calls_present', 'error', index, call_index, call_id))
            if not isinstance(call, Mapping):
                issues.append(ProtocolIssue('tool_call_not_object', 'error', index, call_index))
                invalid_count += 1
                continue
            if call_id is None:
                bad = True
                issues.append(ProtocolIssue('missing_tool_call_id', 'error', index, call_index))
            elif call_id in seen_ids:
                bad = True
                issues.append(ProtocolIssue('duplicate_tool_call_id', 'error', index, call_index, call_id))
            else:
                seen_ids.add(call_id); pending[call_id] = index
            if 'function' in call:
                function = call['function']
                if not isinstance(function, Mapping) or call.get('type', 'function') != 'function':
                    bad = True
                    issues.append(ProtocolIssue('invalid_function_call_shape', 'error', index, call_index, call_id))
                    invalid_count += 1
                    continue
                name, args = function.get('name'), function.get('arguments')
                wire = True
            else:
                name, args, wire = call.get('name'), call.get('args'), explicitly_invalid
            if _identifier(name) is None:
                bad = True
                issues.append(ProtocolIssue('missing_tool_name', 'error', index, call_index, call_id))
            valid_args, error_code = _arguments_valid(args, wire=wire)
            if not valid_args:
                bad = True
                issues.append(ProtocolIssue(error_code, 'error', index, call_index, call_id))
            invalid_count += int(bad)
    for call_id, index in pending.items():
        issues.append(ProtocolIssue('pending_tool_reply', 'error', index, tool_call_id=call_id))
    return ProtocolReport(tuple(issues), tuple(pending), declared_count, invalid_count)


def check_response(message, *, finish_reason=None, reject_length=False):
    """Inspect one completed response; optional finish reason is an immutable view."""
    if finish_reason is None:
        return check_history([message], reject_length=reject_length)
    absent = object()
    view = {}
    for key in ('tool_calls', 'invalid_tool_calls', 'additional_kwargs', 'response_metadata', 'function_call'):
        value = _get(message, key, absent)
        if value is not absent:
            view[key] = value
    view['role'] = _role(message)
    view['finish_reason'] = finish_reason
    return check_history([view], reject_length=reject_length)
