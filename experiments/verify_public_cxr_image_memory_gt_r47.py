"""Reproduce primary R47 scores from portable public saved evidence, offline."""
import argparse
import json
from pathlib import Path
import random

import numpy as np

from analyze_cxr_author_alignment import ROOT, registry, terminal
from cxr_image_memory_r44 import read, rows, tool_failure_reason, write
from score_cxr_author_alignment import adapt, outcomes
from score_cxr_image_memory_gt_r47 import (
    ARM, N, completed_gate, diagnostic, input_overlap, request_evidence, utc,
)
from score_cxr_vqa_extension import bootstrap, cluster_keys


def check_public_images(inputs, evidence):
    """Resolve reused public original references without private absolute paths."""
    for row in inputs:
        for image in row['images']:
            target = (evidence/image).resolve()
            if not target.is_relative_to(ROOT.resolve()) or not target.is_file():
                raise ValueError('public_original_image_missing_or_outside_repository')


def check_public_feedback(frozen, evidence, order, predictions, receipts, contexts, feedback):
    """Check published identities, processed prefixes, chronology and annotations."""
    rowmap = {row['question_id']: row for row in frozen['inputs']}
    events, previous_release, tool_count = {}, None, 0
    for ordinal, item in enumerate(frozen['order'], 1):
        q = item['question_id']; prediction = predictions[q]
        trace, event = read(contexts[q]), read(feedback[q])
        if (trace.get('question_id') != q or event.get('question_id') != q
                or trace.get('ordinal') != ordinal or event.get('ordinal') != ordinal
                or trace.get('image_key') != item['image_key'] or event.get('image_key') != item['image_key']
                or trace.get('previous_ids') != item['previous_ids']
                or trace.get('current_reference_available') is not False):
            raise ValueError('public_feedback_context_identity:' + q)
        included = trace['included_ids']
        if len(set(included)) != len(included) or not set(included) <= set(item['previous_ids']):
            raise ValueError('public_current_future_other_image_feedback:' + q)
        if included != [p for p in item['previous_ids'] if p in included]:
            raise ValueError('public_feedback_order:' + q)
        vault_name = f'reference_vault/{q}.json'
        saved_prediction = event.get('saved_prediction', {})
        if (any(saved_prediction.get(key) != prediction.get(key) for key in ('answer', 'status', 'prediction_saved_at'))
                or event.get('reference_file') != q+'.json'
                or event.get('timing') != 'reference_loaded_only_after_immutable_prediction_save'
                or event.get('provenance') != 'dataset_annotation_feedback_not_patient_history'):
            raise ValueError('public_feedback_saved_prediction_or_reference_identity:' + q)
        created, saved, released = utc(trace['created_at']), utc(prediction['prediction_saved_at']), utc(event['released_at'])
        if not created <= saved <= released or (previous_release is not None and previous_release > created):
            raise ValueError('public_feedback_chronology:' + q)
        for started, result in receipts[q]:
            if not created <= utc(started['utc']) <= utc(result['utc']) <= saved:
                raise ValueError('public_request_chronology:' + q)
        vault = read(evidence/vault_name)
        annotation = {key: vault[key] for key in ('answer', 'answer_text') if key in vault}
        if vault.get('question_id') != q or annotation != event['reference_annotation']:
            raise ValueError('public_vault_feedback_annotation:' + q)
        memory = trace['memory']
        if item['previous_ids']:
            if not isinstance(memory, str) or not included:
                raise ValueError('public_repeat_requires_prior_feedback:' + q)
            displayed = json.loads(memory.split('\n', 1)[1])
            if [entry['question_id'] for entry in displayed] != included:
                raise ValueError('public_displayed_feedback_membership:' + q)
            for entry in displayed:
                prior = entry['question_id']; original = rowmap[prior]
                expected = dict(events[prior]['reference_annotation'])
                options = original.get('options') or {}
                if expected['answer'] in options:
                    expected['option_text'] = options[expected['answer']]
                if (entry.get('question') != original['question'] or entry.get('options') != original.get('options', {})
                        or entry.get('previous_answer') != predictions[prior].get('answer')
                        or entry.get('previous_status') != predictions[prior].get('status')
                        or entry.get('reference_annotation') != expected):
                    raise ValueError('public_displayed_prior_annotation:' + q)
        elif memory is not None or included:
            raise ValueError('public_first_occurrence_has_feedback:' + q)
        selected = sorted((evidence/'tool_selections'/ARM/q).glob('*.json'), key=lambda p: int(p.stem))
        cap, tool_cap = (6, 4) if frozen['policy'][q] == 'C41' else (4, 2)
        if (len(receipts[q]) > cap or len(selected) > tool_cap
                or prediction.get('tool_calls') != len(selected)
                or prediction.get('new_main_calls') != len(receipts[q])
                or prediction.get('new_tool_calls') != len(selected)):
            raise ValueError('public_per_question_caps_or_counts:' + q)
        if [int(path.stem) for path in selected] != list(range(1, len(selected)+1)):
            raise ValueError('public_tool_selection_ordinals:' + q)
        for path in selected:
            if tool_failure_reason(read(path)):
                raise ValueError('public_unhealthy_tool_selection:' + q)
        tool_count += len(selected); events[q] = event; previous_release = released
    return events, tool_count


