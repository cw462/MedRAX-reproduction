"""Run the v6 paired improver trial using the locked official P search."""
from __future__ import annotations

import argparse
from copy import deepcopy
import os
from pathlib import Path
import subprocess
import sys
import time

from . import llm
from .dev100 import execute
from .dev100_report import first_pass_records
from .improver_policy import ImproverPolicy
from .io import ProtocolError, code_export, git, read_json, run_lock, write_json, write_once
from .process_runtime import ProcessRuntime
from .runtime import NativeScorer
from .search import OfficialSearch
from .steps import transition
from .validation import validate_config


def status(root, stage, **details):
    write_json(root / 'status.json', {'stage': stage, 'observed_epoch': time.time(), **details})


def clone_program(source, target, commit):
    if not (target / '.git').is_dir():
        target.mkdir(parents=True, exist_ok=True)
        git(target, 'init', '-q')
    if not (target / 'domains/med_m5/harness/agent.py').is_file():
        git(target, 'fetch', '-q', '--no-tags', str(source), commit)
        git(target, 'checkout', '-q', '--detach', 'FETCH_HEAD')
    if git(target, 'rev-parse', 'HEAD') != commit:
        raise ProtocolError('trial checkout differs from its reference P')
    git(target, 'config', 'user.name', 'MedRAX Experiment')
    git(target, 'config', 'user.email', 'medrax-experiment@localhost')


def search_environment(cfg, gateway):
    from integration.native_gateway import read_key
    search = cfg['search_llm']
    os.environ[search['api_key_env']] = read_key(gateway['key_files']['main'])
    os.environ[search['base_url_env']] = gateway['main_base_url']


def trial_inputs(v5_run, event, initial):
    records = [read_json(v5_run / 'dev/primary' / f'q{step:06d}' / 'completed.json')
               for step in range(1, 13)]
    panels = []
    for index, group in enumerate((records[:6], records[6:]), 1):
        rows = [{key: r[key] for key in ('task_id', 'case', 'reference')} for r in group]
        path = event / f'development_context_{index}.json'
        write_once(path, {'reference_P': initial, 'rows': rows})
        panels.append(path)
    return panels


def one_step(request):
    spec = read_json(request)
    cfg = spec['config']
    validate_config(cfg)
    context = read_json(spec['context'])
    rows = context['rows']
    where = Path(cfg['run_dir'])
    clone_program(spec['source_repo'], Path(cfg['upstream_repo']), context['reference_P'])
    runtime = ProcessRuntime(cfg['runtime'], where / 'runtime_audit')
    runtime.preflight()
    scorer = NativeScorer(cfg['scorer_command'], cfg['metric_id'])
    h0 = code_export(cfg['upstream_repo'], context['reference_P'], where / 'code' / context['reference_P'])
    state = transition(runtime, h0, None, where / 'initial', 'initialize', seed=cfg['seed'])['state']
    search = OfficialSearch(cfg, runtime, scorer)
    result = search.advance(rows, state, context['reference_P'])
    policy = ImproverPolicy.load(cfg['improver_policy'])
    write_once(where / 'revision.json', {'effective_R_version': policy.to_dict()['version'],
               'policy_path': cfg['improver_policy'], 'reference_P': context['reference_P'],
               'evidence_ids': [row['case']['id'] for row in rows],
               'budget': {'rounds':cfg['search']['max_rounds'], 'candidates':cfg['search']['candidates'],
                          'repeats':cfg['search']['repeats'], 'questions_in_panel':len(rows)},
               'selected_P': result['commit'], 'P_selected': result['accepted'],
               'parent_replay_accuracy':result['parent_replay_accuracy'],
               'selected_replay_accuracy':result['selected_replay_accuracy'],
               'search_usage':str(search.usage_path), 'repo': cfg['upstream_repo']})


def paired_scores(old, new):
    key = lambda row: (row['step'], row['dataset'], row['qid'])
    if len(old) != 10 or len(new) != 10 or [key(r) for r in old] != [key(r) for r in new]:
        raise ProtocolError('confirmation streams must contain the same ten questions in order')
    rows = [{'step':a['step'], 'qid':a['qid'], 'dataset':a['dataset'],
             'old_correct':a['correct'], 'new_correct':b['correct']} for a,b in zip(old,new)]
    before = sum(row['old_correct'] for row in rows)
    after = sum(row['new_correct'] for row in rows)
    return {'rows':rows, 'n':len(rows), 'old_correct':before, 'new_correct':after,
            'delta':(after-before)/len(rows),
            'corrected':sum(not r['old_correct'] and r['new_correct'] for r in rows),
            'harmed':sum(r['old_correct'] and not r['new_correct'] for r in rows)}


