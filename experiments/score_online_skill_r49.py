"""Score a completed R49 stream with the common explicit-answer/author metrics.

All current and historical raw answers are adapted before any feedback or
reference annotation is opened. JSON conformance is reported separately.
Semantic identities and receipts are checked; no file/pixel/hash gate is used.
"""
import argparse
import copy
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal
import json
import math
from pathlib import Path
import random

import numpy as np

from analyze_cxr_author_alignment import predictions as historical_predictions, terminal
from score_cxr_author_alignment import adapt, outcomes
from score_cxr_vqa_extension import bootstrap, cluster_keys
from run_online_skill_r49 import ARM
from online_memory_r49 import read, save_once, context, memory_entry
from skill_services_r49 import conditioning
from skill_lifecycle_r49 import initial
from cxr_online_primitives_r49 import tool_failure_reason

EXPECTED = {'chexbench': (618, 'M43', 466), 'slake': (114, 'M43', 108),
            'vqarad': (116, 'M42', 100)}
META_SCHEMA_INSTRUCTION = '''

ONE-CASE SCHEMA CLARIFICATION; no new source evidence is supplied.
The preceding mutation used patch_section="c", which names the whole content container and is not a permitted single-field patch.
For PATCH, retain exactly this patch_target_id: {target_json}.
patch_section must be exactly one of: name, description, applicable_conditions, required_tools, risk_level, core_action.
Return the original PATCH schema for one such field; do not replace the whole content container or change branch, task_category or tool_name.
Use only the same original source payload. Do not add clinical facts or consult another case or future feedback.
If the source does not support a valid single-field patch, explicitly return {{"operation":"NONE"}}.
Return one JSON object with operation PATCH or NONE; do not produce CREATE, another target, or a patch to a different scope.
'''
META_SCHEMA_2_INSTRUCTION = META_SCHEMA_INSTRUCTION.replace('patch_section="c"', 'patch_section="content"')
MUTATION_FIELDS_CLARIFICATION = '''

EXPLICIT MUTATION FIELD CONTRACT; no new clinical information or source evidence.
For operation PATCH, patch_section must be exactly one of: name, description, applicable_conditions, required_tools, risk_level, core_action.
The names "c" and "content" denote the whole content container and are not permitted patch_section values.
A PATCH changes one such field of an eligible target already present in the supplied window snapshot. Do not change branch, task_category or tool_name.
Keep the original CREATE, PATCH and NONE meanings and the original source-evidence requirements. This clarification introduces no new clinical rule or permission to infer facts.
'''
PHRASE_POLICY = 'maira_unclosed_tag_eos_guard_v1'
PHRASE_TOOL = 'xray_phrase_grounding'
PHRASE_QID = 'chexbench_slake_0053'
PHRASE_OLD_KEY = 'b615fd34f038d096aaa2681413f80d45cd25acf9de235ec65ff029dbec90be56'
PHRASE_REVISION = 'MedRAX-dae30e2f136ef0b2a40885a4c335386e9ffad052'
PHRASE_MODEL_REVISION = '795a2b1cd4a310624b4e3d14b5a23e41fd273deb'
PHRASE_TOKENS = {'obj_start': 32000, 'obj_end': 32001, 'box_start': 32202, 'box_end': 32203, 'eos': 2}
ADOPTION_SOURCES = ('chexbench_slake_0081', 'chexbench_slake_0082')
ADOPTION_SKILL = 's_e1a0642fabefb0c7'
ANALYSIS_UNIQUE_CLARIFICATION = '''

EXPLICIT ATTRIBUTION UNIQUENESS CONTRACT; no new clinical information or source evidence.
Report each injected skill_id at most once in skill_adoption. A single entry must represent that skill's adoption in this trajectory using the one best supported actual zero-based step_index and its concise evidence; do not create separate entries for multiple steps.
Keep the original ADOPTED_POSITIVE, ADOPTED_NEGATIVE and IGNORED meanings, original source-evidence requirements and all other output fields unchanged. Never invent an injected ID, step, tool execution or patient fact. This is a uniqueness/schema clarification, not a new clinical guideline.
'''
ADOPTION_SELECTION_INSTRUCTION = '''
BOUNDED ATTRIBUTION REPRESENTATIVE SELECTION ONLY; no new source information.
The original response repeated one injected skill_id with two different step/evidence entries. Both original entries have the same ADOPTED_POSITIVE status.
Use only the original completed trajectory, released feedback, original image and the two original entries supplied below. Select the original entry best supported by its actual recorded step as the representative; this does not add a second credit.
Return exactly one JSON object {"selected_duplicate_index":0} or {"selected_duplicate_index":1}. The index refers to the two-entry duplicate_entries array, not the trajectory step number.
Do not rewrite, add or infer any status, step, evidence, clinical content or other analysis field. Do not return a new adoption list. The selected original entry and all other unique entries will be copied verbatim by the caller.
'''


def rows(path):
    return [json.loads(line) for line in Path(path).read_text(encoding='utf-8').splitlines() if line.strip()]


def utc(value):
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('timestamp_requires_timezone')
    return parsed.astimezone(timezone.utc)


def members(folder, ids, label):
    found = {path.stem: path for path in folder.glob('*.json')}
    if set(found) != ids:
        raise ValueError('incomplete_' + label)
    return found


def completed_gate(data, run, expected_questions):
    """This phase opens neither feedback nor learning snapshots nor labels."""
    inputs = rows(Path(data)/'inputs.jsonl'); ids = [row['question_id'] for row in inputs]
    if len(ids) != expected_questions or len(set(ids)) != len(ids):
        raise ValueError('full_fixed_cohort_required')
    if (run/'generation.exitcode').read_text(encoding='utf-8').strip() != '0':
        raise ValueError('raw_generation_exit_zero_required')
    manifest = read(run/'manifest.json')
    if manifest.get('inputs') != inputs or [item['question_id'] for item in manifest['order']] != ids:
        raise ValueError('manifest_semantic_input_order_changed')
    # Do not open complete.json here: its final_repo is a learned label-bearing
    # artifact. Its existence is sufficient until reference-free adaptation ends.
    if not (run/'complete.json').is_file():
        raise ValueError('completion_record_required')
    paths = {name: members(run/name/(ARM if name == 'predictions' else ''), set(ids), name)
             for name in ('predictions', 'contexts', 'steps', 'prediction_events', 'feedback')}
    agent = run/'services/calls/R49-AGENT'
    if {p.name for p in agent.iterdir() if p.is_dir()} != set(ids):
        raise ValueError('all_questions_require_new_agent_requests')
    return inputs, manifest, paths


def closed_calls(folder):
    calls = sorted((p for p in folder.iterdir() if p.is_dir()), key=lambda p: int(p.name)) if folder.exists() else []
    if [int(p.name) for p in calls] != list(range(1, len(calls)+1)):
        raise ValueError('noncontiguous_calls:' + str(folder))
    values = []
    for call in calls:
        if any(not (call/name).is_file() for name in ('request.json', 'started.json', 'response.json', 'result.json')):
            raise ValueError('unclosed_request:' + str(call))
        started, receipt = read(call/'started.json'), read(call/'result.json')
        if (receipt.get('error') or receipt.get('response_received') is not True
                or started.get('request_id') != receipt.get('request_id')
                or utc(started['utc']) > utc(receipt['utc'])):
            raise ValueError('unhealthy_request_receipt:' + str(call))
        values.append((call, started, receipt))
    return values


def response_text(call):
    message = read(call/'response.json')['choices'][0]['message']
    value = message.get('content')
    if isinstance(value, list):
        value = '\n'.join(item.get('text', '') for item in value
                          if isinstance(item, dict) and item.get('type') == 'text')
    return value if isinstance(value, str) and not (message.get('tool_calls') or message.get('function_call')) else None


def adapt_current(inputs, run, paths):
    adapted, predictions, receipts = {}, {}, {}
    for row in inputs:
        qid = row['question_id']; prediction = read(paths['predictions'][qid])
        if prediction.get('question_id') != qid or prediction.get('arm') != ARM:
            raise ValueError('prediction_identity:' + qid)
        if prediction.get('technical_failure') or any(word in prediction.get('status', '') for word in ('tool_unhealthy', 'transport_unknown')):
            raise ValueError('technical_failure_is_not_complete_stream:' + qid)
        calls = closed_calls(run/'services/calls/R49-AGENT'/qid)
        if not calls or len(calls) != prediction['main_calls']:
            raise ValueError('new_agent_actual_call_count:' + qid)
        raw = response_text(calls[-1][0])
        source = {'raw': raw, 'call_path': str(calls[-1][0]), 'ordinal': calls[-1][0].name,
                  'reuse_chain': [], 'technical_stop': False,
                  'evidence_status': 'received_terminal_text' if raw else 'nonfinal_or_unavailable'}
        adapted[qid] = adapt(row, prediction, source)
        predictions[qid], receipts[qid] = prediction, calls
    return adapted, predictions, receipts


def adapt_historical(inputs, dataset, baseline_name):
    old = historical_predictions(dataset, baseline_name)
    if set(old) != {row['question_id'] for row in inputs}:
        raise ValueError('fixed_whole_baseline_membership')
    return {row['question_id']: adapt(row, old[row['question_id']], terminal(dataset, baseline_name, row['question_id']))
            for row in inputs}


def adapt_r47(inputs, baseline, frozen_path, run):
    """Secondary GT historical comparator; read raw archives, never cached flags."""
    if (frozen_path is None) != (run is None):
        raise ValueError('r47_requires_both_frozen_and_run')
    if run is None:
        return None
    from score_cxr_image_memory_gt_r47 import completed_gate as r47_gate, request_evidence
    frozen = read(frozen_path)
    original, _, order, _, paths, _, _ = r47_gate(frozen, run)
    if original != inputs:
        raise ValueError('r47_fixed_input_order_changed')
    result = {}
    for row in inputs:
        qid = row['question_id']; prediction = read(paths[qid])
        if not order[qid]['previous_ids']:
            if any(prediction.get(k) != frozen['baseline'][qid].get(k) for k in ('answer', 'reason', 'status')):
                raise ValueError('r47_reused_whole_baseline_changed')
            result[qid] = dict(baseline[qid])
        else:
            source, _ = request_evidence(run, qid, prediction)
            result[qid] = adapt(row, prediction, source)
    return result


