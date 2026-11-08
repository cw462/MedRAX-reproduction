"""Offline R47 scoring; run only after the unmodified full generation exits zero.

Every arm's saved raw replies are adapted before any feedback, context or scoring
reference is opened. This is online ground-truth feedback on an exposed cohort,
not a standard closed-test evaluation or a new SOTA claim.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
import random
import re
import unicodedata

import numpy as np

from cxr_image_memory_r44 import read, rows, tool_failure_reason, write
from score_cxr_author_alignment import adapt, outcomes
from analyze_cxr_author_alignment import registry, terminal
from score_cxr_image_memory_r44 import new_terminal as r45_terminal
from score_cxr_vqa_extension import bootstrap, cluster_keys
from cxr_image_memory_gt_r47 import context as feedback_context, memory_entry, validate_frozen

ARM = 'M43-IM-GT'
N, REUSED, FRESH = 618, 488, 130


def utc(value):
    if not isinstance(value, str):
        raise ValueError('missing_audit_timestamp')
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('audit_timestamp_requires_timezone')
    return parsed.astimezone(timezone.utc)


def members(folder, expected, label):
    paths = {p.stem: p for p in folder.glob('*.json')}
    if set(paths) != expected:
        raise ValueError(label + '_membership')
    return paths


def frozen_cohort(frozen):
    inputs = frozen['inputs']; ids = [r['question_id'] for r in inputs]
    if len(ids) != N or len(set(ids)) != N:
        raise ValueError('full618_required')
    order = frozen['order']
    if [x['question_id'] for x in order] != ids:
        raise ValueError('frozen_order_differs_from_inputs')
    seen = {}
    for item in order:
        previous = seen.setdefault(item['image_key'], [])
        if item['previous_ids'] != previous:
            raise ValueError('changed_same_image_prefix')
        previous.append(item['question_id'])
    if sum(not x['previous_ids'] for x in order) != REUSED:
        raise ValueError('expected488reuse130fresh')
    if set(frozen['baseline']) != set(ids) or set(frozen['policy']) != set(ids):
        raise ValueError('baseline_or_policy_membership')
    return inputs, set(ids), {x['question_id']: x for x in order}


def completed_gate(frozen, run):
    """Read no contexts, feedback contents or scoring reference labels."""
    inputs, ids, order = frozen_cohort(frozen)
    if (run/'generation.exitcode').read_text(encoding='utf-8').strip() != '0':
        raise ValueError('raw_generation_exit_not_zero_no_effective_recovery')
    complete = read(run/f'complete_{ARM}.json')
    if (complete.get('questions') != N or complete.get('status') != 'generation_complete'
            or complete.get('feedback_events') != N
            or complete.get('reference_access') != 'only_after_own_prediction_saved'
            or complete.get('current_or_future_reference_in_current_request') is not False
            or complete.get('known_technical_missing_ids')
            or complete.get('completion_mode') is not None
            or complete.get('original_runner_final_exit') not in (None, 0)):
        raise ValueError('unmodified_full_generation_required')
    predictions = members(run/'predictions'/ARM, ids, 'prediction')
    contexts = members(run/'memory_context', ids, 'context')
    feedback = members(run/'feedback_events', ids, 'feedback')
    for part in ('calls', 'tool_selections'):
        unknown = {p.name for p in (run/part/ARM).iterdir() if p.is_dir()}-ids if (run/part/ARM).exists() else set()
        if unknown:
            raise ValueError('evidence_outside_cohort:' + part)
    return inputs, ids, order, complete, predictions, contexts, feedback


def validate_feedback_prefix(frozen, run, order, predictions, receipts, context_paths, feedback_paths):
    """Rebuild the displayed memory from the immutable prior save/feedback chain."""
    contexts, feedback, selections, memories = {}, {}, {}, {}
    rowmap = {row['question_id']: row for row in frozen['inputs']}
    global_previous_release = None
    for ordinal, item in enumerate(frozen['order'], 1):
        qid = item['question_id']; row = rowmap[qid]; prediction = predictions[qid]
        trace, event = read(context_paths[qid]), read(feedback_paths[qid])
        if (prediction.get('question_id') != qid or prediction.get('arm') != ARM
                or trace.get('question_id') != qid or event.get('question_id') != qid
                or trace.get('ordinal') != ordinal or event.get('ordinal') != ordinal
                or trace.get('image_key') != item['image_key'] or event.get('image_key') != item['image_key']):
            raise ValueError('feedback_context_prediction_identity:' + qid)
        if (event.get('schema') != 'post_prediction_dataset_feedback_v1'
                or event.get('provenance') != 'dataset_annotation_feedback_not_patient_history'
                or event.get('timing') != 'reference_loaded_only_after_immutable_prediction_save'
                or trace.get('current_reference_available') is not False):
            raise ValueError('feedback_protocol_changed:' + qid)
        saved_prediction = {key: prediction.get(key) for key in ('answer', 'reason', 'status', 'prediction_saved_at')}
        if event.get('saved_prediction') != saved_prediction or event.get('reference_file') != qid+'.json':
            raise ValueError('feedback_saved_prediction_or_reference_identity:' + qid)
        created, saved, released = utc(trace['created_at']), utc(prediction['prediction_saved_at']), utc(event['released_at'])
        if not created <= saved <= released or (global_previous_release is not None and global_previous_release > created):
            raise ValueError('feedback_not_after_own_save_or_not_sequential:' + qid)
        for started, result in receipts[qid]:
            if not created <= utc(started['utc']) <= utc(result['utc']) <= saved:
                raise ValueError('request_outside_context_prediction_window:' + qid)
        entries = memories.setdefault(item['image_key'], [])
        memory, included = feedback_context(entries, item, ordinal, frozen['memory_max_chars'], frozen['memory_max_entries'])
        if (trace['previous_ids'] != item['previous_ids'] or trace['included_ids'] != included
                or trace['memory'] != memory):
            raise ValueError('changed_prior_only_exact_same_image_memory:' + qid)
        if not set(included) <= set(item['previous_ids']) or qid in included:
            raise ValueError('current_future_or_other_image_feedback:' + qid)
        selected_paths = sorted((run/'tool_selections'/ARM/qid).glob('*.json'), key=lambda path: int(path.stem))
        if [int(path.stem) for path in selected_paths] != list(range(1, len(selected_paths)+1)):
            raise ValueError('noncontiguous_tool_selections:' + qid)
        selected = [read(path) for path in selected_paths]
        main_cap, tool_cap = (6, 4) if frozen['policy'][qid] == 'C41' else (4, 2)
        if len(receipts[qid]) > main_cap or len(selected) > tool_cap or prediction['tool_calls'] != len(selected):
            raise ValueError('per_question_budget_or_tool_count:' + qid)
        if prediction.get('new_main_calls') != len(receipts[qid]) or prediction.get('new_tool_calls') != len(selected):
            raise ValueError('new_call_count_disagrees_with_evidence:' + qid)
        if prediction['reused_M43'] and selected:
            raise ValueError('reused_prediction_has_new_tool_work:' + qid)
        for value in selected:
            if tool_failure_reason(value):
                raise ValueError('unhealthy_tool_no_silent_recovery:' + qid)
            key = value['cache_key']
            cache = (run/'tool_cache'/key).resolve()
            if not cache.is_relative_to((run/'tool_cache').resolve()) or not (cache/'result.json').is_file():
                raise ValueError('tool_cache_not_closed:' + qid)
            backend = read(cache/'result.json')
            if tool_failure_reason(backend) or any(value.get(k) != backend.get(k) for k in backend):
                raise ValueError('tool_selection_cache_binding:' + qid)
            if not created <= utc(value['utc']) <= saved and not value.get('cache_hit'):
                raise ValueError('fresh_tool_outside_episode_window:' + qid)
        for request_path in (run/'calls'/ARM/qid).glob('*/request.json'):
            messages = read(request_path)['messages']
            if memory is None or sum(message.get('content') == memory for message in messages) != 1:
                raise ValueError('actual_request_missing_exact_prior_feedback:' + qid)
        contexts[qid], feedback[qid], selections[qid] = trace, event, selected
        entries.append(memory_entry(row, prediction, event))
        global_previous_release = released
    selected_keys = {value['cache_key'] for values in selections.values() for value in values}
    for started in (run/'tool_cache').glob('*/started.json'):
        if started.parent.name not in selected_keys or not (started.parent/'result.json').is_file():
            raise ValueError('orphan_or_unclosed_tool_attempt')
    return contexts, feedback, selections


def request_evidence(run, qid, prediction, arm=ARM):
    """Validate closed sends and return the actual last response for adaptation."""
    folder = run/'calls'/arm/qid
    folders = sorted((p for p in folder.iterdir() if p.is_dir()), key=lambda p: int(p.name)) if folder.exists() else []
    if [int(p.name) for p in folders] != list(range(1, len(folders)+1)):
        raise ValueError('noncontiguous_actual_calls:' + qid)
    receipts = []
    for call in folders:
        if any(not (call/name).is_file() for name in ('request.json', 'started.json', 'response.json', 'result.json')):
            raise ValueError('unresolved_or_unsent_request:' + qid)
        started, result = read(call/'started.json'), read(call/'result.json')
        if result.get('error') or result.get('response_received') is not True:
            raise ValueError('unhealthy_request_receipt:' + qid)
        if started.get('request_id') != result.get('request_id'):
            raise ValueError('request_receipt_identity:' + qid)
        if utc(started['utc']) > utc(result['utc']):
            raise ValueError('request_timing:' + qid)
        receipts.append((started, result))
    if len(folders) != prediction['main_calls']:
        raise ValueError('prediction_actual_call_count:' + qid)
    if not folders:
        raise ValueError('fresh_prediction_without_request:' + qid)
    last = folders[-1]
    raw = read(last/'response.json'); message = raw['choices'][0]['message']
    content = message.get('content')
    if isinstance(content, list):
        content = '\n'.join(x.get('text', '') for x in content if isinstance(x, dict) and x.get('type') == 'text')
    nonfinal = bool(message.get('tool_calls')) or bool(message.get('function_call'))
    available = isinstance(content, str) and bool(content.strip())
    technical = bool(prediction.get('technical_failure')) or any(x in prediction['status'] for x in ('tool_unhealthy', 'transport_unknown'))
    if technical:
        raise ValueError('technical_failure_cannot_be_scored_as_full_R47:' + qid)
    source = {'raw': content if available and not nonfinal else None,
              'call_path': str(last), 'ordinal': last.name, 'reuse_chain': [],
              'evidence_status': 'received_terminal_text' if available and not nonfinal else 'nonfinal_or_unavailable',
              'technical_stop': False}
    return source, receipts


def optional_r45(frozen_path, run, inputs, baseline):
    if (frozen_path is None) != (run is None):
        raise ValueError('r45_requires_frozen_and_run_archive')
    if run is None:
        return None
    old = read(frozen_path); _, ids, _ = frozen_cohort(old)
    if old['inputs'] != inputs or old['baseline'] != baseline:
        raise ValueError('r45_frozen_cohort_or_baseline_changed')
    complete = read(run/'complete_M43-IM.json')
    if complete.get('questions') != N:
        raise ValueError('r45_full_frozen_archive_required')
    effective = run/('generation.effective.exitcode' if complete.get('completion_mode') == 'independent_known_failure_finalization' else 'generation.exitcode')
    if effective.read_text(encoding='utf-8').strip() != '0':
        raise ValueError('r45_completed_archive_required')
    paths = members(run/'predictions/M43-IM', ids, 'r45_prediction')
    result = {}
    for row in inputs:
        q = row['question_id']; prediction = read(paths[q])
        if prediction.get('reused_M43'):
            if any(prediction.get(k) != baseline[q].get(k) for k in ('answer', 'reason', 'status')):
                raise ValueError('r45_baseline_reuse_changed:' + q)
            result[q] = None
        else:
            result[q] = adapt(row, prediction, r45_terminal(run, q, prediction))
    return result


def resource_report(run, predictions, selections, receipts, frozen, complete):
    records = [record for pairs in receipts.values() for _, record in pairs]
    known = [Decimal(str(x['settlement']['charged_cny'])) for x in records if x.get('settlement', {}).get('charged_cny') is not None]
    unknown = len(records)-len(known)
    selected = [value for values in selections.values() for value in values]
    sends = [started for pairs in receipts.values() for started, _ in pairs]
    end = complete.get('completed_at', complete.get('utc'))
    return {'new_main_sends': len(records), 'new_main_responses': len(records),
            'logical_tool_selections': len(selected),
            'cache_hits': sum(bool(x.get('cache_hit')) for x in selected),
            'fresh_tool_attempts': sum(not x.get('cache_hit') for x in selected),
            'completed_backend_model_events': sum(e.get('status') == 'completed' for x in selected if not x.get('cache_hit') for e in x.get('actual_model_events', [])),
            'tool_elapsed_seconds': sum(x.get('elapsed_s', 0) or 0 for x in selected if not x.get('cache_hit')),
            'model_request_elapsed_seconds_known': sum(x.get('elapsed_s') or 0 for x in records),
            'unknown_request_elapsed_count': sum(x.get('elapsed_s') is None for x in records),
            'new_episode_elapsed_seconds_known': sum(x.get('elapsed_s') or 0 for x in predictions if not x.get('reused_M43')),
            'unknown_episode_elapsed_count': sum(not x.get('reused_M43') and x.get('elapsed_s') is None for x in predictions),
            'wall_seconds_including_interruptions': (utc(end)-min(utc(x['utc']) for x in sends)).total_seconds() if sends and end else None,
            'input_tokens_known': sum((x.get('usage') or {}).get('prompt_tokens', 0) or 0 for x in records),
            'output_tokens_known': sum((x.get('usage') or {}).get('completion_tokens', 0) or 0 for x in records),
            'proxy_cny_known_subtotal': str(sum(known, Decimal(0))),
            'proxy_cny_total': str(sum(known, Decimal(0))) if unknown == 0 else None,
            'unknown_settlement_count': unknown, 'provider_invoice': False,
            'historical_calls_recounted_as_new': False,
            'model_ids': sorted({x['model_returned'] for x in records if x.get('model_returned')}),
            'cohort_main_cap': frozen['new_main_ceiling'], 'cohort_tool_cap': frozen['new_tool_ceiling'],
            'per_policy_caps': {'M': {'main': 4, 'tools': 2}, 'C41': {'main': 6, 'tools': 4}}}


def wording(value):
    return ' '.join(unicodedata.normalize('NFKC', str(value)).casefold().split())


def input_overlap(inputs, order):
    """Predeclared question/option overlap tags; never inspect answers or labels."""
    normalize = lambda value: re.sub(r'[^a-z0-9]+', ' ', str(value).lower()).strip()
    rowmap = {row['question_id']: row for row in inputs}
    pairs = []
    for row in inputs:
        qid = row['question_id']
        options = {k: normalize(v) for k, v in (row.get('options') or {}).items()}
        for prior in order[qid]['previous_ids']:
            old = rowmap[prior]
            if normalize(row['question']) != normalize(old['question']):
                continue
            old_options = {k: normalize(v) for k, v in (old.get('options') or {}).items()}
            shared = sorted(set(options.values()) & set(old_options.values()))
            pairs.append({'previous_id': prior, 'current_id': qid,
                          'complete_question_and_options_match': options == old_options,
                          'shared_normalized_option_texts': shared,
                          'shared_atelectasis_option': any('atelectasis' in text for text in shared)})
    totals = (len(pairs), sum(p['complete_question_and_options_match'] for p in pairs),
              sum(p['shared_atelectasis_option'] for p in pairs))
    if totals != (17, 0, 14):
        raise ValueError('predeclared_input_overlap_groups_changed')
    return {'definition': "lowercase question; replace [^a-z0-9]+ with one space; compare only exact-image prior prefix; options normalized individually",
            'same_wording_prefix_pairs': totals[0], 'same_full_question_and_options_prefix_pairs': totals[1],
            'same_wording_shared_atelectasis_option_pairs': totals[2], 'pairs': pairs,
            'semantic_equivalence_adjudicated': False, 'reference_labels_used_for_tags': False}


def answer_text(row, reference):
    return (row.get('options') or {}).get(reference, reference)


def diagnostic(values):
    return {'extraction_counts': dict(Counter(x['extraction'] for x in values)),
            **{key: sum(bool(x[key]) for x in values) for key in ('raw_whole_json_valid', 'legacy_M_contract_compliant', 'answer_absent', 'choice_domain_invalid', 'technical_stop')}}


def score(frozen_path, run, references, out, r45_frozen=None, r45_run=None):
    if out.exists():
        raise ValueError('new_score_output_directory_required')
    frozen = read(frozen_path)
    validate_frozen(frozen)
    marker = read(run/'run.json')
    if any(marker.get(key) != frozen[key] for key in ('order', 'inputs', 'policy', 'baseline')):
        raise ValueError('run_plan_changed')
    inputs, ids, order, complete, pred_paths, context_paths, feedback_paths = completed_gate(frozen, run)
    overlap = input_overlap(inputs, order)
    overlap_current = {p['current_id'] for p in overlap['pairs']}
    atelectasis_current = {p['current_id'] for p in overlap['pairs'] if p['shared_atelectasis_option']}
    specs = [s for s in registry() if s['dataset'] == 'chexbench' and s['arm'] == 'M43']
    if len(specs) != 1:
        raise ValueError('M43_registry_ambiguous')
    key = specs[0]['key']; baseline, current, predictions, receipts = {}, {}, {}, {}
    # REFERENCE-FREE PHASE: no memory_context, feedback or references are read.
    for row in inputs:
        q = row['question_id']; old = frozen['baseline'][q]; new = read(pred_paths[q])
        baseline[q] = adapt(row, old, terminal('chexbench', key, q))
        reused = not order[q]['previous_ids']
        if bool(new.get('reused_M43')) != reused:
            raise ValueError('expected488reuse130fresh:' + q)
        if reused:
            if any(new.get(k) != old.get(k) for k in ('answer', 'reason', 'status')):
                raise ValueError('baseline_reuse_changed:' + q)
            if list((run/'calls'/ARM/q).glob('*/*')) or new.get('main_calls') != 0 or new.get('tool_calls') != 0:
                raise ValueError('reused_row_has_new_work:' + q)
            current[q] = dict(baseline[q]); receipts[q] = []
        else:
            source, receipts[q] = request_evidence(run, q, new)
            current[q] = adapt(row, new, source)
        predictions[q] = new
    comparison = optional_r45(r45_frozen, r45_run, inputs, frozen['baseline'])
    if comparison is not None:
        comparison = {q: comparison[q] or dict(baseline[q]) for q in ids}
    # Every saved raw reply in every compared arm has now been adapted.
    contexts, feedback, selections = validate_feedback_prefix(frozen, run, order, predictions, receipts, context_paths, feedback_paths)
    resources = resource_report(run, list(predictions.values()), selections, receipts, frozen, complete)
    if (resources['new_main_sends'] > frozen['new_main_ceiling']
            or resources['logical_tool_selections'] > frozen['new_tool_ceiling']):
        raise ValueError('cohort_budget_exceeded')
    if resources['new_main_sends'] != complete['new_main_sends'] or resources['logical_tool_selections'] != complete['new_logical_tool_calls']:
        raise ValueError('completion_evidence_counts_disagree')
    reference_rows = rows(references); refs = {x['question_id']: x['answer'] for x in reference_rows}
    if len(reference_rows) != N or set(refs) != ids:
        raise ValueError('scoring_reference_membership')
    details = []; rowmap = {r['question_id']: r for r in inputs}
    for row in inputs:
        q = row['question_id']; ref = refs[q]; trace = contexts[q]; used = trace['included_ids']
        if feedback[q]['reference_annotation']['answer'] != ref:
            raise ValueError('released_feedback_differs_from_dataset_truth:' + q)
        b = outcomes(row, baseline[q], ref, random.Random(0))['aligned_correct']
        n = outcomes(row, current[q], ref, random.Random(0))['aligned_correct']
        prior_texts = [answer_text(rowmap[p], feedback[p]['reference_annotation']['answer']) for p in used]
        details.append({'question_id': q, 'question': row['question'], 'options': row.get('options'),
                        'image_id': row['image_id'], 'reference': ref, 'M43': baseline[q], ARM: current[q],
                        'before_correct': bool(b), 'after_correct': bool(n),
                        'sequence_position': len(order[q]['previous_ids'])+1,
                        'same_image_previous_ids': order[q]['previous_ids'], 'feedback_included_ids': used,
                        'reused_M43': bool(predictions[q]['reused_M43']),
                        'input_only_same_wording_prefix': q in overlap_current,
                        'input_only_shared_atelectasis_option_prefix': q in atelectasis_current,
                        'same_wording_feedback': any(wording(rowmap[p]['question']) == wording(row['question']) for p in used),
                        'same_wording_and_options_feedback': any(wording(rowmap[p]['question']) == wording(row['question']) and rowmap[p].get('options') == row.get('options') for p in used),
                        'current_reference_text_matches_prior_feedback': any(wording(text) == wording(answer_text(row, ref)) for text in prior_texts),
                        'prior_feedback_answer_text_in_current_options': any(wording(text) in {wording(v) for v in (row.get('options') or {}).values()} for text in prior_texts),
                        **({'M43_IM_R45': comparison[q], 'r45_correct': bool(outcomes(row, comparison[q], ref, random.Random(0))['aligned_correct'])} if comparison is not None else {})})
    before = np.array([x['before_correct'] for x in details], dtype=int)
    after = np.array([x['after_correct'] for x in details], dtype=int)
    if int(before.sum()) != 466:
        raise ValueError('common_author_adapter_M43_must_equal466of618')
    subsets = np.array([r.get('source', {}).get('subset', 'all') for r in inputs])
    delta = after-before
    def counts(mask, comparator=before):
        d = after[mask]-comparator[mask]; n = int(mask.sum())
        return {'n': n, 'baseline_correct': int(comparator[mask].sum()), 'R47_correct': int(after[mask].sum()),
                'baseline_pct': 100*float(comparator[mask].mean()) if n else None,
                'R47_pct': 100*float(after[mask].mean()) if n else None,
                'corrections': int((d > 0).sum()), 'harms': int((d < 0).sum()), 'net': int(d.sum())}
    by_subset = {str(s): counts(subsets == s) for s in sorted(set(subsets))}
    positions = np.array([d['sequence_position'] for d in details]); reused = np.array([d['reused_M43'] for d in details])
    report = {'arm': ARM, 'n': N, 'M43': int(before.sum()), ARM: int(after.sum()),
              'micro_pct': 100*float(after.mean()), 'macro_pct': float(np.mean([s['R47_pct'] for s in by_subset.values()])),
              'M43_micro_pct': 100*float(before.mean()), 'M43_macro_pct': float(np.mean([s['baseline_pct'] for s in by_subset.values()])),
              'corrections': int((delta > 0).sum()), 'harms': int((delta < 0).sum()), 'net': int(delta.sum()),
              'subsets': by_subset, 'paired_image_patient_study_cluster_interval': bootstrap(delta, cluster_keys(inputs), subsets),
              'paired_exact_same_image_interval': bootstrap(delta, [order[r['question_id']]['image_key'] for r in inputs], subsets),
              'by_position': {str(pos): counts(positions == pos) for pos in sorted(set(positions))},
              'by_regeneration': {'reused': counts(reused), 'fresh_with_prior_truth_feedback': counts(~reused)},
              'by_image_occurrence': {'first_or_single': counts(positions == 1), 'repeated': counts(positions > 1)},
              'input_only_prefix_overlap': overlap,
              'by_input_only_overlap': {field: {'yes': counts(np.array([d[field] for d in details])),
                                               'no': counts(~np.array([d[field] for d in details]))}
                                       for field in ('input_only_same_wording_prefix', 'input_only_shared_atelectasis_option_prefix')},
              'feedback_diagnostics': {field: {'yes': counts(np.array([d[field] for d in details])),
                                               'no': counts(~np.array([d[field] for d in details]))}
                                       for field in ('same_wording_feedback', 'same_wording_and_options_feedback', 'current_reference_text_matches_prior_feedback', 'prior_feedback_answer_text_in_current_options')},
              'answer_diagnostics': {'M43': diagnostic(list(baseline.values())), ARM: diagnostic(list(current.values()))},
              'resources': resources, 'references_read_after_all_arms_adapted': True,
              'raw_generation_exit': 0, 'full_prediction_context_feedback_counts': [N, N, N],
              'effective_recovery_used': False, 'online_ground_truth_feedback_advantage': True,
              'standard_closed_test_SOTA_claim': False, 'unseen_test_claim': False,
              'limitations': ['Prior same-image dataset answers are disclosed online after each prediction is saved; this is an oracle feedback advantage.',
                             '488 historical M43 predictions are reused; only 130 repeated-image questions receive new generation.',
                             'The exposed cohort, feedback label overlap, sequential dependence and sampling/runtime differences limit causal interpretation.',
                             'Cluster intervals describe this frozen cohort comparison, not independent-patient generalization.']}
    if comparison is not None:
        old = np.array([d['r45_correct'] for d in details], dtype=int)
        report['frozen_R45_comparison'] = {**counts(np.ones(N, dtype=bool), old),
                                         'macro_pct': float(np.mean([100*old[subsets == s].mean() for s in sorted(set(subsets))])),
                                         'subsets': {str(s): counts(subsets == s, old) for s in sorted(set(subsets))},
                                         'paired_interval': bootstrap(after-old, cluster_keys(inputs), subsets),
                                         'new_R45_generation': False, 'same_common_adapter': True}
        report['answer_diagnostics']['M43_IM_R45'] = diagnostic(list(comparison.values()))
    write(out/'summary.json', report); write(out/'per_question.json', details)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('frozen', 'run', 'references', 'out'):
        parser.add_argument('--'+name, type=Path, required=True)
    parser.add_argument('--r45-frozen', type=Path)
    parser.add_argument('--r45-run', type=Path, help='Completed frozen prediction/call archive; no new R45 generation.')
    args = parser.parse_args()
    print(score(args.frozen, args.run, args.references, args.out, args.r45_frozen, args.r45_run))


if __name__ == '__main__':
    main()
