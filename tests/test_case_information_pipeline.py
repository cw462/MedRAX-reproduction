"""Synthetic frozen-plan/orchestration checks; no real inputs, API, GPU or ledger."""
import json
from pathlib import Path
import shutil
import sys
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO/'experiments'))
import configure_case_information as configure
import run_case_information_pipeline as pipeline


def put(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding='utf-8')


def rows(prefix, count, cases):
    return [{'question_id': f'{prefix}_q{i}', 'case_id': f'{prefix}_c{i % cases}',
             'question': 'Synthetic image.\nA) Alpha\nB) Beta', 'images': ['synthetic.png']}
            for i in range(count)]


@pytest.fixture
def fixture(tmp_path):
    code = tmp_path/'code'; (code/'configs').mkdir(parents=True)
    for name in ('case_information_protocol.json', 'deepseek_v41_flash_1017_token_plan_profile.json',
                 'qwen38_flash_token_plan_profile.json'):
        shutil.copyfile(REPO/'configs'/name, code/'configs'/name)
    profile = json.loads((REPO/'configs/qwen37_token_plan_profile.json').read_text(encoding='utf-8'))
    old_config = code/'old_arm.json'
    old = {'root': str(tmp_path), 'model': 'qwen3.7-plus', 'credential_slot': 'token_plan',
           'samples': 9, 'ledger': configure.PRIOR_LEDGER, 'cap_cny': str(configure.FIXED_CAP),
           'new_experiment_budget_cny': '200', 'profile': profile, 'image_root': 'images'}
    put(old_config, old)
    for split, count, cases in [('tune', 402, 99), ('test', 1002, 241)]:
        path = tmp_path/configure.OLD_INPUTS/f'{split}.inputs.jsonl'; path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(''.join(json.dumps(row)+'\n' for row in rows(split, count, cases)), encoding='utf-8')
    return SimpleNamespace(root=tmp_path, code=code, old_config=old_config, old=old)


def configured(f):
    result = configure.configure(f.root, f.code, f.old_config)
    return f.root/result['manifest']


def approval(f):
    path = f.root/'synthetic_approval.json'
    put(path, {'experiment_id': configure.EXPERIMENT_ID, 'plan_version': '1', 'status': 'approved',
               'approved_by': 'user', 'approved_utc': 'synthetic-test-only', 'models': sorted(configure.MODELS)})
    return path


def cache(f, manifest):
    arm = next(a for a in manifest['arms'] if a['mode'] == 'case_evidence')
    cfg = configure.read(f.root/arm['config']); dest = f.root/cfg['evidence_cache']
    mapping = {r['question_id']: r['case_id'] for r in rows('tune', 402, 99)}
    cases = []
    for case in sorted(set(mapping.values())):
        path = f'cases/{case}.json'; put(dest/path, {'evidence_for_model': {'status': 'NO_EVIDENCE'}})
        cases.append({'case_id': case, 'path': path, 'evidence_status': 'NO_EVIDENCE'})
    put(dest/'index.json', {'status': 'complete', 'schema_version': 1, 'case_count': 99,
                           'question_count': 402, 'question_to_case': mapping, 'cases': cases})


def worker(f, calls, fail_arm=None):
    def run(command, **kwargs):
        calls.append((command, kwargs))
        program = Path(command[2]).name
        if program == 'run_case_information.py':
            assert '--tune-labels' not in command and '--test-labels' not in command
            cfg = configure.read(Path(command[command.index('--config')+1]))
            if cfg['run_id'].endswith('_'+str(fail_arm)):
                return SimpleNamespace(returncode=2)
            out = Path(command[command.index('--out')+1])
            preparing = '--prepare-only' in command
            assert kwargs['input'] == (b'' if preparing else b'synthetic-key\n')
            put(out/'status.json', {'status': 'prepared' if preparing else 'generation_complete'})
        elif program == 'score_case_information.py':
            manifest = configure.read(Path(command[command.index('--manifest')+1]))
            assert all(configure.read(f.root/a['out']/'status.json')['status'] == 'generation_complete'
                       for a in manifest['arms'])
            assert kwargs['input'] == b''
            put(Path(command[command.index('--out')+1])/'metrics.json', {'status': 'completed'})
        else:
            raise AssertionError('Unexpected subprocess, including forbidden GPU/tool builder: '+program)
        return SimpleNamespace(returncode=0)
    return run


def test_configuration_freezes_new_namespaces_inputs_and_inherited_budget(fixture):
    manifest_path = configured(fixture)
    manifest = configure.read(manifest_path)
    assert manifest['status'] == 'awaiting_user_confirmation'
    assert (manifest['normal_requests'], manifest['extra_requests'], manifest['hard_requests']) == (2709, 140, 2849)
    assert len(manifest['arms']) == 6 and manifest['additional_budget_granted_cny'] == '0'
    previous = configure.PRIOR_LEDGER
    for arm in manifest['arms']:
        cfg = configure.read(fixture.root/arm['config'])
        assert cfg['inherit_ledger'] == previous
        assert cfg['cap_cny'] == str(configure.FIXED_CAP)
        assert cfg['status'] == 'awaiting_user_confirmation'
        assert not (fixture.root/cfg['ledger']).exists()
        previous = cfg['ledger']
    assert not (fixture.root/configure.PRIOR_LEDGER).exists()
    assert configure.read(fixture.old_config) == fixture.old
    assert configure.configure(fixture.root, fixture.code, fixture.old_config)['new_paid_calls_started'] == 0
    assert not list(fixture.root.rglob('*approval*.json'))


