"""Native evidence for the user's R54 Skill-off-only scope selection."""
import json
from pathlib import Path

SCHEMA = 'r54_user_selected_off_only_v1'
ARM = 'M43-IM-GT-T54-S0'
DATASETS = ('chexbench', 'slake', 'vqarad')
COUNTS = {'chexbench': 618, 'slake': 114, 'vqarad': 116}
JOBS = {'chexbench': 'chexbench.off', 'slake': 'slake.off_only001', 'vqarad': 'vqarad.off_only001'}
EXITS = {'chexbench': 'generation.exitcode', 'slake': 'generation.off_only001.exitcode', 'vqarad': 'generation.off_only001.exitcode'}


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def native(path):
    return int(Path(path).read_text(encoding='utf-8').strip())


def require_no_on_requests(run):
    run = Path(run)
    for ds in DATASETS:
        out = run / 'generation' / ds / 'on'
        value = read(out / 'USER_CANCELLED_SKILL_ON.json')
        if (value.get('schema') != 'r54_user_cancelled_unstarted_skill_on_v1'
                or value.get('dataset') != ds or value.get('arm') != 'M43-IM-GT-T54-S54'
                or value.get('inference_started') is not False
                or any(value.get(k) != 0 for k in ('predictions', 'main_requests', 'META_requests', 'embedding_requests'))):
            raise ValueError('R54_user_cancelled_On_identity')
        if any((run / 'jobs' / (ds + '.on.' + name)).exists() for name in ('started.json', 'runner.pid', 'exitcode')):
            raise ValueError('R54_cancelled_On_must_remain_unstarted')
        if any(out.glob('services/calls/*/*/*/started.json')) or any(out.glob('predictions/*/*.json')):
            raise ValueError('R54_cancelled_On_has_formal_requests_or_predictions')


def first_off_ready(run):
    """Wait for the original parent to reap/save CheX; never restart that child."""
    run = Path(run); jobs = run / 'jobs'; out = run / 'generation/chexbench/off'
    paths = [jobs / 'chexbench.off.exitcode', out / 'generation.exitcode']
    present = [path.is_file() for path in paths]
    for path, exists in zip(paths, present):
        if exists and native(path) != 0:
            raise RuntimeError('R54_existing_CheX_failed_no_automatic_restart')
    if not all(present) or not (jobs / 'controller.exitcode').is_file():
        return False
    if native(jobs / 'controller.exitcode') != 1:
        raise ValueError('R54_original_controller_expected_user_boundary_exit1')
    require_no_on_requests(run)
    log = (jobs / 'controller.log').read_text(encoding='utf-8', errors='replace')
    if 'fresh_independent_cohort_required' not in log or 'AssertionError' not in log:
        raise ValueError('R54_original_boundary_exit_source_not_preserved')
    return True


def require_scope(out):
    out = Path(out); value = read(out / 'protocol_off_only.json'); ds = value.get('dataset')
    if ds not in COUNTS or value.get('schema') != SCHEMA or value.get('selected_arm') != ARM:
        raise ValueError('R54_off_only_scope_identity')
    if (value.get('dataset_jobs') != JOBS or value.get('generation_exit_files') != EXITS
            or value.get('active_dataset_job') != JOBS[ds]
            or value.get('active_controller') != 'controller_off_only001'
            or value.get('request_source') != 'actual_user_message_R54_without_Skill_only'
            or value.get('existing_outputs_modified') is not False
            or value.get('existing_CheX_restarted') is not False):
        raise ValueError('R54_off_only_scope_mapping')
    return value


def require_generation_zero(out):
    out = Path(out); value = require_scope(out); ds = value['dataset']; run = out.parents[2]
    if native(run / 'jobs' / (JOBS[ds] + '.exitcode')) != 0 or native(out / EXITS[ds]) != 0:
        raise ValueError('R54_actual_off_runner_and_GEN_zero_required')
    if ds != 'chexbench' and ((out / 'generation.exitcode').exists()
            or (run / 'jobs' / (ds + '.off.exitcode')).exists()):
        raise ValueError('R54_original_unstarted_off_exits_must_remain_absent')
    if native(run / 'jobs/controller.exitcode') != 1:
        raise ValueError('R54_original_user_boundary_controller1_required')
    require_no_on_requests(run)
    return value
