"""Score a completed R50 stream with the common explicit-answer/author metrics.

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
from run_online_skill_r50 import ARM
from online_memory_r50 import read, save_once, context, memory_entry
from skill_services_r50 import conditioning
from skill_lifecycle_r50 import initial
from cxr_online_primitives_r50 import tool_failure_reason
from r50_recovery_evidence import generation_completion,tool_recovery_attempts
from r50_failure_observation import validate_delivered_failure,validate_prediction_failures

EXPECTED={'chexbench':(618,'M43',466),'slake':(114,'M43',108),'vqarad':(116,'M42',100)}
PHRASE_POLICY = 'maira_unclosed_tag_eos_guard_v1'
PHRASE_TOOL = 'xray_phrase_grounding'
PHRASE_REVISION = 'MedRAX-dae30e2f136ef0b2a40885a4c335386e9ffad052'
PHRASE_MODEL_REVISION = '795a2b1cd4a310624b4e3d14b5a23e41fd273deb'
PHRASE_TOKENS = {'obj_start': 32000, 'obj_end': 32001, 'box_start': 32202, 'box_end': 32203, 'eos': 2}



def adapt_saved_r49(inputs, run):
    """Reference-free raw-terminal adaptation only; never invoke the old score()."""
    from score_online_skill_r49 import adapt_current as adapt_old
    from run_online_skill_r49 import ARM as OLD_ARM
    run=Path(run)
    if (run/'generation.exitcode').read_text().strip()!='0':raise ValueError('saved_R49_raw_exit_zero_required')
    manifest=read(run/'manifest.json')
    if manifest.get('inputs')!=inputs:raise ValueError('saved_R49_original_input_order_changed')
    paths={'predictions':members(run/'predictions'/OLD_ARM,{r['question_id'] for r in inputs},'saved_R49_predictions')}
    adapted,predictions,_=adapt_old(inputs,run,paths)
    stops={q:p.get('status') for q,p in predictions.items() if str(p.get('status','')).startswith('repeated_')}
    return adapted,{'raw_archive_only':True,'private_R49_score_invoked':False,'repeated_no_progress_by_saved_status':stops}


def tool_attempt_accounting(run, tools, active_keys):
    root=run/'services/tool_cache'
    folders={p.name:p for p in root.iterdir() if p.is_dir()} if root.exists() else {}
    if set(folders)!=active_keys:raise ValueError('orphan_or_unknown_tool_attempt_requires_specific_preserved_recovery')
    physical=[]
    for key,folder in sorted(folders.items()):
        if any(not (folder/n).is_file() for n in ('request.json','started.json','result.json')):raise ValueError('unclosed_R50_tool_attempt')
        result=read(folder/'result.json');request=read(folder/'request.json');started=read(folder/'started.json')
        failure=tool_failure_reason(result)
        if failure:
            selections=[v for v in tools if v.get('cache_key')==key]
            if not selections:raise ValueError('failed_active_R50_backend_without_delivery')
            for selected in selections:
                qid=selected['question_id']
                presented=[v for v in read(run/'predictions'/ARM/(qid+'.json')).get('observations',[]) if v.get('cache_key')==key]
                if not presented:raise ValueError('failed_selected_backend_not_observed_by_main')
                for value in presented:validate_delivered_failure(run,qid,value,reader=read)
        identity=result.get('identity',{})
        if (started.get('identity')!=identity or started.get('automatic_retry') is not False
            or request.get('backend')!=result.get('backend') or request.get('args')!=identity.get('args')
            or (not failure or result.get('original_image')) and request.get('image')!=result.get('original_image')):raise ValueError('actual_R50_tool_request_binding_changed')
        if request['tool']=='xray_phrase_grounding' and not failure:phrase_guarded_backend(run,key,result)
        physical.append(result)
    failed,history=tool_recovery_attempts(run,read)
    return {'physical':physical+failed,'healthy':sum(not tool_failure_reason(v) for v in physical),
      'failed':len(failed)+sum(bool(tool_failure_reason(v)) for v in physical),'technical_recovery_history':history,
      'terminal_tool_failures_delivered_without_retry':sum(bool(tool_failure_reason(v)) for v in physical)}


def resources(run, receipts, tools, attempts):
    if {p.name for p in (run/'services/calls').iterdir() if p.is_dir()}-{'R50-AGENT','R50-META'}:raise ValueError('unexpected_R50_paid_arm')
    meta=[v for folder in (run/'services/calls/R50-META').glob('*') if folder.is_dir() for v in closed_calls(folder)]
    embeds=[]
    for folder in sorted((run/'services/embeddings').glob('*')):
        if not folder.is_dir():continue
        if any(not (folder/n).is_file() for n in ('request.json','started.json','response.json','result.json')):raise ValueError('unclosed_R50_embedding')
        value=read(folder/'result.json')
        if value.get('error') or value.get('response_received') is not True:raise ValueError('failed_R50_embedding')
        embeds.append(value)
    embedding={'requests':len(embeds),'successful_responses':len(embeds),
      'returned_models':sorted({v['model_returned'] for v in embeds if v.get('model_returned')}),
      'total_tokens':sum((v.get('usage') or {}).get('total_tokens',0) or 0 for v in embeds),
      'usage_unknown_count':sum(v.get('usage') is None for v in embeds),
      'usage_cost_cny_proxy_known':str(sum((Decimal(str(v['settlement']['charged_cny'])) for v in embeds if v.get('settlement',{}).get('charged_cny') is not None),Decimal(0))),
      'cost_unknown_count':sum(v.get('settlement',{}).get('charged_cny') is None for v in embeds),
      'elapsed_seconds_known':sum(v.get('elapsed_s') or 0 for v in embeds),
      'elapsed_unknown_count':sum(v.get('elapsed_s') is None for v in embeds),'provider_invoice':False}
    names=('medgemma','llava_rad','chest_xray_expert','llava_med_qa','xray_phrase_grounding','medvlm_r1')
    physical=attempts['physical'];per_tool={}
    for name in names:
        selected=[v for v in tools if v.get('tool')==name];fresh=[v for v in physical if v.get('backend')==name]
        per_tool[name]={'selected_questions':len({v['question_id'] for v in selected}),
          'question_ids':sorted({v['question_id'] for v in selected}),'logical_calls':len(selected),
          'cache_hits':sum(v.get('cache_hit') is True for v in selected),'fresh_backend_attempts':len(fresh),
          'actual_generate_events':sum(e.get('kind')=='generate' for v in fresh for e in v.get('actual_model_events',[])),
          'failed_backend_attempts':sum(tool_failure_reason(v) is not None for v in fresh),
          'backend_elapsed_seconds_known':sum(v.get('elapsed_s') or 0 for v in fresh),
          'backend_compute_seconds_known':sum(v.get('backend_compute_seconds') or 0 for v in fresh),
          'hardware_cost_unknown':bool(fresh),'clinical_verification_claim':False}
    # Actual prescreen requests, not retrieval hits inferred after the fact.
    screens=[]
    screen_calls={p.name for p in (run/'services/calls/R50-META').glob('screen_*') if p.is_dir()}
    events={p.stem:p for p in (run/'prescreen_events').glob('*.json')}
    if screen_calls!={'screen_'+q for q in events}:raise ValueError('actual_prescreen_request_event_membership')
    from run_cxr_action_r41 import parse
    for q,path in sorted(events.items()):
        event=read(path);calls=closed_calls(run/'services/calls/R50-META'/('screen_'+q))
        if len(calls)!=1:raise ValueError('one_actual_prescreen_request_required')
        messages=read(calls[0][0]/'request.json')['messages']
        payload=json.loads(messages[-1]['content'][0]['text']);actual=payload['candidates'];ids=[v['id'] for v in actual]
        chosen=parse(response_text(calls[0][0]))['ids'];ctx=read(run/'contexts'/(q+'.json'))
        if (not ids or event['input_pool_ids']!=ids or event['input_pool_count']!=len(ids)
            or event['returned_ids']!=chosen or event['returned_count']!=len(chosen)
            or event['all_rejected'] is not (not bool(chosen))
            or not {v['id'] for v in ctx['selected_skills']}<=set(chosen)):
            raise ValueError('actual_prescreen_before_after_or_injection_changed')
        screens.append(event)
    lifecycle=Counter();branches=Counter();credits=[]
    for folder in sorted((run/'windows').glob('*')):
        if not folder.is_dir():continue
        event=read(folder/'events.json')
        for value in event['write']:
            if value.get('operation'):lifecycle[value['operation']]+=1
        for value in event['govern']:lifecycle[value[0]]+=1
        credits+=event['credit']
    for value in read(run/'final_repo.json')['skills'].values():branches[value['c']['branch']]+=1
    agent_values=[v for calls in receipts.values() for v in calls]
    starts=[utc(v[1]['utc']) for v in agent_values+meta];ends=[utc(v[2]['utc']) for v in agent_values+meta]
    return {'agent':receipt_resources(agent_values),'R50_META':receipt_resources(meta),'embedding':embedding,
      'tools':{'logical_calls':len(tools),'cache_hits':sum(v.get('cache_hit') is True for v in tools),
        'fresh_backend_attempts':len(physical),'healthy_backend_attempts':attempts['healthy'],
        'failed_backend_attempts':attempts.get('failed',0),'unknown_backend_attempts':0,
        'backend_elapsed_seconds_known':sum(v.get('elapsed_s') or 0 for v in physical),
        'backend_compute_seconds_known':sum(v.get('backend_compute_seconds') or 0 for v in physical),
        'hardware_cost_unknown':bool(physical),'per_tool':per_tool},
      'prescreen':{'requests':len(screens),'input_candidates':sum(v['input_pool_count'] for v in screens),
        'returned_candidates':sum(v['returned_count'] for v in screens),'all_rejected_questions':sum(v['all_rejected'] for v in screens),
        'events':screens},
      'Skill_lifecycle':{'events':dict(lifecycle),'final_branches':{k:branches[k] for k in ('general','task_level','action_level')},'credit_events':credits},
      'request_span_seconds':(max(ends)-min(starts)).total_seconds() if starts and ends else None,
      'request_span_not_total_job_or_provider_billing_time':True,
      'new3_health_probe_cost_time_excluded_from_production_totals':True,
      'technical_recovery_history':attempts.get('technical_recovery_history',[]),
      'old_R49_failure_registrations_imported':False,'uniform_MAIRA_EOS_control_from_start':True}


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
    generation_completion(run)
    manifest = read(run/'manifest.json')
    if manifest.get('inputs') != inputs or [item['question_id'] for item in manifest['order']] != ids:
        raise ValueError('manifest_semantic_input_order_changed')
    # Do not open complete.json here: its final_repo is a learned label-bearing
    # artifact. Its existence is sufficient until reference-free adaptation ends.
    if not (run/'complete.json').is_file():
        raise ValueError('completion_record_required')
    paths = {name: members(run/name/(ARM if name == 'predictions' else ''), set(ids), name)
             for name in ('predictions', 'contexts', 'steps', 'prediction_events', 'feedback')}
    agent = run/'services/calls/R50-AGENT'
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
        validate_prediction_failures(run,qid,prediction,reader=read)
        calls = closed_calls(run/'services/calls/R50-AGENT'/qid)
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
            selection_dir = run/'services/tool_selections/R50-AGENT'/qid
            selections = sorted(selection_dir.glob('*.json'), key=lambda p: int(p.stem))
            if [int(path.stem) for path in selections] != list(range(1, len(selections)+1)) or len(selections) != pred['tool_calls']:
                raise ValueError('actual_tool_count_mismatch')
            for path in selections:
                selection = read(path)
                if tool_failure_reason(selection):
                    matches=[value for value in pred.get('observations',[]) if value.get('cache_key')==selection.get('cache_key')
                             and value.get('failure_observation',{}).get('selection_ordinal')==int(path.stem)]
                    if len(matches)!=1:raise ValueError('failed_tool_without_exact_main_observation')
                    validate_delivered_failure(run,qid,matches[0],reader=read)
                key = selection.get('cache_key')
                cache_root = (run/'services/tool_cache').resolve()
                cache = (cache_root/str(key)).resolve()
                if (not key or not cache.is_relative_to(cache_root)
                        or not (cache/'started.json').is_file() or not (cache/'result.json').is_file()):
                    raise ValueError('unclosed_selected_tool_cache')
                backend = read(cache/'result.json')
                if bool(tool_failure_reason(backend))!=bool(tool_failure_reason(selection)) or any(selection.get(k) != v for k, v in backend.items()):
                    raise ValueError('tool_cache_health_or_semantics_changed')
                cache_keys.add(key)
                tool_values.append(dict(selection,question_id=qid))
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

def score(data, run, references, dataset, *, r47_frozen=None, r47_run=None, r49_run=None):
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
    if r49_run is None:raise ValueError('saved_R49_raw_comparator_required')
    comparisons['R49_online_GT_Skill'],r49_provenance=adapt_saved_r49(inputs,r49_run)
    # Reference-free adaptation of EVERY compared raw arm is now complete.
    hit, windows, tools, attempts = check_semantics(inputs, manifest, run, paths, predictions, receipts)
    resource = resources(run,receipts,tools,attempts)
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
    if counts['R49_online_GT_Skill']!={'chexbench':465,'slake':113,'vqarad':97}[dataset]:raise ValueError('fixed_R49_saved_common_metric_count_changed')
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
                                  'Historical differences combine six tools and applicability gate plus onlineGT, executor/call budgets, prompts, inherited EOS policy, sampling and time.',
                                  'No contemporaneous no-Skill control; same-model adoption is not a causal or clinical verification.',
                                  'Datasets are reported separately; SLAKE overlap and VQA paraphrases preclude pooling independent cases.']}
    summary.update(R49_saved_comparator_provenance=r49_provenance,
      native_generation_completion=generation_completion(run),
      R50_combined_changes=manifest.get('r50_method_changes'),
      R50_uniform_inherited_controls=manifest.get('r50_baseline_controls'),
      repeated_no_progress_by_saved_status={q:p.get('status') for q,p in predictions.items() if str(p.get('status','')).startswith('repeated_')})
    groups={}
    for label,field in [('same_image_followup','same_image_hit'),('skill_injected','skill_hit')]:
        groups[label]={}
        for flag in (False,True):
            selected=[d for d in detail if d[field] is flag]
            groups[label][str(flag)]={'n':len(selected),'correct':sum(d['arms'][ARM]['aligned_correct'] for d in selected),'descriptive_not_randomized':True}
    summary['descriptive_groups']=groups
    return summary, detail

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('data', 'run', 'references', 'out'):
        parser.add_argument('--'+name, required=True, type=Path)
    parser.add_argument('--dataset', required=True, choices=EXPECTED)
    parser.add_argument('--r47-frozen', type=Path); parser.add_argument('--r47-run', type=Path); parser.add_argument('--r49-run', required=True, type=Path)
    args = parser.parse_args()
    if args.out.exists():
        raise ValueError('new_empty_score_output_required')
    summary, detail = score(args.data, args.run, args.references, args.dataset,
                            r47_frozen=args.r47_frozen, r47_run=args.r47_run, r49_run=args.r49_run)
    save_once(args.out/'summary.json', summary); save_once(args.out/'per_question.json', detail)
    print(json.dumps(summary, ensure_ascii=False, indent=2))

if __name__=='__main__':main()
