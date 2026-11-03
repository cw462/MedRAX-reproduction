import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'experiments'))
from run_qwen37_token_plan_pipeline import execute, NAME


def put(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding='utf-8')


def test_three_phases_score_only_after_completion_and_no_labels_to_answers(tmp_path):
    code = tmp_path/'code'; code.mkdir()
    calls = []
    def runner(command, **kw):
        calls.append((command, kw))
        program = Path(command[2]).name
        if program == 'run_vote_phase.py':
            assert '--labels' not in command and kw['input'] == b'fixture-key\n'
            phase = Path(command[command.index('--manifest')+1]).stem
            put(tmp_path/'runs'/NAME/phase/'status.json', {'status': 'generation_complete'})
        elif program == 'score_votes.py':
            assert kw['input'] == b''
            output = Path(command[command.index('--out')+1])
            state = tmp_path/'runs'/NAME/output.name/'status.json'
            assert json.loads(state.read_text())['status'] == 'generation_complete'
            put(output/'metrics.json', {'status': 'completed'})
        return SimpleNamespace(returncode=0)
    execute(tmp_path, code, tmp_path/'old.labels', tmp_path/'tune.labels', b'fixture-key', run=runner)
    programs = [Path(c[0][2]).name for c in calls]
    assert programs.count('run_vote_phase.py') == programs.count('score_votes.py') == 3
    assert programs.count('configure_qwen37_token_plan.py') == 2
    state = json.loads((tmp_path/'runs'/NAME/'pipeline_status.json').read_text())
    assert state['completed_phases'] == ['phase0','phase1','phase2']
    assert state['status'] == 'completed'
    protocol = json.loads((tmp_path/'runs'/NAME/'pipeline_protocol.json').read_text())
    assert protocol['model'] == 'qwen3.7-plus'
    assert protocol['cumulative_cap_cny'] == '394.252828'
    assert protocol['additional_budget_granted_cny'] == '0'
    assert protocol['phase0_gate'].startswith('technical only')


def test_failed_generation_never_scores_or_advances(tmp_path):
    code = tmp_path/'code'; code.mkdir(); calls=[]
    def runner(command, **kw):
        calls.append(command); return SimpleNamespace(returncode=1)
    with pytest.raises(RuntimeError, match='subprocess_failed'):
        execute(tmp_path, code, tmp_path/'labels0', tmp_path/'labels1', b'fixture-key', run=runner)
    assert len(calls) == 1 and Path(calls[0][2]).name == 'run_vote_phase.py'
    assert json.loads((tmp_path/'runs'/NAME/'pipeline_status.json').read_text())['status'] == 'stopped'


def test_stopped_phase_requires_explicit_acknowledgement(tmp_path):
    code=tmp_path/'code';code.mkdir()
    put(tmp_path/'runs'/NAME/'phase0/status.json', {'status':'stopped'})
    def runner(*args, **kwargs):raise AssertionError('must not execute')
    with pytest.raises(RuntimeError, match='requires_explicit_acknowledgement'):
        execute(tmp_path, code, tmp_path/'labels0', tmp_path/'labels1', b'fixture-key', run=runner)


def test_success_exit_without_completion_cannot_open_labels(tmp_path):
    code=tmp_path/'code';code.mkdir();calls=[]
    def runner(command, **kw):calls.append(command);return SimpleNamespace(returncode=0)
    with pytest.raises(RuntimeError, match='generation_not_complete'):
        execute(tmp_path, code, tmp_path/'labels0', tmp_path/'labels1', b'fixture-key', run=runner)
    assert len(calls)==1


def unsent_fixture(root):
    code = root/'code'; code.mkdir()
    out = root/'runs'/NAME
    arm = out/'phase2/Qwen_SC9'
    checkpoint = arm/'checkpoints/6314_8353801558296/sample_4'
    error = 'LedgerIntegrityError:Ledger checksum mismatch'
    put(out/'pipeline_status.json', {'status': 'stopped', 'phase': 'phase2',
        'completed_phases': ['phase0', 'phase1']})
    for phase in ('phase0', 'phase1'):
        put(out/phase/'status.json', {'status': 'generation_complete'})
        put(root/'reports'/NAME/phase/'metrics.json', {'status': 'completed'})
    put(out/'phase2/status.json', {'status': 'stopped', 'active_arm': 'Qwen_SC9'})
    put(arm/'status.json', {'status': 'stopped', 'error': error})
    put(arm/'fatal_error.json', {'error': error, 'question_id': '6314_8353801558296', 'sample': 4})
    put(checkpoint/'attempt_1/reserve_error.json', {'error_type': 'LedgerIntegrityError',
        'message': 'Ledger checksum mismatch', 'request_sent': False})
    put(code/'configs'/NAME/'phase2.json', {'root': str(root),
        'out': f'runs/{NAME}/phase2', 'arms': [{'id': 'Qwen_SC9', 'out': f'runs/{NAME}/phase2/Qwen_SC9'}]})
    return code, out, arm, checkpoint