def _registered_meta_schema_case(run, number):
    """Two explicitly named cases only, not a configurable repair mechanism."""
    if number == 1:
        qid, section, window_index, schema, recovery, instruction_template = (
            'chexbench_slake_0004', 'c', 3, 'r49_registered_meta_schema_repair_v1',
            'meta_schema_1', META_SCHEMA_INSTRUCTION)
    elif number == 2:
        qid, section, window_index, schema, recovery, instruction_template = (
            'chexbench_slake_0013', 'content', 4, 'r49_registered_meta_schema_repair_v2',
            'mutation_fields_2', META_SCHEMA_2_INSTRUCTION)
    else:
        raise ValueError('only_two_fixed_META_schema_cases_are_supported')
    event = 'mutation_'+qid; repaired_event = event+'_schema_'+str(number)
    registry_path = run/'failure_events'/('meta_schema_'+str(number)+'_registration.json')
    folder = run/'services/calls/R49-META'
    if not registry_path.is_file():
        return None
    registration = read(registry_path)
    expected = {'schema': schema, 'recovery_id': recovery,
                'dataset': 'chexbench', 'arm': ARM, 'source_question_id': qid,
                'source_event': event, 'repair_event': repaired_event, 'window_index': window_index,
                'original_call_relative': 'services/calls/R49-META/'+event+'/1',
                'repair_call_relative': 'services/calls/R49-META/'+repaired_event+'/1',
                'same_original_payload': True, 'new_meta_calls': 1, 'extra_agent_calls': 0,
                'extra_embedding_calls': 0, 'extra_tool_calls': 0, 'automatic_invalid_to_none': False,
                'new_clinical_information': False, 'status': 'valid_meta_schema_repair_registered'}
    if any(registration.get(k) != value for k, value in expected.items()):
        raise ValueError('only_the_one_exact_meta_schema_repair_is_supported')
    old_calls, new_calls = closed_calls(folder/event), closed_calls(folder/repaired_event)
    if len(old_calls) != 1 or len(new_calls) != 1:
        raise ValueError('one_original_and_one_fresh_meta_call_required')
    from run_cxr_action_r41 import parse
    from skill_prompts_r49 import MUTATE
    from skill_lifecycle_r49 import validate
    original, repaired = parse(response_text(old_calls[0][0])), parse(response_text(new_calls[0][0]))
    target = registration.get('target_skill_id')
    control = lambda value: {k: value.get(k) for k in ('operation', 'patch_section', 'patch_target_id')}
    if (not isinstance(target, str) or not target
            or control(original) != {'operation': 'PATCH', 'patch_section': section, 'patch_target_id': target}
            or registration.get('original_control') != control(original)
            or registration.get('repair_control') != control(repaired)):
        raise ValueError('actual_old_or_new_meta_control_does_not_match_registration')
    old_request, new_request = read(old_calls[0][0]/'request.json'), read(new_calls[0][0]/'request.json')
    messages = old_request['messages']
    if (len(messages) != 2 or messages[0] != {'role': 'system', 'content': MUTATE}
            or messages[1].get('role') != 'user' or not isinstance(messages[1].get('content'), list)
            or len(messages[1]['content']) != 1 or messages[1]['content'][0].get('type') != 'text'):
        raise ValueError('original_mutation_must_have_only_its_existing_source_payload')
    instruction = instruction_template.format(target_json=json.dumps(target, ensure_ascii=False))
    expected_messages = copy.deepcopy(messages); expected_messages[0]['content'] += instruction
    if (registration.get('repair_instruction') != instruction or new_request.get('messages') != expected_messages
            or {k: v for k, v in old_request.items() if k != 'messages'} != {k: v for k, v in new_request.items() if k != 'messages'}
            or not isinstance(old_calls[0][2].get('model_returned'), str) or not old_calls[0][2]['model_returned']
            or old_calls[0][2].get('model_returned') != new_calls[0][2].get('model_returned')):
        raise ValueError('meta_repair_changed_source_payload_model_or_added_non_schema_information')
    if utc(new_calls[0][1]['utc']) < utc(old_calls[0][2]['utc']):
        raise ValueError('fresh_meta_repair_precedes_its_original_response')
    payload = json.loads(messages[1]['content'][0]['text'])
    window = run/'windows'/f'{window_index:04d}'; snapshot = read(window/'read_snapshot.json')
    trajectory = read(window/'trajectories'/(qid+'.json'))
    if (payload.get('snapshot') != snapshot['skills'] or target not in snapshot['skills']
            or payload.get('trajectory') != trajectory or trajectory.get('id') != qid):
        raise ValueError('meta_repair_source_or_window_snapshot_changed')
    if repaired.get('operation') == 'PATCH':
        if repaired.get('patch_target_id') != target or repaired.get('patch_section') not in (
                'name', 'description', 'applicable_conditions', 'required_tools', 'risk_level', 'core_action'):
            raise ValueError('fresh_meta_patch_changed_target_or_strict_allowed_section')
        content = copy.deepcopy(snapshot['skills'][target]['c'])
        content[repaired['patch_section']] = repaired['patch_content']
        validate(content, payload['tools'])
    elif repaired.get('operation') != 'NONE':
        raise ValueError('fresh_meta_reply_is_neither_valid_PATCH_nor_actual_model_NONE')
    return {'registration': registration, 'original_call': old_calls[0], 'repair_call': new_calls[0],
            'repair_draft': repaired}


def registered_meta_schema_repairs(run):
    proofs = {'meta_schema_1': _registered_meta_schema_case(run, 1),
              'meta_schema_2': _registered_meta_schema_case(run, 2)}
    known_files = {'meta_schema_1_registration.json', 'meta_schema_2_registration.json'}
    if {path.name for path in (run/'failure_events').glob('meta_schema_*_registration.json')}-known_files:
        raise ValueError('unrecognized_meta_schema_repair_registration')
    allowed = {proof['registration']['repair_event'] for proof in proofs.values() if proof is not None}
    present = {path.name for path in (run/'services/calls/R49-META').glob('*_schema_*') if path.is_dir()}
    if present != allowed:
        raise ValueError('unrecognized_meta_schema_repair_namespace')
    return proofs


def registered_meta_schema_repair(run):
    return registered_meta_schema_repairs(run)['meta_schema_1']


def registered_meta_schema_repair_2(run):
    return registered_meta_schema_repairs(run)['meta_schema_2']


def validate_adoption_entries(entries, trajectory, snapshot):
    """The original assess eligibility/evidence rules, with no duplicate credit."""
    if not isinstance(entries, list):
        raise ValueError('adoption_list_required')
    attributed = set()
    for item in entries:
        if not isinstance(item, dict):
            raise ValueError('adoption_object_required')
        sid, status = item.get('skill_id'), item.get('status')
        if sid in attributed:
            raise ValueError('duplicate_skill_adoption')
        attributed.add(sid)
        if sid not in trajectory['injected'] or sid not in snapshot['skills']:
            raise ValueError('adoption_not_injected')
        if status not in ('ADOPTED_POSITIVE', 'ADOPTED_NEGATIVE', 'IGNORED'):
            raise ValueError('adoption_status')
        if status != 'IGNORED' and (type(item.get('step_index')) is not int
                or not 0 <= item['step_index'] < len(trajectory['steps']) or not item.get('evidence')):
            raise ValueError('adoption_evidence')
    return entries


