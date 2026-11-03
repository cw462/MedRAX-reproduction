"""Case isolation and baseline comparability; no model or reference I/O."""


MATCH_FIELDS=('model','temperature','top_p','max_tokens','timeout_seconds',
              'history_fields','tools','central_calls_per_episode','medical_calls_per_episode',
              'image_binding_policy','parser','input_question_ids')


def require_baseline(manifest):
    baseline=manifest.get('A0')
    if not baseline or baseline.get('status')!='matched_complete':
        raise ValueError('A0_not_mapped_no_paid_A1_or_source_evolution')
    if baseline.get('common_question_n')!=manifest['target_question_n']:
        raise ValueError('A0_complete_fixed_target_denominator_required')
    if not baseline.get('trajectory_index') or not baseline.get('runner_entrypoint'):
        raise ValueError('actual_A0_trajectories_and_runner_required')


def require_matched_agent(a0,a1):
    changes=[f for f in MATCH_FIELDS if f not in a0 or f not in a1 or a0[f]!=a1[f]]
    if changes:raise ValueError('A1_changed_baseline_fields:'+','.join(changes))


def require_source_isolation(source_cases,target_cases,skill_sources,utility_sources):
    source=set(source_cases);target=set(target_cases)
    if not source or not target or source&target:raise ValueError('case_folds_must_be_nonempty_disjoint')
    for kind,items in [('skills',skill_sources),('utility',utility_sources)]:
        for item in items:
            origins=set(item.get('source_case_ids',[]))
            if not origins or not origins<=source or origins&target:
                raise ValueError(kind+'_unknown_or_crossfold_provenance')


def case_windows(rows,window_size=30):
    """Keep whole cases in a window; close once the trajectory threshold is met."""
    groups={}
    for row in rows:groups.setdefault(str(row['case_id']),[]).append(row)
    window=[]
    for group in groups.values():
        window.extend(group)
        if len(window)>=window_size:yield window;window=[]
    if window:yield window