def unsent_execute(root, code, runner, **overrides):
    options = dict(acknowledge_phase='phase2', acknowledge_arm='Qwen_SC9',
                   acknowledge_unsent_error='6314_8353801558296__s4')
    options.update(overrides)
    return execute(root, code, root/'labels0', root/'labels1', b'fixture-key',
                   run=runner, **options)


def test_unsent_recovery_runs_only_unfinished_phase_without_fake_terminal_ack(tmp_path):
    code, out, arm, checkpoint = unsent_fixture(tmp_path)
    originals = {p: p.read_bytes() for p in (arm/'fatal_error.json', checkpoint/'attempt_1/reserve_error.json')}
    put(out/'global_requests.json', {'total': 2234, 'technical_extra': 0})
    counter = (out/'global_requests.json').read_bytes()
    calls = []
    def runner(command, **kwargs):
        calls.append(command)
        assert not any(arg.startswith('--acknowledge') for arg in command)
        program = Path(command[2]).name
        if program == 'run_vote_phase.py':
            assert Path(command[command.index('--manifest')+1]).stem == 'phase2'
            assert kwargs['input'] == b'fixture-key\n'
            put(out/'phase2/status.json', {'status': 'generation_complete'})
        elif program == 'score_votes.py':
            assert Path(command[command.index('--out')+1]).name == 'phase2'
            put(tmp_path/'reports'/NAME/'phase2/metrics.json', {'status': 'completed'})
        else:
            pytest.fail('completed phases and frozen recovery configuration must not rerun')
        return SimpleNamespace(returncode=0)
    unsent_execute(tmp_path, code, runner)
    assert [Path(c[2]).name for c in calls] == ['run_vote_phase.py', 'score_votes.py']
    assert all(p.read_bytes() == value for p, value in originals.items())
    assert (out/'global_requests.json').read_bytes() == counter
    confirmation = out/'unsent_recovery_acknowledgements/phase2__Qwen_SC9__6314_8353801558296__s4.json'
    record = json.loads(confirmation.read_text())
    assert record['request_sent'] is False and record['stop_event_created'] is False
    assert record['ledger_modified'] is False and record['counters_reset'] is False
    assert not (arm/'stop_events').exists() and not (arm/'stop_acknowledgements').exists()


@pytest.mark.parametrize('relative', [
    'terminal.json', 'attempt_1/started.json', 'attempt_1/response.json',
    'attempt_1/result.json', 'attempt_1/stream_chunks.jsonl', 'attempt_2/started.json'])
def test_unsent_recovery_rejects_sent_or_terminal_evidence(tmp_path, relative):
    code, out, arm, checkpoint = unsent_fixture(tmp_path)
    put(checkpoint/relative, {'already_existed': True})
    def runner(*args, **kwargs): pytest.fail('must fail before subprocess/API')
    with pytest.raises(ValueError, match='rejects_sent_or_terminal'):
        unsent_execute(tmp_path, code, runner)
    assert not (out/'unsent_recovery_acknowledgements').exists()


@pytest.mark.parametrize('artifact,change,match', [
    ('reserve', {'request_sent': True}, 'exact_unsent'),
    ('reserve', {'message': 'Another error'}, 'exact_unsent'),
    ('reserve', {'error_type': 'TimeoutError'}, 'exact_unsent'),
    ('fatal', {'question_id': 'different'}, 'fatal_target'),
    ('fatal', {'sample': 3}, 'fatal_target'),
    ('fatal', {'error': 'LedgerIntegrityError:Different failure'}, 'exact_unsent'),
    ('arm', {'stop_event_id': 'existing-terminal'}, 'fatal_target'),
    ('arm', {'status': 'running'}, 'fatal_target'),
    ('phase', {'active_arm': 'Other'}, 'current_stopped'),
    ('pipeline', {'phase': 'phase1'}, 'current_stopped'),
    ('pipeline', {'status': 'running'}, 'current_stopped'),
])
def test_unsent_recovery_rejects_mismatched_current_failure(tmp_path, artifact, change, match):
    code, out, arm, checkpoint = unsent_fixture(tmp_path)
    paths = {'reserve': checkpoint/'attempt_1/reserve_error.json', 'fatal': arm/'fatal_error.json',
             'arm': arm/'status.json', 'phase': out/'phase2/status.json', 'pipeline': out/'pipeline_status.json'}
    path = paths[artifact]
    value = json.loads(path.read_text()); value.update(change); put(path, value)
    original_status = (out/'pipeline_status.json').read_bytes()
    def runner(*args, **kwargs): pytest.fail('must fail before subprocess/API')
    with pytest.raises(ValueError, match=match):
        unsent_execute(tmp_path, code, runner)
    assert (out/'pipeline_status.json').read_bytes() == original_status
    assert not (out/'unsent_recovery_acknowledgements').exists()