def registered_adoption_repair(run):
    """Two model choices of existing representatives, solely at assess boundary."""
    from run_cxr_action_r41 import parse
    from skill_prompts_r49 import ANALYZE
    from skill_services_r49 import Services
    path = run/'failure_events/adoption_1_registration.json'
    if set((run/'failure_events').glob('adoption_*_registration.json'))-{path}:
        raise ValueError('unrecognized_adoption_repair_registration')
    folders = run/'services/calls/R49-META'
    present = {folder.name for folder in folders.glob('*_adoption_*') if folder.is_dir()}
    if not path.is_file():
        if present:
            raise ValueError('unregistered_adoption_choice_namespace')
        return None
    value = read(path); manifest = read(run/'manifest.json')
    fixed = {'schema': 'r49_registered_assessment_adoption_repair_v1', 'recovery_id': 'adoption_1',
             'dataset': 'chexbench', 'arm': ARM, 'window_index': 6, 'activation_committed_questions': 210,
             'new_meta_requests': 2, 'assess_only': True, 'write_phase_analysis_unchanged': True,
             'other_analysis_fields_unchanged': True, 'automatic_retry': False,
             'status': 'two_assess_only_adoption_repairs_registered'}
    cases = value.get('repairs', [])
    if (manifest.get('dataset') != 'chexbench' or any(value.get(k) != v for k, v in fixed.items())
            or not isinstance(cases, list) or [case.get('source_question_id') for case in cases] != list(ADOPTION_SOURCES)):
        raise ValueError('only_two_fixed_assess_adoption_choices_supported')
    ordinals = {item['question_id']: index for index, item in enumerate(manifest['order'])}
    window = run/'windows/0006'; snapshot = read(window/'read_snapshot.json')
    credits = read(window/'events.json')['credit']; repairs = []
    for qid, case in zip(ADOPTION_SOURCES, cases):
        event = 'analysis_'+qid; repair_event = event+'_adoption_1'
        expected = {'source_event': event, 'repair_event': repair_event, 'source_question_id': qid,
                    'duplicate_skill_id': ADOPTION_SKILL,
                    'original_call_relative': 'services/calls/R49-META/'+event+'/1',
                    'repair_call_relative': 'services/calls/R49-META/'+repair_event+'/1',
                    'source_payload_unchanged': True, 'new_clinical_information': False}
        if any(case.get(k) != v for k, v in expected.items()) or ordinals.get(qid, -1)//30 != 6:
            raise ValueError('assess_repair_source_window_or_namespace_changed')
        old_calls, new_calls = closed_calls(folders/event), closed_calls(folders/repair_event)
        if len(old_calls) != 1 or len(new_calls) != 1:
            raise ValueError('one_closed_original_and_one_choice_call_per_known_analysis_required')
        original = parse(response_text(old_calls[0][0])); selected = parse(response_text(new_calls[0][0]))
        adoption = original.get('skill_adoption'); index = selected.get('selected_duplicate_index')
        if (set(selected) != {'selected_duplicate_index'} or type(index) is not int or index not in (0, 1)
                or not isinstance(adoption, list) or len(adoption) != 3):
            raise ValueError('fresh_reply_must_only_select_an_original_duplicate_index')
        positions = [i for i, item in enumerate(adoption) if item.get('skill_id') == ADOPTION_SKILL]
        entries = [adoption[i] for i in positions]
        if (len(entries) != 2 or entries[0] == entries[1]
                or any(item.get('status') != 'ADOPTED_POSITIVE' for item in entries)
                or {item.get('step_index') for item in entries} != {0, 1}):
            raise ValueError('known_different_evidence_positive_representatives_changed')
        effective = [item for i, item in enumerate(adoption) if item.get('skill_id') != ADOPTION_SKILL or i == positions[index]]
        if (case.get('original_adoption') != adoption or case.get('selected_duplicate_index') != index
                or case.get('effective_adoption') != effective):
            raise ValueError('effective_adoption_must_exactly_copy_model_selected_original_and_other_unique_entries')
        trajectory = read(window/'trajectories'/(qid+'.json'))
        validate_adoption_entries(effective, trajectory, snapshot)
        old_request = read(old_calls[0][0]/'request.json'); new_request = read(new_calls[0][0]/'request.json')
        messages = old_request.get('messages', [])
        if (len(messages) != 2 or messages[0] != {'role': 'system', 'content': ANALYZE}
                or messages[1].get('role') != 'user' or not isinstance(messages[1].get('content'), list)
                or not messages[1]['content'] or messages[1]['content'][0].get('type') != 'text'):
            raise ValueError('original_analysis_source_request_changed')
        payload = json.loads(messages[1]['content'][0]['text'])
        instruction = ADOPTION_SELECTION_INSTRUCTION+json.dumps({'duplicate_skill_id': ADOPTION_SKILL,
                                                               'duplicate_entries': entries}, ensure_ascii=False)
        expected_messages = copy.deepcopy(messages)+[{'role': 'assistant', 'content': response_text(old_calls[0][0])},
                                                     {'role': 'user', 'content': instruction}]
        if (payload.get('trajectory') != trajectory or trajectory.get('id') != qid
                or case.get('selection_instruction') != instruction
                or Services.text_semantics(new_request.get('messages')) != Services.text_semantics(expected_messages)
                or {k: v for k, v in old_request.items() if k != 'messages'} != {k: v for k, v in new_request.items() if k != 'messages'}
                or not old_calls[0][2].get('model_returned') or old_calls[0][2].get('model_returned') != new_calls[0][2].get('model_returned')
                or utc(new_calls[0][1]['utc']) < utc(old_calls[0][2]['utc'])):
            raise ValueError('adoption_choice_changed_original_source_model_or_added_information')
        mutation = folders/('mutation_'+qid)/'1/request.json'
        if mutation.is_file():
            mutation_payload = json.loads(read(mutation)['messages'][1]['content'][0]['text'])
            if mutation_payload.get('analysis') != original:
                raise ValueError('write_phase_cached_mutation_analysis_was_changed')
        actual = [(item.get('skill'), item.get('status')) for item in credits if item.get('trajectory') == qid]
        expected_credits = [(item['skill_id'], item['status']) for item in effective if item['status'] != 'IGNORED']
        if Counter(actual) != Counter(expected_credits):
            raise ValueError('registered_adoption_credit_must_be_once_per_representative')
        repairs.append({'source_event': event, 'repair_event': repair_event, 'original_call': old_calls[0],
                        'repair_call': new_calls[0], 'effective_adoption': effective,
                        'selected_duplicate_index': index, 'original_adoption': adoption})
    if present != {item['repair_event'] for item in repairs}:
        raise ValueError('unknown_or_extra_adoption_repair_namespace')
    return {'registration': value, 'repairs': repairs}


def validate_analysis_unique_amendment(run, manifest=None):
    from skill_prompts_r49 import ANALYZE
    manifest = read(run/'manifest.json') if manifest is None else manifest
    path = run/'failure_events/analysis_unique_adoption_amendment.json'
    amendment = read(path) if path.is_file() else None; dataset = manifest.get('dataset')
    if amendment is not None:
        expected = {'schema': 'r49_analysis_unique_adoption_amendment_v1', 'recovery_id': 'adoption_1',
            'dataset': dataset, 'arm': ARM, 'activation_committed_questions': 210 if dataset == 'chexbench' else 0,
            'original_system': ANALYZE, 'clarification': ANALYSIS_UNIQUE_CLARIFICATION,
            'ordinary_event_rule': "system == original ANALYZE and event == 'analysis_' + payload['trajectory']['id']",
            'extra_ordinary_meta_calls': 0, 'automatic_future_repair': False, 'new_clinical_information': False, 'status': 'active'}
        protected = amendment.get('protected_original_events')
        if (dataset not in EXPECTED or any(amendment.get(k) != v for k, v in expected.items())
                or not isinstance(protected, list) or protected != sorted(set(protected))
                or dataset != 'chexbench' and protected):
            raise ValueError('only_fixed_analysis_uniqueness_prompt_boundary_supported')
        activation = utc(amendment['utc'])
    else:
        protected = []; activation = None
        if (run/'failure_events/adoption_1_registration.json').exists():
            raise ValueError('adoption_choice_requires_declared_analysis_prompt_boundary')
    repairs = {'analysis_'+qid+'_adoption_1' for qid in ADOPTION_SOURCES}
    observed = set(); original_count = clarified_count = 0
    indices = {item['question_id']: index for index, item in enumerate(manifest['order'])}
    size = manifest.get('defaults', {}).get('window', 30)
    for folder in sorted((run/'services/calls/R49-META').glob('analysis_*')):
        if not folder.is_dir() or folder.name in repairs:
            continue
        calls = closed_calls(folder)
        if len(calls) != 1:
            raise ValueError('one_closed_call_per_ordinary_analysis_required')
        messages = read(calls[0][0]/'request.json').get('messages', [])
        if (len(messages) != 2 or messages[0].get('role') != 'system' or messages[1].get('role') != 'user'
                or not isinstance(messages[1].get('content'), list) or not messages[1]['content']
                or messages[1]['content'][0].get('type') != 'text'):
            raise ValueError('ordinary_analysis_request_control_changed')
        payload = json.loads(messages[1]['content'][0]['text']); qid = payload.get('trajectory', {}).get('id')
        if folder.name != 'analysis_'+str(qid) or qid not in indices:
            raise ValueError('unknown_nonordinary_analysis_namespace')
        trajectory = read(run/'windows'/f'{indices[qid]//size:04d}'/'trajectories'/(qid+'.json'))
        if payload.get('trajectory') != trajectory:
            raise ValueError('ordinary_analysis_changed_saved_past_trajectory')
        system = messages[0]['content']
        if system == ANALYZE:
            original_count += 1; observed.add(folder.name)
            if amendment is not None and (folder.name not in protected or utc(calls[0][2]['utc']) > activation or indices[qid] >= 210):
                raise ValueError('new_or_unprotected_analysis_used_old_prompt')
        elif system == ANALYZE+ANALYSIS_UNIQUE_CLARIFICATION:
            clarified_count += 1
            if amendment is None or folder.name in protected or utc(calls[0][1]['utc']) < activation:
                raise ValueError('clarified_analysis_has_no_declared_activation')
        else:
            raise ValueError('unrecognized_ordinary_analysis_system_prompt')
    if amendment is not None and observed != set(protected):
        raise ValueError('protected_original_analysis_missing_or_reclassified')
    return {'active': amendment is not None, 'amendment': amendment,
            'ordinary_analysis_requests': original_count+clarified_count, 'original_system_requests': original_count,
            'clarified_system_requests': clarified_count, 'protected_original_events': protected, 'extra_ordinary_meta_calls': 0}


def validate_mutation_fields_amendment(run, manifest=None):
    """Prove the declared old/clarified boundary from actual ordinary requests."""
    from skill_prompts_r49 import MUTATE
    manifest = manifest or read(run/'manifest.json')
    amendment_path = run/'failure_events/mutation_fields_2_amendment.json'
    amendment = read(amendment_path) if amendment_path.is_file() else None
    dataset = manifest['dataset']
    if amendment is not None:
        expected = {'schema': 'r49_mutation_fields_amendment_v1', 'recovery_id': 'mutation_fields_2',
                    'dataset': dataset, 'arm': ARM, 'original_system': MUTATE,
                    'clarification': MUTATION_FIELDS_CLARIFICATION,
                    'allowed_sections': ['name', 'description', 'applicable_conditions', 'required_tools', 'risk_level', 'core_action'],
                    'ordinary_event_rule': "system == original MUTATE and event == 'mutation_' + payload['trajectory']['id']",
                    'extra_ordinary_meta_calls': 0, 'new_clinical_information': False, 'same_original_payload': True,
                    'cached_original_or_clarified_replay': True, 'automatic_future_repair': False, 'status': 'active',
                    'committed_questions_at_activation': 150 if dataset == 'chexbench' else 0}
        if any(amendment.get(k) != value for k, value in expected.items()):
            raise ValueError('only_the_declared_literal_mutation_fields_amendment_is_supported')
        protected = amendment.get('protected_original_events')
        if (not isinstance(protected, list) or protected != sorted(set(protected))
                or dataset != 'chexbench' and protected):
            raise ValueError('protected_old_mutation_boundary_changed')
        activated = utc(amendment['utc'])
    else:
        protected, activated = [], None
        if (run/'failure_events/meta_schema_2_registration.json').is_file():
            raise ValueError('second_META_repair_requires_the_declared_prompt_amendment')
    observed_old, original_count, clarified_count = set(), 0, 0
    ordinals = {item['question_id']: index for index, item in enumerate(manifest['order'])}
    window_size = manifest.get('defaults', {}).get('window', 30)
    repairs = {'mutation_chexbench_slake_0004_schema_1', 'mutation_chexbench_slake_0013_schema_2'}
    for folder in sorted((run/'services/calls/R49-META').glob('mutation_*')):
        if not folder.is_dir():
            continue
        calls = closed_calls(folder)
        if len(calls) != 1:
            raise ValueError('one_call_per_ordinary_mutation_namespace_required')
        request = read(calls[0][0]/'request.json'); messages = request['messages']
        if (len(messages) != 2 or messages[0].get('role') != 'system' or messages[1].get('role') != 'user'
                or not isinstance(messages[1].get('content'), list) or len(messages[1]['content']) != 1
                or messages[1]['content'][0].get('type') != 'text'):
            raise ValueError('mutation_request_contains_unrecognized_control_or_extra_evidence')
        payload = json.loads(messages[1]['content'][0]['text'])
        qid = payload.get('trajectory', {}).get('id')
        if folder.name != 'mutation_'+str(qid):
            if folder.name not in repairs:
                raise ValueError('unrecognized_nonordinary_mutation_namespace')
            continue
        if qid not in ordinals:
            raise ValueError('ordinary_mutation_source_outside_dataset')
        window = run/'windows'/f'{ordinals[qid]//window_size:04d}'
        if (payload.get('snapshot') != read(window/'read_snapshot.json')['skills']
                or payload.get('trajectory') != read(window/'trajectories'/(qid+'.json'))):
            raise ValueError('ordinary_mutation_payload_changed_from_its_saved_window_source')
        system = messages[0]['content']
        if system == MUTATE:
            original_count += 1; observed_old.add(folder.name)
            if amendment is not None and (folder.name not in protected or utc(calls[0][2]['utc']) > activated):
                raise ValueError('uncached_new_mutation_used_unamended_or_unprotected_prompt')
        elif system == MUTATE+MUTATION_FIELDS_CLARIFICATION:
            clarified_count += 1
            if amendment is None or folder.name in protected or utc(calls[0][1]['utc']) < activated:
                raise ValueError('clarified_mutation_prompt_has_no_valid_declared_boundary')
        else:
            raise ValueError('unrecognized_ordinary_mutation_system_prompt')
    if amendment is not None and observed_old != set(protected):
        raise ValueError('declared_original_mutation_request_missing_or_reclassified')
    return {'active': amendment is not None, 'amendment': amendment,
            'ordinary_mutation_requests': original_count+clarified_count,
            'original_system_requests': original_count, 'clarified_system_requests': clarified_count,
            'protected_original_events': protected, 'extra_ordinary_meta_calls': 0}


