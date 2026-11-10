"""Export completed V9 outcomes through explicit publication field allowlists.

Input prompts, images, tool result prose, source labels, model messages and private
paths are never copied into public outputs. Run only after generation has finished.
"""
from __future__ import annotations

import argparse
from collections import Counter
import copy
import json
from pathlib import Path
import re

GROUPS = ('D', 'DK', 'DKB', 'DKC')
ACCOUNTING = ('model_calls', 'tool_calls', 'input_tokens', 'output_tokens', 'total_tokens',
              'logical_cost_cny', 'incremental_cost_cny', 'provider_actual_cost_cny',
              'cost_basis', 'usage_complete', 'issues')


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def rows(path):
    return [json.loads(x) for x in Path(path).read_text(encoding='utf-8-sig').splitlines() if x.strip()]


def pick(obj, keys):
    return {key: copy.deepcopy(obj[key]) for key in keys if key in obj}


def save(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def private_file(path, root):
    path = Path(path).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError('private artifact must be inside the selected run')
    return path


def error_code(value):
    if not value:
        return None
    if re.fullmatch(r'[A-Za-z_]+: [a-z_]+', value):
        return value
    return value.split(':', 1)[0]


def message_inventory(messages):
    images, texts = 0, 0
    for msg in messages:
        content = msg.get('data', {}).get('content')
        if isinstance(content, list):
            images += sum(isinstance(p, dict) and p.get('type') == 'image_url' for p in content)
            texts += sum(isinstance(p, dict) and p.get('type') == 'text' for p in content)
        elif isinstance(content, str):
            texts += 1
    return {'message_count': len(messages), 'message_types': dict(Counter(m.get('type') for m in messages)),
            'image_payload_count': images, 'text_part_count': texts}


def observation_inventory(observations):
    return [dict(pick(o, ('evidence_ref', 'tool_name', 'kind', 'phase', 'elapsed_ms', 'is_new_usable')),
                 argument_fields=sorted((o.get('arguments') or {}).keys()),
                 derived_image_ids=[a.get('image_id') for a in o.get('artifacts', [])]) for o in observations]


def retrieval_inventory(value):
    k, e = value.get('k_audit', {}), value.get('e_audit', {})
    hits = []
    for item in k.get('hits', []):
        hit = pick(item, ('rank', 'knowledge_id', 'source_id', 'source_pages', 'score_components',
                          'why_eligible', 'scope_cautions'))
        hit['condition_status'] = pick(item.get('condition_check', {}),
            ('structured_conditions_satisfied', 'recommendation_applicable', 'applicability_status'))
        hits.append(hit)
    return {'k': dict(pick(k, ('mode', 'abstained', 'abstention_reasons', 'rendered_ids')),
                      hits=hits, rejected=[pick(x, ('knowledge_id', 'reasons')) for x in k.get('rejected', [])]),
            'e': dict(pick(e, ('representation', 'index_text', 'rendered_ids', 'abstained')),
                      ranked=[pick(x, ('id', 'score', 'source_ids', 'required_tools')) for x in e.get('ranked', [])],
                      rejected=[pick(x, ('id', 'score', 'reasons')) for x in e.get('rejected', [])])}


def build(run, labels_path, output):
    run, output = Path(run).resolve(), Path(output)
    selection = read(run/'selection.json')
    p0, candidates = rows(run/'p0_results.jsonl'), rows(run/'candidate_results.jsonl')
    qids = {r['question_id'] for r in selection['rows']}
    if (read(run/'status.json')['status'] != 'generation_complete' or len(p0) != len(qids)
            or len(candidates) != len(qids)*4
            or {(r['question_id'], r['group']) for r in candidates} != {(q,g) for q in qids for g in GROUPS}):
        raise ValueError('publication requires complete unique terminals')
    # The isolated labels are opened only after checking completion. Letters are not exported.
    labels = {r['question_id']: r['answer'] for r in rows(labels_path) if r['question_id'] in qids}
    if set(labels) != qids:
        raise ValueError('selected labels are incomplete')
    output.mkdir(parents=True, exist_ok=True)
    cfg = read(run/'effective_config.json')
    project_root = cfg['root']
    cfg['root'] = '${PROJECT_ROOT}'
    cfg['publication_note'] = 'Only the absolute project-root path is substituted; model/branch settings are actual recorded values.'
    save(output/'effective_config.json', cfg)
    save(output/'selection.json', dict(pick(selection, ('planned_n', 'selection_seed', 'per_group', 'method')),
        rows=[pick(r, ('question_id', 'official_group')) for r in selection['rows']]))
    public_p0, evidence, branches, retrievals = [], [], [], []
    for r in p0:
        item = pick(r, ('question_id', 'initial', 'status', 'timing'))
        item['initial_correct'] = r['initial'] == labels[r['question_id']]
        item['accounting'] = pick(r.get('accounting', {}), ACCOUNTING)
        item['execution'] = pick(r.get('report', {}), ('actual_model_calls', 'actual_tool_attempts',
            'validated_tool_returns', 'failed_tool_returns', 'repeated_tool_calls', 'issue_tags',
            'available_tool_names', 'tool_counts', 'selected_tool_names', 'final_finish_reason', 'usage_complete'))
        public_p0.append(item)
        checkpoint = read(private_file(r['checkpoint'], run))
        evidence.append({'question_id': r['question_id'], 'group': 'P0',
            'checkpoint_saved': True, 'system_prompt_saved': bool(checkpoint.get('system_prompt')),
            'tool_schema_names': sorted(checkpoint.get('tool_schemas', {})),
            'messages': message_inventory(checkpoint.get('messages', [])),
            'tool_returns': observation_inventory(checkpoint.get('raw_observations', []))})
    for r in candidates:
        item = pick(r, ('question_id', 'group', 'initial', 'candidate', 'final', 'status', 'fallback',
                       'k_ids', 'e_ids', 'memory_tokens', 'timing', 'candidate_timing', 'gate_timing',
                       'original_observation_refs'))
        qid = r['question_id']
        item.update(initial_correct=r['initial']==labels[qid],
                    candidate_correct=(r['candidate']==labels[qid] if r['candidate'] is not None else None),
                    final_correct=r['final']==labels[qid],
                    candidate_error=error_code(r.get('candidate_error')), gate_error=error_code(r.get('gate_error')))
        item['gate'] = pick(r.get('gate', {}), ('decision', 'evidence_refs'))
        item['gate']['unmet_requirement_count'] = len(r.get('gate', {}).get('unmet_requirements', []))
        for field in ('accounting', 'candidate_accounting', 'gate_accounting'):
            if field in r:
                item[field] = pick(r[field], ACCOUNTING)
        item['new_observations'] = observation_inventory(r.get('new_observations', []))
        branches.append(item)
        if not r.get('evidence_package'):
            continue
        path = private_file(r['evidence_package'], run)
        entry = {'question_id': qid, 'group': r['group'], 'messages_saved': path.exists(),
                 'candidate_messages': message_inventory(read(path)) if path.exists() else None,
                 'tool_returns': observation_inventory(r.get('new_observations', []))}
        gate = path.parent/'gate_messages.json'
        entry['gate_messages'] = message_inventory(read(gate)) if gate.exists() else None
        context = path.parent/'context.json'
        if context.exists():
            entry['tool_counts'] = read(context).get('tool_counts', {})
        attempts = path.parent/'tool_attempts.jsonl'
        entry['tool_attempts'] = [dict(pick(x, ('name', 'status', 'requested_utc')),
            argument_fields=sorted(x.get('args', {}))) for x in rows(attempts)] if attempts.exists() else []
        evidence.append(entry)
        retrieval = path.parent/'retrieval.json'
        retrievals.append({'question_id': qid, 'group': r['group'], 'retrieval_reached': retrieval.exists(),
            'audit': retrieval_inventory(read(retrieval)) if retrieval.exists() else None})
    save(output/'p0_outcomes.json', public_p0)
    save(output/'branch_outcomes.json', branches)
    save(output/'evidence_manifest.json', evidence)
    save(output/'retrieval_audit.json', retrievals)
    metrics = read(run/'paired_metrics.json')
    metrics.pop('case_events', None)  # Original includes clinical prose and isolated reference letters.
    metrics['publication_note'] = 'Case-event prose and reference letters excluded; see branch_outcomes for evaluated derived outcomes.'
    save(output/'paired_metrics.json', metrics)
    (output/'paired_metrics.md').write_text((run/'paired_metrics.md').read_text(encoding='utf-8'), encoding='utf-8')
    errors = Counter(r['candidate_error'] for r in branches if r['candidate_error'])
    summary = {'schema_version': 1, 'status': 'completed', 'planned_n': len(qids),
        'p0_correct': sum(x['initial_correct'] for x in public_p0),
        'final_correct': {g: sum(x['final_correct'] for x in branches if x['group']==g) for g in GROUPS},
        'candidate_errors': dict(errors),
        'uncertain_n': sum(x.get('fallback')=='candidate_uncertain' for x in branches),
        'valid_candidate_n': sum(x['candidate'] is not None for x in branches),
        'changed_candidate_n': sum(x['candidate'] is not None and x['candidate']!=x['initial'] for x in branches),
        'corrective_candidate_n': sum(x['candidate_correct'] is True and not x['initial_correct'] for x in branches),
        'public_fields': ['benchmark_question_id', 'task_group', 'predicted_option_letters', 'derived_correctness',
            'injection_ids', 'retrieval_scores_and_rejection_codes', 'tool_names_argument_field_names_and_counts',
            'evidence_reference_ids_and_message_inventory', 'timestamps_elapsed_usage_accounting'],
        'excluded_fields': ['credentials', 'original_questions_and_options', 'input_images_and_image_paths',
            'raw_tool_results', 'actual_case_prompts_and_model_responses', 'reference_answer_letters',
            'full_guideline_passages', 'model_weights', 'absolute_private_artifact_paths'],
        'base_commit': '2d3e8a0c79bd05cdf70c00685c506bae257ec2f0',
        'inference_code_commit': '8d89a9f',
        'billing_note': 'Existing assumed-rate ledger values are not provider invoices.'}
    save(output/'manifest.json', summary)
    # Guard against accidental copying of private message/data fields or machine paths.
    forbidden = {'question', 'content', 'prompt', 'query_text', 'query_roles', 'parent_passage',
                 'knowledge_card', 'result', 'answer', 'reference', 'image_url', 'image_path', 'image_paths'}
    def inspect(value):
        if isinstance(value, dict):
            if forbidden & value.keys():
                raise ValueError('raw input/output field found in public export')
            for v in value.values(): inspect(v)
        elif isinstance(value, list):
            for v in value: inspect(v)
        elif isinstance(value, str) and (project_root in value or 'data:image/' in value or 'base64,' in value):
            raise ValueError('private payload found in public export')
    for path in output.glob('*.json'):
        inspect(read(path))
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', required=True, type=Path)
    parser.add_argument('--labels', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    result = build(args.run, args.labels, args.out)
    print(json.dumps({'exported': str(args.out), 'planned_n': result['planned_n'],
                      'final_correct': result['final_correct']}))