def confirm(cfg, block, revision, out):
    cfg = deepcopy(cfg)
    cfg.update(phase='test', arm='RSI_selected', run_dir=str(out),
               upstream_repo=revision['repo'], initial_commit=revision['selected_P'],
               manifest=block['manifest'], references=block['references'], expected_questions=10)
    cfg['runtime']['case_metadata'] = block['case_metadata']
    cfg['search']['max_rounds'] = 0
    cfg.pop('improver_policy', None)
    if not execute(cfg):
        raise ProtocolError(f'confirmation stopped before completion: {out}')
    return first_pass_records(out, 'test', 'RSI_selected')


def prepare(v5_run, out):
    from .meta_data import prepare_confirmation
    from .v6_backend import prepare_backend

    cfg = read_json(v5_run / 'dev/config.json')
    blocks = prepare_confirmation(v5_run, out / 'confirmation_input')['blocks']
    manifest = read_json(cfg['manifest'])
    sample = next(row for row in manifest['cases'] if row['dataset']=='rad_restruct')
    overrides = prepare_backend(v5_run, out, sample, Path(cfg['runtime']['case_metadata']))
    cfg['runtime'].update(overrides)
    return cfg, blocks


def pilot(v5_run, out, initial_policy, config, diagnosis):
    run = config['meta_search']
    completed = read_json(v5_run / 'interim_validation/summary.json')['checkpoints']['S10']
    if completed.get('status') != 'complete' or completed.get('n') != 100:
        raise ProtocolError('the validation diagnosis requires a completed paired S10 evaluation')
    if diagnosis['distinct_case_count'] < run['triggers']['completed_paired_validation_repeated_diagnostic']['minimum_distinct_cases']:
        raise ProtocolError('validation diagnosis lacks the required distinct cases')
    out.mkdir(parents=True, exist_ok=True)
    with run_lock(out / 'coordinator.lock'):
        book = out / 'events'
        event_dirs = sorted(book.glob('event_*'))
        evidence_id = diagnosis['evidence_id']
        for prior in event_dirs:
            if read_json(prior / 'intent.json')['evidence_id'] == evidence_id:
                if (prior / 'result.json').is_file():
                    result = read_json(prior / 'result.json')
                    active_path = out / 'active_improver.json'
                    if result['accepted'] and not active_path.exists():
                        write_json(active_path, {'policy_path':result['policy_path'],'version':result['candidate_R']})
                    return result
                event = prior
                break
        else:
            if event_dirs and not (event_dirs[-1] / 'result.json').is_file():
                raise ProtocolError('complete the previous meta event before starting a new one')
            if len(event_dirs) >= run['max_proposed_R_candidates']:
                raise ProtocolError('meta candidate budget exhausted')
            event = book / f'event_{len(event_dirs)+1:02d}'
        number = int(event.name.rsplit('_',1)[-1])
        active_path = out / 'active_improver.json'
        prior_intent = event / 'intent.json'
        if prior_intent.is_file():
            active = Path(read_json(prior_intent)['active_policy'])
        else:
            active = initial_policy
            for prior in event_dirs:
                result = read_json(prior / 'result.json')
                if result['accepted']:
                    active = Path(result['policy_path'])
        policy = ImproverPolicy.load(active)
        status(out, 'preparing', event=number, active_R=policy.to_dict()['version'])
        v5cfg, blocks = prepare(v5_run, out)
        blocks = blocks[(number-1)*2:number*2]
        if len(blocks) != 2 or any(b['questions'] != 10 for b in blocks):
            raise ProtocolError('two ten-question confirmation blocks are required per event')
        search_environment(v5cfg, read_json(Path(v5cfg['runtime']['gateway_config'])))
        initial = v5cfg['initial_commit']
        write_once(event / 'intent.json', {'evidence_id':evidence_id, 'source':'completed_paired_validation',
                   'S10_commit':completed['commit'], 'active_R':policy.to_dict()['version'],
                   'active_policy':str(active), 'reference_P':initial})
        contexts = trial_inputs(v5_run, event, initial)
        candidate_path = out / 'policies' / f'R{number}' / 'policy.json'
        if not candidate_path.is_file():
            if (event / 'proposal_started.json').is_file():
                raise ProtocolError('previous meta proposal response was not saved')
            status(out, 'proposing_R', event=number, active_R=policy.to_dict()['version'])
            llm.configure(v5cfg['search_llm'], event / 'meta_usage.jsonl')
            checkpoints = [read_json(p) for p in sorted((v5_run/'dev/search/checkpoints').glob('after_*/done.json'))]
            history = [{k:r.get(k) for k in ('after_questions','accepted','delta_accuracy','changed_components')} for r in checkpoints]
            write_once(event / 'proposal_started.json', {'epoch':time.time(), 'version':f'R{number}'})
            llm_model = v5cfg['search_llm']['model']
            try:
                candidate = policy.propose_revision(llm, history, diagnosis['summary'],
                                                   candidate_version=f'R{number}', model=llm_model)
                candidate_path.parent.mkdir(parents=True, exist_ok=True)
                candidate.save(candidate_path)
            except (ValueError, ProtocolError) as error:
                result = {'status':'invalid_candidate', 'accepted':False, 'reason':str(error), 'event':number}
                write_once(event / 'result.json', result)
                status(out, 'invalid_candidate', event=number, active_R=policy.to_dict()['version'])
                return result
            except OSError as error:
                result = {'status':'proposal_request_failed', 'accepted':False,
                          'error_type':type(error).__name__, 'event':number}
                write_once(event / 'result.json', result)
                status(out, 'proposal_request_failed', event=number, active_R=policy.to_dict()['version'])
                return result

        revisions = []
        for index, context in enumerate(contexts, 1):
            pair = {}
            for side, policy_path in (('old',active),('new',candidate_path)):
                where = event / f'trial_{index}' / side
                cfg = deepcopy(v5cfg)
                cfg.update(run_dir=str(where), upstream_repo=str(where/'upstream'),
                           expected_questions=len(read_json(context)['rows']), improver_policy=str(policy_path))
                cfg['search'].update(max_rounds=run['P_search_rounds_per_revision_trial'],
                                     candidates=run['P_candidate_slots_per_policy_per_trial'],
                                     repeats=config['ordinary_search']['repeats'],
                                     draft_parallel=1, eval_parallel=1, repeat_parallel=1)
                cfg.pop('manifest', None)
                cfg.pop('references', None)
                request = where / 'request.json'
                write_once(request, {'context':str(context),'source_repo':v5cfg['upstream_repo'],'config':cfg})
                receipt = where / 'revision.json'
                if not receipt.is_file():
                    status(out, 'P_search', event=number, trial=index, side=side, active_R=policy.to_dict()['version'])
                    subprocess.run([sys.executable,'-B','-m','m5rrsi.meta_search','--one-step',str(request)], check=True)
                pair[side] = read_json(receipt)
            revisions.append(pair)
        write_once(event / 'frozen_P_versions.json', revisions)

        scores = []
        for index, (pair, block) in enumerate(zip(revisions,blocks), 1):
            status(out, 'confirmation', event=number, trial=index, active_R=policy.to_dict()['version'])
            old = confirm(v5cfg,block,pair['old'],event/f'confirm_{index}'/'old')
            same_program = pair['old']['selected_P'] == pair['new']['selected_P']
            new = old if same_program else confirm(v5cfg,block,pair['new'],event/f'confirm_{index}'/'new')
            scores.append({**paired_scores(old,new),'identical_program_score_reused':same_program})
        old_correct = sum(s['old_correct'] for s in scores)
        new_correct = sum(s['new_correct'] for s in scores)
        total = sum(s['n'] for s in scores)
        result = {'status':'complete','event':number,'old_R':policy.to_dict()['version'],'candidate_R':f'R{number}',
                  'old_correct':old_correct,'new_correct':new_correct,'n':total,
                  'meta_gain':(new_correct-old_correct)/total,'accepted':new_correct>old_correct,
                  'policy_path':str(candidate_path),'trials':scores}
        write_once(event / 'result.json', result)
        if result['accepted']:
            write_json(active_path, {'policy_path':str(candidate_path),'version':f'R{number}'})
        status(out, 'complete', event=number, active_R=f'R{number}' if result['accepted'] else policy.to_dict()['version'],
               old_correct=old_correct,new_correct=new_correct,n=total,accepted=result['accepted'])
        return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--one-step', type=Path)
    parser.add_argument('--v5-run', type=Path)
    parser.add_argument('--out', type=Path)
    parser.add_argument('--initial-policy', type=Path)
    parser.add_argument('--config', type=Path)
    parser.add_argument('--diagnosis', type=Path)
    parser.add_argument('--prepare-only', action='store_true')
    args = parser.parse_args()
    if args.one_step:
        one_step(args.one_step.resolve())
        return
    try:
        if args.prepare_only:
            root = args.out.resolve()
            status(root, 'preparing')
            _, blocks = prepare(args.v5_run.resolve(), root)
            status(root, 'ready', frozen_blocks=len(blocks), roi_smoke='passed')
            print((root / 'status.json').read_text(), end='')
            return
        pilot(args.v5_run.resolve(), args.out.resolve(), args.initial_policy.resolve(),
              read_json(args.config), read_json(args.diagnosis))
    except Exception as error:
        prior = args.out / 'status.json'
        previous = read_json(prior) if prior.is_file() else {}
        status(args.out, 'failed', previous_stage=previous.get('stage'), error_type=type(error).__name__)
        raise


if __name__ == '__main__':
    main()