def registered_embedding_http_failure(run):
    """One SDK-attested HTTP400 history, never a blanket missing-response retry."""
    registry = run/'failure_events/embedding_arrearage_1_registration.json'
    other = set((run/'failure_events').glob('embedding_*_registration.json'))-set([registry])
    if other:
        raise ValueError('unrecognized_embedding_failure_registration')
    if not registry.is_file():
        return None
    value = read(registry)
    expected = {'schema': 'r49_registered_embedding_http_failure_v1', 'recovery_id': 'embedding_arrearage_1',
                'dataset': 'chexbench', 'arm': ARM, 'original_embedding_id': '000063',
                'retry_embedding_id': '000063_arrearage_1',
                'original_call_relative': 'services/embeddings/000063',
                'retry_call_relative': 'services/embeddings/000063_arrearage_1',
                'original_failure_archive_relative': 'failure_events/embedding_arrearage_1_original_failure.json',
                'same_original_request': True, 'new_production_embedding_requests': 1,
                'extra_agent_calls_for_repair': 0, 'extra_meta_calls_for_repair': 0, 'extra_tool_retries': 0,
                'no_encoding_or_text_change': True, 'no_automatic_retry': True,
                'status': 'healthy_embedding_retry_registered'}
    if any(value.get(k) != v for k, v in expected.items()):
        raise ValueError('only_one_exact_registered_embedding_HTTP_failure_is_supported')
    old_folder, new_folder = run/value['original_call_relative'], run/value['retry_call_relative']
    if (any(not (old_folder/name).is_file() for name in ('request.json', 'started.json', 'result.json'))
            or (old_folder/'response.json').exists()):
        raise ValueError('old_HTTP_failure_must_remain_closed_without_a_fabricated_response')
    old = {name: read(old_folder/(name+'.json')) for name in ('request', 'started', 'result')}
    if old != read(run/value['original_failure_archive_relative']):
        raise ValueError('original_failed_embedding_archive_changed')
    if (set(old['request']) != {'model', 'input'} or old['request']['model'] != 'text-embedding-v4'
            or not isinstance(old['request']['input'], str) or not old['request']['input']
            or old['result'].get('error_type') != 'BadRequestError'
            or old['result'].get('response_received') is not False or old['result'].get('usage') is not None
            or old['result'].get('settlement', {}).get('charged_cny') is not None):
        raise ValueError('original_embedding_is_not_the_one_known_SDK_HTTP_failure')
    failure = {'error_type': 'BadRequestError', 'http_status': 400,
               'http_status_evidence': 'installed_sdk_BadRequestError_status_code_400',
               'sdk_version': '1.109.1', 'http_body_missing': True, 'specific_body_unknown': True,
               'response_archive_absent': True}
    if value.get('original_failure') != failure:
        raise ValueError('original_HTTP_body_must_remain_unknown_not_reconstructed_from_diagnostic')
    manifest = read(run/'manifest.json')
    if manifest.get('dataset') != 'chexbench':
        raise ValueError('registered_embedding_HTTP_failure_is_only_permitted_in_CheXbench')
    identity = {**old['request'], 'endpoint': manifest['embedding_base_url'],
                'encoding_format_argument': 'omitted_preserve_installed_SDK_default'}
    if value.get('identity') != identity or manifest['embedding_model'] != old['request']['model']:
        raise ValueError('registered_embedding_input_model_endpoint_or_SDK_defaults_changed')
    markers = {name: 'recovery/embedding_arrearage_1/'+file for name, file in (
        ('scope', 'SCOPE.json'), ('review', 'REVIEW_READY.json'), ('funding', 'FUNDING_CONFIRMED.json'))}
    if value.get('markers') != markers:
        raise ValueError('explicit_new_review_scope_and_funding_marker_references_required')
    if any(not (new_folder/name).is_file() for name in (
            'request.json', 'started.json', 'response.json', 'result.json', 'wire_request.json', 'http_response.json')):
        raise ValueError('unknown_or_unclosed_embedding_retry')
    new = {name: read(new_folder/(name+'.json')) for name in ('request', 'started', 'response', 'result')}
    if (new['request'] != old['request'] or new['result'].get('error')
            or new['result'].get('response_received') is not True
            or new['result'].get('physical_requests') != 1 or new['result'].get('automatic_retry') is not False):
        raise ValueError('fresh_embedding_retry_was_changed_failed_or_reissued')
    if utc(new['started']['utc']) < utc(old['result']['utc']):
        raise ValueError('fresh_embedding_retry_precedes_original_HTTP_failure')
    wire, http = read(new_folder/'wire_request.json'), read(new_folder/'http_response.json')
    if (wire.get('model') != old['request']['model'] or wire.get('input') != old['request']['input']
            or set(wire)-{'model', 'input', 'encoding_format'} or wire.get('encoding_format') not in (None, 'base64')
            or http.get('http_status') != 200):
        raise ValueError('actual_retry_wire_identity_or_SDK_default_parameters_changed')
    response = new['response']; data = response.get('data')
    vector = data[0].get('embedding') if isinstance(data, list) and len(data) == 1 else None
    if (response.get('model') != old['request']['model'] or not isinstance(vector, list) or len(vector) != 1024
            or any(type(x) not in (int, float) or not math.isfinite(x) for x in vector) or not any(vector)):
        raise ValueError('retry_has_no_actual_healthy_same_model_1024_nonzero_vector')
    retry = {'response_received': True, 'model_returned': response['model'], 'dimensions': len(vector),
             'usage': response.get('usage'), 'elapsed_s': new['result'].get('elapsed_s')}
    if (value.get('retry') != retry or new['result'].get('usage') != response.get('usage')
            or new['result'].get('model_returned') != response['model']):
        raise ValueError('actual_embedding_retry_receipt_differs_from_registration')
    diagnostic = value.get('diagnostic', {})
    if (diagnostic.get('diagnostic_id') != 'r49_embedding_400_once_20261109'
            or diagnostic.get('http_status') != 400 or diagnostic.get('error_code') != 'Arrearage'
            or diagnostic.get('embedding_requests') != 1 or diagnostic.get('usage') is not None
            or diagnostic.get('result_reused_in_R49') is not False
            or diagnostic.get('original_error_body_reconstructed') is not False
            or type(diagnostic.get('elapsed_s')) not in (int, float)
            or not math.isfinite(diagnostic['elapsed_s']) or diagnostic['elapsed_s'] < 0):
        raise ValueError('separate_neutral_diagnostic_cannot_reconstruct_original_body_or_supply_vector')
    return {'registration': value, 'original_failure': old,
            'retry_call': {'path': new_folder, **new}}