def test_changed_cap_is_rejected_without_reading_or_creating_ledger(fixture):
    put(fixture.old_config, dict(fixture.old, cap_cny='999'))
    with pytest.raises(ValueError, match='without_budget_reset'):
        configured(fixture)
    assert not (fixture.root/configure.REL).exists()


def test_overlapping_cases_are_rejected_before_new_files(fixture):
    path = fixture.root/configure.OLD_INPUTS/'test.inputs.jsonl'
    original = rows('test', 1002, 241)
    for row in original:
        if row['case_id'] == 'test_c0': row['case_id'] = 'tune_c0'
    path.write_text(''.join(json.dumps(r)+'\n' for r in original), encoding='utf-8')
    with pytest.raises(ValueError, match='cases_must_be_disjoint'):
        configured(fixture)
    assert not (fixture.root/configure.REL).exists()


def test_default_preparation_has_no_key_labels_approval_or_gpu(fixture):
    manifest_path = configured(fixture); calls = []
    with patch.object(sys, 'stdin', Mock(buffer=Mock(readline=Mock(side_effect=AssertionError('no credential read'))))):
        result = pipeline.execute(manifest_path, run=worker(fixture, calls))
    assert result['status'] == 'awaiting_user_confirmation' and result['new_paid_calls_started'] == 0
    assert len(calls) == 6
    assert all('--prepare-only' in c[0] and '--approval' not in c[0] for c in calls)
    assert not (fixture.root/configure.REL/'execution_approval.json').exists()
    assert not (fixture.root/'reports'/configure.EXPERIMENT_ID).exists()


def test_execute_requires_explicit_approval_before_any_worker(fixture):
    manifest_path = configured(fixture); run = Mock(side_effect=AssertionError('no worker before approval'))
    with pytest.raises(ValueError, match='approval_file_required'):
        pipeline.execute(manifest_path, execute=True, run=run)
    with patch.object(pipeline, 'require_approval', side_effect=ValueError('bad approval fields')) as checker:
        with pytest.raises(ValueError, match='bad approval'):
            pipeline.execute(manifest_path, execute=True, approval=fixture.root/'not_approved.json', run=run)
        checker.assert_called_once()
    run.assert_not_called()


def test_six_serial_arms_then_one_score_and_completed_resume_does_nothing(fixture):
    manifest_path = configured(fixture); manifest = configure.read(manifest_path)
    cache(fixture, manifest); approved = approval(fixture); calls = []
    with patch.object(pipeline, 'require_approval', return_value=configure.read(approved)):
        result = pipeline.execute(manifest_path, execute=True, approval=approved,
                                  tune_labels=fixture.root/'isolated/tune.labels.json',
                                  test_labels=fixture.root/'isolated/test.labels.json',
                                  key=b'synthetic-key', run=worker(fixture, calls))
    assert result['status'] == 'completed' and len(calls) == 7
    assert Path(calls[-1][0][2]).name == 'score_case_information.py'
    assert all(Path(c[0][2]).name == 'run_case_information.py' for c in calls[:6])
    never = Mock(side_effect=AssertionError('completed run must not repeat generation or scoring'))
    again = pipeline.execute(manifest_path, execute=True, run=never)
    assert again == result
    never.assert_not_called()


def test_generation_failure_stops_before_later_arms_or_scoring(fixture):
    manifest_path = configured(fixture); approved = approval(fixture); calls = []
    with patch.object(pipeline, 'require_approval', return_value=configure.read(approved)):
        with pytest.raises(RuntimeError, match='worker_failed:E1_QwenFlash'):
            pipeline.execute(manifest_path, execute=True, approval=approved,
                             tune_labels=fixture.root/'labels/tune', test_labels=fixture.root/'labels/test',
                             key=b'synthetic-key', run=worker(fixture, calls, fail_arm='E1_QwenFlash'))
    assert len(calls) == 2
    assert configure.read(fixture.root/configure.REL/'pipeline_status.json')['status'] == 'stopped'


def test_missing_e3_cache_stops_without_starting_tools_or_scoring(fixture):
    manifest_path = configured(fixture); approved = approval(fixture); calls = []
    with patch.object(pipeline, 'require_approval', return_value=configure.read(approved)):
        with pytest.raises(RuntimeError, match='prebuilt_evidence_cache'):
            pipeline.execute(manifest_path, execute=True, approval=approved,
                             tune_labels=fixture.root/'labels/tune', test_labels=fixture.root/'labels/test',
                             key=b'synthetic-key', run=worker(fixture, calls))
    assert len(calls) == 4
    assert all(Path(c[0][2]).name == 'run_case_information.py' for c in calls)
