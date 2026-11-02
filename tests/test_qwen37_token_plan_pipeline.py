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