def registered_cuda_retry(run):
    """The one reviewed closed historical failure; never forgive active failures."""
    path = run/'failure_events/cuda_1_registration.json'
    candidates = set((run/'failure_events').glob('cuda_*_registration.json'))
    if candidates-set([path]):
        raise ValueError('unrecognized_cuda_retry_registration')
    if not path.is_file():
        return None
    value = read(path)
    expected = {'schema': 'r49_registered_cuda_retry_v1', 'recovery_id': 'cuda_1',
                'dataset': 'chexbench', 'arm': ARM, 'question_id': 'chexbench_rad_restruct_0163',
                'logical_ordinal': 1, 'tool': 'chest_xray_expert',
                'status': 'healthy_production_retry_registered', 'new_tool_attempts': 1,
                'main_api_calls': 0, 'diagnostic_result_reused': False, 'automatic_retry': False,
                'production_debug_flags': {'CUDA_LAUNCH_BLOCKING': None, 'TORCH_SHOW_CPP_STACKTRACES': None},
                'original_selection_archive_relative': 'failure_events/cuda_1_original_selection.json'}
    if any(value.get(k) != v for k, v in expected.items()):
        raise ValueError('only_the_one_reviewed_production_cuda_retry_is_supported')
    old, new = value['original_cache_key'], value['retry_cache_key']
    if (not isinstance(old, str) or not old or old in ('.', '..')
            or any(c in old for c in '/\\:') or new != old+'_cuda_1'):
        raise ValueError('cuda_retry_cache_namespace_changed')
    original = value['original_selection']; replacement = value['retry_selection']
    archive = read(run/'failure_events/cuda_1_original_selection.json')
    if archive != original or original.get('cache_key') != old or replacement.get('cache_key') != new:
        raise ValueError('original_failed_selection_archive_changed')
    active_path = run/'services/tool_selections/R49-AGENT'/value['question_id']/'1.json'
    if read(active_path) != replacement or replacement.get('cache_hit') is not False:
        raise ValueError('registered_first_healthy_retry_not_the_actual_active_selection')
    provenance = {'recovery_id': 'cuda_1', 'original_cache_key': old, 'retry_cache_key': new,
                  'original_failure_preserved': True, 'production_retry': True}
    if replacement.get('cuda_recovery') != provenance:
        raise ValueError('registered_production_retry_provenance_changed')
    cache = run/'services/tool_cache'
    for key in (old, new):
        if not (cache/key/'started.json').is_file() or not (cache/key/'result.json').is_file():
            raise ValueError('unknown_or_unclosed_registered_tool_attempt')
    failed, healthy = read(cache/old/'result.json'), read(cache/new/'result.json')
    def unknown(x):
        if isinstance(x, dict):
            return any(k in ('status', 'analysis_status') and v in ('unknown', 'started_unknown', 'started', 'pending', 'running')
                       for k, v in x.items() if isinstance(v, str)) or any(unknown(v) for v in x.values())
        return isinstance(x, list) and any(unknown(v) for v in x)
    def failed_marker(x):
        if isinstance(x, dict):
            return any(k in ('status', 'analysis_status') and v in ('failed', 'error')
                       for k, v in x.items() if isinstance(v, str)) or any(failed_marker(v) for v in x.values())
        return isinstance(x, list) and any(failed_marker(v) for v in x)
    if (unknown(failed) or failed.get('status') not in ('completed', 'failed')
            or not failed_marker(failed) or tool_failure_reason(failed) is None
            or tool_failure_reason(original) is None
            or any(original.get(k) != v for k, v in failed.items())):
        raise ValueError('registered_original_is_not_a_closed_actual_failure')
    if (tool_failure_reason(healthy) or tool_failure_reason(replacement)
            or any(replacement.get(k) != v for k, v in healthy.items())):
        raise ValueError('registered_production_retry_is_not_healthy')
    identity = value['identity']
    if (any(x.get('identity') != identity for x in (original, replacement, failed, healthy))
            or any(read(cache/key/'started.json').get('identity') != identity for key in (old, new))
            or value.get('backend') != identity.get('backend')
            or value.get('revision') != identity.get('revision') or value.get('args') != identity.get('args')
            or value.get('backend') != 'chest_xray_expert'
            or any(x.get('original_image') != value.get('original_image') for x in (original, replacement, failed, healthy))):
        raise ValueError('registered_original_retry_identity_or_image_binding_changed')
    diagnostic = value.get('diagnostic')
    if (not isinstance(diagnostic, dict) or diagnostic.get('tool_invocations') != 1
            or any(diagnostic.get(k) != 0 for k in ('main_api_calls', 'meta_api_calls', 'embedding_api_calls'))
            or diagnostic.get('result_reused_in_R49') is not False
            or type(diagnostic.get('elapsed_s')) not in (int, float)
            or not math.isfinite(diagnostic['elapsed_s']) or diagnostic['elapsed_s'] < 0):
        raise ValueError('actual_separate_zero_API_diagnostic_metadata_required')
    return {'registration': value, 'original_result': failed, 'retry_result': healthy}


def phrase_guarded_backend(run, key, result=None):
    """Actual one-generation EOS evidence; the original parser/health check is unchanged."""
    folder = run/'services/tool_cache'/key
    result = read(folder/'result.json') if result is None else result
    evidence = result.get('generation_policy_evidence', {})
    if (tool_failure_reason(result) or result.get('backend') != PHRASE_TOOL
            or result.get('cuda_visible_devices') != '1'
            or any(evidence.get(k) != v for k, v in {
                'policy_id': PHRASE_POLICY, 'capture_complete': True, 'policy_healthy': True,
                'eos_terminated': True, 'final_generated_token_ids': [2], 'generation_policy_changed': True,
                'same_generation_settings': False, 'clinical_prompt_changed': False,
                'parser_changed': False, 'diagnostic_result_reused': False, 'cuda_visible_devices': '1',
                'inserted_tokens': 0, 'parse_fallback': False, 'forced_box': False}.items())):
        raise ValueError('guarded_MAIRA_requires_runtime_healthy_complete_EOS2_evidence')
    artifacts = folder/'artifacts'
    names = ('generation_tokens', 'decode', 'conversion_inputs', 'swallowed_exceptions',
             'observability_errors', 'factory', 'eos_guard', 'policy_status')
    if any(not (artifacts/(name+'.json')).is_file() for name in names):
        raise ValueError('guarded_MAIRA_actual_capture_files_required')
    records = {name: read(artifacts/(name+'.json')) for name in names}
    generations, decodes, conversion = (records[name] for name in ('generation_tokens', 'decode', 'conversion_inputs'))
    policy = records['eos_guard']; calls = policy.get('calls', [])
    if (len(generations) != 1 or len(decodes) != 1 or len(conversion) != 1 or len(calls) != 1
            or records['observability_errors'] or records['factory'] != evidence.get('factory')
            or any(evidence.get(k) != v for k, v in policy.items())):
        raise ValueError('one_actual_guarded_generation_and_unchanged_capture_records_required')
    factory = records['factory']
    if (len(factory) != 1 or any(factory[0].get(k) != v for k, v in {
            'model_revision': PHRASE_MODEL_REVISION, 'source_commit': PHRASE_REVISION.removeprefix('MedRAX-'),
            'cuda_visible_devices': '1', 'model_device': 'cuda:0', 'model_dtype': 'torch.float16',
            'is_loaded_in_8bit': True}.items())):
        raise ValueError('guarded_MAIRA_original_factory_revision_precision_GPU1_required')
    profile = {'tag_token_ids': {k: v for k, v in PHRASE_TOKENS.items() if k != 'eos'}, 'eos_token_id': 2,
               'do_sample': False, 'num_beams': 1, 'forced_eos_token_id': None, 'is_loaded_in_8bit': True,
               'model_dtype': 'torch.float16', 'visible_model_device': 'cuda:0'}
    if policy.get('profile') != profile:
        raise ValueError('guarded_MAIRA_original_greedy_profile_changed')
    generation, call = generations[0], calls[0]
    length = generation.get('prompt_length'); output = generation.get('output_token_ids'); suffix = generation.get('generated_token_ids')
    if (type(length) is not int or length < 0 or not isinstance(output, list) or len(output) != 1
            or not isinstance(output[0], list) or suffix != [output[0][length:]]
            or not suffix or not suffix[0] or len(suffix[0]) > 300 or suffix[0][-1] != 2
            or any(type(value) is not int for value in suffix[0])
            or generation.get('max_new_tokens') != 300 or generation.get('use_cache') is not True
            or call.get('prompt_length') != length or call.get('max_new_tokens') != 300
            or call.get('use_cache') is not True or call.get('existing_logits_processors') != 0
            or call.get('processor_invocations') != len(suffix[0])
            or call.get('generation_policy_changed') is not True):
        raise ValueError('guarded_MAIRA_raw_tokens_original_max300_and_EOS2_required')
    expected_masks = []; obj = box = 0
    for index, token in enumerate(suffix[0]):
        if obj or box:
            expected_masks.append({'step': index+1, 'batch_row': 0, 'generated_length': index,
                'unclosed_obj_depth': obj, 'unclosed_box_depth': box, 'masked_token_id': 2})
            if token == 2:
                raise ValueError('EOS_emitted_while_generated_grounding_tag_unclosed')
        if token == PHRASE_TOKENS['obj_start']: obj += 1
        elif token == PHRASE_TOKENS['obj_end']: obj = max(0, obj-1)
        elif token == PHRASE_TOKENS['box_start']: box += 1
        elif token == PHRASE_TOKENS['box_end']: box = max(0, box-1)
    if (call.get('masking_steps') != expected_masks or call.get('masking_step_count') != len(expected_masks)
            or decodes[0].get('input_token_ids') != suffix[0]
            or decodes[0].get('kwargs') != {'skip_special_tokens': True}
            or not isinstance(decodes[0].get('decoded_text'), str)
            or conversion[0].get('text') != decodes[0]['decoded_text']
            or any(records['policy_status'].get(k) is not True for k in ('capture_complete', 'policy_healthy', 'eos_terminated'))):
        raise ValueError('actual_EOS_only_mask_steps_decode_and_unchanged_parser_chain_required')
    started = read(folder/'started.json')
    request = read(folder/'request.json')
    identity = result.get('identity', {})
    if (started.get('identity') != identity or started.get('policy_id') != PHRASE_POLICY
            or started.get('generation_policy_changed') is not True or started.get('automatic_retry') is not False
            or identity.get('backend') != PHRASE_TOOL or identity.get('revision') != PHRASE_REVISION
            or request.get('tool') != PHRASE_TOOL or request.get('backend') != PHRASE_TOOL
            or request.get('args') != identity.get('args') or request.get('image') != result.get('original_image')):
        raise ValueError('guarded_MAIRA_actual_request_identity_changed')
    return {'masked_eos_steps': len(expected_masks), 'result': result}


