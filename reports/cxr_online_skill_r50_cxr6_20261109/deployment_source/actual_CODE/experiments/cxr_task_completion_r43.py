"""Reference-free strict task completion on otherwise unscorable outputs."""
from cxr_answer_domain_r42 import binary_domain, normalize
from run_cxr_vqa_toolsets import parse_final
from score_cxr_vqa_extension import grade


def unscorable(row, prediction):
    # Only the fixed scorer's legality flag is used. There is no gold value.
    return grade(row, prediction, None)[1]


def decision(row, best, original):
    if not unscorable(row, best):
        return 'preserve_accepted_answer'
    if best.get('reused_historical_M') is not True:
        return 'outside_inherited_M_scope'
    assert all(best.get(k) == original.get(k) for k in ['answer', 'reason', 'status'])
    if original.get('technical_failure') or 'tool_unhealthy' in original.get('status', ''):
        return 'technical_failure_excluded'
    if type(original.get('main_calls')) is not int or not 1 <= original['main_calls'] < 4:
        return 'actual_prefix_budget_exhausted'
    if type(original.get('tool_calls')) is not int or not 0 <= original['tool_calls'] <= 2:
        return 'invalid_actual_tool_budget'
    observations = original.get('observations', [])
    if len(observations) != original['tool_calls'] or any(
            x.get('status') != 'completed' or x.get('observation') is None for x in observations):
        return 'unhealthy_actual_prefix'
    return 'complete_once'


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


def accepted_reply(row, raw):
    result = parse_final(raw)
    if result['status'] != 'completed' or unscorable(row, result):
        raise ValueError('original_output_contract_failed')
    if not row.get('options') and binary_domain(row) and normalize(result['answer']) not in ('yes', 'no'):
        raise ValueError('explicit_binary_answer_required')
    return result
