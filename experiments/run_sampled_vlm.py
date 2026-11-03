"""Independent, label-free multi-model samples with immutable per-sample recovery.

One directory contains one frozen model/prompt/temperature configuration. Phase
orchestration, label access, votes and model selection belong to separate programs.
No successful or ambiguous paid request is repeated, including across restarts.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from decimal import Decimal
import json
import os
from pathlib import Path
import re
import sys
import time

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from run_direct_vlm import SYSTEM_PROMPT, now, read, read_lines, write
from official_gain_answer_scoring import explicit_answer
from v12_evidence import build_images, multimodal_content, question_parts

TOKEN_PLAN_FLASH_MODELS = {'deepseek-v4.1-flash-1017', 'qwen3.8-flash'}
TOKEN_PLAN_MODELS = {'qwen3.7-plus'} | TOKEN_PLAN_FLASH_MODELS
MODELS = {'qwen3-vl-plus', 'qwen3.8-max-0902', 'gpt-4o'} | TOKEN_PLAN_MODELS
TOKEN_PLAN_BASE_URL = 'https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1'
TOKEN_PLAN_ACCOUNTING_NOTE = (
    'Token Plan usage is measured in provider Credits; these CNY rates are a conservative '
    'budget proxy, not a provider invoice or Credits-to-CNY conversion. '
    'This runner never purchases additional quota automatically.')
TOKEN_PLAN_FLASH_ACCOUNTING_NOTE = (
    'Inherited 4/12 CNY-per-million bookkeeping rates are a budget proxy only: '
    'they are not actual provider prices, a verified upper bound, or a Credits-to-CNY conversion. '
    'Token Plan Credits remain authoritative. The original cumulative budget cap is unchanged; '
    'this runner never purchases additional quota automatically.')
VARIANTS = {'answer', 'cot', 'think', 'text_only'}
ROW_FIELDS = {'question_id', 'case_id', 'question', 'images', 'figure_labels'}
FAILURE_POLICY = {
    'version': 'sample-failure-v1', 'consecutive_failed_samples_limit': 5,
    'sample_rejections': '400/413/422 except identified systemic configuration errors become missing',
    'unknown_outcomes': 'missing, never resend; the original ledger conservatively retains the reservation',
    'retry': 'only explicit non-quota HTTP 429, at most one technical retry within all existing limits',
    'immediate_stop': 'authentication/permission/model/endpoint/quota/configuration/identity/ledger/local failures',
    'reset_streak': 'a successfully processed provider response, including an unparsed answer',
    'operator_resume': 'explicit one-use stop-event acknowledgement may continue only unfinished samples; prior terminals and money protections remain',
    'accounting': 'error reservation is a conservative budget charge, not a provider invoice',
}
COT_PROMPT = '''You answer medical image multiple-choice questions. Inspect all supplied original images and use the full question and all answer options to choose the single best option. Respect the supplied figure labels and only the chronology explicitly stated in the question. Give a concise evidence summary of at most 150 words: relevant findings by region and side, and brief support or conflict for the answer options. End with Answer: <one legal option letter> on its own last line. Give the best option even when details remain uncertain. Do not provide a long reasoning trace.'''


def parse_answer(text, legal):
    """New protocol: last explicit Answer line, never search the explanation.

    The older experiments' conservative conflicting-label parser is untouched.
    Ambiguous final alternatives and explicit refusals remain unparsed.
    """
    if not isinstance(text, str):
        return {'answer': None, 'status': 'unparsed', 'parser_rule': 'non_text'}
    clean = text.replace('**', '').replace('__', '').replace('`', '').strip()
    labelled = [line.strip() for line in clean.splitlines()
                if re.match(r'^(?:Return\s+)?(?:Final\s+)?Answer\s*:', line.strip(), re.I)]
    if labelled:
        value = re.sub(r'^(?:Return\s+)?(?:Final\s+)?Answer\s*:\s*', '', labelled[-1], flags=re.I)
        match = re.match(r'^\(?([A-Z])\)?(?=$|[\s).,:;—–-])', value, re.I)
        answer = match[1].upper() if match and match[1].upper() in legal else None
        # "Answer: A or B"/"A/B" is not one committed choice.
        if answer and re.match(r'^\(?[A-Z]\)?[).:]?\s*(?:/|or\b|and\b|,\s*[A-Z]\b)', value, re.I):
            answer = None
        rule = 'last_explicit_answer' if answer else 'last_explicit_non_option'
    else:
        answer, rule = explicit_answer(clean, legal)
    return {'answer': answer, 'status': 'completed' if answer else 'unparsed', 'parser_rule': rule}


def frozen_write(path, value):
    path = Path(path)
    if path.exists():
        if read(path) != value:
            raise ValueError('immutable_record_conflict:' + path.name)
    else:
        write(path, value)


@contextmanager
def exclusive_lock(path):
    """Process-lifetime lock, not a stale PID sentinel or byte-drift monitor."""
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a+b') as handle:
        if os.name == 'nt':
            import msvcrt
            if handle.seek(0, 2) == 0:
                handle.write(b'0'); handle.flush()
            handle.seek(0); msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            try: yield
            finally:
                handle.seek(0); msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            try: yield
            finally: fcntl.flock(handle, fcntl.LOCK_UN)


def profile_for(cfg):
    from provider_profile import ProviderProfile
    class SamplingProfile(ProviderProfile):
        def identity_ok(self, returned):
            if self.model == 'gpt-4o':
                # The requested name is a provider alias, not a promised snapshot.
                # Prefix matching would also accept gpt-4o-mini and is forbidden.
                return isinstance(returned, str) and (
                    returned == 'gpt-4o' or re.fullmatch(r'gpt-4o-\d{4}-\d{2}-\d{2}', returned) is not None)
            if self.model == 'qwen3.7-plus':
                return isinstance(returned, str) and (
                    returned == 'qwen3.7-plus' or
                    re.fullmatch(r'qwen3\.7-plus-\d{4}-\d{2}-\d{2}', returned) is not None)
            if self.model == 'deepseek-v4.1-flash-1017':
                # A requested dated snapshot must not silently become another alias.
                return returned == 'deepseek-v4.1-flash-1017'
            if self.model == 'qwen3.8-flash':
                return isinstance(returned, str) and (
                    returned == 'qwen3.8-flash' or
                    re.fullmatch(r'qwen3\.8-flash-\d{4}-\d{2}-\d{2}', returned) is not None)
            return super().identity_ok(returned)
    p = cfg['profile']
    required = {'base_url', 'identity_prefixes', 'input_cny_per_million',
                'output_cny_per_million', 'price_basis', 'max_input_tokens', 'max_output_tokens'}
    if not required <= set(p) or not p['price_basis'] or not p['identity_prefixes']:
        raise ValueError('explicit_cost_and_identity_profile_required')
    if not str(p['base_url']).startswith('https://') or '@' in p['base_url']:
        raise ValueError('https_provider_endpoint_without_credentials_required')
    rates = [Decimal(str(p[k])) for k in ('input_cny_per_million', 'output_cny_per_million')]
    if any(not x.is_finite() or x <= 0 for x in rates):
        raise ValueError('positive_explicit_rates_required')
    if any(type(p[k]) is not int or p[k] <= 0 for k in ('max_input_tokens', 'max_output_tokens')):
        raise ValueError('positive_explicit_token_bounds_required')
    if cfg['model'] == 'gpt-4o':
        if p['max_input_tokens'] > 120000 or p['max_output_tokens'] > 8192:
            raise ValueError('gpt4o_context_requires_120000_input_and_8192_output_ceiling')
        if p['identity_prefixes'] != ['gpt-4o']:
            raise ValueError('gpt4o_exact_family_identity_required')
    price_basis = p['price_basis']
    if cfg['model'] == 'qwen3.7-plus':
        if p['base_url'] != TOKEN_PLAN_BASE_URL:
            raise ValueError('qwen37_token_plan_endpoint_required')
        if p['identity_prefixes'] != ['qwen3.7-plus']:
            raise ValueError('qwen37_exact_family_identity_required')
        if TOKEN_PLAN_ACCOUNTING_NOTE not in price_basis:
            price_basis += ' ' + TOKEN_PLAN_ACCOUNTING_NOTE
    if cfg['model'] in TOKEN_PLAN_FLASH_MODELS:
        if p['base_url'] != TOKEN_PLAN_BASE_URL:
            raise ValueError('token_plan_endpoint_required')
        if p['identity_prefixes'] != [cfg['model']]:
            raise ValueError('token_plan_exact_family_identity_required')
        if TOKEN_PLAN_FLASH_ACCOUNTING_NOTE not in price_basis:
            price_basis += ' ' + TOKEN_PLAN_FLASH_ACCOUNTING_NOTE
    return SamplingProfile(name=cfg['model'], base_url=p['base_url'], model=cfg['model'],
        identity_prefixes=tuple(p['identity_prefixes']), input_cny_per_million=rates[0],
        output_cny_per_million=rates[1], price_basis=price_basis,
        max_input_tokens=p['max_input_tokens'], max_output_tokens=p['max_output_tokens'],
        supports_vision=True, notes='Frozen sampling-phase profile; costs are disclosed accounting rates.')


def validate_cfg(cfg):
    if cfg['model'] not in MODELS or cfg['prompt_variant'] not in VARIANTS:
        raise ValueError('unsupported_model_or_variant')
    expected_slot = ('token_plan' if cfg['model'] in TOKEN_PLAN_MODELS
                     else 'apiyi' if cfg['model'] == 'gpt-4o' else 'dashscope')
    if cfg.get('credential_slot') != expected_slot:
        raise ValueError('explicit_model_provider_credential_slot_required')
    if not re.fullmatch(r'[A-Za-z0-9_.-]{1,64}', cfg['run_id']):
        raise ValueError('unsafe_run_id')
    if type(cfg['samples']) is not int or not 1 <= cfg['samples'] <= 15:
        raise ValueError('samples_must_be_1_to_15')
    if not 0 <= cfg['temperature'] <= 2 or not 0 < cfg['top_p'] <= 1:
        raise ValueError('invalid_sampling_parameters')
    for field in ('max_requests', 'max_extra_requests', 'global_max_requests', 'global_max_extra_requests'):
        if type(cfg[field]) is not int or cfg[field] < 0:
            raise ValueError('explicit_nonnegative_request_bounds_required')
    if cfg.get('max_attempts_per_sample', 2) not in (1, 2):
        raise ValueError('at_most_one_technical_retry_per_sample')
    profile = profile_for(cfg)
    if not 0 < cfg['max_output_tokens'] <= profile.max_output_tokens:
        raise ValueError('output_ceiling_must_fit_profile')
    extra = cfg.get('extra_body', {})
    if set(extra) - {'enable_thinking', 'thinking_budget', 'vl_high_resolution_images', 'reasoning_effort'}:
        raise ValueError('unknown_extra_body_parameter')
    if cfg['prompt_variant'] == 'think' and cfg['model'].startswith('qwen') and extra.get('enable_thinking') is not True:
        raise ValueError('think_variant_requires_explicit_enable_thinking')
    if cfg['model'].startswith('qwen') and cfg['prompt_variant'] != 'think' and extra.get('enable_thinking') is not False:
        raise ValueError('pin_qwen_non_thinking_explicitly')
    if cfg['model'] in TOKEN_PLAN_FLASH_MODELS and (
        cfg['prompt_variant'] == 'think' or extra.get('enable_thinking') is not False
    ):
        raise ValueError('token_plan_flash_non_thinking_required')
    if cfg['model'] == 'gpt-4o':
        if extra or cfg['prompt_variant'] == 'think':
            raise ValueError('gpt4o_no_provider_thinking_or_highres_parameters')
        if cfg['temperature'] not in (.2, .7) or cfg['top_p'] != .95:
            raise ValueError('gpt4o_fixed_baseline_or_sampling_parameters_required')
    if bool(cfg.get('high_resolution')) != bool(extra.get('vl_high_resolution_images', False)):
        raise ValueError('high_resolution_flag_must_match_actual_payload')
    if (cfg.get('high_resolution') or cfg['prompt_variant'] == 'think') and not (
        cfg.get('capability_confirmed') or cfg.get('capability_smoke')):
        raise ValueError('two_question_capability_smoke_required_first')
    return profile


def images_for(row, image_root, figure_labels=False):
    images = build_images(row, image_root)
    explicit = row.get('figure_labels')
    if explicit is not None:
        if not isinstance(explicit, list) or len(explicit) != len(images) or any(not isinstance(x, str) for x in explicit):
            raise ValueError('invalid_figure_binding')
        for image, label in zip(images, explicit):
            if label:
                image['figure_label'] = label
    if figure_labels:
        # Move only labels actually named in the question; unknowns keep input order.
        question = row['question'].lower()
        def order(pair):
            i, image = pair
            label = image['figure_label']
            if not re.fullmatch(r'(?i)(?:Figure|Fig\.?)\s*\d+[a-z]?', label):
                return (len(question) + i, i)
            term = re.sub(r'(?i)^(?:Figure|Fig\.?)\s*', '', label)
            match = re.search(r'(?i)\b(?:Figure|Fig\.?)\s*' + re.escape(term) + r'\b', question)
            return (match.start() if match else len(question) + i, i)
        images = [x for _, x in sorted(enumerate(images), key=order)]
    return images


def request_for(row, cfg):
    system = COT_PROMPT if cfg['prompt_variant'] == 'cot' else SYSTEM_PROMPT
    if cfg['prompt_variant'] == 'text_only':
        return [{'role':'system', 'content':system}, {'role':'user', 'content':row['question']}], []
    images = images_for(row, Path(cfg['root']) / cfg['image_root'], cfg.get('figure_labels', False))
    content = multimodal_content(row['question'], images)
    if cfg.get('figure_labels'):
        # Plain figure text is immediately before its bound image; metadata retained.
        result = [content[0]]
        for i, image in enumerate(images):
            result.extend([content[1+2*i], {'type':'text', 'text':image['figure_label'] + ':'}, content[2+2*i]])
        content = result
    return [{'role':'system', 'content':system}, {'role':'user', 'content':content}], images


def prepare(cfg, out):
    validate_cfg(cfg)
    rows = read_lines(Path(cfg['root']) / cfg['input'])
    if not rows or len({r.get('question_id') for r in rows}) != len(rows):
        raise ValueError('nonempty_unique_question_ids_required')
    for row in rows:
        if set(row) - ROW_FIELDS or not {'question_id', 'question', 'images'} <= set(row):
            raise ValueError('inference_input_has_forbidden_or_missing_fields')
        if not re.fullmatch(r'[A-Za-z0-9_-]+', row['question_id']):
            raise ValueError('unsafe_question_id')
        question_parts(row['question'])
    if cfg.get('capability_smoke') and len(rows) != 2:
        raise ValueError('capability_smoke_requires_two_questions')
    if cfg['max_requests'] < len(rows)*cfg['samples']:
        raise ValueError('normal_samples_exceed_phase_request_limit')
    # No repeated image hash scans. The actual request saves native byte payloads.
    frozen_write(out/'protocol.json', dict(cfg, system_prompt=COT_PROMPT if cfg['prompt_variant']=='cot' else SYSTEM_PROMPT,
        implementation_commit=os.environ.get('MEDRAX_CODE_COMMIT', 'unrecorded'),
        labels_loaded_by_generation=False, parser_version='sampled-last-explicit-answer-v1', failure_policy=FAILURE_POLICY))
    frozen_write(out/'selection.json', {'planned_n':len(rows), 'rows':rows})
    return rows


def claim_global(cfg, request_id, extra, reserve=None):
    """Check the shared limit before a monetary reservation under one lock.

    ``reserve`` is called only when the request fits. There is no unprotected
    window in which another phase can consume the final request allowance.
    """
    path = Path(cfg['root'])/cfg['global_request_counter']
    with exclusive_lock(str(path)+'.lock'):
        state = read(path) if path.exists() else {'request_ids':[], 'extra_request_ids':[],
            'max_requests':cfg['global_max_requests'], 'max_extra_requests':cfg['global_max_extra_requests']}
        if (state['max_requests'], state['max_extra_requests']) != (cfg['global_max_requests'], cfg['global_max_extra_requests']):
            raise ValueError('global_request_policy_conflict')
        if request_id in state['request_ids']:
            raise ValueError('global_request_id_already_claimed_no_reissue')
        if len(state['request_ids']) >= state['max_requests'] or (extra and len(state['extra_request_ids']) >= state['max_extra_requests']):
            raise ValueError('global_request_limit_reached')
        reservation = reserve() if reserve is not None else None
        state['request_ids'].append(request_id)
        if extra: state['extra_request_ids'].append(request_id)
        try:
            write(path, state)
        except Exception as exc:
            # The caller knows no HTTP request has yet been sent and records
            # the original ledger's conservative unsent settlement explicitly.
            exc.unsent_reservation = reservation
            raise
        return reservation


def safe_error(exc, key=''):
    message = str(exc).replace(key, '[REDACTED]') if key else str(exc)
    message = re.sub(r'(?i)(?:Bearer\s+\S+|sk-[A-Za-z0-9_-]{12,})', '[REDACTED]', message)
    return message[:1600]


def failure_details(exc, key=''):
    """Classify execution failure without persisting arbitrary provider bodies.

    An HTTP error is not evidence of zero usage. All error accounting continues
    through the unchanged ledger, and 408/5xx may follow completed generation.
    """
    status = getattr(exc, 'status_code', None)
    status = status if type(status) is int else None
    body = getattr(exc, 'body', None)
    body = body.get('error', body) if isinstance(body, dict) else {}
    if not isinstance(body, dict):body = {}
    identifiers = {}
    for field in ('code', 'type', 'param'):
        value = body.get(field)
        if (isinstance(value, str) and re.fullmatch(r'[A-Za-z0-9_.\[\]-]{1,100}', value)
                and not (key and key in value) and not re.match(r'(?i)^(?:sk[-_]|bearer)',value)):
            identifiers['provider_error_' + field] = value
    code = str(identifiers.get('provider_error_code', '')).lower()
    param = str(identifiers.get('provider_error_param', '')).lower()
    error_type = str(identifiers.get('provider_error_type', '')).lower()
    provider_message = body.get('message')
    # DashScope reports account arrears as HTTP 400, including Arrearage in
    # code/type and an overdue-payment documentation link. This is systemic,
    # not a rejected image/sample. Preserve the existing billing guard/category.
    account_arrears = any(marker in value for value in (code, error_type)
                          for marker in ('arrearage', 'overdue-payment', 'overdue_payment'))
    if isinstance(provider_message, str):
        account_arrears = account_arrears or bool(re.search(r'\boverdue[-_ ]payment\b', provider_message, re.I))
    quota = any(x in code for x in ('insufficient_quota','quota_exceeded','insufficient_balance',
        'insufficient_funds','credit_balance','billing_hard_limit','balance_not_enough','account_deactivated',
        'spend_limit','usage_limit')) or account_arrears
    configuration = any(x in code for x in ('model_not_found','model_not_exist','invalid_model',
        'unsupported_model','unsupported_parameter','unsupported_param','invalid_parameter','invalid_api_key',
        'invalid_request_format','invalid_request_schema')) or param in {
        'model','temperature','top_p','max_tokens','max_completion_tokens','stream','stream_options',
        'enable_thinking','thinking_budget','vl_high_resolution_images','reasoning_effort'}
    # The provider explicitly rejects one unavailable media input under its
    # generic invalid-parameter code. This exact response is sample-local; it
    # does not authorize a resend or establish zero billable usage.
    media_download_timeout = (status == 400 and code == 'invalid_parameter_error'
        and error_type == 'invalid_request_error' and not param
        and isinstance(provider_message, str)
        and ' '.join(provider_message.split()).casefold() == 'download multimodal file timed out')
    kind, fatal, retry = 'local_execution_failure', True, False
    if isinstance(exc, RuntimeError) and str(exc) == 'returned_model_identity_mismatch':
        kind = 'model_identity_mismatch'
    elif quota:
        kind = 'provider_quota_or_balance'
    elif media_download_timeout:
        kind, fatal = 'sample_rejected', False
    elif configuration:
        kind = 'provider_configuration'
    elif status in {401,403}:
        kind = 'authentication_or_permission'
    elif status in {404,405}:
        kind = 'endpoint_or_model'
    elif status in {400,413,422}:
        kind, fatal = 'sample_rejected', False
    elif status == 429:
        kind, fatal, retry = 'rate_limited', False, True
    elif status in {408,409} or (status is not None and 500 <= status < 600):
        kind, fatal = 'unknown_provider_outcome', False
    elif isinstance(exc, (TimeoutError, ConnectionError)) or type(exc).__name__ in {
        'APITimeoutError','APIConnectionError','InterruptedUnknown'}:
        kind, fatal = 'unknown_provider_outcome', False
    return dict(failure_class=kind, fatal=fatal, retryable=retry, status_code=status,
                billing_outcome='unknown_conservative_reservation_not_invoice', **identifiers)


def terminal_failure(terminal):
    """Read saved policy decisions; never alter terminal or attempt records."""
    attempts = terminal.get('attempts', [])
    last = attempts[-1] if attempts else {}
    fatal = terminal.get('fatal_reason')
    if last.get('settlement_error'):fatal = 'ledger_settlement_error'
    if last.get('fatal'):fatal = last.get('failure_class', 'fatal_execution_failure')
    if last.get('error_type') == 'RuntimeError' and 'identity' in last.get('error_message', ''):
        fatal = 'model_identity_mismatch'
    failed = terminal.get('status') == 'request_failed' or bool(fatal)
    return failed, fatal


def failure_prefix(rows, samples, records, out):
    """Restore the streak, respecting only explicit immutable acknowledgements."""
    consecutive = 0
    for row in rows:
        for sample in range(1,samples+1):
            terminal = records.get((row['question_id'],sample))
            if terminal is None:return consecutive, None
            failed, fatal = terminal_failure(terminal)
            consecutive = consecutive + 1 if failed else 0
            if fatal or consecutive >= FAILURE_POLICY['consecutive_failed_samples_limit']:
                reason = fatal or 'consecutive_failed_samples_limit'
                suffix = re.sub(r'[^A-Za-z0-9_.-]', '_', reason)[:24]
                event = {'event_id':f"{row['question_id']}__s{sample}__{suffix}",
                    'question_id':row['question_id'],'sample_index':sample,'reason':reason,
                    'consecutive_failed_samples':consecutive,'occurred_utc':terminal.get('ended_utc'),
                    'failure_policy_version':FAILURE_POLICY['version']}
                acknowledged = out/'stop_acknowledgements'/(event['event_id']+'.json')
                if acknowledged.exists():
                    ack = read(acknowledged)
                    if ack.get('stop_event') != event:
                        raise ValueError('stop_acknowledgement_event_conflict')
                    consecutive = 0
                else:return consecutive, event
    return consecutive, None


def invoke(client, payload, attempt_dir):
    if not payload.get('stream'):
        response = client.chat.completions.create(**payload)
        raw = response.model_dump(mode='json')
    else:
        chunks, content, reasoning, model, finish, usage = [], [], [], None, None, None
        stream = client.chat.completions.create(**payload)
        # Save observable chunks incrementally; a crash leaves an ambiguous attempt
        # that will NOT be charged or sent twice by this program.
        with (attempt_dir/'stream_chunks.jsonl').open('x', encoding='utf-8') as handle:
            for chunk in stream:
                item = chunk.model_dump(mode='json'); chunks.append(item)
                handle.write(json.dumps(item, ensure_ascii=False)+'\n'); handle.flush()
                model = item.get('model') or model; usage = item.get('usage') or usage
                for choice in item.get('choices', []):
                    delta = choice.get('delta') or {}
                    if delta.get('content'): content.append(delta['content'])
                    if delta.get('reasoning_content'): reasoning.append(delta['reasoning_content'])
                    finish = choice.get('finish_reason') or finish
        raw = {'model':model, 'choices':[{'message':{'role':'assistant', 'content':''.join(content),
            'reasoning_content':''.join(reasoning)}, 'finish_reason':finish}], 'usage':usage,
            'assembled_from_saved_stream':True, 'chunk_count':len(chunks)}
    frozen_write(attempt_dir/'response.json', raw)
    return raw


def recover_attempt(folder, legal, profile=None, parse_fn=None):
    parse_fn = parse_answer if parse_fn is None else parse_fn
    if (folder/'result.json').exists():
        return read(folder/'result.json')
    if not (folder/'started.json').exists():
        return None
    result = dict(read(folder/'started.json'), retryable=False, settlement=None, elapsed_s=None)
    if (folder/'response.json').exists():
        raw = read(folder/'response.json'); message = raw.get('choices',[{}])[0].get('message',{})
        result.update(response_received=True, raw_content=message.get('content'), usage=raw.get('usage'),
            reasoning_content=message.get('reasoning_content'), parsed=parse_fn(message.get('content'),legal),
            response_model=raw.get('model'), finish_reason=raw.get('choices',[{}])[0].get('finish_reason'),
            recovery='saved_response_reused_no_new_request',
            recovered_cost_note='Original ledger recovery determines charge; response usage is preserved without rewriting the ledger.')
        if profile is not None and not profile.identity_ok(raw.get('model')):
            result.update(error_type='RuntimeError', error_message='returned_model_identity_mismatch')
    else:
        result.update(response_received=False, error_type='InterruptedUnknown', recovery='unknown_paid_request_not_reissued',
            failure_class='unknown_provider_outcome', fatal=False,
            billing_outcome='unknown_conservative_reservation_not_invoice')
    frozen_write(folder/'result.json', result)
    return result


def run(args, cfg, out, adapter=None):
    """Execute samples with optional input/request/parser adaptation only.

    Adapters do not receive a client, ledger, request counter, or persistence
    callback. Request accounting, identity checks and recovery remain here.
    """
    if adapter is None:
        rows = prepare(cfg, out)
        parse_fn = parse_answer
    else:
        validate_cfg(cfg)
        rows = adapter.prepare(cfg, out)
        parse_fn = adapter.parse
    root = Path(cfg['root']); profile = profile_for(cfg)
    records = {}
    for row in rows:
        for sample in range(1,cfg['samples']+1):
            path = out/'checkpoints'/row['question_id']/f'sample_{sample}'/'terminal.json'
            if path.exists():
                value=read(path)
                if value['question_id']!=row['question_id'] or value['sample_index']!=sample:
                    raise ValueError('terminal_identity_conflict')
                records[row['question_id'],sample]=value
    starts=list((out/'checkpoints').glob('*/sample_*/attempt_*/started.json'))
    used=len(starts); extras=sum(p.parent.name!='attempt_1' for p in starts)
    planned=len(rows)*cfg['samples']
    # Reconstruct the serial prefix before opening any key/client/ledger. A
    # restart cannot erase four failures or bypass a previously reached stop.
    consecutive_failed, pending_stop = failure_prefix(rows,cfg['samples'],records,out)
    requested_ack = getattr(args,'acknowledge_stop',None)
    if requested_ack:
        if args.prepare_only:raise ValueError('prepare_cannot_acknowledge_stop')
        if pending_stop is None or requested_ack != pending_stop['event_id']:
            raise ValueError('acknowledgement_must_match_current_unacknowledged_stop')
        frozen_write(out/'stop_events'/(requested_ack+'.json'),pending_stop)
        frozen_write(out/'stop_acknowledgements'/(requested_ack+'.json'),
            {'stop_event':pending_stop,'acknowledged_utc':now(),
             'operator_action':'explicit_cli_acknowledgement_after_review',
             'effect':'continue_unfinished_samples_only_no_prediction_or_cost_rewrite'})
        consecutive_failed,pending_stop=failure_prefix(rows,cfg['samples'],records,out)
    def status(state, **extra):
        write(out/'status.json', dict(status=state,updated_utc=now(),planned_n=len(rows),planned_samples=planned,
            completed_n=sum(all((row['question_id'],i) in records for i in range(1,cfg['samples']+1)) for row in rows),
            completed_samples=len(records),requests_used=used,extra_requests_used=extras,model=cfg['model'],
            consecutive_failed_samples=consecutive_failed,**extra))
    def aggregate():
        text=''.join(json.dumps(records[row['question_id'],i],ensure_ascii=False)+'\n' for row in rows for i in range(1,cfg['samples']+1))
        target=out/'predictions.jsonl'
        if target.exists() and target.read_text(encoding='utf-8')!=text: raise ValueError('aggregate_conflict')
        if not target.exists():target.write_text(text,encoding='utf-8')
    if used>cfg['max_requests'] or extras>cfg['max_extra_requests']:
        raise ValueError('persistent_phase_request_limit_exceeded')
    if pending_stop:
        frozen_write(out/'stop_events'/(pending_stop['event_id']+'.json'),pending_stop)
        status('stopped',error=pending_stop['reason'],stop_event_id=pending_stop['event_id']);return 2
    if len(records)==planned:
        aggregate();status('generation_complete');return 0
    if args.prepare_only:
        status('prepared');print(json.dumps({'status':'prepared','planned_n':len(rows),'planned_samples':planned}));return 0
    cap=Decimal(str(cfg['cap_cny']))
    if not cfg.get('budget_authorization') or cap<=0:
        raise ValueError('concrete_user_budget_authorization_required')
    key=sys.stdin.readline().strip() if args.api_key_stdin else ''
    if not key:raise ValueError('missing_api_key_on_stdin')
    from openai import OpenAI
    from v12_ledger import V12ProviderLedger
    client=OpenAI(api_key=key,base_url=profile.base_url,max_retries=0,timeout=cfg['request_timeout_seconds'])
    inherit=root/cfg['inherit_ledger'] if cfg.get('inherit_ledger') else None
    with V12ProviderLedger(root/cfg['ledger'],profile,cap_cny=str(cap),inherit_ledger_path=inherit) as ledger:
        if not (out/'ledger_start.json').exists():write(out/'ledger_start.json',{'utc':now(),'committed_cny':str(cap-ledger.remaining),'cap_cny':str(cap)})
        def end_ledger():
            write(out/'ledger_final_summary.json',{'utc':now(),'run_increment_cny':str(cap-ledger.remaining-Decimal(read(out/'ledger_start.json')['committed_cny'])),
                'price_basis':profile.price_basis,'provider_invoice':False})
        for index,row in enumerate(rows,1):
            legal=question_parts(row['question'])[1] if adapter is None else adapter.legal(row)
            for sample in range(1,cfg['samples']+1):
                qid=row['question_id']
                if (qid,sample) in records:continue
                folder=out/'checkpoints'/qid/f'sample_{sample}'
                messages,images=request_for(row,cfg) if adapter is None else adapter.request(row,cfg,out)
                payload={'model':cfg['model'],'messages':messages,'temperature':cfg['temperature'],'top_p':cfg['top_p'],
                    'max_tokens':cfg['max_output_tokens'],'extra_body':cfg.get('extra_body',{}),'stream':cfg.get('stream',False)}
                if payload['stream']:payload['stream_options']={'include_usage':True}
                frozen_write(folder/'request.json',payload)
                frozen_write(folder/'image_metadata.json',{'images':[{k:v for k,v in im.items() if k!='path'} for im in images],
                    'native_bytes_sent':bool(images),'billed_image_tokens':'reported only when provider returns a distinct usage field'})
                terminal={'question_id':qid,'case_id':row.get('case_id'),'sample_index':sample,'model':cfg['model'],
                    'prompt_variant':cfg['prompt_variant'],'temperature':cfg['temperature'],'answer':None,'status':'request_failed',
                    'raw_response':None,'attempts':[],'started_utc':now()}
                stop=None
                for attempt_number in range(1,cfg.get('max_attempts_per_sample',2)+1):
                    attempt_dir=folder/f'attempt_{attempt_number}'
                    result=recover_attempt(attempt_dir,legal,profile,parse_fn=parse_fn)
                    if result is None:
                        if used>=cfg['max_requests'] or (attempt_number>1 and extras>=cfg['max_extra_requests']):
                            stop='phase_request_limit';break
                        request_id=f"sample:{cfg['run_id']}:{qid}:{sample}:{attempt_number}"
                        try:
                            # Reserve full configured input bound: no undocumented
                            # high-resolution image-token estimate can understate it.
                            reservation=claim_global(cfg,request_id,attempt_number>1, reserve=lambda: ledger.reserve(
                                request_id=request_id,estimated_input_tokens=profile.max_input_tokens,
                                max_output_tokens=cfg['max_output_tokens'],model=cfg['model'],
                                metadata={'question_id':qid,'sample':sample,'attempt':attempt_number,'phase':cfg['run_id']}))
                        except Exception as exc:
                            stop=type(exc).__name__+':'+safe_error(exc,key)
                            unsent = {'utc':now(),'error_type':type(exc).__name__,'message':safe_error(exc,key),'request_sent':False}
                            if getattr(exc, 'unsent_reservation', None) is not None:
                                try:
                                    unsent['settlement']=ledger.settle(exc.unsent_reservation,response_received=False,error_type='UnsentCounterWriteError')
                                    unsent['cost_note']='No request sent; the unchanged original ledger conservatively charges an error reservation in full.'
                                except Exception as settle_exc:
                                    unsent['settlement_error']=safe_error(settle_exc,key)
                            frozen_write(attempt_dir/'reserve_error.json',unsent)
                            break
                        result={'question_id':qid,'sample_index':sample,'ordinal':attempt_number,'request_id':request_id,
                            'started_utc':now(),'response_received':False,'retryable':False}
                        frozen_write(attempt_dir/'started.json',result);used+=1;extras+=int(attempt_number>1)
                        status('running',active_index=index,active_question=qid,active_sample=sample)
                        tick=time.monotonic();raw=None;usage=None;error=None
                        try:
                            raw=invoke(client,payload,attempt_dir);usage=raw.get('usage')
                            message=raw.get('choices',[{}])[0].get('message',{})
                            result.update(response_received=True,raw_content=message.get('content'),reasoning_content=message.get('reasoning_content'),
                                response_model=raw.get('model'),usage=usage,finish_reason=raw.get('choices',[{}])[0].get('finish_reason'),parsed=parse_fn(message.get('content'),legal))
                            if not profile.identity_ok(raw.get('model')):raise RuntimeError('returned_model_identity_mismatch')
                        except Exception as exc:
                            error=exc
                            decision=failure_details(exc,key)
                            # A malformed response or local processing error after
                            # a reply is a controller problem, not a rejected sample.
                            if raw is not None and decision['failure_class'] != 'model_identity_mismatch':
                                decision.update(failure_class='response_processing_failure',fatal=True,retryable=False)
                            result.update(error_type=type(exc).__name__,error_message=safe_error(exc,key),**decision)
                            if result['fatal']:stop=result['failure_class']
                        result.update(elapsed_s=round(time.monotonic()-tick,3),ended_utc=now())
                        try:result['settlement']=ledger.settle(reservation,usage=usage,response_received=raw is not None,error_type=type(error).__name__ if error else None)
                        except Exception as exc:
                            result['settlement_error']={'error_type':type(exc).__name__,'message':safe_error(exc,key)};stop='ledger_settlement_error'
                        frozen_write(attempt_dir/'result.json',result)
                    terminal['attempts'].append(result)
                    if result.get('settlement_error'):stop='ledger_settlement_error'
                    if result.get('fatal'):stop=result.get('failure_class','fatal_execution_failure')
                    if result.get('response_received'):
                        terminal.update(result.get('parsed') or parse_fn(result.get('raw_content'),legal))
                        terminal['raw_response']=result.get('raw_content')
                        if result.get('error_type')=='RuntimeError' and 'identity' in result.get('error_message',''):
                            terminal.update(answer=None,status='request_failed');stop='returned_model_identity_mismatch'
                        break
                    if stop or not result.get('retryable'):break
                    if attempt_number<cfg.get('max_attempts_per_sample',2):time.sleep(2)
                if terminal['attempts']:
                    if stop:
                        terminal['fatal_reason']=stop
                        terminal.update(answer=None,status='request_failed')
                    failure=terminal['attempts'][-1].get('failure_class')
                    if failure:terminal['failure_class']=failure
                    failed,_=terminal_failure(terminal)
                    consecutive_failed=consecutive_failed+1 if failed else 0
                    terminal['consecutive_failed_samples']=consecutive_failed
                    terminal['ended_utc']=now();frozen_write(folder/'terminal.json',terminal);records[qid,sample]=terminal
                    print(json.dumps({'event':'sample_terminal','index':index,'sample':sample,'status':terminal['status'],'requests_used':used}),flush=True)
                if consecutive_failed >= FAILURE_POLICY['consecutive_failed_samples_limit']:
                    stop=stop or 'consecutive_failed_samples_limit'
                if stop or not terminal['attempts']:
                    _,pending_stop=failure_prefix(rows,cfg['samples'],records,out)
                    detail={}
                    if pending_stop:
                        frozen_write(out/'stop_events'/(pending_stop['event_id']+'.json'),pending_stop)
                        detail={'stop_event_id':pending_stop['event_id']}
                    write(out/'fatal_error.json',{'utc':now(),'error':stop or 'request_limit','question_id':qid,'sample':sample,**detail})
                    status('stopped',error=stop or 'request_limit',**detail);end_ledger();return 2
                status('running')
        aggregate();end_ledger();status('generation_complete');return 0


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',type=Path,required=True);parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--samples',type=int);parser.add_argument('--temperature',type=float)
    parser.add_argument('--model',choices=sorted(MODELS));parser.add_argument('--prompt-variant',choices=sorted(VARIANTS))
    parser.add_argument('--api-key-stdin',action='store_true');parser.add_argument('--prepare-only',action='store_true')
    parser.add_argument('--resume',action='store_true')
    parser.add_argument('--acknowledge-stop',help='Explicitly acknowledge the exact stopped event after operator review; never retries an existing sample.')
    args=parser.parse_args(argv);out=args.out.resolve();out.mkdir(parents=True,exist_ok=True)
    cfg=read(args.config)
    for name in ('samples','temperature','model','prompt_variant'):
        if getattr(args,name) is not None:cfg[name]=getattr(args,name)
    with exclusive_lock(out/'.generation.lock'):
        try:return run(args,cfg,out)
        except Exception as exc:
            write(out/'fatal_error.json',{'utc':now(),'error_type':type(exc).__name__,'message':safe_error(exc)})
            old=read(out/'status.json') if (out/'status.json').exists() else {}
            write(out/'status.json',dict(old,status='stopped',updated_utc=now(),error_type=type(exc).__name__))
            print(json.dumps({'status':'stopped','error_type':type(exc).__name__}),flush=True);return 2


if __name__=='__main__':raise SystemExit(main())