def registered_phrase_guard_retry(run):
    """The one preserved closed phrase failure; policy changes are explicit."""
    path = run/'failure_events/phrase_guard_1_registration.json'
    if set((run/'failure_events').glob('phrase_guard_*_registration.json'))-{path}:
        raise ValueError('unrecognized_phrase_guard_recovery')
    if not path.is_file():
        return None
    value = read(path)
    fixed = {'schema': 'r49_registered_phrase_guard_retry_v1', 'recovery_id': 'phrase_guard_1',
             'dataset': 'chexbench', 'arm': ARM, 'question_id': PHRASE_QID, 'question_ordinal': 169,
             'logical_tool_ordinal': 1, 'tool': PHRASE_TOOL, 'backend': PHRASE_TOOL,
             'original_cache_key': PHRASE_OLD_KEY, 'retry_cache_key': PHRASE_OLD_KEY+'_phrase_guard_1',
             'original_selection_archive_relative': 'failure_events/phrase_guard_1_original_selection.json',
             'policy_id': PHRASE_POLICY, 'generation_policy_changed': True, 'same_generation_settings': False,
             'guarded_production_retry_limit': 1, 'automatic_retry': False,
             'status': 'healthy_guarded_production_retry_registered'}
    manifest = read(run/'manifest.json')
    if (any(value.get(k) != v for k, v in fixed.items()) or manifest.get('dataset') != 'chexbench'
            or len(manifest.get('order', [])) <= 168 or manifest['order'][168]['question_id'] != PHRASE_QID):
        raise ValueError('only_exact_q169_declared_phrase_guard_retry_supported')
    old, active = value['original_selection'], value['active_selection']
    failed = read(run/'services/tool_cache'/PHRASE_OLD_KEY/'result.json')
    healthy = read(run/'services/tool_cache'/value['retry_cache_key']/'result.json')
    old_started = read(run/'services/tool_cache'/PHRASE_OLD_KEY/'started.json')
    if (read(run/value['original_selection_archive_relative']) != old
            or old.get('cache_key') != PHRASE_OLD_KEY or old.get('tool') != PHRASE_TOOL
            or old.get('status') != 'completed' or failed.get('status') != 'completed'
            or not isinstance(failed.get('observation'), list) or len(failed['observation']) != 2
            or failed['observation'][0].get('error') != '' or failed['observation'][1].get('analysis_status') != 'failed'
            or any(event.get('status') != 'completed' for event in failed.get('actual_model_events', []))
            or tool_failure_reason(old) != 'nested_backend_error'
            or any(old.get(k) != v for k, v in failed.items())):
        raise ValueError('original_phrase_nested_error_must_remain_closed_preserved_failure')
    identity = value['identity']
    if (identity.get('backend') != PHRASE_TOOL or identity.get('revision') != PHRASE_REVISION
            or any(item.get('identity') != identity for item in (old_started, old, active, failed, healthy))
            or any(item.get('original_image') != value.get('canonical_original_image') for item in (old, active, failed, healthy))
            or active.get('cache_key') != value['retry_cache_key']
            or read(run/'services/tool_selections/R49-AGENT'/PHRASE_QID/'1.json') != active
            or any(active.get(k) != v for k, v in healthy.items())):
        raise ValueError('phrase_guard_original_retry_or_active_identity_changed')
    phrase_guarded_backend(run, value['retry_cache_key'], healthy)
    diagnostic = value.get('diagnostic', {})
    if (diagnostic.get('diagnostic_id') != 'r49_phrase_grounding_diagnostic_20261109'
            or diagnostic.get('tool_invocations') != 1 or diagnostic.get('status') != 'failed'
            or diagnostic.get('capture_complete') is not True or diagnostic.get('result_reused_in_R49') is not False
            or any(diagnostic.get(k) != 0 for k in ('main_api_calls', 'meta_api_calls', 'embedding_api_calls'))
            or type(diagnostic.get('elapsed_s')) not in (int, float) or not math.isfinite(diagnostic['elapsed_s'])
            or diagnostic['elapsed_s'] < 0):
        raise ValueError('one_separate_failed_complete_zero_API_phrase_diagnostic_required')
    return {'registration': value, 'original_result': failed, 'retry_result': healthy}


def validate_phrase_guard_amendment(run, manifest=None):
    manifest = read(run/'manifest.json') if manifest is None else manifest
    path = run/'failure_events/phrase_guard_1_amendment.json'
    counts = {'active': path.is_file(), 'amendment': None, 'legacy_saved_selections': 0,
              'legacy_healthy_cache_selections': 0, 'guarded_new_selections': 0,
              'guarded_cache_selections': 0, 'guarded_physical_attempts': 0, 'masked_eos_steps': 0}
    if not path.is_file():
        if ((run/'failure_events/phrase_guard_1_registration.json').exists()
                or any((run/'services/tool_cache').glob('*_phrase_guard_1'))):
            raise ValueError('phrase_retry_requires_its_declared_policy_boundary')
        return counts
    amendment = read(path); dataset = manifest.get('dataset')
    fixed = {'schema': 'r49_phrase_guard_amendment_v1', 'recovery_id': 'phrase_guard_1',
             'dataset': dataset, 'arm': ARM, 'policy_id': PHRASE_POLICY, 'activation_boundary_chexbench': 168,
             'activation_committed_questions': 168 if dataset == 'chexbench' else 0,
             'scope': 'all_new_physical_MAIRA_calls_after_activation', 'token_ids': PHRASE_TOKENS,
             'max_new_tokens': 300, 'generation_policy_changed': True, 'same_generation_settings': False,
             'legacy_healthy_cache_reuse': True, 'automatic_retry': False,
             'clinical_prompt_changed': False, 'parser_changed': False, 'diagnostic_result_reused': False,
             'cache_naming': 'unchanged_legacy_identity_and_key_plus_explicit_policy_suffix; image_fingerprint_is_existing_naming_not_a_validation_gate'}
    if dataset not in EXPECTED or any(amendment.get(k) != v for k, v in fixed.items()):
        raise ValueError('only_declared_all_new_physical_MAIRA_EOS_policy_supported')
    protected = amendment.get('protected_existing_selections', []); legacy = amendment.get('legacy_cache_keys_at_activation', [])
    if (protected != sorted(set(protected)) or legacy != sorted(set(legacy))
            or any(not isinstance(k, str) or not k or '/' in k or '\\' in k or k in ('.', '..') for k in legacy)):
        raise ValueError('phrase_policy_activation_sets_malformed')
    activation = utc(amendment['utc']); indices = {item['question_id']: index for index, item in enumerate(manifest['order'])}
    if dataset != 'chexbench' and (protected or legacy):
        raise ValueError('cold_SLAKE_VQA_phrase_policy_boundary_must_be_empty')
    seen = set(); physical = set()
    for selection_path in sorted((run/'services/tool_selections').glob('*/*/*.json')):
        relative = selection_path.relative_to(run).as_posix(); selection = read(selection_path)
        qid = selection_path.parent.name
        if relative in protected:
            seen.add(relative)
            if qid not in indices or indices[qid] >= 168 or selection.get('generation_policy'):
                raise ValueError('protected_selection_moved_after_phrase_policy_activation')
            if selection.get('tool') == PHRASE_TOOL:
                if selection.get('cache_key') not in legacy or tool_failure_reason(selection):
                    raise ValueError('protected_legacy_MAIRA_selection_changed')
                counts['legacy_saved_selections'] += 1
            continue
        if selection.get('tool') != PHRASE_TOOL:
            continue
        if qid not in indices or (dataset == 'chexbench' and indices[qid] < 168):
            raise ValueError('undeclared_earlier_MAIRA_policy_selection')
        metadata = selection.get('generation_policy', {}); source = metadata.get('source'); key = selection.get('cache_key')
        backend = read(run/'services/tool_cache'/str(key)/'result.json')
        if (metadata.get('bound_original_image') != selection.get('original_image') or tool_failure_reason(backend)
                or any(selection.get(k) != v for k, v in backend.items())):
            raise ValueError('phrase_policy_actual_selection_cache_binding_changed')
        if source == 'legacy_healthy_cache':
            if (key not in legacy or metadata.get('policy_id') != 'legacy_original_maira'
                    or metadata.get('generation_policy_changed') is not False or metadata.get('same_generation_settings') is not True
                    or metadata.get('applied_actual_invocation') is not False or selection.get('cache_hit') is not True
                    or backend.get('generation_policy_evidence')):
                raise ValueError('legacy_MAIRA_cache_reclassified_or_recomputed')
            counts['legacy_healthy_cache_selections'] += 1
        elif source in ('guarded_new', 'guarded_cache'):
            if (not isinstance(key, str) or not key.endswith('_phrase_guard_1') or key in legacy
                    or metadata.get('policy_id') != PHRASE_POLICY or metadata.get('generation_policy_changed') is not True
                    or metadata.get('same_generation_settings') is not False
                    or metadata.get('applied_actual_invocation') is not (source == 'guarded_new')
                    or selection.get('cache_hit') is not (source == 'guarded_cache')):
                raise ValueError('guarded_MAIRA_policy_source_or_cache_provenance_changed')
            started = read(run/'services/tool_cache'/key/'started.json')
            if utc(started['utc']) < activation:
                raise ValueError('guarded_physical_attempt_precedes_declared_activation')
            proof = phrase_guarded_backend(run, key, backend)
            counts['guarded_new_selections' if source == 'guarded_new' else 'guarded_cache_selections'] += 1
            if key not in physical:
                physical.add(key); counts['masked_eos_steps'] += proof['masked_eos_steps']
        else:
            raise ValueError('missing_declared_MAIRA_policy_source_after_activation')
    if set(protected) != seen:
        raise ValueError('protected_prepolicy_selection_missing')
    counts.update(amendment=amendment, guarded_physical_attempts=len(physical))
    return counts


def tool_attempt_accounting(run, tools, active_keys):
    registered = registered_cuda_retry(run)
    phrase = registered_phrase_guard_retry(run)
    registrations = [proof for proof in (registered, phrase) if proof]
    preserved = {proof['registration']['original_cache_key'] for proof in registrations}
    if registered and registered['registration']['retry_cache_key'] not in active_keys:
        raise ValueError('registered_healthy_retry_not_used_by_the_completed_stream')
    if registered:
        key = registered['registration']['retry_cache_key']
        expected = registered['registration']['retry_selection']['cuda_recovery']
        if any(t.get('cuda_recovery') != expected for t in tools if t.get('cache_key') == key):
            raise ValueError('future_registered_cache_alias_provenance_changed')
    if phrase and phrase['registration']['retry_cache_key'] not in active_keys:
        raise ValueError('registered_phrase_guard_retry_not_used_by_completed_stream')
    cache_root = run/'services/tool_cache'
    folders = [path for path in cache_root.iterdir() if path.is_dir()] if cache_root.is_dir() else []
    for folder in folders:
        if folder.name not in active_keys|preserved or any(not (folder/name).is_file() for name in ('started.json', 'result.json')):
            raise ValueError('orphan_or_unknown_tool_attempt')
    for key in active_keys:
        if any(not (run/'services/tool_cache'/key/name).is_file() for name in ('started.json', 'result.json')):
            raise ValueError('unclosed_active_tool_attempt')
    active = [read(run/'services/tool_cache'/key/'result.json') for key in sorted(active_keys)]
    if any(tool_failure_reason(value) for value in active):
        raise ValueError('failed_active_backend_attempt')
    physical = active + [proof['original_result'] for proof in registrations]
    return {'physical': physical, 'healthy': len(active), 'registered': registered, 'phrase': phrase}