def test_unsent_recovery_requires_complete_prior_phase_and_rejects_reuse(tmp_path):
    code, out, arm, checkpoint = unsent_fixture(tmp_path)
    def runner(*args, **kwargs): pytest.fail('must fail before subprocess/API')
    put(out/'phase1/status.json', {'status': 'stopped'})
    with pytest.raises(ValueError, match='next_unfinished_phase'):
        unsent_execute(tmp_path, code, runner)
    put(out/'phase1/status.json', {'status': 'generation_complete'})
    put(out/'unsent_recovery_acknowledgements/phase2__Qwen_SC9__6314_8353801558296__s4.json', {})
    with pytest.raises(ValueError, match='already_acknowledged'):
        unsent_execute(tmp_path, code, runner)


def test_unsent_and_terminal_ack_are_mutually_exclusive(tmp_path):
    code, *_ = unsent_fixture(tmp_path)
    with pytest.raises(ValueError, match='mutually_exclusive'):
        unsent_execute(tmp_path, code, lambda *a, **k: None, acknowledge_event='fake')


def test_unsent_recovery_worker_failure_stops_without_scoring_or_retry(tmp_path):
    code, out, _, _ = unsent_fixture(tmp_path)
    calls = []
    def failed_original_worker(command, **kwargs):
        calls.append(command)
        assert Path(command[2]).name == 'run_vote_phase.py'
        assert not any(arg.startswith('--acknowledge') for arg in command)
        return SimpleNamespace(returncode=2)
    with pytest.raises(RuntimeError, match='subprocess_failed'):
        unsent_execute(tmp_path, code, failed_original_worker)
    assert len(calls) == 1
    state = json.loads((out/'pipeline_status.json').read_text())
    assert state['status'] == 'stopped' and state['phase'] == 'phase2'
    assert state['completed_phases'] == ['phase0', 'phase1']
    assert not (tmp_path/'reports'/NAME/'phase2/metrics.json').exists()


def test_original_pipeline_protocol_unchanged_when_recovery_is_rejected(tmp_path):
    code, out, arm, checkpoint = unsent_fixture(tmp_path)
    def fail(command, **kwargs): return SimpleNamespace(returncode=1)
    # Establish the ordinary frozen protocol, without reading labels or calling an API.
    with pytest.raises(RuntimeError):
        execute(tmp_path, code, tmp_path/'l0', tmp_path/'l1', b'fixture-key', run=fail)
    original = (out/'pipeline_protocol.json').read_bytes()
    with pytest.raises(ValueError):
        unsent_execute(tmp_path, code, fail)
    assert (out/'pipeline_protocol.json').read_bytes() == original


def acknowledged_startup_fixture(root):
    code, out, arm, _ = unsent_fixture(root)
    event_id = '919_8353802159390__s6__ledger_settlement_error'
    event = {'event_id': event_id, 'question_id': '919_8353802159390', 'sample_index': 6,
        'reason': 'ledger_settlement_error', 'consecutive_failed_samples': 1,
        'occurred_utc': '2026-11-02T18:41:41.572233+00:00', 'failure_policy_version': 'sample-failure-v1'}
    put(arm/'status.json', {'status': 'stopped', 'error': 'ledger_settlement_error',
        'stop_event_id': event_id, 'completed_samples': 2670, 'requests_used': 2670})
    put(arm/'fatal_error.json', {'utc': '2026-11-02T18:44:58.357456+00:00',
        'error_type': 'LedgerIntegrityError', 'message': 'Invalid existing ledger; refusing to reset it'})
    put(arm/'stop_events'/f'{event_id}.json', event)
    put(arm/'stop_acknowledgements'/f'{event_id}.json', {'stop_event': event,
        'acknowledged_utc': '2026-11-02T18:44:57.948258+00:00',
        'operator_action': 'explicit_cli_acknowledgement_after_review',
        'effect': 'continue_unfinished_samples_only_no_prediction_or_cost_rewrite'})
    put(arm/'checkpoints/919_8353802159390/sample_6/terminal.json', {
        'question_id': event['question_id'], 'sample_index': 6, 'status': 'request_failed',
        'answer': None, 'fatal_reason': event['reason'], 'ended_utc': event['occurred_utc']})
    put(arm/'protocol.json', {'samples': 9})
    put(arm/'selection.json', {'rows': [{'question_id': event['question_id']}]})
    put(out/'global_requests.json', {'used': 3536})
    return code, out, arm, event_id


