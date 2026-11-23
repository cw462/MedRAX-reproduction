"""Deliver the native failed-tool observation without replacing its evidence."""
import copy
from .context import tool_failure_reason

SCHEMA = 'r54_terminal_failure_observation_v1'

def delivered_failure(services, row, ordinal, action, observation):
    reason = tool_failure_reason(observation)
    if not reason:
        raise ValueError('healthy_tool_is_not_failed')
    if observation.get('status') not in ('failed', 'error', 'completed'):
        raise RuntimeError('unknown_tool_attempt_stop_no_retry')
    if any(event.get('status') == 'started_unknown' for event in observation.get('actual_model_events', [])):
        raise RuntimeError('unknown_model_generation_stop_no_retry')
    return dict(copy.deepcopy(observation), failure_observation={
        'schema': SCHEMA, 'selection_ordinal': ordinal, 'failure_reason': reason,
        'outcome': 'tool_failed_no_usable_evidence', 'automatic_retry': False,
        'instruction': 'This tool failed. Partial output supplies no usable finding. Continue from the original images and other evidence; preserve the failure and do not repeat the failed call.'})
