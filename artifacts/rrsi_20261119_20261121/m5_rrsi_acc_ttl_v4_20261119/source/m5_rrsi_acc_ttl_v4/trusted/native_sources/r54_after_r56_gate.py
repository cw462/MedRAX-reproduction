"""Metadata-only admission for the user's sequential R56 -> R54 Skill-off queue.

This does not connect, launch, read labels, or interpret incomplete scores.
The actual launcher must separately verify the owned native files and GPU1.
"""
DATASETS={'chexbench':618,'slake':114,'vqarad':116}
R56_RUN='/home/imss/cw/MedRAX_reproduction_20261027/runs/r49_hybrid_skill_r56_20261110'
R56_ARM='M43-IM-GT-S56-DS'

def zero(value):return type(value) is int and value==0

def require_r56_finished(status,expected_controller):
    if status.get('run')!=R56_RUN or status.get('arm')!=R56_ARM:
        raise ValueError('R54_after_R56_wrong_predecessor')
    if (not isinstance(expected_controller,str) or not expected_controller.startswith('controller_recovery')
            or not expected_controller.removeprefix('controller_recovery').isdigit()
            or status.get('active_controller_job')!=expected_controller):
        raise ValueError('R54_after_R56_active_controller_mapping')
    if not zero(status.get('controller_native_exit')):
        raise ValueError('R54_wait_R56_actual_active_controller_zero')
    if (status.get('controller') or {}).get('alive') is True:
        raise ValueError('R54_wait_R56_controller_exit')
    cohorts=status.get('datasets',{});scores=status.get('complete_dataset_scores',{})
    if set(cohorts)!=set(DATASETS) or set(scores)!=set(DATASETS):
        raise ValueError('R54_wait_R56_all_three_complete_scores')
    suffix=expected_controller.removeprefix('controller')
    for ds,n in DATASETS.items():
        v=cohorts[ds]
        if v.get('active_job')!=ds+suffix.replace('_recovery','.recovery',1):
            raise ValueError('R54_after_R56_dataset_native_mapping')
        if (v.get('expected')!=n or v.get('saved')!=n or v.get('contexts')!=n or v.get('feedback')!=n
                or v.get('generation_complete') is not True or scores[ds].get('questions')!=n):
            raise ValueError('R54_wait_R56_full_selected_cohort')
        if any(not zero(v.get(k)) for k in ('runner_native_exit','GEN_native_exit','score_native_exit')):
            raise ValueError('R54_wait_R56_actual_runner_GEN_score_zeros')
        if (v.get('runner') or {}).get('alive') is True:raise ValueError('R54_wait_R56_runner_exit')
    return {'predecessor_run':R56_RUN,'predecessor_active_controller':expected_controller,
        'completed_predecessor_questions':sum(DATASETS.values()),'predecessor_native_and_saved_scores_complete':True,
        'R54_selected_arm':'M43-IM-GT-T54-S0','R54_selected_questions':848,
        'R54_Skill_on_authorized':False,'launch_performed':False,
        'separate_GPU1_and_single_submission_checks_required':True}
