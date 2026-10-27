"""Execution facts from real, completed runs; references never become prompt text.

Only fixed diagnostic and multi-tool run formats are recognized. File hashes prove
consistency with pinned artifacts, not authenticity of an external log producer.
The compiler never opens label files, accepts answer text, or infers medical truth.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
import re

from memory_core.schema import (AuditRegistry, canonical_bytes, digest, read_json, read_jsonl,
                                sha256_string, strict_fields)
from memory_core.retrieval import tokenize

MULTI_KIND = 'first5_matched_direct_vs_available_original_classifier_report_agent'
HISTORICAL_KIND = 'matched_diagnostic_direct_vs_restricted_classifier_agent'
TOOL_KINDS = {'chest_xray_classifier': 'classification', 'chest_xray_report_generator': 'report',
              'chest_xray_segmentation': 'segmentation'}
FAMILIES = ('multitool_original', 'historical_classifier')
FEATURES = {'vqa', 'laterality', 'localization', 'comparison', 'diagnosis', 'finding', 'report',
            'anatomy', 'single_image', 'multi_image', 'no_image'}
OUTCOMES = {'unknown', 'correct', 'incorrect', 'invalid', 'error'}
EXECUTIONS = {'returned_valid', 'returned_invalid', 'exception', 'unknown'}
TERMINALS = {'completed', 'invalid_answer', 'tool_error', 'model_error', 'failed', 'case_budget_exceeded',
             'monetary_budget_exceeded', 'monetary_guard_error', 'interrupted_no_retry', 'invalid_input', 'missing_image'}
SHAPE_FIELDS = {'score_count', 'report_chars', 'findings_chars', 'impression_chars',
                'metrics_returned_count', 'configured_model_channel_count'}


def file_hash(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def implementation_hashes():
    return {name: hashlib.sha256(Path(path).read_bytes().replace(b'\r\n', b'\n')).hexdigest()
        for name, path in [('memory_pipeline/core.py', __file__),
            ('memory_core/schema.py', Path(__file__).resolve().parents[1] / 'memory_core/schema.py'),
            ('memory_core/retrieval.py', Path(__file__).resolve().parents[1] / 'memory_core/retrieval.py')]}


def visible_features(question, image_count):
    """Coarse operational features from question stem only, never option contents.

    This intentionally does not claim semantic/clinical abstraction. It cannot
    reconstruct missing reasoning or report text from hashes in existing traces.
    """
    if not isinstance(question, str) or not question.strip() or type(image_count) is not int or image_count < 0:
        raise ValueError('Invalid inference-visible task input')
    stem = re.split(r'(?m)(?:^|\n)\s*(?:[A-F][.)：:]|\([A-F]\))\s*', question, maxsplit=1)[0].lower()
    found = {'vqa', 'no_image' if image_count == 0 else 'single_image' if image_count == 1 else 'multi_image'}
    patterns = {'laterality': r'\b(left|right|bilateral|laterality)\b',
                'localization': r'\b(where|location|located|localization)\b',
                'comparison': r'\b(compare|comparison|change|previous|prior)\b',
                'diagnosis': r'\b(diagnosis|diagnostic|differential|disease)\b',
                'finding': r'\b(finding|findings|abnormality|abnormalities)\b',
                'report': r'\b(report|impression)\b', 'anatomy': r'\b(anatomic|anatomy|structure)\b'}
    found.update(name for name, pattern in patterns.items() if re.search(pattern, stem))
    return sorted(found)


@dataclass(frozen=True)
class Boundary:
    """Immutable case/input projection; does not retain question/option prose."""
    _bytes: bytes

    @classmethod
    def from_split_directory(cls, directory, exclusions, *, expected_exclusions_sha256):
        directory, exclusions = Path(directory), Path(exclusions)
        registry = AuditRegistry.from_split_directory(directory)
        expected = sha256_string(expected_exclusions_sha256)
        if file_hash(exclusions) != expected:
            raise ValueError('Exclusion manifest differs from independently pinned digest')
        excluded = read_json(exclusions)
        if (excluded.get('schema_version') != 1 or excluded.get('heldout_labels_or_outputs_used') is not False
                or excluded.get('phash_used_for_exclusion') is not False):
            raise ValueError('Unsupported or label-informed leakage exclusion manifest')
        by_case = {row.case_hash: row.split for row in registry.rows}
        removed = excluded.get('excluded_case_hashes_by_split')
        if type(removed) is not dict or set(removed) != {'memory_train', 'validation', 'heldout_test'}:
            raise ValueError('Exclusion cases must cover all frozen splits')
        for split, cases in removed.items():
            if type(cases) is not list or len(set(cases)) != len(cases):
                raise ValueError('Invalid exclusion list')
            for case in cases:
                if by_case.get(sha256_string(case)) != split:
                    raise ValueError('Excluded case is not in its declared frozen split')
        image_audit = exclusions.parent / 'image_audit.jsonl'
        image_audit_sha = sha256_string(excluded.get('source_image_audit_sha256'))
        if file_hash(image_audit) != image_audit_sha:
            raise ValueError('Image audit differs from pinned exclusion evidence')
        image_rows = read_jsonl(image_audit)
        image_by_name = {x['dataset_image_path']: x for x in image_rows}
        if len(image_by_name) != len(image_rows):
            raise ValueError('Duplicate image audit identity')
        entries = []
        for split in ('memory_train', 'validation', 'heldout_test'):
            for row in read_jsonl(directory / (split + '.inputs.jsonl')):
                audit = registry.lookup(row['question_id'])
                image_hashes = []
                for name in row['images']:
                    fact = image_by_name.get(name)
                    if fact is None or row['question_id'] not in fact.get('question_ids', []) or audit.case_hash not in fact.get('case_hashes', []) or split not in fact.get('splits', []):
                        raise ValueError('Image audit does not establish the declared case membership')
                    image_hashes.append(sha256_string(fact['sha256']) if fact.get('status') == 'readable' else None)
                entries.append({'question_id': row['question_id'], 'case_hash': audit.case_hash,
                    'split': split, 'question_sha256': digest(row['question']), 'image_count': len(row['images']),
                    'image_references_sha256': digest(row['images']), 'image_sha256': image_hashes,
                    'features': visible_features(row['question'], len(row['images'])),
                    'excluded': audit.case_hash in removed[split]})
        payload = {'schema_version': 1, 'registry': registry.to_dict(), 'exclusions_sha256': expected,
                   'image_audit_sha256': image_audit_sha,
                   'entries': sorted(entries, key=lambda x: x['question_id']), 'evidence_kind': 'split_artifacts'}
        return cls(canonical_bytes(payload))

    @classmethod
    def synthetic(cls, rows):
        """Only fixtures; freeze_pool requires a separate explicit override."""
        registry = AuditRegistry.synthetic([{k: row[k] for k in ('question_id', 'case_hash', 'split')} for row in rows])
        entries = [{**{k: row[k] for k in ('question_id', 'case_hash', 'split')},
            'question_sha256': digest(row['question']), 'image_count': len(row['images']),
            'image_references_sha256': digest(row['images']), 'image_sha256': row['image_sha256'],
            'features': visible_features(row['question'], len(row['images'])), 'excluded': row.get('excluded', False)} for row in rows]
        return cls(canonical_bytes({'schema_version': 1, 'registry': registry.to_dict(), 'exclusions_sha256': '0' * 64,
            'image_audit_sha256': '0' * 64,
            'entries': sorted(entries, key=lambda x: x['question_id']), 'evidence_kind': 'synthetic_fixture_only'}))

    def payload(self): return json.loads(self._bytes)
    @property
    def sha256(self): return hashlib.sha256(self._bytes).hexdigest()
    def lookup(self, qid):
        for entry in self.payload()['entries']:
            if entry['question_id'] == qid:
                return entry
        raise ValueError('Unknown question cannot establish case/split isolation')


def _jsonl_complete(path):
    raw = Path(path).read_bytes()
    if raw and not raw.endswith(b'\n'):
        raise ValueError('Incomplete journal tail')
    return read_jsonl(path)


def _protocol(plan, family):
    if family == 'multitool_original':
        registry = plan.get('tool_registry')
        if plan.get('kind') != MULTI_KIND or type(registry) is not dict:
            raise ValueError('Only the declared multi-tool run format can enter this family')
        if not {'chest_xray_classifier', 'chest_xray_report_generator'} <= set(registry) or not set(registry) <= set(TOOL_KINDS):
            raise ValueError('Multiple-tool registry differs from supported original tools')
        if any(p.get('mode') != 'original' or p.get('kind') != TOOL_KINDS[name] for name, p in registry.items()):
            raise ValueError('Tool variant is not the original declared baseline')
        versions = {name: digest(value) for name, value in registry.items()}
    elif family == 'historical_classifier':
        if plan.get('kind') != HISTORICAL_KIND or 'tool_registry' in plan:
            raise ValueError('Historical single-tool family requires its original diagnostic format')
        versions = {'chest_xray_classifier': digest({'source': plan['source_sha256']['official_classifier.py'],
            'model_name': plan['tool_model_name'], 'asset_verification': 'not_complete_in_historical_manifest'})}
    else:
        raise ValueError('Unknown pool family')
    keys = ('model', 'provider_base_url', 'prompts', 'max_output_tokens', 'max_model_calls', 'max_tool_calls',
            'temperature', 'top_p', 'provider_retries', 'image_detail', 'source_sha256', 'package_versions')
    if any(key not in plan for key in keys):
        raise ValueError('Source inference protocol is incomplete')
    description = {key: plan[key] for key in keys}
    description.update(family=family, tool_versions=versions)
    return digest(description), versions


def _outcomes(path, boundary, run_hash, results_hash, terminal):
    if path is None:
        return {}, None
    payload = read_json(path)
    strict_fields(payload, ('schema_version', 'source_run_manifest_sha256', 'source_results_sha256',
        'split_manifest_sha256', 'outcomes'), 'outcome sidecar')
    if (payload['schema_version'] != 1 or payload['source_run_manifest_sha256'] != run_hash
            or payload['source_results_sha256'] != results_hash
            or payload['split_manifest_sha256'] != boundary.payload()['registry']['split_manifest_sha256']):
        raise ValueError('Outcome sidecar is not bound to this run and split')
    values = {}
    for item in payload['outcomes']:
        strict_fields(item, ('question_id', 'arm', 'task_outcome'), 'outcome row')
        qid, outcome = item['question_id'], item['task_outcome']
        if (item['arm'] != 'agent' or outcome not in OUTCOMES or qid in values
                or boundary.lookup(qid)['split'] != 'memory_train' or (qid, 'agent') not in terminal):
            raise ValueError('Invalid/duplicate/non-training outcome')
        if outcome in ('correct', 'incorrect') and terminal[(qid, 'agent')]['status'] != 'completed':
            raise ValueError('A non-completed response cannot have a valid-answer outcome')
        values[qid] = outcome
    return values, file_hash(path)


def compile_run(directory, boundary, *, family='multitool_original', outcomes=None):
    """Compile completed train execution facts; reference answers are never opened."""
    directory = Path(directory)
    files = {name: file_hash(directory / name) for name in ('manifest.json', 'results.jsonl', 'trace.jsonl', 'summary.json')}
    manifest, summary = read_json(directory / 'manifest.json'), read_json(directory / 'summary.json')
    plan = manifest['plan']
    if manifest.get('plan_sha256') != digest(plan) or summary.get('plan_sha256') != digest(plan) or summary.get('run_id') != manifest.get('run_id'):
        raise ValueError('Run manifest/summary mismatch')
    schedule = plan['schedule']; planned = {(x['question_id'], x['arm']) for x in schedule}
    if (len(planned) != len(schedule) or summary.get('stop_reason') != 'complete'
            or summary.get('terminal_count') != len(schedule) or any(arm not in ('direct', 'agent') for _, arm in planned)):
        raise ValueError('Only a completed, nonduplicated planned run can be compiled')
    records = {x['question_id']: x for x in plan['records']}
    if set(records) != set(plan['question_ids']) or {qid for qid, arm in planned} != set(records):
        raise ValueError('Source question denominator differs across manifest sections')
    for qid, record in records.items():
        entry = boundary.lookup(qid)
        if entry['split'] != 'memory_train':
            raise ValueError('Validation/heldout trajectories cannot enter training memory')
        if (record['question_sha256'] != entry['question_sha256'] or len(record['images']) != entry['image_count']
                or [x.get('sha256') for x in record['images']] != entry['image_sha256']
                or None in entry['image_sha256']):
            raise ValueError('Run inputs differ from the frozen split-visible question')
    protocol, versions = _protocol(plan, family)
    starts, terminals = {}, {}
    for event in _jsonl_complete(directory / 'results.jsonl'):
        key = (event.get('question_id'), event.get('arm'))
        if key not in planned:
            raise ValueError('Unplanned journal row')
        if event.get('record_type') == 'started':
            if key in starts: raise ValueError('Duplicate start')
            starts[key] = event
        elif event.get('record_type') == 'terminal':
            if key not in starts or key in terminals or event.get('thread_id') != starts[key].get('thread_id'):
                raise ValueError('Duplicate/unpaired terminal')
            if event.get('status') not in TERMINALS: raise ValueError('Unrecognized terminal status')
            terminals[key] = event
        else:
            raise ValueError('Unrecognized journal record')
    if set(terminals) != planned:
        raise ValueError('Durable results do not cover the planned denominator')
    summary_rows = summary.get('question_results', [])
    if (len(summary_rows) != len(planned) or {(x.get('question_id'), x.get('arm')) for x in summary_rows} != planned
            or any(terminals.get((x.get('question_id'), x.get('arm'))) != x for x in summary_rows)):
        raise ValueError('Summary disagrees with durable terminal records')
    feedback, feedback_hash = _outcomes(outcomes, boundary, files['manifest.json'], files['results.jsonl'], terminals)
    trace = _jsonl_complete(directory / 'trace.jsonl'); grouped = {key: [] for key in planned}
    for position, event in enumerate(trace, 1):
        key = (event.get('question_id'), event.get('arm'))
        if key not in planned or event.get('thread_id') != starts[key]['thread_id']:
            raise ValueError('Trace question/thread is outside this run')
        if event.get('node') == 'tool':
            grouped[key].append((position, event))
    compiled, skipped = [], Counter()
    for qid, arm in ((x['question_id'], x['arm']) for x in schedule):
        if arm != 'agent': continue
        entry, terminal = boundary.lookup(qid), terminals[(qid, arm)]
        if entry['excluded']:
            skipped['quarantined_case'] += 1; continue
        steps = []
        for position, event in grouped[(qid, arm)]:
            # Pre-invocation argument errors have no argument fingerprint and are not real executions.
            fingerprint = event.get('arguments_sha256', event.get('argument_sha256'))
            if fingerprint is None: continue
            sha256_string(fingerprint)
            name = event.get('tool_name')
            if name not in versions: raise ValueError('Trace tool absent from frozen tool registry')
            if event.get('phase') not in (1, 2) or event.get('execution') not in ('returned', 'exception'):
                raise ValueError('Unknown tool phase or execution status')
            if family == 'multitool_original' and (event.get('tool_kind') != TOOL_KINDS[name]
                    or event.get('tool_version_sha256') != versions[name]):
                raise ValueError('Tool event version differs from actual initialized tool registry')
            image_hash = sha256_string(event.get('image_sha256'))
            if image_hash not in {x.get('sha256') for x in records[qid]['images']}:
                raise ValueError('Tool ran on an image outside the declared question')
            elapsed = event.get('elapsed_ms')
            if type(elapsed) not in (int, float) or not math.isfinite(elapsed) or elapsed < 0:
                raise ValueError('Missing/invalid execution timing')
            contract = event.get('output_contract', {})
            if family == 'historical_classifier':
                valid = event.get('tool_analysis_status') == 'completed' and event.get('execution') == 'returned'
            else:
                valid = contract.get('valid') is True and contract.get('tool_analysis_status') == 'completed'
            state = ('returned_valid' if valid else 'returned_invalid') if event.get('execution') == 'returned' else 'exception'
            safe_shape = {key: contract[key] for key in sorted(SHAPE_FIELDS)
                          if key in contract and type(contract[key]) is int and contract[key] >= 0}
            steps.append({'step_id': len(steps) + 1, 'phase': event.get('phase'), 'tool_name': name,
                'tool_kind': TOOL_KINDS[name], 'tool_version_sha256': versions[name],
                'arguments_sha256': fingerprint, 'image_sha256': image_hash, 'execution': state,
                'elapsed_ms': elapsed, 'observation_shape': safe_shape,
                'source_event_line': position, 'source_event_sha256': digest(event),
                'clinical_evidence': 'unknown', 'step_credit': None})
        attempts = terminal.get('actual_tool_attempts')
        if type(attempts) is not int or attempts != len(steps):
            if attempts is None and terminal['status'] == 'interrupted_no_retry':
                skipped['interrupted_unknown_execution'] += 1; continue
            raise ValueError('Actual tool count is not supported by trace execution events')
        if sum(x['execution'] == 'returned_valid' for x in steps) != terminal.get('validated_tool_returns'):
            raise ValueError('Validated return count disagrees with execution trace')
        if family == 'multitool_original':
            for name in versions:
                count = terminal.get('tool_counts', {}).get(name, {})
                if (count.get('attempted') != sum(x['tool_name'] == name for x in steps)
                        or count.get('validated_returns') != sum(x['tool_name'] == name and x['execution'] == 'returned_valid' for x in steps)):
                    raise ValueError('Per-tool terminal counters disagree with execution trace')
        if not steps:
            skipped['no_actual_tool_execution'] += 1; continue
        value = {'source_question_id': qid, 'source_case_hash': entry['case_hash'], 'source_split': 'memory_train',
            'source_thread_id': terminal['thread_id'], 'source_files_sha256': files,
            'outcome_sidecar_sha256': feedback_hash, 'family': family, 'protocol_sha256': protocol,
            'available_tool_versions': versions, 'features': entry['features'], 'steps': steps,
            'terminal_status': terminal['status'], 'task_outcome': feedback.get(qid, 'unknown'),
            'clinical_evidence': 'unknown', 'step_credit': None,
            'representation': 'structured_execution_trajectory_not_original_reasoning_or_report_text'}
        value['memory_id'] = digest(value)
        compiled.append(value)
    report = {'source_files_sha256': files, 'family': family, 'protocol_sha256': protocol,
        'planned_agent_questions': sum(x['arm'] == 'agent' for x in schedule), 'compiled_trajectories': len(compiled),
        'compiled_actual_tool_steps': sum(len(x['steps']) for x in compiled), 'skipped': dict(skipped),
        'task_outcomes': dict(Counter(x['task_outcome'] for x in compiled)),
        'clinical_evidence': 'unknown', 'step_credit_nonnull_count': 0, 'labels_read': False}
    if any(file_hash(directory / name) != value for name, value in files.items()):
        raise ValueError('Source evidence changed during compilation')
    return compiled, report


def _context(record, summary_mode=False):
    steps = [{'tool': x['tool_name'], 'execution': x['execution'], 'output_structure': x['observation_shape']}
             for x in record['steps']]
    if summary_mode:
        return {'representation': 'deterministic_execution_rule_summary_not_llm', 'task_features': record['features'],
            'observed_tool_sequence': [x['tool'] for x in steps],
            'execution_validity': [x['execution'] for x in steps],
            'limits': ['Execution success does not establish clinical correctness.',
                       'Source observations were logged as structures and hashes; medical reasoning is unavailable.'],
            'clinical_evidence': 'unknown', 'step_credit': None}
    return {'representation': 'observed_structured_execution_trajectory', 'task_features': record['features'],
            'steps': steps, 'clinical_evidence': 'unknown', 'step_credit': None}


def _validate_record(record, boundary, family, protocol):
    fields = ('source_question_id', 'source_case_hash', 'source_split', 'source_thread_id', 'source_files_sha256',
        'outcome_sidecar_sha256', 'family', 'protocol_sha256', 'available_tool_versions', 'features', 'steps',
        'terminal_status', 'task_outcome', 'clinical_evidence', 'step_credit', 'representation', 'memory_id')
    strict_fields(record, fields, 'trajectory')
    entry = boundary.lookup(record['source_question_id'])
    if (entry['split'] != 'memory_train' or entry['excluded'] or record['source_split'] != 'memory_train'
            or record['source_case_hash'] != entry['case_hash'] or record['features'] != entry['features']
            or record['family'] != family or record['protocol_sha256'] != protocol
            or record['task_outcome'] not in OUTCOMES or record['clinical_evidence'] != 'unknown' or record['step_credit'] is not None):
        raise ValueError('Trajectory admission boundary violated')
    if not record['steps']: raise ValueError('No real tool steps')
    if record['terminal_status'] not in TERMINALS or not set(record['features']) <= FEATURES:
        raise ValueError('Unknown terminal or visible task feature')
    if record['representation'] != 'structured_execution_trajectory_not_original_reasoning_or_report_text':
        raise ValueError('Unrecognized trajectory representation')
    sha256_string(record['protocol_sha256'])
    if record['task_outcome'] != 'unknown' and record['outcome_sidecar_sha256'] is None:
        raise ValueError('Known task outcome requires a bound independent sidecar')
    strict_fields(record['source_files_sha256'], ('manifest.json', 'results.jsonl', 'trace.jsonl', 'summary.json'), 'source files')
    for value in record['source_files_sha256'].values(): sha256_string(value)
    if record['outcome_sidecar_sha256'] is not None: sha256_string(record['outcome_sidecar_sha256'])
    versions = record['available_tool_versions']
    if type(versions) is not dict or not versions or not set(versions) <= set(TOOL_KINDS):
        raise ValueError('Unsupported tool registry')
    if (family == 'historical_classifier' and set(versions) != {'chest_xray_classifier'} or
            family == 'multitool_original' and not {'chest_xray_classifier', 'chest_xray_report_generator'} <= set(versions)):
        raise ValueError('Historical and multiple-tool memory families cannot be mixed')
    for value in versions.values(): sha256_string(value)
    for index, step in enumerate(record['steps'], 1):
        strict_fields(step, ('step_id', 'phase', 'tool_name', 'tool_kind', 'tool_version_sha256', 'arguments_sha256',
            'image_sha256', 'execution', 'elapsed_ms', 'observation_shape', 'source_event_line', 'source_event_sha256',
            'clinical_evidence', 'step_credit'), 'execution step')
        if (step['execution'] not in EXECUTIONS or step['clinical_evidence'] != 'unknown' or step['step_credit'] is not None
                or step['tool_name'] not in TOOL_KINDS or step['tool_kind'] != TOOL_KINDS[step['tool_name']]
                or record['available_tool_versions'].get(step['tool_name']) != step['tool_version_sha256']):
            raise ValueError('Execution evidence cannot create clinical verification/credit')
        shape = step['observation_shape']
        if (type(shape) is not dict or not set(shape) <= SHAPE_FIELDS
                or any(type(v) is not int or v < 0 for v in shape.values())
                or step['step_id'] != index or step['phase'] not in (1, 2)
                or type(step['source_event_line']) is not int or step['source_event_line'] < 1):
            raise ValueError('Execution structure contains non-whitelisted content')
        if (type(step['elapsed_ms']) not in (int, float) or not math.isfinite(step['elapsed_ms']) or step['elapsed_ms'] < 0
                or step['image_sha256'] not in entry['image_sha256']):
            raise ValueError('Execution timing/image is outside admitted evidence')
        for key in ('tool_version_sha256', 'arguments_sha256', 'image_sha256', 'source_event_sha256'):
            sha256_string(step[key])
    if digest({k: v for k, v in record.items() if k != 'memory_id'}) != record['memory_id']:
        raise ValueError('Trajectory content identity mismatch')


@dataclass(frozen=True)
class FrozenPool:
    _bytes: bytes

    def payload(self): return json.loads(self._bytes)
    @property
    def sha256(self): return hashlib.sha256(self._bytes).hexdigest()
    def save(self, path):
        with Path(path).open('xb') as handle:
            handle.write(canonical_bytes({'sha256': self.sha256, 'payload': self.payload()}))
        return self.sha256

    @classmethod
    def load(cls, path, *, expected_sha256):
        envelope = read_json(path)
        strict_fields(envelope, ('sha256', 'payload'), 'pool envelope')
        expected_sha256 = sha256_string(expected_sha256)
        if envelope['sha256'] != expected_sha256 or digest(envelope['payload']) != expected_sha256:
            raise ValueError('Pool differs from independently pinned digest')
        payload = envelope['payload']
        strict_fields(payload, ('schema_version', 'family', 'pool_version', 'previous_pool_sha256', 'protocol_sha256',
            'boundary', 'implementation_sha256', 'records', 'evidence_kind', 'summary_method', 'retrieval',
            'heldout_queries_enabled', 'agent_integration_enabled'), 'frozen pool')
        if (payload['schema_version'] != 1 or payload['family'] not in FAMILIES
                or type(payload['pool_version']) is not int or payload['pool_version'] < 1
                or payload['heldout_queries_enabled'] is not False or payload['agent_integration_enabled'] is not False
                or payload['summary_method'] != 'deterministic_execution_rules_v1_not_llm'
                or payload['retrieval'] != {'tokenizer': 'coarse_operational_features_v1', 'algorithm': 'filtered_bm25', 'k1': 1.5, 'b': 0.75}
                or type(payload['records']) is not list or not payload['records']):
            raise ValueError('Unrecognized frozen pool policy')
        if payload['implementation_sha256'] != implementation_hashes():
            raise ValueError('Pool implementation changed; require an explicit new version')
        boundary = Boundary(canonical_bytes(payload['boundary']))
        for record in payload['records']:
            _validate_record(record, boundary, payload['family'], payload['protocol_sha256'])
        if len({x['memory_id'] for x in payload['records']}) != len(payload['records']):
            raise ValueError('Duplicate frozen trajectory')
        return cls(canonical_bytes(payload))

    def search(self, query, *, top_k=3, min_score=0.1, include_failures=False, summary_mode=False):
        strict_fields(query, ('question_id', 'question', 'images', 'available_tools', 'protocol_sha256'), 'retrieval query')
        if (type(top_k) is not int or top_k not in (1, 3, 5) or type(min_score) not in (int, float)
                or not math.isfinite(min_score) or min_score < 0 or type(include_failures) is not bool or type(summary_mode) is not bool
                or type(query['images']) is not list or type(query['available_tools']) is not dict):
            raise ValueError('Use declared validation retrieval settings')
        payload = self.payload(); boundary = Boundary(canonical_bytes(payload['boundary']))
        source = boundary.lookup(query['question_id'])
        if source['split'] == 'heldout_test':
            raise ValueError('Heldout queries are disabled until a separate locked evaluation adapter exists')
        if (source['excluded'] or digest(query['question']) != source['question_sha256']
                or digest(query['images']) != source['image_references_sha256']):
            raise ValueError('Query must exactly match isolated visible input, without appended labels')
        if query['protocol_sha256'] != payload['protocol_sha256']:
            raise ValueError('Query protocol differs from this separate pool family')
        candidates = [record for record in payload['records'] if record['source_case_hash'] != source['case_hash']
            and (record['task_outcome'] == 'correct' or include_failures and record['task_outcome'] in {'incorrect', 'invalid', 'error'})
            and query['available_tools'] == record['available_tool_versions']]
        documents = [tokenize(' '.join(record['features']) + ' ' + ' '.join(x['tool_name'] for x in record['steps'])) for record in candidates]
        query_tokens = set(tokenize(' '.join(source['features'])))
        if not documents: return []
        average = sum(map(len, documents)) / len(documents)
        frequency = Counter(token for document in documents for token in set(document))
        scored = []
        for record, document in zip(candidates, documents):
            counts, score = Counter(document), 0.0
            for word in query_tokens:
                count = counts[word]
                if count:
                    inverse = math.log(1 + (len(documents) - frequency[word] + 0.5) / (frequency[word] + 0.5))
                    score += inverse * count * 2.5 / (count + 1.5 * (0.25 + 0.75 * len(document) / average))
            if score > 0 and score >= min_score:
                scored.append({'memory_id': record['memory_id'], 'score': score, 'context': _context(record, summary_mode)})
        return sorted(scored, key=lambda x: (-x['score'], x['memory_id']))[:top_k]


def freeze_pool(boundary, records, *, family, version, previous_sha256=None, allow_synthetic=False):
    if family not in FAMILIES or type(version) is not int or version < 1:
        raise ValueError('A declared family and positive pool version are required')
    if boundary.payload()['evidence_kind'] == 'synthetic_fixture_only' and allow_synthetic is not True:
        raise ValueError('Synthetic fixtures cannot masquerade as a real memory pool')
    if previous_sha256 is not None: sha256_string(previous_sha256)
    if not records: raise ValueError('No real compiled trajectories; cannot fabricate an empty success pool')
    protocol = records[0]['protocol_sha256']
    ids = set()
    for record in records:
        _validate_record(record, boundary, family, protocol)
        if record['memory_id'] in ids: raise ValueError('Duplicate trajectory')
        ids.add(record['memory_id'])
    payload = {'schema_version': 1, 'family': family, 'pool_version': version, 'previous_pool_sha256': previous_sha256,
        'protocol_sha256': protocol, 'boundary': boundary.payload(), 'implementation_sha256': implementation_hashes(),
        'records': sorted(deepcopy(records), key=lambda x: x['memory_id']),
        'evidence_kind': boundary.payload()['evidence_kind'], 'summary_method': 'deterministic_execution_rules_v1_not_llm',
        'retrieval': {'tokenizer': 'coarse_operational_features_v1', 'algorithm': 'filtered_bm25', 'k1': 1.5, 'b': 0.75},
        'heldout_queries_enabled': False, 'agent_integration_enabled': False}
    return FrozenPool(canonical_bytes(payload))
