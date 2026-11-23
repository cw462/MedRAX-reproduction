"""Admission metadata for R54 Off after the first R56 cohort."""
from r54_after_r56_gate import DATASETS, R56_ARM, R56_RUN, zero

CONTROLLER = 'controller_recovery008'
HELD = ('slake', 'vqarad')
HOLD_EXIT = 75
SCOPE = 'R56_CheXBench_only'


def held_receipt(receipt, dataset, pid):
    return (
        receipt.get('schema') == 'r56_cohort_held_before_inference_v1'
        and receipt.get('dataset') == dataset
        and type(pid) is int and pid > 0 and receipt.get('pid') == pid
        and receipt.get('exit_requested') == HOLD_EXIT
        and receipt.get('inference_started') is False
        and zero(receipt.get('model_API_GPU_GT_calls'))
    )


def require_r56_chexbench_finished(status, expected_controller=CONTROLLER):
    if (status.get('run') != R56_RUN or status.get('arm') != R56_ARM
            or expected_controller != CONTROLLER or status.get('active_controller_job') != CONTROLLER):
        raise ValueError('R54_CheXBench_predecessor_identity')
    install = status.get('chexbench_scope_install') or {}
    if (install.get('schema') != 'r56_chexbench_only_guard_installed_v1'
            or install.get('controller') != CONTROLLER or install.get('held_datasets') != list(HELD)
            or install.get('held_exit_code') != HOLD_EXIT):
        raise ValueError('R54_CheXBench_owned_hold_install_required')
    if (status.get('controller_native_exit') != HOLD_EXIT
            or (status.get('controller') or {}).get('alive') is not False):
        raise ValueError('R54_wait_R56_controller_intentional_exit')
    cohorts = status.get('datasets', {})
    scores = status.get('complete_dataset_scores', {})
    n = DATASETS['chexbench']
    if set(cohorts) != set(DATASETS) or set(scores) != {'chexbench'} or scores['chexbench'].get('questions') != n:
        raise ValueError('R54_wait_R56_CheXBench_saved_whole_score')
    for ds, cohort in cohorts.items():
        if cohort.get('active_job') != ds + '.recovery008' or cohort.get('expected') != DATASETS[ds]:
            raise ValueError('R54_CheXBench_dataset_native_mapping')
    chex = cohorts['chexbench']
    if (any(chex.get(k) != n for k in ('saved', 'contexts', 'feedback'))
            or chex.get('generation_complete') is not True
            or (chex.get('runner') or {}).get('alive') is not False
            or any(not zero(chex.get(k)) for k in ('runner_native_exit', 'GEN_native_exit', 'score_native_exit'))):
        raise ValueError('R54_wait_R56_CheXBench_actual_native_zeros')
    for ds in HELD:
        v = cohorts[ds]
        if (any(not zero(v.get(k)) for k in ('saved', 'contexts', 'feedback', 'main_sends',
                'activation_META_sends', 'writer_sends', 'embedding_sends'))
                or v.get('generation_complete') is not False or v.get('score_native_exit') is not None):
            raise ValueError('R54_R56_held_cohort_inference_forbidden')
        if ds == 'slake':
            runner = v.get('runner') or {}
            if (runner.get('alive') is not False or v.get('runner_native_exit') != HOLD_EXIT
                    or v.get('GEN_native_exit') != HOLD_EXIT
                    or not held_receipt(v.get('cohort_hold') or {}, ds, runner.get('pid'))):
                raise ValueError('R54_wait_R56_SLAKE_intentional_hold')
        elif any(v.get(k) is not None for k in ('runner', 'runner_native_exit', 'GEN_native_exit', 'cohort_hold')):
            raise ValueError('R54_R56_VQA_RAD_unstarted_required')
    return {
        'predecessor_scope': SCOPE,
        'predecessor_run': R56_RUN,
        'predecessor_active_controller': CONTROLLER,
        'completed_predecessor_questions': n,
        'completed_predecessor_datasets': {'chexbench': n},
        'held_predecessor_datasets': list(HELD),
        'predecessor_native_and_saved_scores_complete': True,
        'R54_selected_questions': 848,
    }
