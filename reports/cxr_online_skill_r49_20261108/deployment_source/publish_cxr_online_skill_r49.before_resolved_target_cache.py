"""Explicit future publication phases for the completed three-dataset R49 run.

This private helper is excluded from publication. It never generates, scores or
exports answers. Prepare requires finished reports and public reproduction for
all three datasets before writing an allowlist or publication manifest. Content
checks use JSON, secret patterns, ordinary links and hosting limits, not hashes.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import subprocess
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
REPORT_REL = 'reports/cxr_online_skill_r49_20261108'
REPORT = ROOT/REPORT_REL
RECEIPTS = ROOT/'local_assets/r49_publication'
MANIFEST = REPORT/'PUBLICATION_MANIFEST.json'
EXPECTED_BASE = '641746b8680c3b62d655abb154ab773cd57e6388'
ARM = 'M43-IM-GT-S49'
DATASETS = {
    'chexbench': {'n': 618, 'baseline': 'M43', 'baseline_correct': 466, 'groups': 488, 'repeats': 130, 'windows': 21},
    'slake': {'n': 114, 'baseline': 'M43', 'baseline_correct': 108, 'groups': 30, 'repeats': 84, 'windows': 4},
    'vqarad': {'n': 116, 'baseline': 'M42', 'baseline_correct': 100, 'groups': 58, 'repeats': 58, 'windows': 4},
}
# Exactly the current new R49 modules and tests; no upstream, R48 or private file.
SCRIPTS = sorted(p.relative_to(ROOT).as_posix() for folder in ('experiments', 'tests')
                 for p in (ROOT/folder).glob('*r49.py') if p.is_file())
REQUIRED_SCRIPTS = {
    'experiments/'+name for name in (
        'cxr_online_primitives_r49.py', 'online_memory_r49.py', 'prepare_feedback_r49.py',
        'run_online_skill_r49.py', 'skill_services_r49.py', 'skill_prompts_r49.py',
        'skill_lifecycle_r49.py', 'skill_evolve_r49.py', 'score_online_skill_r49.py',
        'export_online_skill_r49.py', 'verify_public_online_skill_r49.py')
} | {'tests/'+name for name in (
        'test_execution_r49.py', 'test_online_r49.py', 'test_skill_lifecycle_r49.py',
        'test_score_online_skill_r49.py', 'test_publication_r49.py', 'test_adoption_recovery_r49.py')}

INDEXES = ['README.md', 'findings.md', 'MANIFEST.md',
           'reports/cxr_author_alignment_20261108/TABLES.md']
REFINE_LOGS = [
    'refine-logs/EXPERIMENT_PLAN_R49_20261108_223523.md',
    'refine-logs/EXPERIMENT_TRACKER_R49_20261108_223523.md',
]
ORIGINAL_ROOTS = ('data/chexbench/images/', 'data/slake_cxr/images/', 'data/vqarad_cxr/images/')
TEXT_SUFFIXES = {'.json', '.jsonl', '.md', '.txt', '.py', '.log', '.exitcode', '.sh', '.ps1'}
IMAGE_SUFFIXES = {'.png', '.jpg', '.jpeg', '.webp'}
FORBIDDEN_SUFFIXES = {'.pt', '.pth', '.safetensors', '.zip', '.npy', '.npz', '.pkl', '.pickle'}
SECRET = re.compile(r'\b(?:sk-[A-Za-z0-9_-]{20,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|AKIA[A-Z0-9]{16})\b|\bBearer\s+[A-Za-z0-9._~+/=-]{12,}|-----BEGIN (?:[A-Z ]+ )?PRIVATE KEY-----')


def command(args, data=None):
    result = subprocess.run(args, cwd=ROOT, input=data, capture_output=True)
    if result.returncode:
        raise RuntimeError('command_failed: '+repr(args)+'\n'+result.stderr.decode('utf-8', errors='replace'))
    return result.stdout


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def json_rows(path):
    return [json.loads(line) for line in path.read_text(encoding='utf-8-sig').splitlines() if line.strip()]


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')


def names(data):
    return {value.decode('utf-8') for value in data.split(b'\0') if value}


def staged_paths():
    return names(command(['git', 'diff', '--cached', '--name-only', '-z']))


def tracked_paths():
    return names(command(['git', 'ls-tree', '-r', '--name-only', '-z', 'HEAD']))


def head():
    return command(['git', 'rev-parse', 'HEAD']).decode().strip()


def remote_main():
    lines = command(['git', 'ls-remote', 'origin', 'refs/heads/main']).decode().splitlines()
    if len(lines) != 1 or len(lines[0].split()) != 2:
        raise ValueError('remote_main_not_uniquely_resolved')
    return lines[0].split()[0]


def require_base(expected):
    local, remote = head(), remote_main()
    if local != expected or remote != expected:
        raise ValueError(f'base_changed: expected={expected} local={local} remote_main={remote}; inspect before proceeding')


def original_image(relative):
    return relative.startswith(ORIGINAL_ROOTS) and Path(relative).suffix.lower() in IMAGE_SUFFIXES


def validate_relative(relative, originals=()):
    path = Path(relative)
    if path.is_absolute() or '..' in path.parts or '\\' in relative or ':' in relative:
        raise ValueError('unsafe_allowlist_path:'+relative)
    target = (ROOT/path).resolve()
    if not target.is_relative_to(ROOT.resolve()):
        raise ValueError('allowlist_path_outside_repository:'+relative)
    allowed = relative in SCRIPTS+INDEXES+REFINE_LOGS or relative.startswith(REPORT_REL+'/')
    allowed = allowed or (relative in originals and original_image(relative))
    low = relative.lower()
    if (not allowed or any(part in low for part in (
            'local_assets/', '.aris/', '.secrets/', 'review-stage/', 'review_stage/',
            'prototype', 'request_image_base64/', 'hf_modules/', '__pycache__/', '.git/'))
            or target.suffix.lower() in FORBIDDEN_SUFFIXES
            or (target.suffix.lower() == '.bin' and not relative.startswith(REPORT_REL+'/evidence/'))):
        raise ValueError('excluded_publication_path:'+relative)
    return target


def paths():
    values = read(RECEIPTS/'allowlist.json')
    prepared = read(RECEIPTS/'prepared.json'); originals = set(prepared['new_original_images'])
    if len(values) != len(set(values)) or not originals <= set(values):
        raise ValueError('duplicate_or_changed_original_allowlist')
    for value in values:
        validate_relative(value, originals)
    return values


_PUBLIC_MAPPINGS = {}


def public_asset_semantics(value, document):
    """Apply the same ordered substitutions, caching by evidence/document parent."""
    import os
    evidence = REPORT/'evidence/chexbench'
    for dataset in DATASETS:
        candidate = REPORT/'evidence'/dataset
        if document.resolve().is_relative_to(candidate.resolve()):
            evidence = candidate
            break
    cache_key = (evidence, document.parent)
    if cache_key not in _PUBLIC_MAPPINGS:
        assets = read(evidence/'image_assets.json')
        mappings = sorted([(os.path.relpath((evidence/item['path']).resolve(), document.parent).replace('\\', '/'),
                            'PUBLIC_ASSET:'+str(index)) for index, item in enumerate(assets)],
                          key=lambda pair: -len(pair[0]))
        # A substitution cannot occur if every old path requires this absent
        # literal substring. This avoids scanning inline base64 once per asset.
        anchor = '/assets/' if mappings and all('/assets/' in old for old, _ in mappings) else None
        _PUBLIC_MAPPINGS[cache_key] = mappings, anchor
    mappings, anchor = _PUBLIC_MAPPINGS[cache_key]
    def normalize(item):
        if isinstance(item, dict):
            return {key: normalize(child) for key, child in item.items()}
        if isinstance(item, list):
            return [normalize(child) for child in item]
        if isinstance(item, str):
            if anchor and anchor not in item:
                return item
            for old, new in mappings:
                item = item.replace(old, new)
        return item
    return normalize(value)


def embedding_http_recovery(continued_by_phrase=False):
    """Require the one actually funded retry, preserving the missing old body."""
    recovery = REPORT/'evidence/recovery/embedding_arrearage_1'
    if not recovery.exists():
        return False
    import sys
    source = str(ROOT/'experiments')
    if source not in sys.path:
        sys.path.insert(0, source)
    import score_online_skill_r49 as scoring
    from unittest.mock import patch
    def portable(path):
        return public_asset_semantics(read(path), path)
    raw_read = scoring.read
    with patch.object(scoring, 'read', side_effect=lambda path: public_asset_semantics(raw_read(path), path)):
        proof = scoring.registered_embedding_http_failure(REPORT/'evidence/chexbench')
    if proof is None:
        raise ValueError('actual_registered_embedding_HTTP_recovery_required')
    registration = proof['registration']
    for name in (('controller', 'chexbench') if continued_by_phrase else ('controller', *DATASETS)):
        if (recovery/(name+'.exitcode')).read_text(encoding='utf-8-sig').strip() != ('1' if continued_by_phrase else '0'):
            raise ValueError('actual_final_embedding_continuation_exit_zero_required:'+name)
    for path in (recovery/'prior_generation.exitcode', recovery/'prior_jobs/controller.exitcode',
                 recovery/'prior_jobs/chexbench.exitcode'):
        if path.read_text(encoding='utf-8-sig').strip() != '1':
            raise ValueError('prior_fields2_embedding_HTTP_failure_raw1_must_remain_preserved')
    tail = (recovery/'prior_jobs/chexbench.mutation_fields_2.log').read_text(encoding='utf-8-sig').rstrip().splitlines()
    if not tail or tail[-1] != 'RuntimeError: embedding_api_failure_no_automatic_retry:BadRequestError':
        raise ValueError('preserved_latest_failure_is_not_the_known_embedding_SDK_HTTP_failure')
    for path in (recovery/'controller.py', recovery/'resume_runner.py',
                 REPORT/'deployment_source/recover_cxr_online_skill_r49_embedding_arrearage.py',
                 REPORT/'EMBEDDING_ARREARAGE_RECOVERY_PLAN.md', REPORT/'EMBEDDING_ARREARAGE_RECOVERY_REVIEW.md',
                 REPORT/'EMBEDDING_ARREARAGE_RECOVERY_METADATA.json'):
        if not path.is_file() or not path.stat().st_size:
            raise ValueError('actual_embedding_source_or_operational_review_required:'+str(path))
    scope, review, funding, plan = (portable(recovery/name) for name in ('SCOPE.json', 'REVIEW_READY.json', 'FUNDING_CONFIRMED.json', 'plan.json'))
    expected = {'recovery_id': 'embedding_arrearage_1', 'uses_existing_r49_authorization': True,
                'new_user_approval_claimed': False, 'fresh_production_embedding_limit': 1,
                'same_original_embedding_input': True, 'sdk_defaults_unchanged': True,
                'extra_agent_calls_for_repair': 0, 'extra_meta_calls_for_repair': 0, 'extra_tool_retries': 0,
                'modify_completed_records': False, 'automatic_future_embedding_retry': False,
                'retain_all_prior_overlays': True}
    if (any(scope.get(key) != value for key, value in expected.items()) or not scope.get('authorization_basis')
            or review.get('recovery_id') != 'embedding_arrearage_1' or review.get('verdict') != 'ready'
            or review.get('scope_complete') is not True or not review.get('trace')
            or funding.get('recovery_id') != 'embedding_arrearage_1' or funding.get('provider') != 'aliyun_dashscope'
            or funding.get('funding_confirmed') is not True or funding.get('confirmation_source') != 'explicit_user_reply'
            or not funding.get('confirmation_reply') or not funding.get('confirmed_at')):
        raise ValueError('actual_new_review_existing_scope_and_explicit_DashScope_funding_required')
    if (plan.get('committed_questions_before') != 150 or plan.get('committed_windows_before') != 4
            or plan.get('fresh_production_embedding_limit') != 1
            or plan.get('previous_wrapper') != 'recovery/mutation_fields_2/resume_runner.py'
            or plan.get('sdk_evidence') != {'sdk_version': '1.109.1', 'BadRequestError_status_code': 400}
            or plan.get('original_failure_bundle') != proof['original_failure']
            or portable(recovery/'registration.json') != registration):
        raise ValueError('actual_embedding_boundary_SDK_attestation_and_registration_chain_required')
    old = {name: portable(recovery/'original_failure'/(name+'.json')) for name in ('request', 'started', 'result')}
    if old != proof['original_failure'] or (recovery/'original_failure/response.json').exists():
        raise ValueError('old_embedding_failure_must_remain_unchanged_without_fake_response')
    for name in ('wire_request.json', 'http_response.json'):
        if not (proof['retry_call']['path']/name).is_file():
            raise ValueError('actual_new_embedding_wire_and_HTTP_evidence_required')
    diagnostic = recovery/'diagnostic_evidence'
    for name in ('scope.json', 'review_ready.json', 'request.json', 'started.json', 'packages.json',
                 'wire_request.json', 'http_response.json', 'error.json', 'status.json', 'exitcode'):
        if not (diagnostic/name).is_file():
            raise ValueError('complete_independent_embedding_diagnostic_required:'+name)
    status, error = read(diagnostic/'status.json'), read(diagnostic/'error.json')
    if ((diagnostic/'exitcode').read_text().strip() != '1' or status.get('status') != 'known_http_error'
            or status.get('http_status') != 400 or status.get('embedding_requests') != 1
            or status.get('usable_diagnostic_vector') is not False or status.get('usage') is not None
            or any(status.get(key) != 0 for key in ('agent_calls', 'meta_calls', 'cxr_tool_calls', 'gpu_calls'))
            or error.get('http_status') != 400 or error.get('body', {}).get('code') != 'Arrearage'
            or status.get('elapsed_s') != registration['diagnostic']['elapsed_s']):
        raise ValueError('independent_Arrearage_HTTP400_is_failed_separate_and_not_original_body')
    metadata = read(REPORT/'EMBEDDING_ARREARAGE_RECOVERY_METADATA.json')
    if (metadata.get('status') != 'completed' or metadata.get('is_error') or not metadata.get('session_id')
            or not metadata.get('modelUsage') or not any('deepseek' in name.lower() for name in metadata['modelUsage'])
            or (metadata.get('duration_ms') or 0) <= 0 or (metadata.get('turns') or 0) <= 0):
        raise ValueError('actual_completed_DeepSeek_embedding_operational_review_required')
    return True


def phrase_guard_recovery(continued_by_adoption=False):
    """Require actual guarded inference and honest policy/failure disclosure."""
    recovery = REPORT/'evidence/recovery/phrase_guard_1'
    if not recovery.exists():
        return False
    import sys
    from unittest.mock import patch
    source = str(ROOT/'experiments')
    if source not in sys.path:
        sys.path.insert(0, source)
    import score_online_skill_r49 as scoring
    def portable(path):
        return public_asset_semantics(read(path), path)
    raw_read = scoring.read
    with patch.object(scoring, 'read', side_effect=lambda path: public_asset_semantics(raw_read(path), path)):
        proof = scoring.registered_phrase_guard_retry(REPORT/'evidence/chexbench')
        amendments = {ds: scoring.validate_phrase_guard_amendment(REPORT/'evidence'/ds) for ds in DATASETS}
    if proof is None or any(value.get('active') is not True for value in amendments.values()):
        raise ValueError('actual_phrase_retry_and_all_three_policy_amendments_required')
    for name in (('controller', 'chexbench') if continued_by_adoption else ('controller', *DATASETS)):
        if (recovery/(name+'.exitcode')).read_text(encoding='utf-8-sig').strip() != ('1' if continued_by_adoption else '0'):
            raise ValueError('actual_final_phrase_guard_exit_zero_required:'+name)
    for path in (recovery/'prior_generation.exitcode', recovery/'prior_jobs/controller.exitcode',
                 recovery/'prior_jobs/chexbench.exitcode'):
        if path.read_text(encoding='utf-8-sig').strip() != '1':
            raise ValueError('prior_embedding_continuation_tool_failure_raw1_must_remain')
    tail = (recovery/'prior_jobs/chexbench.embedding_arrearage_1.log').read_text(encoding='utf-8-sig').rstrip().splitlines()
    if not tail or tail[-1] != 'RuntimeError: tool_failure_stop_no_automatic_retry:nested_backend_error':
        raise ValueError('preserved_phrase_tool_failure_tail_required')
    for path in (recovery/'controller.py', recovery/'resume_runner.py', recovery/'maira_guard_worker.py',
                 recovery/'eos_guard_policy.py', REPORT/'deployment_source/recover_cxr_online_skill_r49_phrase_guard.py',
                 REPORT/'deployment_source/r49_phrase_grounding_eos_guard_candidate.py',
                 REPORT/'PHRASE_GROUNDING_EOS_GUARD_RECOVERY_PLAN.md', REPORT/'PHRASE_GUARD_RECOVERY_REVIEW.md',
                 REPORT/'PHRASE_GUARD_RECOVERY_METADATA.json', REPORT/'PHRASE_GROUNDING_DIAGNOSTIC_RESULT.md'):
        if not path.is_file() or not path.stat().st_size:
            raise ValueError('actual_phrase_source_plan_review_required:'+str(path))
    scope, review, plan, global_registration = (portable(recovery/name) for name in
        ('SCOPE.json', 'REVIEW_READY.json', 'plan.json', 'registration.json'))
    expected = {'recovery_id': 'phrase_guard_1', 'uses_existing_r49_authorization': True,
                'new_user_approval_claimed': False, 'activation_boundary_chexbench': 168,
                'known_failed_guarded_retry_limit': 1, 'all_new_physical_maira_calls': True,
                'generation_policy_changed': True, 'same_generation_settings': False,
                'clinical_prompt_changed': False, 'parser_changed': False, 'max_new_tokens': 300,
                'extra_agent_calls_for_repair': 0, 'extra_meta_calls_for_repair': 0,
                'extra_embedding_calls_for_repair': 0, 'automatic_tool_retry': False,
                'modify_completed_records': False, 'retain_all_prior_overlays': True,
                'diagnostic_result_reused': False}
    registration = proof['registration']
    if (any(scope.get(key) != value for key, value in expected.items()) or not scope.get('authorization_basis')
            or review.get('recovery_id') != 'phrase_guard_1' or review.get('verdict') != 'ready'
            or review.get('scope_complete') is not True or not review.get('trace')
            or plan.get('activation_boundary_chexbench') != 168 or plan.get('committed_windows_before') != 5
            or plan.get('previous_wrapper') != 'recovery/embedding_arrearage_1/resume_runner.py'
            or plan.get('generation_policy_changed') is not True or plan.get('same_generation_settings') is not False
            or plan.get('original_selection') != registration.get('original_selection')
            or global_registration != registration
            or portable(recovery/'original_selection.json') != registration.get('original_selection')):
        raise ValueError('actual_phrase_scope_policy_boundary_registration_chain_required')
    for ds, value in amendments.items():
        amendment = value['amendment']
        if (portable(recovery/'amendments'/(ds+'.json')) != amendment
                or amendment.get('activation_committed_questions') != (168 if ds == 'chexbench' else 0)
                or amendment.get('generation_policy_changed') is not True
                or amendment.get('same_generation_settings') is not False):
            raise ValueError('all_new_MAIRA_policy_and_legacy_cache_amendments_required:'+ds)
    diagnostic = recovery/'diagnostic_evidence'
    for name in ('EXECUTION_SCOPE.json', 'REVIEW_READY.json', 'request.json', 'plan.json', 'started.json',
                 'worker_started.json', 'generation_tokens.json', 'decode.json', 'conversion_inputs.json',
                 'swallowed_exceptions.json', 'observability_errors.json', 'factory.json', 'result.json',
                 'status.json', 'stdout.log', 'stderr.log', 'exitcode', 'artifacts/raw.json',
                 'artifacts/backend_events.json', 'artifacts/provenance.json'):
        if not (diagnostic/name).is_file():
            raise ValueError('complete_independent_phrase_diagnostic_required:'+name)
    status = read(diagnostic/'status.json')
    if ((diagnostic/'exitcode').read_text().strip() != '1' or status.get('status') != 'failed'
            or status.get('capture_complete') is not True or status.get('tool_invocations') != 1
            or any(status.get(key) != 0 for key in ('main_api_calls', 'meta_api_calls', 'embedding_api_calls'))
            or status.get('result_reused_in_R49') is not False or status.get('original_run_modified') is not False
            or status.get('elapsed_s') != registration['diagnostic']['elapsed_s']
            or plan.get('diagnostic') != registration['diagnostic']):
        raise ValueError('failed_phrase_diagnostic_is_separate_complete_not_production_reuse')
    metadata = read(REPORT/'PHRASE_GUARD_RECOVERY_METADATA.json')
    if (metadata.get('status') != 'completed' or metadata.get('is_error') or not metadata.get('session_id')
            or not metadata.get('modelUsage') or not any('deepseek' in name.lower() for name in metadata['modelUsage'])
            or (metadata.get('duration_ms') or 0) <= 0 or (metadata.get('turns') or 0) <= 0):
        raise ValueError('actual_completed_DeepSeek_phrase_operational_review_required')
    return True


def adoption_recovery():
    """Gate final publication on two actual choices and the deferred actual full audit."""
    recovery = REPORT/'evidence/recovery/adoption_1'
    if not recovery.exists():
        return False
    # Check the latest attempt before opening any result or attribution proof.
    for name in ('controller', *DATASETS):
        if (recovery/(name+'.exitcode')).read_text(encoding='utf-8-sig').strip() != '0':
            raise ValueError('actual_final_adoption_exit_zero_required:'+name)
    for ds in DATASETS:
        evidence = REPORT/'evidence'/ds
        for path in (evidence/'generation.exitcode', evidence/'job_records/controller.exitcode', evidence/'job_records'/(ds+'.exitcode')):
            if path.read_text(encoding='utf-8-sig').strip() != '0':
                raise ValueError('actual_final_adoption_dataset_exit_zero_required:'+ds)
        queue = read(evidence/'job_records/queue_status.json')
        if (queue.get('state') != 'all_three_datasets_exited_zero_after_adoption_recovery'
                or queue.get('recovery') != 'adoption_1' or queue.get('prior_production_attempts_include_exit1') is not True
                or list(queue.get('datasets', [])) != list(DATASETS)):
            raise ValueError('actual_serial_adoption_controller_completion_required:'+ds)
    for path in (recovery/'prior_generation.exitcode', recovery/'prior_jobs/controller.exitcode',
                 recovery/'prior_jobs/chexbench.exitcode'):
        if path.read_text(encoding='utf-8-sig').strip() != '1':
            raise ValueError('prior_phrase_guard_adoption_failure_raw1_must_remain')
    if ((recovery/'prior_jobs/controller.pid').read_text(encoding='utf-8-sig').strip() != '2722301'
            or (recovery/'prior_jobs/chexbench.pid').read_text(encoding='utf-8-sig').strip() != '2722307'):
        raise ValueError('actual_prior_phrase_guard_attempt_identity_required')
    tail = (recovery/'prior_jobs/chexbench.phrase_guard_1.log').read_text(encoding='utf-8-sig').rstrip().splitlines()
    if not tail or tail[-1] != 'ValueError: duplicate_skill_adoption':
        raise ValueError('preserved_duplicate_adoption_failure_tail_required')
    for path in (recovery/'controller.py', recovery/'resume_runner.py',
                 REPORT/'deployment_source/recover_cxr_online_skill_r49_adoption.py', REPORT/'ADOPTION_RECOVERY_PLAN.md',
                 REPORT/'RESULT_CLAIM_REVIEW.md', REPORT/'RESULT_CLAIM_METADATA.json', REPORT/'CLAIMS_FROM_RESULTS.md'):
        if not path.is_file() or not path.stat().st_size:
            raise ValueError('actual_adoption_source_plan_final_audit_required:'+str(path))
    metadata = read(REPORT/'RESULT_CLAIM_METADATA.json')
    audit_scope = {'adoption_protocol', 'request_resource_accounting', 'complete_results_and_claims'}
    if (metadata.get('status') != 'completed' or metadata.get('is_error') or not metadata.get('session_id')
            or not metadata.get('modelUsage') or not any('deepseek' in name.lower() for name in metadata['modelUsage'])
            or (metadata.get('duration_ms') or 0) <= 0 or (metadata.get('turns') or 0) <= 0
            or metadata.get('scope_complete') is not True or not isinstance(metadata.get('audit_scope'), list)
            or not audit_scope <= set(metadata['audit_scope'])
            or len((REPORT/'RESULT_CLAIM_REVIEW.md').read_text(encoding='utf-8-sig').strip()) < 20
            or len((REPORT/'CLAIMS_FROM_RESULTS.md').read_text(encoding='utf-8-sig').strip()) < 20):
        raise ValueError('actual_single_final_DeepSeek_audit_of_protocol_resources_and_results_required')
    import sys
    from unittest.mock import patch
    source = str(ROOT/'experiments')
    if source not in sys.path:
        sys.path.insert(0, source)
    import score_online_skill_r49 as scoring
    def portable(path):
        return public_asset_semantics(read(path), path)
    raw_read = scoring.read
    with patch.object(scoring, 'read', side_effect=lambda path: public_asset_semantics(raw_read(path), path)):
        proof = scoring.registered_adoption_repair(REPORT/'evidence/chexbench')
        amendments = {ds: scoring.validate_analysis_unique_amendment(REPORT/'evidence'/ds) for ds in DATASETS}
    if proof is None or any(value.get('active') is not True or value.get('extra_ordinary_meta_calls') != 0 for value in amendments.values()):
        raise ValueError('two_actual_adoption_choices_and_all_three_analysis_amendments_required')
    registration = proof['registration']
    expected_registration = {'schema': 'r49_registered_assessment_adoption_repair_v1', 'recovery_id': 'adoption_1',
        'dataset': 'chexbench', 'arm': ARM, 'window_index': 6, 'activation_committed_questions': 210,
        'new_meta_requests': 2, 'assess_only': True, 'write_phase_analysis_unchanged': True,
        'other_analysis_fields_unchanged': True, 'automatic_retry': False, 'status': 'two_assess_only_adoption_repairs_registered'}
    if any(registration.get(key) != value for key, value in expected_registration.items()):
        raise ValueError('only_exact_two_assessment_representative_choices_supported')
    cases = registration.get('repairs', [])
    expected_events = {'analysis_chexbench_slake_0081', 'analysis_chexbench_slake_0082'}
    if (len(cases) != 2 or {case.get('source_event') for case in cases} != expected_events
            or any(case.get('repair_event') != case['source_event']+'_adoption_1' for case in cases)
            or any(type(case.get('selected_duplicate_index')) is not int or case['selected_duplicate_index'] not in (0, 1) for case in cases)):
        raise ValueError('two_known_model_selected_original_representatives_required')
    scope, authorization, plan = (portable(recovery/name) for name in ('SCOPE.json', 'EXECUTION_AUTHORIZATION.json', 'plan.json'))
    expected_scope = {'recovery_id': 'adoption_1', 'uses_existing_r49_authorization': True, 'new_user_approval_claimed': False,
        'fresh_meta_repair_limit': 2, 'assess_only': True, 'write_phase_analysis_unchanged': True, 'representative_index_only': True,
        'extra_agent_calls_for_repair': 0, 'extra_embedding_calls_for_repair': 0, 'extra_tool_retries': 0,
        'analysis_clarification_all_datasets': True, 'extra_meta_calls_per_ordinary_analysis': 0, 'automatic_future_repair': False,
        'modify_completed_records': False, 'retain_all_prior_overlays': True}
    expected_authorization = {'recovery_id': 'adoption_1', 'verdict': 'audit_deferred_until_full_generation',
        'review_completed': False, 'scope_complete': False, 'exact_user_reply': '这个可以跑完再审计？',
        'confirmation_source': 'explicit_user_reply', 'audit_before_publication': True, 'implementation_checks_passed': True}
    if (any(scope.get(key) != value for key, value in expected_scope.items()) or not scope.get('authorization_basis')
            or any(authorization.get(key) != value for key, value in expected_authorization.items())
            or plan.get('window_index') != 6 or plan.get('activation_committed_questions') != 210
            or plan.get('committed_windows_before') != 6 or plan.get('new_meta_request_limit') != 2
            or plan.get('representative_index_only') is not True
            or plan.get('previous_wrapper') != 'recovery/phrase_guard_1/resume_runner.py'
            or plan.get('audit_timing') != 'after_full_generation_before_publication'
            or portable(recovery/'registration.json') != registration):
        raise ValueError('truthful_adoption_deferral_scope_boundary_and_registration_required')
    for ds, value in amendments.items():
        amendment = value['amendment']
        if (portable(recovery/'amendments'/(ds+'.json')) != amendment
                or amendment.get('schema') != 'r49_analysis_unique_adoption_amendment_v1'
                or amendment.get('recovery_id') != 'adoption_1' or amendment.get('dataset') != ds
                or amendment.get('arm') != ARM or amendment.get('activation_committed_questions') != (210 if ds == 'chexbench' else 0)
                or amendment.get('automatic_future_repair') is not False or amendment.get('new_clinical_information') is not False):
            raise ValueError('actual_all_three_analysis_prompt_boundary_proof_required:'+ds)
        resources = read(REPORT/'results'/ds/'summary.json')['resources']
        account = resources['adoption_repair']; registered = ds == 'chexbench'
        expected_subset = scoring.receipt_resources([item['repair_call'] for item in proof['repairs']] if registered else [])
        if (account.get('registered') is not registered or account.get('added_meta_requests') != (2 if registered else 0)
                or account.get('included_in_R49_META_totals') is not True
                or account.get('original_analysis_retained_for_mutation') is not True or account.get('assess_only_overlay') is not True
                or account.get('model_selected_existing_entry_only') is not registered
                or account.get('manual_selection') is not False or account.get('new_evidence_written') is not False
                or any(account.get(key) != 0 for key in ('extra_agent_calls', 'extra_embedding_calls', 'extra_tool_calls'))
                or account.get('repair_request_resources') != expected_subset
                or resources.get('analysis_unique_amendment') != value):
            raise ValueError('actual_adoption_choice_subset_and_analysis_prompt_resources_required:'+ds)
    return True


def mutation_fields_recovery(continued_by_embedding=False):
    recovery = REPORT/'evidence/recovery/mutation_fields_2'
    if not recovery.exists():
        return False
    for name in (('controller', 'chexbench') if continued_by_embedding else ('controller', *DATASETS)):
        if (recovery/(name+'.exitcode')).read_text(encoding='utf-8-sig').strip() != ('1' if continued_by_embedding else '0'):
            raise ValueError('actual_final_mutation_fields_continuation_exit_zero_required:'+name)
    for path in (recovery/'prior_generation.exitcode', recovery/'prior_jobs/controller.exitcode',
                 recovery/'prior_jobs/chexbench.exitcode'):
        if path.read_text(encoding='utf-8-sig').strip() != '1':
            raise ValueError('prior_150_question_content_field_failure_must_remain_preserved')
    tail = (recovery/'prior_jobs/chexbench.meta_schema_1.log').read_text(encoding='utf-8-sig').rstrip().splitlines()
    if not tail or tail[-1] != 'ValueError: invalid_patch_section':
        raise ValueError('preserved_latest_failure_is_not_the_known_content_field_error')
    for path in (recovery/'controller.py', recovery/'resume_runner.py',
                 REPORT/'deployment_source/recover_cxr_online_skill_r49_mutation_fields.py',
                 REPORT/'MUTATION_FIELDS_RECOVERY_PLAN.md', REPORT/'MUTATION_FIELDS_RECOVERY_REVIEW.md',
                 REPORT/'MUTATION_FIELDS_RECOVERY_METADATA.json'):
        if not path.is_file() or not path.stat().st_size:
            raise ValueError('actual_mutation_fields_source_or_review_required:'+str(path))
    ready, scope, plan = read(recovery/'REVIEW_READY.json'), read(recovery/'SCOPE.json'), read(recovery/'plan.json')
    if (ready.get('verdict') != 'ready' or ready.get('scope_complete') is not True
            or scope.get('fresh_meta_repair_limit') != 1 or scope.get('automatic_future_repair') is not False
            or scope.get('extra_meta_calls_per_ordinary_event') != 0
            or scope.get('ordinary_field_clarification_all_datasets') is not True
            or scope.get('automatic_invalid_to_none') is not False
            or plan.get('committed_questions_before') != 150 or plan.get('committed_windows_before') != 4):
        raise ValueError('exact_two_case_scope_and_150_commit_boundary_required')
    gen_path = REPORT/'evidence/chexbench/failure_events/meta_schema_2_registration.json'
    shared_path = recovery/'registration.json'
    gen, shared = public_asset_semantics(read(gen_path), gen_path), public_asset_semantics(read(shared_path), shared_path)
    if (gen != shared or gen.get('schema') != 'r49_registered_meta_schema_repair_v2'
            or gen.get('recovery_id') != 'mutation_fields_2' or gen.get('new_meta_calls') != 1):
        raise ValueError('shared_and_GEN_second_META_registration_must_match')
    for dataset in DATASETS:
        gen_amendment = read(REPORT/'evidence'/dataset/'failure_events/mutation_fields_2_amendment.json')
        if gen_amendment != read(recovery/'amendments'/(dataset+'.json')):
            raise ValueError('shared_and_GEN_prompt_amendment_boundary_changed:'+dataset)
    metadata = read(REPORT/'MUTATION_FIELDS_RECOVERY_METADATA.json')
    if (metadata.get('status') != 'completed' or metadata.get('is_error') or not metadata.get('session_id')
            or not metadata.get('modelUsage') or not any('deepseek' in name.lower() for name in metadata['modelUsage'])
            or (metadata.get('duration_ms') or 0) <= 0 or (metadata.get('turns') or 0) <= 0):
        raise ValueError('actual_completed_DeepSeek_mutation_fields_review_required')
    return True


def meta_schema_recovery(continued_by_fields=False):
    recovery = REPORT/'evidence/recovery/meta_schema_1'
    if not recovery.exists():
        return False
    for name in (('controller', 'chexbench') if continued_by_fields else ('controller', *DATASETS)):
        if (recovery/(name+'.exitcode')).read_text(encoding='utf-8-sig').strip() != ('1' if continued_by_fields else '0'):
            raise ValueError('actual_final_META_schema_continuation_exit_zero_required:'+name)
    for path in (recovery/'prior_generation.exitcode', recovery/'prior_jobs/controller.exitcode',
                 recovery/'prior_jobs/chexbench.exitcode'):
        if path.read_text(encoding='utf-8-sig').strip() != '1':
            raise ValueError('prior_META_schema_failure_exit_one_must_remain_preserved')
    tail = (recovery/'prior_jobs/chexbench.cuda_1.log').read_text(encoding='utf-8-sig').rstrip().splitlines()
    if not tail or tail[-1] != 'ValueError: invalid_patch_section':
        raise ValueError('preserved_latest_failure_is_not_the_known_META_patch_schema_error')
    for path in (recovery/'controller.py', recovery/'resume_runner.py',
                 REPORT/'deployment_source/recover_cxr_online_skill_r49_meta_schema.py',
                 REPORT/'META_SCHEMA_RECOVERY_PLAN.md', REPORT/'META_SCHEMA_RECOVERY_REVIEW.md',
                 REPORT/'META_SCHEMA_RECOVERY_METADATA.json'):
        if not path.is_file() or not path.stat().st_size:
            raise ValueError('actual_META_schema_source_or_review_required:'+str(path))
    ready, scope, plan = read(recovery/'REVIEW_READY.json'), read(recovery/'SCOPE.json'), read(recovery/'plan.json')
    if (ready.get('verdict') != 'ready' or ready.get('scope_complete') is not True
            or scope.get('fresh_meta_repair_limit') != 1
            or any(scope.get(k) != 0 for k in ('extra_agent_calls', 'extra_embedding_calls', 'extra_tool_retries'))
            or scope.get('automatic_invalid_to_none') is not False or scope.get('keep_cuda_cache_overlay') is not True
            or plan.get('committed_questions_before') != 120 or plan.get('committed_windows_before') != 3):
        raise ValueError('actual_exact_META_schema_scope_and_120_commit_boundary_required')
    gen_path = REPORT/'evidence/chexbench/failure_events/meta_schema_1_registration.json'
    shared_path = recovery/'registration.json'
    gen, shared = public_asset_semantics(read(gen_path), gen_path), public_asset_semantics(read(shared_path), shared_path)
    if (gen != shared or gen.get('schema') != 'r49_registered_meta_schema_repair_v1'
            or gen.get('status') != 'valid_meta_schema_repair_registered'
            or gen.get('new_meta_calls') != 1 or gen.get('automatic_invalid_to_none') is not False):
        raise ValueError('shared_and_GEN_META_schema_registration_must_match')
    metadata = read(REPORT/'META_SCHEMA_RECOVERY_METADATA.json')
    if (metadata.get('status') != 'completed' or metadata.get('is_error') or not metadata.get('session_id')
            or not metadata.get('modelUsage') or not any('deepseek' in name.lower() for name in metadata['modelUsage'])
            or (metadata.get('duration_ms') or 0) <= 0 or (metadata.get('turns') or 0) <= 0):
        raise ValueError('actual_completed_DeepSeek_META_schema_operational_review_required')
    return True


def cuda_recovery(continued_by_meta=False):
    recovery = REPORT/'evidence/recovery/cuda_1'
    if not recovery.exists():
        return False
    for name in (('controller', 'chexbench') if continued_by_meta else ('controller', *DATASETS)):
        if (recovery/(name+'.exitcode')).read_text(encoding='utf-8-sig').strip() != ('1' if continued_by_meta else '0'):
            raise ValueError('actual_CUDA_attempt_exit_history_required:'+name)
    for path in (recovery/'prior_generation.exitcode', recovery/'prior_jobs/controller.exitcode',
                 recovery/'prior_jobs/chexbench.exitcode'):
        if path.read_text(encoding='utf-8-sig').strip() != '1':
            raise ValueError('prior_cuda_failure_exit_one_must_remain_preserved')
    for path in (recovery/'controller.py', recovery/'resume_runner.py', recovery/'original_selection.json',
                 REPORT/'deployment_source/recover_cxr_online_skill_r49_cuda.py',
                 REPORT/'CUDA_PRODUCTION_RECOVERY.md', REPORT/'CUDA_PRODUCTION_RECOVERY_REVIEW.md',
                 REPORT/'CUDA_PRODUCTION_RECOVERY_METADATA.json'):
        if not path.is_file() or not path.stat().st_size:
            raise ValueError('actual_cuda_operational_evidence_required:'+str(path))
    ready = read(recovery/'REVIEW_READY.json'); scope = read(recovery/'SCOPE.json')
    if (ready.get('verdict') != 'ready' or ready.get('scope_complete') is not True
            or scope.get('production_tool_retry_limit') != 1 or scope.get('new_diagnostic_invocations') != 0
            or scope.get('retry_current_question_main_plan') is not False
            or scope.get('technical_null_fill') is not False or scope.get('modify_completed_predictions') is not False
            or scope.get('diagnostic_result_reused') is not False):
        raise ValueError('actual_narrow_cuda_operational_scope_and_ready_required')
    gen_path = REPORT/'evidence/chexbench/failure_events/cuda_1_registration.json'
    global_path = recovery/'registration.json'; original_path = recovery/'original_selection.json'
    gen = public_asset_semantics(read(gen_path), gen_path)
    shared = public_asset_semantics(read(global_path), global_path)
    original = public_asset_semantics(read(original_path), original_path)
    if gen != shared or gen.get('original_selection') != original:
        raise ValueError('public_cuda_registration_or_original_selection_semantics_changed')
    if (gen.get('schema') != 'r49_registered_cuda_retry_v1'
            or gen.get('status') != 'healthy_production_retry_registered'
            or gen.get('diagnostic_result_reused') is not False or gen.get('new_tool_attempts') != 1):
        raise ValueError('actual_one_healthy_production_retry_registration_required')
    diagnostic = read(recovery/'diagnostic_evidence/status.json')
    if (diagnostic.get('status') != 'completed_healthy' or diagnostic.get('tool_invocations') != 1
            or any(diagnostic.get(k) != 0 for k in ('main_api_calls', 'meta_api_calls', 'embedding_api_calls'))
            or diagnostic.get('elapsed_s') != gen['diagnostic']['elapsed_s']
            or (recovery/'diagnostic_evidence/exitcode').read_text().strip() != '0'):
        raise ValueError('actual_separate_zero_API_diagnostic_evidence_required')
    metadata = read(REPORT/'CUDA_PRODUCTION_RECOVERY_METADATA.json')
    if (metadata.get('status') != 'completed' or metadata.get('is_error')
            or not metadata.get('session_id') or not metadata.get('modelUsage')
            or not any('deepseek' in name.lower() for name in metadata['modelUsage'])
            or (metadata.get('duration_ms') or 0) <= 0 or (metadata.get('turns') or 0) <= 0):
        raise ValueError('actual_completed_DeepSeek_cuda_operational_review_required')
    return True


def dependency_recovery(continued_by_cuda=False):
    """Distinguish the preserved first exit 1 from a healthy final continuation."""
    recovery = REPORT/'evidence/recovery/dependency_1'
    if not recovery.exists():
        return False
    for name in ('controller.exitcode', 'chexbench.exitcode', 'generation.exitcode'):
        if (recovery/'original'/name).read_text(encoding='utf-8-sig').strip() != '1':
            raise ValueError('initial_dependency_failure_exit_one_must_remain_preserved:'+name)
    for name in (('controller', 'chexbench') if continued_by_cuda else ('controller', *DATASETS)):
        expected_exit = '1' if continued_by_cuda else '0'
        if (recovery/(name+'.exitcode')).read_text(encoding='utf-8-sig').strip() != expected_exit:
            raise ValueError('actual_dependency_attempt_exit_history_required:'+name)
    diagnosis, review_ready = read(recovery/'diagnosis.json'), read(recovery/'REVIEW_READY.json')
    expected = {'repair': 'missing_deployed_cxr_author_alignment_only', 'original_controller_exit': 1,
                'original_chexbench_exit': 1, 'committed_predictions': 1, 'closed_main_requests': 3,
                'healthy_tool_selections': 2, 'released_feedback_events': 1, 'prediction_rewrites': 0,
                'new_reference_reads_for_repair': 0, 'runtime_policy_changed': False,
                'unknown_requests_reissued': False, 'automatic_failure_nulls': False}
    if any(diagnosis.get(key) != value for key, value in expected.items()):
        raise ValueError('only_the_documented_postcommit_dependency_repair_is_supported')
    if review_ready.get('verdict') != 'ready' or review_ready.get('scope_complete') is not True:
        raise ValueError('actual_dependency_repair_readiness_required')
    tail = (recovery/'original/chexbench.log').read_text(encoding='utf-8-sig').rstrip().splitlines()
    if not tail or tail[-1] != "ModuleNotFoundError: No module named 'cxr_author_alignment'":
        raise ValueError('preserved_original_failure_is_not_the_documented_dependency')
    for path in (recovery/'controller.py', REPORT/'deployment_source/resume_cxr_online_skill_r49.py',
                 REPORT/'DEPENDENCY_RECOVERY.md', REPORT/'DEPENDENCY_REPAIR_REVIEW.md',
                 REPORT/'DEPENDENCY_REPAIR_METADATA.json'):
        if not path.is_file() or not path.stat().st_size:
            raise ValueError('actual_dependency_repair_source_or_review_required:'+str(path))
    metadata = read(REPORT/'DEPENDENCY_REPAIR_METADATA.json')
    if (metadata.get('status') != 'completed' or metadata.get('is_error')
            or not metadata.get('session_id') or (metadata.get('duration_ms') or 0) <= 0
            or (metadata.get('turns') or 0) <= 0 or not metadata.get('modelUsage')
            or not any('deepseek' in name.lower() for name in metadata['modelUsage'])):
        raise ValueError('actual_completed_DeepSeek_dependency_delta_review_required')
    return True


def ready():
    """Require actual three-stream completion, public reproduction and result review."""
    if not REQUIRED_SCRIPTS <= set(SCRIPTS):
        raise ValueError('required_R49_source_or_test_missing')
    documents = ('README.md', 'PLAN.md', 'PROTOCOL.json', 'TESTS.md', 'REVIEW_STATUS.md',
                 'CODE_SOURCE_REVIEW.md', 'CODE_REVIEW_METADATA.json', 'RESULT_CLAIM_REVIEW.md',
                 'RESULT_CLAIM_METADATA.json', 'CLAIMS_FROM_RESULTS.md', 'RESOURCE_SUMMARY.json',
                 'CASE_INDEX.md', 'REPRODUCTION.md')
    for name in documents:
        if not (REPORT/name).is_file() or not (REPORT/name).stat().st_size:
            raise ValueError('actual_finished_report_required:'+name)
    for name in ('deploy_cxr_online_skill_r49.py', 'queue_controller.py', 'PROTOCOL.executed.json',
                 'EXECUTION_REVIEW_READY.json', 'PROVENANCE.md'):
        path = REPORT/'deployment_source'/name
        if not path.is_file() or not path.stat().st_size:
            raise ValueError('actual_deployment_source_snapshot_required:'+name)
    review = read(REPORT/'RESULT_CLAIM_METADATA.json')
    execution = read(REPORT/'CODE_REVIEW_METADATA.json')
    if (review.get('status') != 'completed' or review.get('is_error')
            or not review.get('session_id') or review.get('session_id') == execution.get('session_id')
            or (review.get('duration_ms') or 0) <= 0 or (review.get('turns') or 0) <= 0
            or not review.get('modelUsage')
            or not any('deepseek' in name.lower() for name in review['modelUsage'])
            or len((REPORT/'RESULT_CLAIM_REVIEW.md').read_text(encoding='utf-8-sig').strip()) < 20
            or len((REPORT/'CLAIMS_FROM_RESULTS.md').read_text(encoding='utf-8-sig').strip()) < 20):
        raise ValueError('fresh_actual_DeepSeek_result_claim_reply_required_not_execution_ready')
    # Any supported/partial/negative result claim is publishable. No favorable
    # review score, clinical verification or independent audit is invented.
    resource = read(REPORT/'RESOURCE_SUMMARY.json')
    if (resource.get('raw_controller_exit') != 0
            or resource.get('raw_dataset_exits') != {name: 0 for name in DATASETS}
            or any(resource.get(name) is not False for name in (
                'clinical_verification_or_integrity_audit_claim', 'official_SOTA_claim',
                'same_budget_causal_Skill_claim', 'pooled_independent_848_case_accuracy_claim'))):
        raise ValueError('actual_controller_exits_and_honest_claim_scope_required')
    adoption_recovered = adoption_recovery()
    if not adoption_recovered:
        raise ValueError('actual_latest_adoption_completion_and_final_audit_required')
    phrase_recovered = phrase_guard_recovery(continued_by_adoption=adoption_recovered)
    if adoption_recovered and not phrase_recovered:
        raise ValueError('prior_phrase_guard_success_and_later_assessment_failure_must_be_preserved')
    embedding_recovered = embedding_http_recovery(continued_by_phrase=phrase_recovered)
    if phrase_recovered and not embedding_recovered:
        raise ValueError('prior_successful_embedding_recovery_and_later_tool_failure_must_be_preserved')
    fields_recovered = mutation_fields_recovery(continued_by_embedding=embedding_recovered)
    if embedding_recovered and not fields_recovered:
        raise ValueError('earlier_fields2_success_and_later_embedding_failure_must_also_be_preserved')
    meta_recovered = meta_schema_recovery(continued_by_fields=fields_recovered)
    if fields_recovered and not meta_recovered:
        raise ValueError('earlier_first_META_repair_history_must_also_be_preserved')
    cuda_recovered = cuda_recovery(continued_by_meta=meta_recovered)
    if meta_recovered and not cuda_recovered:
        raise ValueError('earlier_successful_CUDA_retry_and_later_exit_one_must_also_be_preserved')
    recovered = dependency_recovery(continued_by_cuda=cuda_recovered)
    if cuda_recovered and not recovered:
        raise ValueError('earlier_dependency_failure_history_must_also_be_preserved')
    checked = {}
    fields = ('dataset', 'arm', 'questions', 'all_questions_fresh', 'mode', 'arms', 'comparisons',
              'skill_hit_questions', 'same_image_hit_questions', 'windows', 'resources',
              'references_read_after_all_arms_adapted')
    for dataset, spec in DATASETS.items():
        evidence = REPORT/'evidence'/dataset
        summary = read(REPORT/'results'/dataset/'summary.json')
        public = read(REPORT/'public_reproduction'/dataset/'summary.json')
        exported = read(evidence/'scores/summary.json')
        complete = read(evidence/'complete.json')
        if (summary.get('dataset') != dataset or summary.get('arm') != ARM
                or summary.get('questions') != spec['n'] or summary.get('all_questions_fresh') is not True
                or summary.get('references_read_after_all_arms_adapted') is not True
                or summary['arms'][spec['baseline']]['correct'] != spec['baseline_correct']
                or any(public.get(k) != summary.get(k) or exported.get(k) != summary.get(k) for k in fields)
                or public.get('matches_published_primary_scores_and_extractions') is not True
                or public.get('matches_published_resources') is not True
                or public.get('new_inference_calls') != 0 or public.get('private_run_paths_required') is not False
                or public.get('image_or_file_digests_checked') is not False):
            raise ValueError('complete_scored_and_publicly_reproduced_whole_dataset_required:'+dataset)
        if summary['resources']['tools'].get('registered_failed_historical_attempts', 0) != int(cuda_recovered and dataset == 'chexbench')+int(phrase_recovered and dataset == 'chexbench'):
            raise ValueError('registered_failed_physical_attempt_accounting_changed:'+dataset)
        if phrase_recovered:
            phrase = summary['resources']['phrase_guard_retry']
            amendment = summary['resources']['phrase_guard_amendment']
            diagnostic = summary['resources']['isolated_phrase_diagnostic']
            registered = dataset == 'chexbench'
            if (phrase.get('registered') is not registered or phrase.get('guarded_production_retries') != int(registered)
                    or phrase.get('included_in_tools_totals') is not True
                    or (registered and (phrase.get('generation_policy_changed') is not True
                        or phrase.get('same_generation_settings') is not False or phrase.get('diagnostic_result_reused') is not False))
                    or amendment.get('active') is not True
                    or summary['resources']['tools'].get('registered_cuda_failed_attempts') != int(registered and cuda_recovered)
                    or summary['resources']['tools'].get('registered_phrase_failed_attempts') != int(registered)
                    or diagnostic.get('tool_invocations') != int(registered)
                    or diagnostic.get('included_in_production_attempts') is not False
                    or diagnostic.get('result_reused_in_R49') is not False):
                raise ValueError('separate_phrase_policy_failed_attempt_and_diagnostic_accounting_required:'+dataset)
        meta_account = summary['resources']['meta_schema_repair']
        if (meta_account.get('registered') is not bool(meta_recovered and dataset == 'chexbench')
                or meta_account.get('added_meta_requests') != int(meta_recovered and dataset == 'chexbench')
                or meta_account.get('included_in_R49_META_totals') is not True
                or meta_account.get('automatic_invalid_to_none') is not False):
            raise ValueError('registered_META_repair_must_count_once_inside_META_resources:'+dataset)
        second = summary['resources']['meta_schema_repair_2']
        prompt_mode = summary['resources']['mutation_fields_amendment']
        if (second.get('registered') is not bool(fields_recovered and dataset == 'chexbench')
                or second.get('added_meta_requests') != int(fields_recovered and dataset == 'chexbench')
                or second.get('included_in_R49_META_totals') is not True
                or prompt_mode.get('active') is not fields_recovered
                or prompt_mode.get('extra_ordinary_meta_calls') != 0):
            raise ValueError('second_META_cost_and_declared_prompt_modes_required:'+dataset)
        embedding_account = summary['resources']['embedding_http_recovery']
        diagnostic_account = summary['resources']['isolated_embedding_diagnostic']
        has_embedding_repair = bool(embedding_recovered and dataset == 'chexbench')
        if (embedding_account.get('registered') is not has_embedding_repair
                or embedding_account.get('new_production_embedding_requests') != int(has_embedding_repair)
                or embedding_account.get('included_in_embedding_totals') is not True
                or summary['resources']['embedding'].get('registered_http_failed_attempts') != int(has_embedding_repair)
                or diagnostic_account.get('embedding_requests') != int(has_embedding_repair)
                or diagnostic_account.get('included_in_production_embedding_totals') is not False
                or diagnostic_account.get('original_error_body_reconstructed') is not False):
            raise ValueError('one_registered_embedding_failure_and_separate_diagnostic_accounting_required:'+dataset)
        if has_embedding_repair and (embedding_account.get('original_specific_body_unknown') is not True
                or embedding_account.get('original_usage_unknown') is not True
                or embedding_account.get('original_cost_unknown') is not True
                or diagnostic_account.get('usage_unknown') is not True or diagnostic_account.get('cost_unknown') is not True):
            raise ValueError('unknown_old_embedding_and_diagnostic_usage_are_not_free')
        compared = {spec['baseline'], 'R47_online_GT'} if dataset == 'chexbench' else {spec['baseline']}
        if set(summary['comparisons']) != compared or set(summary['arms']) != compared|{ARM}:
            raise ValueError('fixed_full_historical_compared_arms:'+dataset)
        if dataset == 'chexbench' and summary['arms']['R47_online_GT']['correct'] != 468:
            raise ValueError('fixed_R47_secondary_common_metric_count')
        if (complete.get('status') != 'generation_complete' or complete.get('arm') != ARM
                or complete.get('questions') != spec['n'] or len(complete.get('windows', [])) != spec['windows']
                or complete.get('fixed_main_call_limit') is not None or complete.get('fixed_tool_call_limit') is not None
                or complete.get('known_technical_missing_ids') or complete.get('completion_mode')):
            raise ValueError('original_full_R49_completion_required:'+dataset)
        for path in (evidence/'generation.exitcode', evidence/'job_records/controller.exitcode',
                     evidence/'job_records'/(dataset+'.exitcode')):
            if path.read_text(encoding='utf-8-sig').strip() != '0':
                raise ValueError('actual_original_exit_zero_required:'+str(path))
        queue = read(evidence/'job_records/queue_status.json')
        expected_state = ('all_three_datasets_exited_zero_after_adoption_recovery' if adoption_recovered else
                          'all_three_datasets_exited_zero_after_phrase_guard_recovery' if phrase_recovered else
                          'all_three_datasets_exited_zero_after_embedding_arrearage_recovery' if embedding_recovered else
                          'all_three_datasets_exited_zero_after_mutation_fields_amendment' if fields_recovered else
                          'all_three_datasets_exited_zero_after_registered_meta_schema_repair' if meta_recovered else
                          'all_three_datasets_exited_zero_after_registered_cuda_retry' if cuda_recovered else
                          'all_three_datasets_exited_zero_after_known_dependency_repair' if recovered else
                          'all_three_datasets_exited_zero')
        if (queue.get('state') != expected_state
                or list(queue.get('datasets', [])) != list(DATASETS)):
            raise ValueError('actual_serial_controller_completion_required')
        if adoption_recovered and (queue.get('recovery') != 'adoption_1' or queue.get('prior_production_attempts_include_exit1') is not True):
            raise ValueError('current_status_must_disclose_adoption_repair_and_all_prior_raw1')
        if phrase_recovered and not adoption_recovered and (queue.get('recovery') != 'phrase_guard_1' or queue.get('prior_production_attempts_include_exit1') is not True):
            raise ValueError('current_status_must_disclose_phrase_policy_and_all_prior_raw1')
        if embedding_recovered and not phrase_recovered and (queue.get('recovery') != 'embedding_arrearage_1' or queue.get('prior_production_attempts_include_exit1') is not True):
            raise ValueError('current_status_must_disclose_embedding_recovery_and_all_prior_raw1')
        if fields_recovered and not embedding_recovered and (queue.get('recovery') != 'mutation_fields_2' or queue.get('prior_production_attempts_include_exit1') is not True):
            raise ValueError('current_status_must_disclose_the_second_META_and_prompt_amendment')
        if meta_recovered and not fields_recovered and (queue.get('recovery') != 'meta_schema_1' or queue.get('prior_production_attempts_include_exit1') is not True):
            raise ValueError('current_status_must_disclose_the_preserved_META_schema_failure')
        if cuda_recovered and not meta_recovered and not fields_recovered and (queue.get('recovery') != 'cuda_1' or queue.get('prior_production_attempts_include_exit1') is not True):
            raise ValueError('current_status_must_disclose_the_preserved_cuda_failure')
        if recovered and not cuda_recovered and not meta_recovered and (queue.get('recovery') != 'dependency_1' or queue.get('initial_controller_exit') != 1
                          or queue.get('initial_chexbench_exit') != 1):
            raise ValueError('current_status_must_disclose_the_preserved_initial_failure')
        inputs = json_rows(evidence/'inputs.jsonl'); ids = [row['question_id'] for row in inputs]
        manifest = read(evidence/'manifest.json')
        publication = read(evidence/'publication_manifest.json')
        if (len(ids) != spec['n'] or len(set(ids)) != spec['n']
                or manifest.get('dataset') != dataset or manifest.get('arm') != ARM
                or manifest.get('initial_repo') != 'empty' or manifest.get('defaults', {}).get('window') != 30
                or [row['question_id'] for row in manifest['inputs']] != ids
                or [item['question_id'] for item in manifest['order']] != ids
                or len({item['image_key'] for item in manifest['order']}) != spec['groups']
                or sum(bool(item['previous_ids']) for item in manifest['order']) != spec['repeats']
                or publication.get('scope') != 'complete_scored_online_stream'
                or publication.get('raw_generation_exit') != 0):
            raise ValueError('cold_start_fixed_cohort_and_group_partition_required:'+dataset)
        for folder in (evidence/'predictions'/ARM, evidence/'contexts', evidence/'steps',
                       evidence/'prediction_events', evidence/'feedback', evidence/'reference_vault'):
            if {path.stem for path in folder.glob('*.json')} != set(ids):
                raise ValueError('full_public_artifact_membership:'+dataset+':'+folder.name)
        for path in (REPORT/'results'/dataset/'per_question.json', evidence/'scores/per_question.json',
                     REPORT/'public_reproduction'/dataset/'per_question.json'):
            details = read(path)
            if len(details) != spec['n'] or [row['question_id'] for row in details] != ids:
                raise ValueError('full_scored_order_membership:'+dataset)
        checked[dataset] = {'n': spec['n'], 'baseline': spec['baseline'], 'baseline_correct': spec['baseline_correct'],
                            'R49_correct': summary['arms'][ARM]['correct'], 'all_predictions_fresh': True,
                            'raw_exit': 0, 'initial_controller_exit': 1 if recovered else None,
                            'known_dependency_repair_used': recovered,
                            'registered_cuda_retry_used': cuda_recovered,
                            'registered_meta_schema_repair_used': meta_recovered,
                            'mutation_fields_amendment_used': fields_recovered,
                            'registered_embedding_HTTP_recovery_used': embedding_recovered,
                            'phrase_guard_generation_policy_used': phrase_recovered,
                            'registered_assess_only_adoption_repair_used': adoption_recovered,
                            'user_directed_initial_audit_deferral_preserved': adoption_recovered,
                            'actual_final_adoption_protocol_resource_result_audit_complete': adoption_recovered,
                            'all_attempts_exited_zero_claim': False if recovered else None,
                            'public_scores_and_resources_reproduced': True}
    return checked


def require_index_scope():
    """Stage only the new R49 block, refusing unrelated unstaged index edits."""
    start = '<!-- R49_ONLINE_GT_WINDOW_SKILL_START -->'
    end = '<!-- R49_ONLINE_GT_WINDOW_SKILL_END -->'
    pattern = re.compile(re.escape(start)+r'.*?'+re.escape(end), flags=re.S)
    for relative in INDEXES:
        current = (ROOT/relative).read_text(encoding='utf-8-sig')
        previous = command(['git', 'show', 'HEAD:'+relative]).decode('utf-8-sig')
        if current.count(start) != current.count(end) or current.count(start) > 1:
            raise ValueError('ambiguous_R49_index_block:'+relative)
        if pattern.sub('', current).rstrip() != pattern.sub('', previous).rstrip():
            raise ValueError('unrelated_index_edits_outside_R49_block:'+relative)


def values_in(value):
    if isinstance(value, dict):
        for item in value.values():
            yield from values_in(item)
    elif isinstance(value, list):
        for item in value:
            yield from values_in(item)
    elif isinstance(value, str):
        yield value


def local_image(value, document):
    if (not isinstance(value, str) or len(value) > 4096 or '\n' in value
            or urlsplit(value).scheme or Path(value).suffix.lower() not in IMAGE_SUFFIXES):
        return None
    target = (document.parent/unquote(value.split('#', 1)[0])).resolve()
    if not target.is_relative_to(ROOT.resolve()):
        return None
    return target.relative_to(ROOT).as_posix()


def outgoing_report_paths():
    """New/modified report files only; committed evidence is already published."""
    modified = names(command(['git', 'diff', '--name-only', '-z', 'HEAD', '--', REPORT_REL]))
    untracked = names(command(['git', 'ls-files', '--others', '-z', '--', REPORT_REL]))
    return [ROOT/relative for relative in sorted(modified|untracked)
            if (ROOT/relative).is_file()]


def referenced_originals():
    """Only image paths explicitly referenced by the outgoing report tree."""
    result = set()
    for path in outgoing_report_paths():
        if path.suffix.lower() == '.json':
            values = values_in(read(path))
        elif path.suffix.lower() == '.jsonl':
            values = values_in(json_rows(path))
        elif path.suffix.lower() == '.md':
            values = (value.strip('<>') for value in re.findall(r'\[[^\]]*\]\(([^)]+)\)', path.read_text(encoding='utf-8-sig')))
        else:
            continue
        for value in values:
            relative = local_image(value, path)
            if relative is not None and original_image(relative):
                if not (ROOT/relative).is_file():
                    raise FileNotFoundError('referenced_original_image:'+relative)
                result.add(relative)
    return result


def prepare(args):
    if MANIFEST.exists() or (RECEIPTS/'allowlist.json').exists():
        raise ValueError('publication_already_prepared')
    completed = ready()  # No manifest/receipt is written until actual docs exist.
    require_index_scope()
    if staged_paths():
        raise ValueError('preexisting_staged_work')
    require_base(args.expected_base)
    old = tracked_paths(); needed = referenced_originals()-old
    if needed and not args.include_untracked_originals:
        raise ValueError('referenced_original_images_not_tracked; use prepare --include-untracked-originals for the explicit referenced files')
    originals = needed if args.include_untracked_originals else set()
    required = SCRIPTS+INDEXES+REFINE_LOGS
    for relative in required:
        if not validate_relative(relative).is_file():
            raise FileNotFoundError(relative)
    values = set(required) | originals
    values.update(path.relative_to(ROOT).as_posix() for path in REPORT.rglob('*') if path.is_file())
    values.add(MANIFEST.relative_to(ROOT).as_posix()); values = sorted(values)
    for relative in values:
        validate_relative(relative, originals)
    write(MANIFEST, {'scope': 'Completed, separately reported CheXbench/SLAKE/VQA-RAD online feedback and Skill experiments',
                     'status': 'allowlist_prepared', 'files': values, 'allowlist_count': len(values),
                     'datasets': completed, 'new_inference_scoring_or_export': False,
                     'cross_dataset_feedback_shared': False, 'independent_848_case_pool_claim': False})
    write(RECEIPTS/'allowlist.json', values)
    write(RECEIPTS/'prepared.json', {'expected_base': args.expected_base, 'allowlist_count': len(values),
                                   'new_original_images': sorted(originals),
                                   'prepared_at': datetime.now(timezone.utc).isoformat()})
    print(json.dumps({'status': 'prepared', 'allowlist_count': len(values), 'new_original_images': len(originals)}))


def check(args):
    completed = ready(); values = paths(); allowed = set(values); old = tracked_paths()
    published_paths = old | allowed
    modified = names(command(['git', 'diff', '--name-only', '-z', 'HEAD']))
    check_values = [relative for relative in values if relative not in old or relative in modified]
    originals = set(read(RECEIPTS/'prepared.json')['new_original_images'])
    if originals != referenced_originals()-old:
        raise ValueError('referenced_untracked_original_allowlist_changed')
    assets = {}
    for relative in old:
        if relative.startswith('reports/') and '/assets/' in relative:
            assets.setdefault('assets/'+relative.rsplit('/assets/', 1)[1], []).append(relative)
    counts = {'json_files': 0, 'jsonl_rows': 0, 'markdown_links': 0,
              'image_references': 0, 'actual_request_images': 0, 'historical_image_references': 0}

    def asset(value, document, actual=False):
        if not isinstance(value, str) or value.startswith(('http:', 'https:', 'data:')):
            if actual:
                raise ValueError('unexported_actual_request_image:'+str(document))
            return
        if len(value) > 4096 or '\n' in value or Path(value).suffix.lower() not in IMAGE_SUFFIXES|{'.bin'}:
            if actual:
                raise ValueError('actual_request_image_path_not_recognized:'+str(value))
            return
        if not actual and not value.startswith(('../', './', 'assets/', 'invalid_request_image_bytes/')):
            return
        target = (document.parent/value).resolve()
        if not target.is_relative_to(ROOT.resolve()):
            raise ValueError('asset_link_outside_repository:'+value)
        relative = target.relative_to(ROOT).as_posix()
        if target.is_file() and relative in published_paths:
            counts['image_references'] += 1
            return
        if actual:
            raise ValueError('actual_request_image_link_missing:'+value)
        # Inherited historical metadata retains its earlier document base.
        candidates = []
        match = re.fullmatch(r'(?:\.\./)+(cxr_[^/]+/.+)', value)
        if match:
            candidates.append('reports/'+match.group(1))
        if value.startswith('assets/'):
            candidates.extend(assets.get(value, []))
        if not any(candidate in old and (ROOT/candidate).is_file() for candidate in candidates):
            raise ValueError('historical_image_reference_missing:'+document.relative_to(ROOT).as_posix()+':'+value)
        counts['historical_image_references'] += 1

    def walk(value, document):
        if isinstance(value, dict):
            for key, item in value.items():
                if key == 'image_url':
                    url = item.get('url') if isinstance(item, dict) else item
                    if document.name == 'request.json' and document.is_relative_to(REPORT/'evidence'):
                        asset(url, document, actual=True); counts['actual_request_images'] += 1
                walk(item, document)
        elif isinstance(value, list):
            for item in value:
                walk(item, document)
        elif isinstance(value, str):
            asset(value, document)

    for relative in check_values:
        path = validate_relative(relative, originals)
        if not path.is_file() or path.stat().st_size >= 100_000_000:
            raise ValueError('missing_or_above_hosting_file_limit:'+relative)
        if path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        text = path.read_text(encoding='utf-8-sig')
        if SECRET.search(text):
            raise ValueError('credential_pattern:'+relative)
        for match in re.finditer(r'"(?:api_key|authorization|password|client_secret|access_token)"\s*:\s*"([^"\n]+)"', text, re.I):
            if match.group(1) not in ('[REDACTED]', 'REDACTED', '***'):
                raise ValueError('credential_value:'+relative)
        if path.suffix.lower() == '.json':
            value = json.loads(text); counts['json_files'] += 1
            if path.is_relative_to(REPORT/'evidence'):
                walk(value, path)
        elif path.suffix.lower() == '.jsonl':
            for line in text.splitlines():
                if line.strip():
                    value = json.loads(line); counts['jsonl_rows'] += 1
                    if path.is_relative_to(REPORT/'evidence'):
                        walk(value, path)
        elif path.suffix.lower() == '.md' and (path.is_relative_to(REPORT) or relative in INDEXES+REFINE_LOGS):
            for value in re.findall(r'\[[^\]]*\]\(([^)]+)\)', text):
                value = value.strip('<>')
                if urlsplit(value).scheme or value.startswith('#'):
                    continue
                target = (path.parent/unquote(value.split('#', 1)[0])).resolve()
                if not target.is_relative_to(ROOT.resolve()) or not target.exists():
                    raise ValueError('markdown_link_missing:'+relative+':'+value)
                if target.is_file() and target.relative_to(ROOT).as_posix() not in published_paths:
                    raise ValueError('markdown_link_unpublished:'+relative+':'+value)
                counts['markdown_links'] += 1
    result = {'status': 'outgoing_content_checks_passed', 'allowlist_count': len(values), **counts,
              'checked_new_or_modified_files': len(check_values),
              'unchanged_committed_files_reused_without_rescan': len(values)-len(check_values),
              'datasets': completed, 'new_original_images': len(originals),
              'credentials_excluded': True, 'unrelated_user_edits_excluded': True,
              'new_inference_scoring_or_export': False}
    write(RECEIPTS/'content_check.json', result)
    print(json.dumps(result))


def code_whitespace_check():
    # Archived native sources, raw logs and reviewer replies retain their
    # original blank lines. Formatting checks apply to active code and indexes.
    command(['git', '-c', 'core.whitespace=-blank-at-eol,-blank-at-eof',
             'diff', '--cached', '--check', '--',
             *SCRIPTS, *INDEXES, *REFINE_LOGS, REPORT_REL+'/README.md'])


def stage(args):
    ready(); require_index_scope(); values = paths(); allowed = set(values)
    if not (RECEIPTS/'content_check.json').is_file():
        raise ValueError('run_content_check_first')
    if not staged_paths() <= allowed:
        raise ValueError('unrelated_preexisting_staged_work')
    pathspec = RECEIPTS/'git_pathspec.nul'
    pathspec.write_bytes(b'\0'.join(value.encode('utf-8') for value in values)+b'\0')
    command(['git', '--literal-pathspecs', 'add', '-f',
             '--pathspec-from-file='+str(pathspec), '--pathspec-file-nul'])
    staged = staged_paths()
    if not staged <= allowed or not set(SCRIPTS) <= staged|tracked_paths():
        raise ValueError('staged_paths_not_expected_allowlist')
    manifest_relative = MANIFEST.relative_to(ROOT).as_posix(); outgoing = sorted(staged|{manifest_relative})
    write(MANIFEST, {'scope': 'Completed R49 per-dataset online same-image truth feedback and window Skill learning',
                     'status': 'explicit_git_index_allowlist', 'git_index_paths': outgoing,
                     'git_index_path_count': len(outgoing), 'allowlist_count': len(values),
                     'file_limit_bytes': 100_000_000, 'new_paid_work_from_publication': 0,
                     'user_unrelated_edits_excluded': True, 'online_ground_truth_feedback_advantage': True,
                     'standard_closed_test_SOTA_claim': False, 'clinical_causality_claim': False,
                     'cross_dataset_feedback_shared': False, 'independent_848_case_pool_claim': False})
    command(['git', 'add', '--', manifest_relative])
    if staged_paths() != set(outgoing):
        raise ValueError('final_index_paths_differ_from_manifest')
    # Preserve deliberate two-space hard breaks in raw DeepSeek review Markdown.
    code_whitespace_check()
    write(RECEIPTS/'stage.json', {'git_index_paths': outgoing, 'git_index_path_count': len(outgoing),
                                 'unrelated_user_edits_staged': False})
    print(json.dumps({'status': 'staged_explicit_allowlist', 'git_index_path_count': len(outgoing)}))


def commit_push(args):
    prepared = read(RECEIPTS/'prepared.json'); staged = read(RECEIPTS/'stage.json')
    base = prepared['expected_base']; receipt = RECEIPTS/'commit.json'
    if receipt.exists():
        commit = read(receipt)['commit']
        if head() != commit or remote_main() not in (base, commit):
            raise ValueError('resume_commit_or_remote_changed')
    else:
        ready(); require_base(base)
        if staged_paths() != set(staged['git_index_paths']):
            raise ValueError('index_changed_after_explicit_stage')
        code_whitespace_check()
        command(['git', 'commit', '-m', args.message]); commit = head()
        if command(['git', 'rev-parse', 'HEAD^']).decode().strip() != base:
            raise ValueError('unexpected_commit_parent')
        committed = names(command(['git', 'diff-tree', '--no-commit-id', '--name-only', '-r', '-z', commit]))
        if committed != set(staged['git_index_paths']):
            raise ValueError('commit_path_membership_differs_from_explicit_stage')
        write(receipt, {'commit': commit, 'base': base, 'git_index_path_count': staged['git_index_path_count']})
    if remote_main() != commit:
        command(['git', 'push', 'origin', 'HEAD:refs/heads/main'])
    print(json.dumps({'status': 'commit_pushed_verify_next', 'commit': commit}))


def verify(args):
    receipt = read(RECEIPTS/'commit.json'); commit = receipt['commit']
    if head() != commit or remote_main() != commit:
        raise ValueError('remote_main_or_local_head_not_publication_commit')
    if command(['git', 'rev-parse', commit+'^']).decode().strip() != receipt['base']:
        raise ValueError('publication_commit_parent_changed')
    expected = set(read(RECEIPTS/'stage.json')['git_index_paths'])
    changed = names(command(['git', 'diff-tree', '--no-commit-id', '--name-only', '-r', '-z', commit]))
    tree = names(command(['git', 'ls-tree', '-r', '--name-only', '-z', commit]))
    if changed != expected or not expected <= tree or not expected <= set(paths()):
        raise ValueError('remote_commit_path_membership_differs_from_allowlist')
    result = {'status': 'published_and_remote_main_verified', 'commit': commit,
              'git_index_path_count': len(expected), 'unrelated_user_edits_excluded': True,
              'report_url': 'https://github.com/cw462/MedRAX-reproduction/blob/main/'+REPORT_REL+'/README.md'}
    write(RECEIPTS/'remote_verification.json', result)
    print(json.dumps(result))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['prepare', 'check', 'stage', 'commit-push', 'verify'])
    parser.add_argument('--expected-base', default=EXPECTED_BASE)
    parser.add_argument('--include-untracked-originals', action='store_true',
                        help='Prepare only: add only explicitly referenced untracked images in the three named image roots.')
    parser.add_argument('--message', default='Publish R49 online feedback and window Skill results on three datasets')
    args = parser.parse_args()
    {'prepare': prepare, 'check': check, 'stage': stage, 'commit-push': commit_push, 'verify': verify}[args.mode](args)
