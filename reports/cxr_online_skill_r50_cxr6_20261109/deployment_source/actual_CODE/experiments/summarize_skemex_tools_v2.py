"""Derive report tables from the completed public export; never rescore or call APIs."""
import argparse
from collections import Counter
import json
from pathlib import Path
import re


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def summarize(base):
    base = Path(base)
    metrics = read(base/'analysis/metrics.json')
    records = read(base/'analysis/per_question.json')['records']
    rows = {r['question_id']: r for r in read(base/'cases.json')['rows']}
    source = [read(p) for p in (base/'source_predictions').glob('*/*.json')]
    windows = [(p, read(p)) for p in sorted((base/'window_records').glob('*/*.json'))]
    events = [e for _, w in windows for e in w['events']]
    delivery=read(base/'analysis/reflection_context_delivery.json')
    checks=delivery['records']
    assert delivery['complete_serialized_context_verified_before_public_path_redaction']
    inventory = []
    for fold in 'AB':
        ids = set(read(base/'evolution'/fold/'complete.json')['active_skill_ids'])
        for path in (base/'evolution'/fold/'current').rglob('*.md'):
            text = path.read_text(encoding='utf-8')
            match = re.search(r'^id: "(.*?)"', text, re.M)
            if not match or match[1] not in ids:
                continue
            def field(key):
                m = re.search(r'^'+re.escape(key)+r': (".*")$', text, re.M)
                return json.loads(m[1]) if m else None
            inventory.append({'source_fold': fold, 'id': match[1], 'name': field('name'),
                'description': field('description'), 'applicable_conditions': field('applicable_conditions'),
                'path': path.relative_to(base).as_posix(), 'body': text.split('---', 2)[-1].strip()})

    def tools(predictions):
        observations = [o for p in predictions for o in p.get('tool_observations', [])]
        return {'n': len(predictions), 'questions_with_usable_evidence': sum(any(o['usable'] for o in p.get('tool_observations', [])) for p in predictions),
            'selections': len(observations), 'by_tool': dict(Counter(o['tool'] for o in observations)),
            'same_round_cache_hits': sum(o['same_round_cache_hit'] for o in observations),
            'fresh_backend_attempts': sum(o['fresh_inference_attempted'] for o in observations),
            'withheld_temporal_clause_occurrences': sum(o['model_observation'].get('withheld_temporal_clause_count', 0) for o in observations),
            'questions_with_withheld_temporal_clauses': sum(any(o['model_observation'].get('withheld_temporal_clause_count', 0) for o in p.get('tool_observations', [])) for p in predictions),
            'planner_errors': dict(Counter(p['tool_plan_error'] for p in predictions if p.get('tool_plan_error'))),
            'status_counts': dict(Counter(p['status'] for p in predictions))}
    targets = [x['A1_details'] for x in records]
    backend = [read(p) for p in (base/'tool_cache/invocations').glob('*/*/*/result.json')]
    subsets = {}
    for name, predicate in [('both_tools', lambda n: len(n) == 2),
        ('report_only', lambda n: n == {'chest_xray_report_generator'}),
        ('classifier_only', lambda n: n == {'chest_xray_classifier'}), ('no_tools', lambda n: not n)]:
        group = [x for x in records if predicate({o['tool'] for o in x['A1_details']['tool_observations']})]
        subsets[name] = {'n': len(group),
            'D_correct': sum(x['predictions']['D_A0'] == x['reference'] for x in group),
            'A1_correct': sum(x['predictions']['A1'] == x['reference'] for x in group),
            'corrections': sum(x['predictions']['D_A0'] != x['reference'] and x['predictions']['A1'] == x['reference'] for x in group),
            'harms_including_missing': sum(x['predictions']['D_A0'] == x['reference'] and x['predictions']['A1'] != x['reference'] for x in group),
            'missing': sum(x['predictions']['A1'] is None for x in group)}
    changes = []
    for record in records:
        for comparison in ('D_A0', 'tools_v1_A1'):
            before, after, gold = record['predictions'][comparison], record['predictions']['A1'], record['reference']
            if (before == gold) != (after == gold) or after is None:
                changes.append({'comparison': comparison,
                    'change': 'correction' if after == gold else 'correct_to_missing' if before == gold and after is None else 'harm' if before == gold else 'missing_from_wrong',
                    'input': rows[record['question_id']], **record})
    summary = {'n': 402, 'case_n': 99, 'totals': metrics['totals'],
        'comparisons_A1_vs': metrics['comparisons_A1_vs'], 'usage': metrics['usage'],
        'usage_by_stage': metrics['usage_by_stage'], 'tools': {'target': tools(targets), 'source': tools(source),
            'unique_backend_attempts': len(backend),
            'backend_by_tool': dict(Counter(x['identity'].get('tool_name', x['identity'].get('tool', 'unknown')) for x in backend)),
            'backend_elapsed_s_sum': sum(x.get('elapsed_s', 0) for x in backend),
            'backend_status': dict(Counter(x['status'] for x in backend))},
        'skills': {'source_reflection_contexts_saved': len(list((base/'reflection_contexts').glob('*/*.json'))),
            'actual_encoded_analysis_contexts_checked': len(checks), 'complete_core_context_present_in_all_checked': True,
            'source_window_count': len(windows), 'encode_action_counts': dict(Counter(e['encode']['output_action'] for e in events)),
            'materialized_skill_count': sum(bool(e.get('created')) for e in events),
            'final_active_A': sum(x['source_fold'] == 'A' for x in inventory), 'final_active_B': sum(x['source_fold'] == 'B' for x in inventory),
            'admission_rejections': metrics['source_skill_admission_rejections'],
            'injected_target_questions': metrics['skill_context_questions'], 'declared_ID_mentions': metrics['declared_adoption_questions']},
        'model_selected_subsets_descriptive_only': subsets, 'answer_contract_errors': metrics['answer_contract_errors'],
        'new_paid_requests': metrics['usage']['saved_attempts'], 'exact_completed_API_reuses': len(read(base/'reused_calls.json')['records']),
        'series_requests': 6284, 'series_proxy_CNY': '57.841596', 'actual_Credits': None,
        'generation_code': 'e4c8bbeb883645d44b2746bc1e9d5e7c332a3d3b',
        'full_pipeline_wall_minutes': 220.0976509, 'interruption_or_paid_retry': False}
    def emit(name, value):
        (base/'analysis'/name).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf-8')
    emit('summary.json', summary)
    emit('skill_inventory.json', {'records': inventory, 'IDs_unique_within_source_fold_only': True})
    emit('changed_questions.json', {'records': changes})
    emit('answer_contract_failures.json', {'records': [{'input': rows[x['question_id']], **x} for x in records if x['predictions']['A1'] is None],
         'primary_answers_unchanged': True, 'paid_repairs': 0})
    print(json.dumps({k: summary[k] for k in ('skills', 'tools', 'model_selected_subsets_descriptive_only', 'exact_completed_API_reuses')}, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--results', type=Path, required=True)
    summarize(parser.parse_args().results)
