"""Versioned R54 Off continuation evidence; no launch, model calls or labels."""
import json
from pathlib import Path
from r54_after_r56_gate import require_r56_finished
from r54_after_r56_chexbench_gate import SCOPE, require_r56_chexbench_finished
from r56_pause_for_r54 import SCOPE as PAUSED_SCOPE, paused_gate
from r54_off_only_completion import require_no_on_requests

SCHEMA = 'r54_off_resume_after_full_R56_v1'
ARM = 'M43-IM-GT-T54-S0'
COUNTS = {'chexbench': 618, 'slake': 114, 'vqarad': 116}
CONTROLLER = 'controller_off_resume002'
JOBS = {ds: ds + '.off_resume002' for ds in COUNTS}
FINAL_EXIT = 'generation.off_resume002.exitcode'
QID = 'chexbench_openi_0070'
KEY = '42559bd71161ef9842efdc65727cf2518d03ff54c0092ec7a85868b97da6147a'
ORDINAL = 6
TOOL = 'medgemma'


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def native(path):
    return int(Path(path).read_text(encoding='utf-8').strip())


def require_old_stop(run):
    run = Path(run); jobs = run / 'jobs'
    for path, expected in ((jobs / 'controller.exitcode', 241),
                           (jobs / 'controller_off_only001.exitcode', 143),
                           (jobs / 'chexbench.off.exitcode', -15),
                           (run / 'generation/chexbench/off/generation.exitcode', -15)):
        if native(path) != expected:
            raise ValueError('R54_original_stop_native_must_remain_unchanged')
    stop = read(jobs / 'USER_STOP_FOR_R56_COMPLETED.json')
    value = stop.get('counts', {}).get('chexbench.off', {})
    if (stop.get('status') != 'USER_STOPPED_R54_INCOMPLETE_CONTINUE_R56'
            or value.get('predictions') != 308 or value.get('contexts') != 309
            or value.get('main_sends') != 815 or value.get('main_responses') != 815
            or stop.get('saved_predictions_modified') is not False):
        raise ValueError('R54_original_stopped_scope_binding')
    for ds in ('slake', 'vqarad'):
        for path in (jobs / (ds + '.off.exitcode'), jobs / (ds + '.off_only001.exitcode'),
                     run / 'generation' / ds / 'off/generation.exitcode',
                     run / 'generation' / ds / 'off/generation.off_only001.exitcode'):
            if path.exists():
                raise ValueError('R54_old_unstarted_native_must_remain_absent')
    require_no_on_requests(run)
    return stop


def require_resume(out, *, predecessor=True):
    out = Path(out); run = out.parents[2]
    value = read(out / 'off_resume002.json'); ds = value.get('dataset')
    if (ds not in COUNTS or value.get('schema') != SCHEMA or value.get('selected_arm') != ARM
            or value.get('active_controller') != CONTROLLER or value.get('dataset_jobs') != JOBS
            or value.get('active_dataset_job') != JOBS.get(ds)
            or value.get('generation_exit_file') != FINAL_EXIT
            or value.get('maximum_new_local_recovery_attempts') != 1
            or value.get('old_outputs_modified') is not False
            or value.get('Skill_on_authorized') is not False
            or value.get('external_unknown_resends_authorized') is not False):
        raise ValueError('R54_resume002_contract_identity')
    global_value = read(run / 'jobs/protocol_off_resume002.json')
    if value != dict(global_value, dataset=ds, active_dataset_job=JOBS[ds]):
        raise ValueError('R54_resume002_global_dataset_contract_mismatch')
    require_old_stop(run)
    if predecessor:
        admission = read(run / 'off_resume002/R56_completed_admission.json')
        if admission.get('actual_remote_native_files_checked') is not True:
            raise ValueError('R54_resume002_requires_actual_predecessor_native_files')
        if (admission.get('gate') or {}).get('predecessor_scope') == SCOPE:
            if require_r56_chexbench_finished(admission['status'], admission['active_controller']) != admission['gate']:
                raise ValueError('R54_resume002_CheXBench_admission_receipt_mismatch')
        elif (admission.get('gate') or {}).get('predecessor_scope') == PAUSED_SCOPE:
            if paused_gate(admission['status']) != admission['gate']:
                raise ValueError('R54_resume002_paused_admission_receipt_mismatch')
        else:
            require_r56_finished(admission['status'], admission['active_controller'])
    return value


def recovery_folder(out):
    return Path(out).parents[2] / 'off_resume002/local_tool_recovery001'