def verify(evidence, out):
    evidence, out = evidence.resolve(), out.resolve()
    if out.exists() or out.is_relative_to(evidence) or evidence.is_relative_to(out):
        raise ValueError('new_output_separate_from_public_evidence_required')
    frozen = read(evidence/'frozen.public.json')
    inputs, ids, order, complete, pred_paths, contexts, feedback = completed_gate(frozen, evidence)
    originals = rows(evidence/'inputs.jsonl')
    if (len(originals) != N or [r['question_id'] for r in originals] != [r['question_id'] for r in inputs]
            or any(set(row)-{'question_id', 'question', 'images', 'image_id', 'source', 'options'} for row in originals)):
        raise ValueError('public_input_membership_or_unexpected_fields')
    for row, original in zip(inputs, originals):
        if any(row.get(key) != original.get(key) for key in ('question', 'options', 'image_id')):
            raise ValueError('public_input_content_differs_from_frozen')
    check_public_images(originals, evidence)
    marker = read(evidence/'run.json')
    if any(marker.get(key) != frozen[key] for key in ('order', 'policy', 'inputs', 'baseline')):
        raise ValueError('public_run_plan_changed')
    specs = [s for s in registry() if s['dataset'] == 'chexbench' and s['arm'] == 'M43']
    if len(specs) != 1:
        raise ValueError('M43_registry_ambiguous')
    baseline, current, predictions, receipts = {}, {}, {}, {}
    # No context/feedback/vault/scoring-reference contents are opened in this phase.
    for row in inputs:
        q = row['question_id']; old = frozen['baseline'][q]; new = read(pred_paths[q])
        baseline[q] = adapt(row, old, terminal('chexbench', specs[0]['key'], q))
        reused = not order[q]['previous_ids']
        if new.get('question_id') != q or new.get('arm') != ARM or bool(new.get('reused_M43')) != reused:
            raise ValueError('public_prediction_reuse_or_identity:' + q)
        if reused:
            if (any(new.get(k) != old.get(k) for k in ('answer', 'status'))
                    or list((evidence/'calls'/ARM/q).glob('*/*'))
                    or new.get('main_calls') != 0 or new.get('tool_calls') != 0):
                raise ValueError('public_baseline_reuse_changed:' + q)
            current[q], receipts[q] = dict(baseline[q]), []
        else:
            source, receipts[q] = request_evidence(evidence, q, new)
            current[q] = adapt(row, new, source)
        predictions[q] = new
    # Every compared raw answer is adapted before any feedback or scoring label is opened.
    events, tool_count = check_public_feedback(frozen, evidence, order, predictions, receipts, contexts, feedback)
    sends = sum(len(pairs) for pairs in receipts.values())
    if (sends != complete['new_main_sends'] or tool_count != complete['new_logical_tool_calls']
            or sends > frozen['new_main_ceiling'] or tool_count > frozen['new_tool_ceiling']):
        raise ValueError('public_cohort_caps_or_completion_counts')
    reference_rows = rows(evidence/'references.jsonl'); refs = {r['question_id']: r['answer'] for r in reference_rows}
    if len(reference_rows) != N or set(refs) != ids:
        raise ValueError('public_reference_membership')
    details = []
    for row in inputs:
        q = row['question_id']; ref = refs[q]
        if events[q]['reference_annotation']['answer'] != ref:
            raise ValueError('public_reference_feedback_truth_disagrees:' + q)
        details.append({'question_id': q, 'M43': baseline[q], ARM: current[q],
                        'before_correct': bool(outcomes(row, baseline[q], ref, random.Random(0))['aligned_correct']),
                        'after_correct': bool(outcomes(row, current[q], ref, random.Random(0))['aligned_correct'])})
    before = np.array([d['before_correct'] for d in details], dtype=int)
    after = np.array([d['after_correct'] for d in details], dtype=int); delta = after-before
    if int(before.sum()) != 466:
        raise ValueError('public_common_adapter_M43_must_equal466of618')
    subsets = np.array([r.get('source', {}).get('subset', 'all') for r in inputs])
    def counts(mask):
        d = delta[mask]
        return {'n': int(mask.sum()), 'M43': int(before[mask].sum()), ARM: int(after[mask].sum()),
                'micro_pct': 100*float(after[mask].mean()), 'corrections': int((d > 0).sum()),
                'harms': int((d < 0).sum()), 'net': int(d.sum())}
    by_subset = {str(s): counts(subsets == s) for s in sorted(set(subsets))}
    result = {'scope': 'Primary public score reproduction and semantic evidence consistency.',
              'arm': ARM, **counts(np.ones(N, dtype=bool)),
              'macro_pct': float(np.mean([value['micro_pct'] for value in by_subset.values()])),
              'subsets': by_subset, 'paired_interval': bootstrap(delta, cluster_keys(inputs), subsets),
              'input_only_prefix_overlap': input_overlap(inputs, order),
              'answer_diagnostics': {'M43': diagnostic(list(baseline.values())), ARM: diagnostic(list(current.values()))},
              'raw_generation_exit': 0, 'full_prediction_context_feedback_counts': [N, N, N],
              'new_inference_calls': 0,
              'references_read_after_all_arms_adapted': True,
              'R45_secondary_comparison_reproduced': False,
              'online_ground_truth_feedback_advantage': True, 'standard_closed_test_SOTA_claim': False}
    saved = read(evidence/'scores/summary.json'); saved_rows = read(evidence/'scores/per_question.json')
    for key in ('n', 'M43', ARM, 'micro_pct', 'macro_pct', 'corrections', 'harms', 'net'):
        if key not in saved or abs(saved[key]-result[key]) > 1e-10:
            raise ValueError('public_primary_score_differs_from_private_score:' + key)
    if len(saved_rows) != N or {row['question_id'] for row in saved_rows} != ids:
        raise ValueError('published_scored_row_membership')
    expected_rows = {row['question_id']: row for row in saved_rows}
    for value in details:
        old = expected_rows[value['question_id']]
        if any(value[key] != old[key] for key in ('before_correct', 'after_correct')):
            raise ValueError('public_per_question_score_changed:' + value['question_id'])
        for arm in ('M43', ARM):
            if any(value[arm][key] != old[arm][key] for key in ('explicit_answer', 'choice', 'extraction')):
                raise ValueError('public_per_question_adaptation_changed:' + value['question_id'])
    result['matches_published_primary_scores_and_extractions'] = True
    write(out/'summary.json', result); write(out/'per_question.json', details)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(verify(args.evidence, args.out), ensure_ascii=False))
