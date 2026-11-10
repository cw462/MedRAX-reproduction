"""Single-use record of the actual non-EOS MAIRA stop; no recovery execution."""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PREP = ROOT / 'local_assets/r50_cxr6_preparation'
FOLDER = PREP / 'failures/003_chex_316'


def main():
    status = json.loads(sys.argv[1])
    assert status['controller'] == {'pid': '3277341', 'alive': False, 'exit': '1'}
    d = status['datasets']['chexbench']
    assert d['pid'] == '3277347' and d['exit'] == '1' and d['saved'] == 316
    read = lambda p: json.loads(p.read_text(encoding='utf-8-sig'))
    failure = read(FOLDER / 'actual_failure.json')
    selection = failure['failed_selection']['record']
    assert failure['question_id'] == 'chexbench_openi_0078' and failure['ordinal'] == 317
    assert selection['error'] == 'guard_policy_incomplete_or_non_eos_termination'
    assert selection['tool'] == 'xray_phrase_grounding'
    artifacts = FOLDER / 'originals' / failure['tool_cache'] / 'artifacts'
    tokens = read(artifacts / 'generation_tokens.json')
    generated = tokens[0]['generated_token_ids'][0]
    assert len(tokens) == 1 and len(generated) == 300 and generated[-1] == 32000
    assert len(selection['actual_model_events']) == 1 and selection['actual_model_events'][0]['status'] == 'completed'
    capture_failure = read(FOLDER / 'artifact_capture.failure.json')
    assert len(capture_failure['partial_files']) == 11 and (artifacts / 'maira_runtime').stat().st_size == 0
    when = datetime.now(timezone.utc).astimezone().isoformat()
    value = {
        'utc': when, 'status': 'actual_model_output_parser_stop_awaiting_explicit_protocol_decision',
        'failure_id': '003_maira_300_token_non_eos', 'question_id': failure['question_id'],
        'ordinal': 317, 'saved_prefix': 316, 'tool': selection['tool'], 'selection_ordinal': 1,
        'cache_key': selection['cache_key'], 'args': selection['identity']['args'],
        'current_controller_and_runner_exit': 1, 'original_and_recovery001_and_recovery002_exits_retained': True,
        'actual_model_events': selection['actual_model_events'], 'generated_tokens': 300,
        'final_generated_token_id': 32000, 'eos_terminated': False, 'parser_exception': 'AssertionError',
        'failed_generation_retried': False, 'explicit_tool_retry_launched': False, 'queue_restarted': False,
        'prior_two_successful_retries_still_consumed': True, 'prior_helpers_reexecuted': False,
        'completed_predictions_producer_model_environment_or_parameters_modified': False,
        'failed_question_prediction_and_own_feedback_absent': True,
        'original_inspection_native_exit': 0, 'original_inspection_files': 21,
        'additional_artifact_capture_native_exit': 1,
        'additional_artifact_capture_failure': 'directory maira_runtime was opened as a file; SFTP read returned OSError Failure',
        'additional_artifact_files_copied_before_failure': 11,
        'failed_capture_source_receipt_and_zero_byte_placeholder_preserved': True,
        'native_stderr_evidence': 'original native exec transcript; no separately captured raw-byte stderr file claimed',
        'new_model_score_or_publication_calls_during_inspection': 0,
        'latest_actual_status': status,
        'decision_proposal': 'PROPOSED_FAILURE_OBSERVATION_AMENDMENT.md',
        'decision_required_because': 'the user froze producer/configuration and forbids regenerating poor completed outputs; error-observation continuation changes the failure-handling protocol',
        'next': 'Await explicit user decision. Do not retry this completed generation, relax EOS/parser checks, materialize a successful cache, launch a queue, score, or run final review. Existing automation remains sole owner and active; unchanged stopped state stays quiet.',
    }
    with (FOLDER / 'ACTUAL_THIRD_STOP.json').open('x', encoding='utf-8') as f:
        json.dump(value, f, ensure_ascii=False, indent=2)
        f.write('\n')
    path = ROOT / '.aris/IMPROVEMENT_STATE.json'
    state = read(path)
    r = state['R50']
    history = r.setdefault('technical_recovery_events', [])
    history.append(value)
    r['current_technical_recovery'] = value
    r['status'] = 'STOPPED_AWAITING_EXPLICIT_PROTOCOL_DECISION'
    state.update(status='R50_actual_non_EOS_parser_stop_awaiting_user_decision', updated_at=when, next=value['next'])
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    header = f'''## R50 ACTUAL MAIRA NON-EOS STOP — EXPLICIT PROTOCOL DECISION PENDING ({when})

Recovery002 controller3277341/CheXrunner3277347 are DEAD/raw1 at316saved,317contexts,316feedback,829main sends/responses,155META/10windows. Original, recovery001 and recovery002 native generation/controller/CheX exit1 records all remain unchanged. SLAKE/VQA not started. This supersedes all older RUNNING text. No recovery003 or retry is launched.

Held case chexbench_openi_0078 ordinal317/tool1 xray_phrase_grounding, args phrase=surgical instruments in the abdomen. MAIRA actually completed ONE generate48.27794743003324s/300tokens, stopped at existing300 limit, final token32000 (<obj>), noEOS. Original decoded text and token IDs preserved; original parser AssertionError at unmatched delimiter, guard policy unhealthy. Unlike the prior two zero-generation loader failures, this completed malformed model output cannot be retried under the user's frozen/no-poor-output-redo constraints. No output repair, EOS relaxation, successful-cache materialization or queue restart performed.316predictions unchanged and held question has no own feedback/prediction. Prior001+002 retries remainADOPTED/CONSUMED and were not rerun.

Bounded new original inspection succeeded native0/21files. Additional existing-artifact capture actually FAILED native1 after11copied files when maira_runtime directory was read as a file. Source, started/failure receipt,11completed copies and zero-byte local placeholder are retained. Original exec transcript contains native stderr; no separate raw-byte stderr file is claimed. Saved11files already include generation/decode/originalresult/parser exception, enough to locate this failure. Do not rerun either new capture helper or re-copy completed artifacts.

ACTUAL_THIRD_STOP.json and PROPOSED_FAILURE_OBSERVATION_AMENDMENT.md in failures/003_chex_316 contain the exact evidence and an unimplemented proposal: if explicitly approved, return failed tool outcomes honestly to the main model uniformly for the held and all remaining questions, with no retry or output repair; record amended-code/protocol boundary and all failures/resources. Without explicit approval keep this original frozen run stopped/incomplete. Confirmation is needed because this changes the user's frozen failure-handling protocol, not because a skill imposed approval.

Do not score/transfer complete datasets/export/review/write-ready/publish before true gates. Current postprocessing gates still accept only the two prior actual loader recoveries and must not be fooled with an unregistered third recovery or exit0. Existing medrax-r47 remains ACTIVE/sole owner; do not duplicate or pause it. Unchanged stopped state stays quiet; act on an explicit user decision. No R51, environment changes, probes, old reviews or hashes.

'''
    for relative in ('local_assets/R50_NEW_CHAT_HANDOFF.md', 'local_assets/cxr_vqa_handoff.md'):
        p = ROOT / relative
        p.write_text(header + p.read_text(encoding='utf-8-sig'), encoding='utf-8')
    print(json.dumps({'third_stop_recorded': True, 'saved': 316, 'new_generate_or_queue_launch': False,
                      'explicit_protocol_decision_pending': True}))


if __name__ == '__main__':
    main()
