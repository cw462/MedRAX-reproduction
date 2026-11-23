"""Explicit R50 amendment: terminal tool failures remain failed observations.

Implements MedRAX appendix A.4 in the existing R50 JSON observation interface.
It does not repair output, retry a backend, relax EOS, or change saved results.
"""
import copy
from pathlib import Path

from cxr_online_primitives_r50 import read, tool_failure_reason
from online_memory_r50 import save_once, safe_qid

ARM = 'M43-IM-GT-S50-CXR6'
POLICY_ID = '003_paper_tool_failure_observation'
SCHEMA = 'r50_paper_tool_failure_observation_v1'
HELD_Q = 'chexbench_openi_0078'
HELD_KEY = '65e65ea9f529a7ce811f54147a7c2326bf115aeaf0ddb2960ff9c3437d77626d'
SOURCES = ('r50_failure_observation.py', 'r50_services_amended.py', 'r50_run_amended.py')


def amendment(out):
    value = read(Path(out) / 'protocol_amendment.json')
    ds = Path(out).name
    if (value.get('schema') != SCHEMA or value.get('policy_id') != POLICY_ID
            or value.get('arm') != ARM or value.get('dataset') != ds
            or ds not in ('chexbench', 'slake', 'vqarad')
            or value.get('explicit_user_approval') is not True
            or value.get('user_reply') != '那按照论文中的同样来吧'
            or value.get('saved_prefix') != (316 if ds == 'chexbench' else 0)
            or value.get('all_remaining_questions') is not True
            or value.get('regenerate_failed_output') is not False
            or value.get('modify_original_producers') is not False
            or value.get('change_model_EOS_or_token_parameters') is not False):
        raise ValueError('invalid_explicit_R50_failure_observation_amendment')
    return value


def terminal_failure(record):
    reason = tool_failure_reason(record)
    if not reason:
        raise ValueError('healthy_tool_must_not_be_reported_failed')
    if record.get('status') not in ('failed', 'error', 'completed'):
        raise RuntimeError('unknown_tool_attempt_stop_no_retry')
    return reason


def _source(services, qid, ordinal, observation):
    safe_qid(qid)
    if type(ordinal) is not int or ordinal < 1:
        raise ValueError('invalid_tool_selection_ordinal')
    key = observation.get('cache_key')
    if not isinstance(key, str) or len(key) != 64 or any(c not in '0123456789abcdef' for c in key):
        raise ValueError('invalid_existing_cache_identity')
    selection = Path(services) / 'tool_selections' / 'R50-AGENT' / qid / (str(ordinal) + '.json')
    cache = Path(services) / 'tool_cache' / key
    raw = read(selection)
    result = read(cache / 'result.json')
    request = read(cache / 'request.json')
    if raw != observation or any(raw.get(k) != v for k, v in result.items()):
        raise ValueError('failed_selection_or_backend_result_changed')
    if request.get('tool') != raw.get('tool') or not (cache / 'started.json').is_file():
        raise ValueError('failed_tool_request_or_terminal_evidence_missing')
    terminal_failure(raw)
    return raw, request, selection, cache


def delivered_failure(services, row, ordinal, action, observation):
    """Write an immutable delivery receipt; never write into the physical cache."""
    services = Path(services)
    policy = amendment(services.parent)
    qid = row['question_id']
    context = read(services.parent / 'contexts' / (safe_qid(qid) + '.json'))
    if context['ordinal'] <= policy['saved_prefix']:
        raise ValueError('failure_delivery_before_approved_boundary')
    raw, request, selection, cache = _source(services, qid, ordinal, observation)
    if (raw.get('tool') != action['tool'] or request.get('args') != action.get('args', {})
            or raw.get('image_index', 1) != action.get('image_index', 1)):
        raise ValueError('replayed_failed_selection_action_changed')
    note = {'policy_id': POLICY_ID, 'outcome': 'tool_failed_no_usable_evidence',
            'failure_reason': terminal_failure(raw), 'selection_ordinal': ordinal,
            'automatic_retry': False, 'partial_output_is_not_a_finding': True,
            'instruction': 'This tool call failed and supplies no usable result. Continue reasoning with the original image and other available evidence; preserve the failure and do not infer a finding from partial output.'}
    presented = dict(copy.deepcopy(raw), failure_observation=note)
    receipt = {'schema': SCHEMA, 'policy_id': POLICY_ID, 'question_id': qid,
               'question_ordinal': context['ordinal'], 'selection_ordinal': ordinal,
               'cache_key': raw['cache_key'], 'raw_selection': raw,
               'delivered_observation': presented,
               'selection_file': str(selection.relative_to(services.parent)),
               'cache_file': str((cache / 'result.json').relative_to(services.parent)),
               'tool_remains_failed': True, 'backend_regenerated': False,
               'output_repaired': False, 'current_reference_read': False}
    save_once(services.parent / 'failure_observations' / qid / (str(ordinal) + '.json'), receipt)
    return presented


def validate_delivered_failure(out, qid, observation):
    """A failed outcome is acceptable only with its exact authorized raw receipt."""
    out = Path(out)
    policy = amendment(out)
    note = observation.get('failure_observation') or {}
    ordinal = note.get('selection_ordinal')
    if note.get('policy_id') != POLICY_ID or type(ordinal) is not int:
        raise ValueError('failed_tool_without_delivery_receipt')
    receipt = read(out / 'failure_observations' / safe_qid(qid) / (str(ordinal) + '.json'))
    raw = copy.deepcopy(observation)
    raw.pop('failure_observation', None)
    _source(out / 'services', qid, ordinal, raw)
    if (receipt.get('schema') != SCHEMA or receipt.get('policy_id') != POLICY_ID
            or receipt.get('question_id') != qid or receipt.get('selection_ordinal') != ordinal
            or receipt.get('question_ordinal', 0) <= policy['saved_prefix']
            or receipt.get('raw_selection') != raw
            or receipt.get('delivered_observation') != observation
            or receipt.get('backend_regenerated') is not False
            or receipt.get('output_repaired') is not False
            or receipt.get('tool_remains_failed') is not True):
        raise ValueError('failed_tool_delivery_binding_changed')
    return receipt


def validate_prediction_failures(out, qid, result):
    count = 0
    for value in result.get('observations', []):
        if tool_failure_reason(value):
            validate_delivered_failure(out, qid, value)
            count += 1
    return count


def validate_selection_failures(out):
    count = 0
    for path in (Path(out) / 'services/tool_selections/R50-AGENT').glob('*/*.json'):
        raw = read(path)
        if tool_failure_reason(raw):
            receipt = read(Path(out) / 'failure_observations' / path.parent.name / path.name)
            validate_delivered_failure(out, path.parent.name, receipt['delivered_observation'])
            if receipt['raw_selection'] != raw:
                raise ValueError('terminal_selection_differs_from_delivered_failure')
            count += 1
    return count