def check_semantics(inputs, manifest, run, paths, predictions, receipts):
    """After all arms are adapted, check the committed prediction/feedback chain."""
    ids = [row['question_id'] for row in inputs]; order = manifest['order']; memory = {}
    previous_release = None; previous_repo = initial(); tool_values = []; hit = []; window_counts = []; cache_keys = set()
    window_size = manifest.get('defaults', {}).get('window', 30)
    for wi, start in enumerate(range(0, len(inputs), window_size)):
        window = run/'windows'/f'{wi:04d}'; snapshot = read(window/'read_snapshot.json')
        if snapshot != previous_repo:
            raise ValueError('window_start_snapshot_changed')
        for skill in snapshot['skills'].values():
            if not set(skill['source_ids']) <= set(ids[:start]):
                raise ValueError('current_or_future_skill_source')
        n_hit = 0
        for index in range(start, min(start+window_size, len(inputs))):
            row, item = inputs[index], order[index]; qid = row['question_id']; pred = predictions[qid]
            ordinal = index+1; ctx = read(paths['contexts'][qid]); event = read(paths['feedback'][qid])
            saved = read(paths['prediction_events'][qid]); entries = memory.setdefault(item['image_key'], [])
            same_text, same_ids = context(entries, item, ordinal)
            if (ctx.get('question_id') != qid or ctx.get('ordinal') != ordinal or ctx.get('window') != wi
                    or ctx.get('skill_snapshot') != snapshot or ctx.get('same_image_ids') != same_ids
                    or ctx.get('same_image_context') != same_text):
                raise ValueError('same_image_or_window_context_changed:' + qid)
            selected = ctx['selected_skills']; selected_ids = [value['id'] for value in selected]
            if len(selected_ids) != len(set(selected_ids)):
                raise ValueError('duplicate_injected_skill')
            for value in selected:
                if (value['id'] not in snapshot['skills'] or value['c'] != snapshot['skills'][value['id']]['c']
                        or snapshot['skills'][value['id']]['status'] not in ('active', 'mature')):
                    raise ValueError('unavailable_or_changed_injected_skill')
            if (pred.get('ordinal') != ordinal or pred.get('selected_skill_ids') != selected_ids
                    or pred.get('same_image_ids') != same_ids
                    or saved.get('saved_prediction') != pred or event.get('saved_prediction') != pred
                    or event.get('question_id') != qid or event.get('ordinal') != ordinal
                    or event.get('image_key') != item['image_key']
                    or event.get('timing') != 'after_immutable_prediction'
                    or event.get('provenance') != 'dataset_annotation_feedback_not_patient_history'):
                raise ValueError('prediction_before_feedback_semantic_binding:' + qid)
            saved_at, released = utc(pred['prediction_saved_at']), utc(event['released_at'])
            if saved_at > released or previous_release is not None and previous_release > saved_at:
                raise ValueError('feedback_timing_not_sequential:' + qid)
            injected = '\n\n'.join(value for value in (conditioning(selected), same_text) if value)
            steps = read(paths['steps'][qid])
            if len(steps) != len(receipts[qid]):
                raise ValueError('steps_actual_calls_mismatch')
            for step_index, (call, started, receipt) in enumerate(receipts[qid]):
                if utc(receipt['utc']) > saved_at or previous_release is not None and utc(started['utc']) < previous_release:
                    raise ValueError('request_outside_feedback_sequence')
                if steps[step_index].get('response') != response_text(call):
                    raise ValueError('steps_do_not_match_actual_response')
                messages = read(call/'request.json')['messages']
                contents = [message.get('content') for message in messages if isinstance(message.get('content'), str)]
                if injected and contents.count(injected) != 1:
                    raise ValueError('actual_request_missing_injected_context')
            selection_dir = run/'services/tool_selections/R49-AGENT'/qid
            selections = sorted(selection_dir.glob('*.json'), key=lambda p: int(p.stem))
            if [int(path.stem) for path in selections] != list(range(1, len(selections)+1)) or len(selections) != pred['tool_calls']:
                raise ValueError('actual_tool_count_mismatch')
            for path in selections:
                selection = read(path)
                if tool_failure_reason(selection):
                    raise ValueError('failed_tool_in_completed_stream')
                key = selection.get('cache_key')
                cache_root = (run/'services/tool_cache').resolve()
                cache = (cache_root/str(key)).resolve()
                if (not key or not cache.is_relative_to(cache_root)
                        or not (cache/'started.json').is_file() or not (cache/'result.json').is_file()):
                    raise ValueError('unclosed_selected_tool_cache')
                backend = read(cache/'result.json')
                if tool_failure_reason(backend) or any(selection.get(k) != v for k, v in backend.items()):
                    raise ValueError('tool_cache_health_or_semantics_changed')
                cache_keys.add(key)
                tool_values.append(selection)
            entries.append(memory_entry(row, pred, event)); previous_release = released
            n_hit += bool(selected); hit.append({'question_id': qid, 'window': wi,
                                               'skill_hit': bool(selected), 'same_image_hit': bool(same_ids)})
        previous_repo = read(window/'repo.json')
        window_counts.append({'window': wi, 'questions': min(window_size, len(inputs)-start),
                              'skill_hit_questions': n_hit,
                              'active_skills': sum(s['status'] in ('active', 'mature') for s in previous_repo['skills'].values())})
    complete, final_repo = read(run/'complete.json'), read(run/'final_repo.json')
    if (complete.get('status') != 'generation_complete' or complete.get('arm') != ARM
            or complete.get('questions') != len(ids) or complete.get('final_repo') != final_repo
            or final_repo != previous_repo):
        raise ValueError('full_semantic_completion_required')
    attempts = tool_attempt_accounting(run, tool_values, cache_keys)
    return hit, window_counts, tool_values, attempts


def receipt_resources(values):
    records = [value[2] for value in values]
    known = [Decimal(str(value['settlement']['charged_cny'])) for value in records
             if value.get('settlement', {}).get('charged_cny') is not None]
    return {'requests': len(records), 'returned_models': sorted({v['model_returned'] for v in records if v.get('model_returned')}),
            'prompt_tokens': sum((v.get('usage') or {}).get('prompt_tokens', 0) or 0 for v in records),
            'completion_tokens': sum((v.get('usage') or {}).get('completion_tokens', 0) or 0 for v in records),
            'cached_tokens': sum(((v.get('usage') or {}).get('prompt_tokens_details') or {}).get('cached_tokens', 0) or 0 for v in records),
            'usage_cost_cny_proxy_known': str(sum(known, Decimal(0))), 'cost_unknown_count': len(records)-len(known),
            'elapsed_seconds_known': sum(v.get('elapsed_s') or 0 for v in records),
            'elapsed_unknown_count': sum(v.get('elapsed_s') is None for v in records), 'provider_invoice': False}


def meta_repair_resources(proof):
    return {'registered': proof is not None, 'added_meta_requests': int(proof is not None),
            'source_invalid_schema_response_retained': proof is not None,
            'included_in_R49_META_totals': True, 'automatic_invalid_to_none': False,
            'fresh_model_operation': proof['repair_draft']['operation'] if proof else None,
            'extra_agent_calls': 0, 'extra_embedding_calls': 0, 'extra_tool_calls': 0,
            'repair_request_resources': receipt_resources([proof['repair_call']] if proof else [])}


