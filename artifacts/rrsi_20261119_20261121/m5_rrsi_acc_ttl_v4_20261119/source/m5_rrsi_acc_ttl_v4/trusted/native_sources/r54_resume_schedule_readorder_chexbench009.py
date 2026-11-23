"""R54 Off serial continuation after actual complete R56; importing performs no work."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
from r54_after_r56_gate import R56_RUN, R56_ARM, require_r56_finished
from r54_after_r56_chexbench_gate import HELD, require_r56_chexbench_finished
from r54_off_resume_evidence import (SCHEMA, ARM, COUNTS, CONTROLLER, JOBS, FINAL_EXIT,
                                     require_resume, require_generation_zero, approved_recovery, read)
from r54_resume_worker import await_gpu1, save
from r54_resume_readorder_guard001 import require_native_full

MAPPING = {'schema': SCHEMA, 'selected_arm': ARM, 'active_controller': CONTROLLER,
           'dataset_jobs': JOBS, 'generation_exit_file': FINAL_EXIT,
           'queue_status_file': 'queue_status.off_resume002.json',
           'score_jobs': {ds: ds + '.off_resume002.score' for ds in COUNTS},
           'maximum_new_local_recovery_attempts': 1, 'old_outputs_modified': False,
           'Skill_on_authorized': False, 'external_unknown_resends_authorized': False,
           'actual_user_request': '\u540e\u9762R56\u8dd1\u5b8c\u4e4b\u540e\uff0c\u53ef\u4ee5\u628a\u65e0skill\u7ec4\u7ee7\u7eed\u63a5\u4e0a\u8dd1\u5b8c',
           'local_recovery_limit_is_implementation_inference': True,
           'preserved_saved_predictions': 308, 'new_final_predictions': 540}

PROTOCOLS = (('protocol_amendment001.json', 'r56_schema_repair_amendment_v1'),
             ('protocol_resource_recovery002.json', 'r56_user_stop_R54_continue_R56_gpu1_v1'),
             ('protocol_analysis_recovery003.json', 'r56_duplicate_analysis_credit_repair_v1'),
             ('protocol_analysis_recovery004.json', 'r56_analysis_envelope_parser_v1'),
             ('protocol_analysis_recovery005.json', 'r56_exact_context_envelope_parser_v1'),
             ('protocol_governance_recovery006.json', 'r56_single_received_merge_delimiter_recovery_v1'),
             ('protocol_writer_continuation007.json', 'r56_writer_failure_continuation_v1'),
             ('protocol_writer_continuation008.json', 'r56_writer_failure_continuation_replay_fix_v2'))


def native(path):
    path = Path(path)
    if not path.is_file():
        raise ValueError('R54_wait_predecessor_actual_native_file:' + path.name)
    return int(path.read_text(encoding='utf-8').strip())


def exited_pid(path, *, proc_root=Path('/proc')):
    path = Path(path)
    if not path.is_file():
        raise ValueError('R54_predecessor_missing_saved_PID:' + path.name)
    pid = int(path.read_text()); proc = Path(proc_root) / str(pid)
    if proc.is_dir():
        try:
            state = (proc / 'stat').read_text().split(') ', 1)[1].split()[0]
            if state != 'Z':
                raise ValueError('R54_wait_predecessor_process_exit:' + str(pid))
        except FileNotFoundError:
            pass
    return {'pid': pid, 'alive': False}


def predecessor_admission(expected_controller, *, run=Path(R56_RUN), proc_root=Path('/proc'), chexbench_only=False):
    """Only paths/counts, native integers, complete metadata and saved full scores."""
    run = Path(run); jobs = run / 'jobs'; active = None
    for filename, schema in PROTOCOLS:
        path = jobs / filename
        if path.is_file():
            value = read(path)
            if value.get('schema') != schema:
                raise ValueError('R54_predecessor_protocol_schema_mismatch')
            active = value
    if not active or expected_controller != 'controller_recovery008' or active.get('active_controller') != expected_controller:
        raise ValueError('R54_predecessor_latest_actual_mapping_mismatch')
    if (active.get('bound_analysis_event') != 'analysis_chexbench_slake_0096'
            or active.get('maximum_new_bound_requests') != 1
            or native(jobs / 'controller_recovery006.exitcode') != 1
            or native(jobs / 'controller_recovery007.exitcode') != 1):
        raise ValueError('R54_predecessor_writer008_protocol_or_native_history')
    suffix = expected_controller.removeprefix('controller_')
    if (active.get('dataset_jobs') != {ds: ds + '.' + suffix for ds in COUNTS}
            or active.get('final_generation_exit_file') != 'generation.' + suffix + '.exitcode'):
        raise ValueError('R54_predecessor_dataset_or_GEN_mapping_mismatch')
    status = {'run': R56_RUN, 'arm': R56_ARM, 'active_controller_job': expected_controller,
              'controller_native_exit': native(jobs / (expected_controller + '.exitcode')),
              'controller': exited_pid(jobs / (expected_controller + '.pid'), proc_root=proc_root),
              'datasets': {}, 'complete_dataset_scores': {}}
    if chexbench_only:
        scope = run / 'recovery008/chexbench_only'
        status['chexbench_scope_install'] = read(scope / 'installed.json')
        for ds in HELD:
            out = run / 'generation' / ds
            services = out / 'services'
            label = active['dataset_jobs'][ds]
            runner_file = jobs / (label + '.runner.pid')
            receipt = scope / (ds + '.held.json')
            runner_exit = jobs / (label + '.exitcode')
            gen_exit = out / active['final_generation_exit_file']
            score_exit = jobs / (label + '.score.exitcode')
            if any((jobs / (label + '.score.' + suffix)).exists() for suffix in ('started.json', 'completed.json')):
                raise ValueError('R54_R56_held_cohort_score_started')
            status['datasets'][ds] = {
                'active_job': label, 'expected': COUNTS[ds],
                'saved': len(list((out / 'predictions' / R56_ARM).glob('*.json'))),
                'contexts': len(list((out / 'contexts').glob('*.json'))),
                'feedback': len(list((out / 'feedback').glob('*.json'))),
                'generation_complete': (out / 'complete.json').is_file(),
                'runner': exited_pid(runner_file, proc_root=proc_root) if runner_file.exists() else None,
                'runner_native_exit': native(runner_exit) if runner_exit.exists() else None,
                'GEN_native_exit': native(gen_exit) if gen_exit.exists() else None,
                'score_native_exit': native(score_exit) if score_exit.exists() else None,
                'cohort_hold': read(receipt) if receipt.exists() else None,
                'main_sends': len(list((services / 'calls/R49-AGENT').glob('*/*/started.json'))),
                'activation_META_sends': len(list((services / 'calls/R49-META').glob('*/*/started.json'))),
                'writer_sends': len(list((services / 'calls/R56-WRITER').glob('*/*/started.json'))),
                'embedding_sends': len(list((services / 'embeddings').glob('*/started.json'))),
            }
    selected = {'chexbench': COUNTS['chexbench']} if chexbench_only else COUNTS
    for ds, n in selected.items():
        out = run / 'generation' / ds; services = out / 'services'; label = active['dataset_jobs'][ds]
        complete = read(out / 'complete.json'); summary = read(out / 'analysis/summary.json')
        if (complete.get('status') != 'generation_complete' or complete.get('arm') != R56_ARM
                or complete.get('questions') != n or summary.get('arm') != R56_ARM
                or summary.get('dataset') != ds or summary.get('questions') != n):
            raise ValueError('R54_predecessor_complete_and_score_identity')
        if (read(jobs / (label + '.score.completed.json')).get('native_exit') != 0
                or read(jobs / (label + '.score.started.json')).get('whole_cohort') != n):
            raise ValueError('R54_predecessor_saved_whole_score_receipt_required')
        value = {'active_job': label, 'expected': n, 'generation_complete': True,
                 'saved': len(list((out / 'predictions' / R56_ARM).glob('*.json'))),
                 'contexts': len(list((out / 'contexts').glob('*.json'))),
                 'feedback': len(list((out / 'feedback').glob('*.json'))),
                 'runner_native_exit': native(jobs / (label + '.exitcode')),
                 'GEN_native_exit': native(out / active['final_generation_exit_file']),
                 'score_native_exit': native(jobs / (label + '.score.exitcode')),
                 'runner': exited_pid(jobs / (label + '.runner.pid'), proc_root=proc_root)}
        for slot in ('R49-AGENT', 'R49-META', 'R56-WRITER'):
            sends = {p.parent for p in (services / 'calls' / slot).glob('*/*/started.json')}
            replies = {p.parent for p in (services / 'calls' / slot).glob('*/*/response.json')}
            if slot == 'R56-WRITER':
                for call in sends - replies:
                    receipt = read(call / 'result.json')
                    rejection = read(call / 'continued_after_failure007.json')
                    if (receipt.get('response_received') is not False
                            or receipt.get('send_state') != 'unknown_no_reissue'
                            or rejection.get('state') != 'unknown_send_no_reissue'
                            or rejection.get('event') != call.parent.name
                            or rejection.get('attempt') != int(call.name)
                            or rejection.get('automatic_retry') is not False):
                        raise ValueError('R54_predecessor_unrecorded_writer_send')
                replies = replies | (sends - replies)
            if sends != replies:
                raise ValueError('R54_predecessor_unclosed_API_requests')
        status['datasets'][ds] = value
        status['complete_dataset_scores'][ds] = {'questions': n}
    verify = require_r56_chexbench_finished if chexbench_only else require_r56_finished
    gate = verify(status, expected_controller)
    return {'status': status, 'active_controller': expected_controller,
            'actual_remote_native_files_checked': True, 'gate': gate,
            'utc': datetime.now(timezone.utc).isoformat(), 'GPU_or_model_or_GT_calls': 0}


def validate_programs(programs, run, code):
    if set(programs) != set(COUNTS):
        raise ValueError('R54_resume_exactly_three_Off_programs')
    for ds, n in COUNTS.items():
        command = programs[ds]
        expected = {'--skill': 'off', '--dataset': ds, '--expect-questions': str(n),
                    '--out': (Path(run) / 'generation' / ds / 'off').as_posix()}
        if (command[2].replace('\\', '/') != (Path(code) / 'experiments/run_r54_off_resume002.py').as_posix()
                or '--execute' in command or '--api-key-stdin' in command
                or any(command.count(k) != 1 or (command[command.index(k) + 1].replace('\\', '/')
                       if k == '--out' else command[command.index(k) + 1]) != v
                       for k, v in expected.items())):
            raise ValueError('R54_resume_program_or_Off_scope_changed')


def require_preserved_prefix(run):
    """An absent old prediction must never turn into authorization to regenerate it."""
    run = Path(run); out = run / 'generation/chexbench/off'
    manifest = read(out / 'manifest.json'); ids = [v['question_id'] for v in manifest['inputs']]
    from r54_off_resume_evidence import QID
    if (manifest.get('arm') != ARM or manifest.get('skill_enabled') is not False
            or len(ids) != COUNTS['chexbench'] or ids[308] != QID):
        raise ValueError('R54_original_308_prefix_manifest_identity')
    for folder in ('predictions/' + ARM, 'prediction_events', 'feedback', 'steps', 'contexts'):
        expected = set(ids[:309] if folder == 'contexts' else ids[:308])
        if {p.stem for p in (out / folder).glob('*.json')} != expected:
            raise ValueError('R54_preserved_308_prefix_must_not_be_regenerated:' + folder)
    calls = out / 'services/calls/R49-AGENT'
    starts = {p.parent for p in calls.glob('*/*/started.json')}
    replies = {p.parent for p in calls.glob('*/*/response.json')}
    if starts != replies or len(starts) != 815:
        raise ValueError('R54_preserved_815_closed_main_requests_required')
    for ds in ('slake', 'vqarad'):
        out = run / 'generation' / ds / 'off'
        if (any((out / 'predictions').glob('*/*.json')) or any((out / 'contexts').glob('*.json'))
                or any((out / 'services/calls').glob('*/*/*/started.json'))):
            raise ValueError('R54_original_unstarted_Off_cohort_not_fresh')


def queue_status(run, value):
    jobs = Path(run) / 'jobs'; path = jobs / MAPPING['queue_status_file']
    value.update(schema=SCHEMA, arm=ARM, utc=datetime.now(timezone.utc).isoformat())
    temporary = path.with_suffix('.tmp'); temporary.write_text(json.dumps(value, indent=2), encoding='utf-8')
    temporary.replace(path)


def save_native(path, value):
    if type(value) is not int:
        raise ValueError('R54_actual_native_integer_required')
    with Path(path).open('x', encoding='utf-8') as handle:
        handle.write(str(value) + '\n')


def run_schedule(run, code, programs, python, main_key, embedding_key, expected_controller,
                 *, popen=subprocess.Popen, run_process=subprocess.run, gpu_gate=await_gpu1,
                 chexbench_only=False):
    """Called only by the separately verified and once-submitted controller."""
    run = Path(run); code = Path(code); jobs = run / 'jobs'; scope = run / 'off_resume002'
    validate_programs(programs, run, code)
    if not main_key.strip() or not embedding_key.strip():
        raise ValueError('R54_resume_stdin_credentials_required')
    if read(scope / 'ENTRY_VERIFIED.json').get('passed') is not True:
        raise ValueError('R54_resume_new_entry_verification_required')
    predecessor_admission(expected_controller, chexbench_only=chexbench_only)
    for ds in COUNTS:
        require_resume(run / 'generation' / ds / 'off')
    require_preserved_prefix(run)
    approved_recovery(run / 'generation/chexbench/off')
    save(scope / 'CONTROLLER_CONSUMED.json', {'utc': datetime.now(timezone.utc).isoformat(),
         'single_submission': True, 'selected_arm': ARM})
    env = dict(os.environ, R49_EMBEDDING_API_KEY=embedding_key.strip().decode('utf-8'),
               LANGCHAIN_TRACING_V2='false', LANGSMITH_TRACING='false', PYTHONDONTWRITEBYTECODE='1')
    for flag in ('CUDA_LAUNCH_BLOCKING', 'TORCH_SHOW_CPP_STACKTRACES'):
        env.pop(flag, None)
    for ds, n in COUNTS.items():
        out = run / 'generation' / ds / 'off'; label = JOBS[ds]
        for suffix in ('send_intent.json', 'started.json', 'runner.pid', 'exitcode'):
            if (jobs / (label + '.' + suffix)).exists():
                raise RuntimeError('R54_resume_submission_consumed_no_reissue:' + label)
        gpu_gate(scope / 'dataset_GPU_admissions' / ds)
        command = programs[ds] + ['--execute', '--api-key-stdin']
        save(jobs / (label + '.send_intent.json'), {'command': command, 'dataset': ds, 'mode': 'off',
             'utc': datetime.now(timezone.utc).isoformat(), 'existing_answers_regenerated': False})
        with (jobs / (label + '.stdout.log')).open('xb') as stdout, (jobs / (label + '.stderr.log')).open('xb') as stderr:
            child = popen(command, stdin=subprocess.PIPE, stdout=stdout, stderr=stderr, cwd=code, env=env)
            with (jobs / (label + '.runner.pid')).open('x', encoding='utf-8') as handle:
                handle.write(str(child.pid) + '\n')
            save(jobs / (label + '.started.json'), {'pid': child.pid, 'command': command, 'arm': ARM,
                 'schema': SCHEMA, 'dataset': ds, 'mode': 'off'})
            queue_status(run, {'state': 'running_off_resume_cohort', 'dataset': ds,
                              'active_job': label, 'runner_pid': child.pid})
            child.communicate(main_key)
        rc = child.returncode
        save_native(jobs / (label + '.exitcode'), rc); save_native(out / FINAL_EXIT, rc)
        if rc:
            queue_status(run, {'state': 'off_resume_cohort_failed_stop_no_retry', 'dataset': ds,
                              'active_job': label, 'native_exit': rc})
            raise SystemExit(rc)
        require_native_full(out)
        score_label = MAPPING['score_jobs'][ds]
        command = [python, '-u', str(code / 'experiments/report_r54_off_resume_readorder001.py'),
                   '--run', str(out), '--out', str(out / 'analysis')]
        save(jobs / (score_label + '.started.json'), {'command': command, 'dataset': ds,
             'whole_cohort': n, 'schema': SCHEMA, 'mode': 'off'})
        queue_status(run, {'state': 'scoring_complete_off_cohort_once', 'dataset': ds, 'active_job': score_label})
        with (jobs / (score_label + '.stdout.log')).open('xb') as stdout, (jobs / (score_label + '.stderr.log')).open('xb') as stderr:
            completed = run_process(command, stdout=stdout, stderr=stderr, cwd=code, env=env)
        save_native(jobs / (score_label + '.exitcode'), completed.returncode)
        if completed.returncode:
            queue_status(run, {'state': 'off_resume_whole_score_failed_stop_no_retry', 'dataset': ds,
                              'active_job': score_label, 'native_exit': completed.returncode})
            raise SystemExit(completed.returncode)
        save(jobs / (score_label + '.completed.json'), {'native_exit_code': 0, 'whole_cohort': n, 'dataset': ds})
    queue_status(run, {'state': 'all_three_resumed_Off_cohorts_and_scores_zero', 'questions': sum(COUNTS.values()),
                      'cancelled_Skill_on_requests': 0})
