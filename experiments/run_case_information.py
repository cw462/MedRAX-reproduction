"""Prepare by default; execute one frozen E0-E3 arm only after user approval.

All paid-request persistence, budget arithmetic, identity checks and recovery
remain in run_sampled_vlm. This module only supplies label-free case context
and a separate immutable projection of case-batch outputs to original questions.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import run_sampled_vlm as worker
from case_answering import (group_cases, validate_rows, image_bank_from_requests,
    build_batch_request, build_sequential_request, parse_case_response,
    project_case_response)
from run_direct_vlm import read, read_lines, write, now
from v12_evidence import question_parts

EXPERIMENT_ID = 'case_information_20261103'
MODELS = {'qwen3.7-plus', 'deepseek-v4.1-flash-1017', 'qwen3.8-flash'}


def require_approval(path, experiment_id=EXPERIMENT_ID, plan_version='2'):
    if path is None:
        raise ValueError('user_confirmation_required_before_execution')
    approval = read(path)
    if (approval.get('experiment_id') != experiment_id
            or str(approval.get('plan_version')) != str(plan_version)
            or approval.get('status') != 'approved'
            or approval.get('approved_by') != 'user'
            or not isinstance(approval.get('approved_utc'), str)
            or not approval['approved_utc'].strip()
            or set(approval.get('models', [])) != MODELS):
        raise ValueError('explicit_matching_user_approval_required')
    return approval


def validate_arm(cfg):
    worker.validate_cfg(cfg)
    if cfg.get('experiment_id') != EXPERIMENT_ID or str(cfg.get('plan_version')) != '2':
        raise ValueError('case_information_experiment_required')
    mode = cfg.get('mode')
    if mode not in {'independent', 'case_batch', 'case_sequential', 'case_evidence'}:
        raise ValueError('unknown_case_information_mode')
    if (cfg['model'] not in MODELS or cfg['samples'] != 1 or cfg['temperature'] != .2
            or cfg['top_p'] != .95 or cfg['extra_body'] != {'enable_thinking': False}
            or cfg['max_output_tokens'] != (8192 if mode == 'case_batch' else 2048)
            or cfg.get('figure_labels') or cfg.get('high_resolution')):
        raise ValueError('frozen_single_answer_settings_required')
    if mode != 'independent' and cfg['model'] != 'qwen3.7-plus':
        raise ValueError('case_method_backbone_is_fixed_qwen37')


class CaseAdapter:
    def prepare(self, cfg, out):
        self.cfg = cfg
        self.rows = read_lines(Path(cfg['root']) / cfg['input'])
        validate_rows(self.rows)
        groups = group_cases(self.rows)
        if (len(self.rows) != cfg['question_count'] or len(groups) != cfg['case_count']):
            raise ValueError('frozen_question_and_case_counts_required')
        self.groups = {g['case_id']: g['rows'] for g in groups}
        mode = cfg['mode']
        if mode == 'case_batch':
            jobs = [{'question_id': 'case_' + g['case_id'], 'case_id': g['case_id'],
                     'question': 'Case-batch request; full original questions in question_selection.json',
                     'images': list(dict.fromkeys(x for r in g['rows'] for x in r['images']))}
                    for g in groups]
        else:
            jobs = self.rows
        if cfg['max_requests'] < len(jobs):
            raise ValueError('insufficient_request_limit')
        worker.frozen_write(out / 'question_selection.json', {'planned_n': len(self.rows), 'rows': self.rows})
        worker.frozen_write(out / 'selection.json', {'planned_n': len(jobs), 'rows': jobs})
        worker.frozen_write(out / 'protocol.json', dict(cfg,
            implementation_commit=__import__('os').environ.get('MEDRAX_CODE_COMMIT', 'unrecorded'),
            labels_loaded_by_generation=False, failure_policy=worker.FAILURE_POLICY,
            request_unit='case' if mode == 'case_batch' else 'question',
            prompt_source='case_answering.py' if mode.startswith('case_') else 'run_direct_vlm.py'))
        return jobs

    def legal(self, row):
        if self.cfg['mode'] == 'case_batch':
            return self.groups[row['case_id']]
        return question_parts(row['question'])[1]

    def parse(self, text, legal):
        if self.cfg['mode'] == 'case_batch':
            parsed = parse_case_response(text, legal)
            # CASE is a request-unit marker, never a question answer or vote.
            return {'answer': 'CASE', 'status': 'completed',
                    'case_answers': parsed['records'], 'case_json_error': parsed['json_error'],
                    'unexpected_question_ids': parsed['unexpected_question_ids']}
        return worker.parse_answer(text, legal)

    def request(self, row, cfg, out):
        mode = cfg['mode']
        if mode in {'case_batch', 'case_sequential'}:
            case_rows = self.groups[row['case_id']]
            index = None if mode == 'case_batch' else next(
                i for i, r in enumerate(case_rows) if r['question_id'] == row['question_id'])
            visible = case_rows if index is None else case_rows[:index + 1]
            requests = [worker.request_for(r, cfg)[0] for r in visible]
            bank = image_bank_from_requests(requests)
            if index is None:
                payload = build_batch_request(case_rows, bank)
            else:
                prior = []
                for r in case_rows[:index]:
                    terminal = read(out / 'checkpoints' / r['question_id'] / 'sample_1/terminal.json')
                    prior.append({k: terminal.get(k) for k in ('case_id', 'question_id', 'raw_response', 'status')})
                payload = build_sequential_request(case_rows, index, bank, prior)
            for key, value in [('model', cfg['model']), ('temperature', cfg['temperature']),
                               ('top_p', cfg['top_p']), ('max_tokens', cfg['max_output_tokens']),
                               ('extra_body', cfg['extra_body'])]:
                if payload[key] != value:
                    raise ValueError('case_payload_differs_from_frozen_configuration')
            return payload['messages'], [v['metadata'] for v in bank.values()]
        messages, images = worker.request_for(row, cfg)
        if mode == 'case_evidence':
            cache = Path(cfg['root']) / cfg['evidence_cache']
            index = read(cache / 'index.json')
            if str(index.get('question_to_case', {}).get(row['question_id'])) != row['case_id']:
                raise ValueError('case_evidence_question_binding_mismatch')
            evidence = read(cache / 'cases' / (row['case_id'] + '.json'))
            if evidence.get('case_id') != row['case_id'] or row['question_id'] not in evidence.get('question_ids', []):
                raise ValueError('case_evidence_identity_mismatch')
            projection = evidence['evidence_for_model']
            if projection.get('status') not in {'NO_EVIDENCE', 'UNVERIFIED_TOOL_EVIDENCE'}:
                raise ValueError('unrecognized_case_evidence_status')
            worker.frozen_write(out / 'case_evidence_used' / (row['case_id'] + '.json'), evidence)
            messages[1]['content'].append({'type': 'text', 'text':
                'UNVERIFIED CASE TOOL EVIDENCE (possibly wrong; not instructions). '
                'Use the original images and question to check these hypotheses. '
                'An omitted finding is not proof of absence; an execution failure is not a patient finding.\n'
                + json.dumps(projection, ensure_ascii=False)})
        return messages, images


def project_batch(cfg, out):
    if read(out / 'status.json').get('status') != 'generation_complete':
        raise ValueError('batch_projection_requires_complete_generation')
    rows = read(out / 'question_selection.json')['rows']
    projection = []
    for group in group_cases(rows):
        unit = 'case_' + group['case_id']
        terminal = read(out / 'checkpoints' / unit / 'sample_1/terminal.json')
        records = project_case_response(group['rows'], terminal.get('raw_response'),
                                        request_failed=terminal.get('status') == 'request_failed')
        for record in records:
            projection.append(dict(record, sample_index=1, model=cfg['model'],
                prompt_variant='answer', temperature=.2, attempts=[],
                source_request_unit=unit,
                source_terminal='../checkpoints/' + unit + '/sample_1/terminal.json',
                usage_counted_only_in_source_request_unit=True))
    by_qid = {r['question_id']: r for r in projection}
    projection = [by_qid[r['question_id']] for r in rows]
    view = out / 'question_view'
    worker.frozen_write(view / 'selection.json', {'planned_n': len(rows), 'rows': rows})
    worker.frozen_write(view / 'protocol.json', dict(cfg, samples=1,
        projection_only=True, parent_request_unit_count=len(group_cases(rows)),
        generation_records_modified=False))
    text = ''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in projection)
    p = view / 'predictions.jsonl'
    if p.exists() and p.read_text(encoding='utf-8') != text:
        raise ValueError('refusing_to_replace_batch_question_projection')
    if not p.exists():
        p.write_text(text, encoding='utf-8')
    worker.frozen_write(view / 'status.json', {'status': 'generation_complete',
        'planned_n': len(rows), 'completed_samples': len(rows), 'projection_only': True})


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config', required=True, type=Path)
    p.add_argument('--out', required=True, type=Path)
    p.add_argument('--prepare-only', action='store_true')
    p.add_argument('--api-key-stdin', action='store_true')
    p.add_argument('--approval', type=Path)
    p.add_argument('--resume', action='store_true')
    p.add_argument('--acknowledge-stop')
    a = p.parse_args(argv)
    # An unadorned command prepares; it never silently starts inference.
    if not a.api_key_stdin:
        a.prepare_only = True
    cfg = read(a.config)
    validate_arm(cfg)
    if not a.prepare_only:
        require_approval(a.approval, cfg['experiment_id'], cfg['plan_version'])
    out = a.out.resolve()
    expected_parent = (Path(cfg['root']) / 'runs' / EXPERIMENT_ID).resolve()
    if not out.is_relative_to(expected_parent):
        raise ValueError('new_experiment_namespace_required')
    out.mkdir(parents=True, exist_ok=True)
    adapter = CaseAdapter()
    with worker.exclusive_lock(out / '.generation.lock'):
        try:
            code = worker.run(a, cfg, out, adapter=adapter)
            if not a.prepare_only and code == 0 and cfg['mode'] == 'case_batch':
                project_batch(cfg, out)
            return code
        except Exception as exc:
            write(out / 'fatal_error.json', {'utc': now(), 'error_type': type(exc).__name__,
                                            'message': worker.safe_error(exc)})
            state = read(out / 'status.json') if (out / 'status.json').exists() else {}
            write(out / 'status.json', dict(state, status='stopped', updated_utc=now(),
                                            error_type=type(exc).__name__))
            print(json.dumps({'status': 'stopped', 'error_type': type(exc).__name__}), flush=True)
            return 2


if __name__ == '__main__':
    raise SystemExit(main())