def resources(run, receipts, tools, attempts, meta_repair=None, meta_repair_2=None, fields_amendment=None,
              embedding_repair=None, phrase_amendment=None, adoption_repair=None, analysis_unique_amendment=None):
    if {p.name for p in (run/'services/calls').iterdir() if p.is_dir()}-{'R49-AGENT', 'R49-META'}:
        raise ValueError('unexpected_paid_call_arm')
    agent = receipt_resources([value for calls in receipts.values() for value in calls])
    meta = [value for folder in (run/'services/calls/R49-META').glob('*') if folder.is_dir() for value in closed_calls(folder)]
    embedding = []
    for folder in sorted((run/'services/embeddings').glob('*')):
        if not folder.is_dir():
            continue
        if embedding_repair is not None and folder.name == '000063':
            embedding.append(embedding_repair['original_failure']['result'])
            continue
        if any(not (folder/name).is_file() for name in ('request.json', 'started.json', 'response.json', 'result.json')):
            raise ValueError('unclosed_embedding_request')
        receipt = read(folder/'result.json')
        if receipt.get('error') or receipt.get('response_received') is not True:
            raise ValueError('failed_embedding_request')
        embedding.append(receipt)
    embeddings = {'requests': len(embedding), 'returned_models': sorted({r['model_returned'] for r in embedding if r.get('model_returned')}),
                  'successful_responses': sum(r.get('response_received') is True for r in embedding),
                  'registered_http_failed_attempts': int(embedding_repair is not None),
                  'usage_unknown_count': sum(r.get('usage') is None for r in embedding),
                  'total_tokens': sum((r.get('usage') or {}).get('total_tokens', 0) or 0 for r in embedding),
                  'usage_cost_cny_proxy_known': str(sum((Decimal(str(r['settlement']['charged_cny'])) for r in embedding if r.get('settlement', {}).get('charged_cny') is not None), Decimal(0))),
                  'cost_unknown_count': sum(r.get('settlement', {}).get('charged_cny') is None for r in embedding),
                  'elapsed_seconds_known': sum(r.get('elapsed_s') or 0 for r in embedding),
                  'elapsed_unknown_count': sum(r.get('elapsed_s') is None for r in embedding), 'provider_invoice': False}
    physical = attempts['physical']; registration = attempts['registered']; phrase = attempts.get('phrase')
    diagnostic = registration['registration']['diagnostic'] if registration else None
    phrase_diagnostic = phrase['registration']['diagnostic'] if phrase else None
    return {'agent': agent, 'R49_META': receipt_resources(meta), 'embedding': embeddings,
            'tools': {'logical_calls': len(tools), 'cache_hits': sum(bool(t.get('cache_hit')) for t in tools),
                      'fresh_backend_attempts': len(physical), 'healthy_backend_attempts': attempts['healthy'],
                      'registered_failed_historical_attempts': int(registration is not None)+int(phrase is not None),
                      'registered_cuda_failed_attempts': int(registration is not None),
                      'registered_phrase_failed_attempts': int(phrase is not None),
                      'failed_backend_attempts': int(registration is not None)+int(phrase is not None), 'unknown_backend_attempts': 0,
                      'backend_compute_seconds_known': sum(t.get('backend_compute_seconds') or 0 for t in physical),
                      'backend_compute_unknown_count': sum(t.get('backend_compute_seconds') is None for t in physical),
                      'backend_elapsed_seconds_known': sum(t.get('elapsed_s') or 0 for t in physical),
                      'backend_elapsed_unknown_count': sum(t.get('elapsed_s') is None for t in physical),
                      'failed_or_unknown_tools': sum(tool_failure_reason(t) is not None for t in tools)},
            'isolated_cuda_diagnostic': {
                'tool_invocations': diagnostic['tool_invocations'] if diagnostic else 0,
                'elapsed_s': diagnostic['elapsed_s'] if diagnostic else None,
                'main_api_calls': 0, 'meta_api_calls': 0, 'embedding_api_calls': 0,
                'result_reused_in_R49': False, 'included_in_production_attempts': False,
                'hardware_cost_unknown': diagnostic is not None},
            'phrase_guard_retry': {'registered': phrase is not None, 'guarded_production_retries': int(phrase is not None),
                'generation_policy_changed': phrase is not None, 'same_generation_settings': False if phrase else None,
                'diagnostic_result_reused': False, 'included_in_tools_totals': True},
            'phrase_guard_amendment': phrase_amendment or {
                'active': False, 'amendment': None, 'legacy_saved_selections': 0,
                'legacy_healthy_cache_selections': 0, 'guarded_new_selections': 0,
                'guarded_cache_selections': 0, 'guarded_physical_attempts': 0, 'masked_eos_steps': 0},
            'isolated_phrase_diagnostic': {
                'tool_invocations': phrase_diagnostic['tool_invocations'] if phrase_diagnostic else 0,
                'elapsed_s': phrase_diagnostic['elapsed_s'] if phrase_diagnostic else None,
                'status': phrase_diagnostic['status'] if phrase_diagnostic else None,
                'capture_complete': phrase_diagnostic['capture_complete'] if phrase_diagnostic else None,
                'main_api_calls': 0, 'meta_api_calls': 0, 'embedding_api_calls': 0,
                'result_reused_in_R49': False, 'included_in_production_attempts': False,
                'hardware_cost_unknown': phrase_diagnostic is not None},
            'meta_schema_repair': meta_repair_resources(meta_repair),
            'meta_schema_repair_2': meta_repair_resources(meta_repair_2),
            'adoption_repair': {'registered': adoption_repair is not None,
                'added_meta_requests': len(adoption_repair['repairs']) if adoption_repair else 0,
                'included_in_R49_META_totals': True, 'original_analysis_retained_for_mutation': True,
                'assess_only_overlay': True, 'model_selected_existing_entry_only': adoption_repair is not None,
                'manual_selection': False, 'new_evidence_written': False,
                'extra_agent_calls': 0, 'extra_embedding_calls': 0, 'extra_tool_calls': 0,
                'repair_request_resources': receipt_resources([item['repair_call'] for item in adoption_repair['repairs']] if adoption_repair else [])},
            'analysis_unique_amendment': analysis_unique_amendment or {
                'active': False, 'amendment': None, 'ordinary_analysis_requests': 0,
                'original_system_requests': 0, 'clarified_system_requests': 0,
                'protected_original_events': [], 'extra_ordinary_meta_calls': 0},
            'mutation_fields_amendment': fields_amendment or {
                'active': False, 'amendment': None, 'ordinary_mutation_requests': 0,
                'original_system_requests': 0, 'clarified_system_requests': 0,
                'protected_original_events': [], 'extra_ordinary_meta_calls': 0},
            'embedding_http_recovery': {
                'registered': embedding_repair is not None,
                'new_production_embedding_requests': int(embedding_repair is not None),
                'included_in_embedding_totals': True,
                'original_error_type': 'BadRequestError' if embedding_repair else None,
                'original_http_status': 400 if embedding_repair else None,
                'original_specific_body_unknown': embedding_repair is not None,
                'original_usage_unknown': embedding_repair is not None,
                'original_cost_unknown': embedding_repair is not None},
            'isolated_embedding_diagnostic': {
                'embedding_requests': int(embedding_repair is not None),
                'http_status': 400 if embedding_repair else None,
                'error_code': 'Arrearage' if embedding_repair else None,
                'elapsed_s': embedding_repair['registration']['diagnostic']['elapsed_s'] if embedding_repair else None,
                'usage_unknown': embedding_repair is not None, 'cost_unknown': embedding_repair is not None,
                'agent_calls': 0, 'meta_calls': 0, 'tool_calls': 0, 'local_gpu_calls': 0,
                'included_in_production_embedding_totals': False, 'original_error_body_reconstructed': False}}


def score(data, run, references, dataset, *, r47_frozen=None, r47_run=None):
    n, baseline_name, expected_baseline = EXPECTED[dataset]
    inputs, manifest, paths = completed_gate(data, run, n)
    if manifest.get('dataset') != dataset:
        raise ValueError('dataset_manifest_identity_changed')
    current, predictions, receipts = adapt_current(inputs, run, paths)
    baseline = adapt_historical(inputs, dataset, baseline_name)
    comparisons = {baseline_name: baseline}
    if r47_run is not None or r47_frozen is not None:
        if dataset != 'chexbench':
            raise ValueError('R47_comparator_is_chexbench_only')
        comparisons['R47_online_GT'] = adapt_r47(inputs, baseline, r47_frozen, r47_run)
    # Reference-free adaptation of EVERY compared raw arm is now complete.
    hit, windows, tools, attempts = check_semantics(inputs, manifest, run, paths, predictions, receipts)
    meta_repairs = registered_meta_schema_repairs(run)
    fields_amendment = validate_mutation_fields_amendment(run, manifest)
    embedding_repair = registered_embedding_http_failure(run)
    phrase_amendment = validate_phrase_guard_amendment(run, manifest)
    adoption_repair = registered_adoption_repair(run)
    analysis_unique_amendment = validate_analysis_unique_amendment(run, manifest)
    resource = resources(run, receipts, tools, attempts, meta_repairs['meta_schema_1'],
                        meta_repairs['meta_schema_2'], fields_amendment, embedding_repair, phrase_amendment,
                        adoption_repair, analysis_unique_amendment)
    reference_rows = rows(references); refs = {row['question_id']: row['answer'] for row in reference_rows}
    if len(refs) != len(reference_rows) or set(refs) != {row['question_id'] for row in inputs}:
        raise ValueError('scoring_reference_cohort')
    detail, rng = [], random.Random(0)
    all_arms = {ARM: current, **comparisons}
    for row, info in zip(inputs, hit):
        qid = row['question_id']; event = read(paths['feedback'][qid])
        if event['reference_annotation']['answer'] != refs[qid]:
            raise ValueError('released_feedback_differs_from_scoring_reference')
        scores = {name: {**value[qid], **outcomes(row, value[qid], refs[qid], rng)} for name, value in all_arms.items()}
        detail.append({**info, 'subset': (row.get('source') or {}).get('subset', 'all'),
                       'reference': refs[qid], 'arms': scores})
    counts = {name: sum(d['arms'][name]['aligned_correct'] for d in detail) for name in all_arms}
    if counts[baseline_name] != expected_baseline or 'R47_online_GT' in counts and counts['R47_online_GT'] != 468:
        raise ValueError('fixed_historical_common_metric_count_changed')
    subsets = np.array([d['subset'] for d in detail]); clusters = cluster_keys(inputs)
    def summarize(name):
        groups = {label: {'n': sum(d['subset'] == label for d in detail),
                          'correct': sum(d['arms'][name]['aligned_correct'] for d in detail if d['subset'] == label)}
                  for label in sorted(set(subsets))}
        for group in groups.values():
            group['accuracy_pct'] = 100*group['correct']/group['n']
        return {'n': n, 'correct': counts[name], 'micro_pct': 100*counts[name]/n,
                'macro_pct': float(np.mean([g['accuracy_pct'] for g in groups.values()])), 'subsets': groups,
                'word_recall_pct': None if dataset == 'chexbench' else 100*float(np.mean([d['arms'][name]['word_recall'] for d in detail])),
                'answer_absent': sum(d['arms'][name]['answer_absent'] for d in detail),
                'domain_invalid': sum(d['arms'][name]['choice_domain_invalid'] for d in detail),
                'raw_whole_json_valid': sum(d['arms'][name]['raw_whole_json_valid'] for d in detail),
                'legacy_M_contract_compliant': sum(d['arms'][name]['legacy_M_contract_compliant'] for d in detail),
                'extraction_counts': dict(Counter(d['arms'][name]['extraction'] for d in detail))}
    paired = {}
    for name in comparisons:
        delta = np.array([int(d['arms'][ARM]['aligned_correct'])-int(d['arms'][name]['aligned_correct']) for d in detail])
        paired[name] = {'corrected': int(sum(delta > 0)), 'harmed': int(sum(delta < 0)), 'net': int(sum(delta)),
                        'micro_delta_pp': 100*float(delta.mean()),
                        'confidence': bootstrap(delta, clusters, subsets),
                        'changes': [{'question_id': d['question_id'], 'delta': int(value)} for d, value in zip(detail, delta) if value]}
    for window in windows:
        selected = [d for d in detail if d['window'] == window['window']]
        window['correct'] = sum(d['arms'][ARM]['aligned_correct'] for d in selected)
    summary = {'dataset': dataset, 'arm': ARM, 'questions': n, 'all_questions_fresh': True,
               'mode': 'online_post_prediction_ground_truth_feedback_and_window_skill_learning',
               'arms': {name: summarize(name) for name in all_arms}, 'comparisons': paired,
               'skill_hit_questions': sum(d['skill_hit'] for d in detail),
               'same_image_hit_questions': sum(d['same_image_hit'] for d in detail),
               'windows': windows, 'resources': resource, 'references_read_after_all_arms_adapted': True,
               'interpretation': ['Exposed online label-feedback system, not closed-test or official SOTA.',
                                  'Historical differences combine Skill learning, changed executor/call budgets, sampling and time.',
                                  'No contemporaneous no-Skill control; same-model adoption is not a causal or clinical verification.',
                                  'Datasets are reported separately; SLAKE overlap and VQA paraphrases preclude pooling independent cases.']}
    return summary, detail


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('data', 'run', 'references', 'out'):
        parser.add_argument('--'+name, required=True, type=Path)
    parser.add_argument('--dataset', required=True, choices=EXPECTED)
    parser.add_argument('--r47-frozen', type=Path); parser.add_argument('--r47-run', type=Path)
    args = parser.parse_args()
    if args.out.exists():
        raise ValueError('new_empty_score_output_required')
    summary, detail = score(args.data, args.run, args.references, args.dataset,
                            r47_frozen=args.r47_frozen, r47_run=args.r47_run)
    save_once(args.out/'summary.json', summary); save_once(args.out/'per_question.json', detail)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