def original_interruption(out):
    out = Path(out); require_resume(out)
    if read(out / 'off_resume002.json')['dataset'] != 'chexbench':
        raise ValueError('R54_local_recovery_is_CheX_only')
    cache = out / 'services/tool_cache' / KEY
    request = read(cache / 'request.json'); started = read(cache / 'started.json')
    if (request.get('tool') != TOOL or request.get('backend') != TOOL
            or started.get('identity', {}).get('args') != request.get('args')
            or started.get('identity', {}).get('backend') != TOOL):
        raise ValueError('R54_user_interrupted_local_source_identity')
    forbidden = ('result.json', 'backend.exit.json', 'backend.stdout.log', 'backend.stderr.log',
                 'backend.timeout.json', 'artifacts/backend_events.json')
    if any((cache / name).exists() for name in forbidden):
        raise ValueError('R54_original_interruption_must_not_be_filled_or_reclassified')
    stop = read(out.parents[2] / 'jobs/USER_STOP_FOR_R56_COMPLETED.json')
    if not any(v.get('pid') == 3983473 and v.get('signal') == 'SIGTERM'
               for v in stop.get('signals', [])):
        raise ValueError('R54_local_attempt_not_bound_to_known_user_stop')
    return cache, request, started


def recovery_result(out):
    out = Path(out); cache, old_request, old_started = original_interruption(out)
    folder = recovery_folder(out); binding = read(folder / 'ORIGINAL_BINDING.json')
    if binding != {'original_cache': str(cache), 'request': old_request, 'started': old_started,
                   'original_generation_state': 'unknown_after_known_user_stop'}:
        raise ValueError('R54_original_local_attempt_binding_changed')
    request = read(folder / 'request.json'); result = read(folder / 'result.json')
    if ({k: v for k, v in request.items() if k != 'artifact_dir'}
            != {k: v for k, v in old_request.items() if k != 'artifact_dir'}
            or request.get('artifact_dir') != str(folder / 'artifacts')):
        raise ValueError('R54_local_recovery_changed_original_inputs')
    started = read(folder / 'started.json'); admission = read(folder / 'GPU_admission.json')
    if (started.get('identity') != old_started['identity']
            or started.get('new_attempt_number') != 1 or started.get('gpu') != '1'
            or admission.get('gpu') != '1' or admission.get('free_mib_observed', 0) < 18432
            or admission.get('compute_processes') != []):
        raise ValueError('R54_local_recovery_identity_or_GPU_admission')
    if (native(folder / 'worker.exitcode') != 0
            or read(folder / 'backend.exit.json').get('returncode') != 0
            or result.get('status') != 'completed' or result.get('error')
            or result.get('identity') != old_started['identity']
            or result.get('cuda_visible_devices') != '1'
            or any(v.get('status') == 'started_unknown' for v in result.get('actual_model_events', []))
            or not any(v.get('kind') == 'generate' and v.get('status') == 'completed'
                       for v in result.get('actual_model_events', []))):
        raise ValueError('R54_local_recovery_requires_actual_healthy_original_tool')
    return {'directory': folder, 'result': result, 'request': request}


def adoption_value(folder):
    return {'schema': SCHEMA, 'question_id': QID, 'selection_ordinal': ORDINAL,
            'original_cache_key': KEY, 'new_attempt_directory': str(folder),
            'new_local_attempts': 1, 'original_generation_state': 'unknown_after_known_user_stop',
            'old_outputs_modified': False, 'external_API_requests_resent': False}


def approved_recovery(out):
    value = recovery_result(out); folder = value['directory']
    adoption = read(folder / 'ADOPTION.json'); expected = adoption_value(folder)
    if any(adoption.get(k) != v for k, v in expected.items()):
        raise ValueError('R54_local_recovery_adoption_binding')
    return dict(value, adoption=adoption)


def require_generation_zero(out):
    out = Path(out); value = require_resume(out); ds = value['dataset']
    for path in (out / FINAL_EXIT, out.parents[2] / 'jobs' / (JOBS[ds] + '.exitcode')):
        if native(path) != 0:
            raise ValueError('R54_resume002_actual_runner_and_GEN_zero_required')
    manifest = read(out / 'manifest.json'); complete = read(out / 'complete.json')
    if (manifest.get('dataset') != ds or manifest.get('arm') != ARM
            or manifest.get('skill_enabled') is not False
            or len(manifest.get('inputs', [])) != COUNTS[ds]
            or complete.get('status') != 'generation_complete' or complete.get('arm') != ARM
            or complete.get('questions') != COUNTS[ds]):
        raise ValueError('R54_resume002_full_cohort_required')
    for name in ('predictions/' + ARM, 'prediction_events', 'contexts', 'feedback', 'steps'):
        if len(list((out / name).glob('*.json'))) != COUNTS[ds]:
            raise ValueError('R54_resume002_full_saved_artifacts_required')
    if (any((out / 'services/calls/R49-META').glob('*/*/started.json'))
            or any((out / 'services/embeddings').glob('*/started.json'))):
        raise ValueError('R54_Skill_off_requires_zero_META_and_embeddings')
    return value