def acknowledged_execute(root, code, event, runner, **overrides):
    options = dict(acknowledge_phase='phase2', acknowledge_arm='Qwen_SC9', resume_acknowledged_event=event)
    options.update(overrides)
    return execute(root, code, root/'labels0', root/'labels1', b'fixture-key', run=runner, **options)


def test_existing_ack_resumes_remaining_phase_and_scores_without_reack_or_reconfigure(tmp_path):
    code, out, arm, event = acknowledged_startup_fixture(tmp_path)
    evidence = [arm/'stop_acknowledgements'/f'{event}.json', arm/'stop_events'/f'{event}.json',
                arm/'fatal_error.json', arm/'checkpoints/919_8353802159390/sample_6/terminal.json',
                out/'global_requests.json']
    original = {p: p.read_bytes() for p in evidence}
    calls = []
    def runner(command, **kwargs):
        calls.append(Path(command[2]).name)
        assert not any(arg.startswith('--acknowledge') or arg.startswith('--resume-acknowledged') for arg in command)
        if calls[-1] == 'run_vote_phase.py':
            assert Path(command[command.index('--manifest')+1]).stem == 'phase2'
            put(out/'phase2/status.json', {'status': 'generation_complete'})
        elif calls[-1] == 'score_votes.py':
            put(tmp_path/'reports'/NAME/'phase2/metrics.json', {'status': 'completed'})
        else:
            pytest.fail('must not reconfigure frozen phases')
        return SimpleNamespace(returncode=0)
    acknowledged_execute(tmp_path, code, event, runner)
    assert calls == ['run_vote_phase.py', 'score_votes.py']
    assert all(path.read_bytes() == value for path, value in original.items())
    recovery = json.loads(next((out/'acknowledged_startup_recoveries').glob('*.json')).read_text())
    assert recovery['next_sample'] == 7 and recovery['terminal_retried'] is False
    assert recovery['acknowledgement_rewritten'] is False and recovery['ledger_modified'] is False
    assert not (out/'private_ledgers').exists()
    assert json.loads((out/'pipeline_status.json').read_text())['status'] == 'completed'


@pytest.mark.parametrize('damage', ['ack_absent', 'ack_mismatch', 'terminal_mismatch',
    'wrong_fatal', 'fatal_before_ack', 'later_started', 'later_terminal', 'wrong_active_arm', 'already_resumed'])
def test_existing_ack_recovery_rejects_unmatched_or_advanced_state(tmp_path, damage):
    code, out, arm, event = acknowledged_startup_fixture(tmp_path)
    if damage == 'ack_absent':
        (arm/'stop_acknowledgements'/f'{event}.json').unlink()
    elif damage == 'ack_mismatch':
        put(arm/'stop_acknowledgements'/f'{event}.json', {'stop_event': {'event_id': 'different'}})
    elif damage == 'terminal_mismatch':
        put(arm/'checkpoints/919_8353802159390/sample_6/terminal.json', {'status': 'completed', 'answer': 'A'})
    elif damage in ('wrong_fatal', 'fatal_before_ack'):
        fatal = json.loads((arm/'fatal_error.json').read_text())
        fatal.update({'message': 'A different error'} if damage == 'wrong_fatal' else {'utc': '2026-11-02T18:40:00+00:00'})
        put(arm/'fatal_error.json', fatal)
    elif damage in ('later_started', 'later_terminal'):
        suffix = 'attempt_1/started.json' if damage == 'later_started' else 'terminal.json'
        put(arm/'checkpoints/919_8353802159390/sample_7'/suffix, {})
    elif damage == 'wrong_active_arm':
        put(out/'phase2/status.json', {'status': 'stopped', 'active_arm': 'Other'})
    else:
        put(out/'acknowledged_startup_recoveries'/f'phase2__Qwen_SC9__{event}.json', {})
    def runner(*a, **k): pytest.fail('must reject before any subprocess')
    with pytest.raises((ValueError, FileNotFoundError)):
        acknowledged_execute(tmp_path, code, event, runner)


def test_existing_ack_recovery_still_stops_if_original_worker_rejects_ledger(tmp_path):
    code, out, arm, event = acknowledged_startup_fixture(tmp_path)
    calls = []
    def runner(command, **kwargs):
        calls.append(Path(command[2]).name)
        return SimpleNamespace(returncode=2)
    with pytest.raises(RuntimeError, match='subprocess_failed'):
        acknowledged_execute(tmp_path, code, event, runner)
    assert calls == ['run_vote_phase.py']
    assert json.loads((out/'pipeline_status.json').read_text())['status'] == 'stopped'
    assert not (tmp_path/'reports'/NAME/'phase2/metrics.json').exists()
