"""Cached, source-anonymous V11 selection. This generator never opens labels."""
from __future__ import annotations

import argparse
from collections import Counter
from contextlib import contextmanager
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import sys
import time
from types import SimpleNamespace
import uuid

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
from run_v9_diagnostic import accounting, append, now, options_of, read_jsonl, saved_context, write_json
from v11_selection import SELECTOR_PROMPT, build_comparison, parse_choice


@contextmanager
def run_lock(out):
    import fcntl
    with (out / '.generation.lock').open('a') as handle:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def route_for(initial, candidate):
    if initial is None:
        return 'p0_missing', candidate
    if candidate is None:
        return 'candidate_missing', initial
    if initial == candidate:
        return 'inherited_agreement', initial
    return 'selector', None


def exception_chain(exc):
    # Private diagnostic; never include API headers, request bodies, or credentials.
    result, seen = [], set()
    while exc is not None and id(exc) not in seen:
        seen.add(id(exc))
        result.append({'type': type(exc).__name__, 'message': str(exc)[:1200]})
        exc = exc.__cause__
    return result


def run(a, cfg, out):
    root = Path(cfg['root'])
    source = root / cfg['source_run']
    source_status = json.loads((source / 'status.json').read_text(encoding='utf-8'))
    if source_status.get('status') != 'generation_complete':
        raise ValueError('v10_generation_not_complete')
    selection = json.loads((source / 'selection.json').read_text(encoding='utf-8'))
    rows = selection['rows']
    p0s = {r['question_id']: r for r in read_jsonl(source / 'p0_results.jsonl')}
    branches = {r['question_id']: r for r in read_jsonl(source / 'candidate_results.jsonl') if r['group'] == cfg['group']}
    qids = [r['question_id'] for r in rows]
    if len(qids) != 60 or len(set(qids)) != 60 or set(qids) != set(p0s) or set(qids) != set(branches):
        raise ValueError('fixed_sixty_source_records_incomplete')
    for row in rows:
        legal = options_of(row['question'])
        for answer in (p0s[row['question_id']]['initial'], branches[row['question_id']]['candidate']):
            if answer is not None and answer not in legal:
                raise ValueError('illegal_cached_answer')
    frozen = dict(cfg, source_commit='48b0da61ee76791592f4f2b47592b6120c36c950',
                  labels_loaded=False, question_ids=qids, selector_prompt=SELECTOR_PROMPT,
                  implementation_sha256={name: hashlib.sha256((HERE / name).read_bytes()).hexdigest()
                    for name in ('run_v11_selection.py', 'v11_selection.py')})
    frozen_path = out / 'effective_config.json'
    if frozen_path.exists() and json.loads(frozen_path.read_text(encoding='utf-8')) != frozen:
        raise ValueError('frozen_selection_configuration_changed')
    if not frozen_path.exists():
        write_json(frozen_path, frozen)
    if not (out / 'selection.json').exists():
        write_json(out / 'selection.json', selection)
    completed = {r['question_id']: r for r in read_jsonl(out / 'results.jsonl')}
    if len(completed) != len(read_jsonl(out / 'results.jsonl')):
        raise ValueError('duplicate_terminal_results')
    for qid in qids:
        terminal = out / 'checkpoints' / qid / 'terminal.json'
        if qid not in completed and terminal.exists():
            record = json.loads(terminal.read_text(encoding='utf-8'))
            append(out / 'results.jsonl', record)
            completed[qid] = record
    routes = {qid: route_for(p0s[qid]['initial'], branches[qid]['candidate'])[0] for qid in qids}
    route_counts = dict(Counter(routes.values()))
    def status(state, **extra):
        write_json(out / 'status.json', dict(status=state, updated_utc=now(),
            planned_n=60, completed_n=len(completed), group=cfg['group'], stage=cfg['stage'],
            route_counts=route_counts, selector_completed=sum(r['route']=='selector' for r in completed.values()), **extra))
    if len(completed) == 60:
        status('generation_complete')
        return 0
    status('preparing')
    for row in rows:
        qid = row['question_id']
        folder = out / 'checkpoints' / qid
        folder.mkdir(parents=True, exist_ok=True)
        if routes[qid] == 'selector' and not (folder / 'comparison.json').exists():
            packet = build_comparison(row, p0s[qid], branches[qid], root / cfg['image_root'],
                                      folder / 'artifacts', cfg['seed'])
            write_json(folder / 'comparison.json', packet)
    print(json.dumps({'event':'prepared','planned_n':60,'routes':route_counts,'utc':now()}),flush=True)
    if a.prepare_only:
        status('prepared')
        return 0
    key = sys.stdin.readline().strip() if a.api_key_stdin else ''
    if not key:
        raise ValueError('missing_api_key')
    from langchain_openai import ChatOpenAI
    from langchain_core.messages import HumanMessage, SystemMessage, messages_to_dict
    from memory_agent_eval import BudgetedModel
    from run_bc_recovery import new_ctx
    from provider_ledger import ProviderLedger
    from provider_profile import get_profile
    profile = get_profile(cfg['model'])
    ledger_path = root / cfg['ledger']
    # Read the actual existing policy. Never create, reset, or increase a budget.
    if not ledger_path.is_file():
        raise ValueError('existing_ledger_required')
    state = json.loads(ledger_path.read_text(encoding='utf-8'))
    if state.get('blocked'):
        raise ValueError('existing_ledger_blocked')
    cap = state['policy']['cap_cny']
    if Decimal(cap) <= 0:
        raise ValueError('invalid_existing_cap')
    runtime = SimpleNamespace(tools={}, tool_provenance={}, model=ChatOpenAI(
        model=profile.model,base_url=profile.base_url,api_key=key,temperature=cfg['temperature'],
        top_p=cfg['top_p'],max_tokens=cfg['max_output_tokens'],max_retries=0,
        timeout=cfg['request_timeout_seconds']))
    args = SimpleNamespace(max_output_tokens=cfg['max_output_tokens'],max_case_seconds=cfg['max_case_seconds'])
    with ProviderLedger(ledger_path,profile,cap_cny=cap,
            inherit_ledger_path=root/cfg['inherit_ledger']) as ledger, (out/'execution.trace.jsonl').open('a',encoding='utf-8') as trace:
        if not (out/'ledger_start.json').exists():
            write_json(out/'ledger_start.json',{'committed_cny':state['committed_cny'],
                'cap_cny':cap,'ledger_id':state['ledger_id'],'recorded_utc':now()})
        for row in rows:
            qid=row['question_id']
            if qid in completed:
                continue
            folder=out/'checkpoints'/qid
            if (folder/'request_started.json').exists():
                raise RuntimeError('interrupted_request_requires_targeted_recovery:'+qid)
            route, answer = route_for(p0s[qid]['initial'],branches[qid]['candidate'])
            began, started=time.monotonic(),now()
            result=dict(question_id=qid,group=cfg['group'],stage=cfg['stage'],
                initial=p0s[qid]['initial'],candidate=branches[qid]['candidate'],final=answer,
                route=route,selector=None,selector_error=None,fallback=None,stop_run=False,
                accounting=accounting({}),timing=None)
            status('running',active_route=route,active_started_utc=started)
            print(json.dumps({'event':'case_started','index':qids.index(qid)+1,'route':route,'utc':started}),flush=True)
            if route == 'selector':
                packet=json.loads((folder/'comparison.json').read_text(encoding='utf-8'))
                paths=[Path(i['path']) for i in packet['images']]
                ctx=new_ctx(qid,str(uuid.uuid4()),paths,runtime,args,trace,0,1)
                ctx['run_id'],ctx['arm']=out.name,cfg['stage']+'_'+cfg['group']
                messages=[SystemMessage(content=SELECTOR_PROMPT),HumanMessage(content=packet['content'])]
                write_json(folder/'request_started.json',{'started_utc':started,'thread_id':ctx['thread_id']})
                try:
                    response=BudgetedModel(runtime.model,ledger,ctx,profile).invoke(messages)
                    messages.append(response)
                    choice,payload=parse_choice(response.content,set(packet['refs']))
                    result.update(final=packet['private_mapping'][choice],selector=payload)
                except Exception as exc:
                    result.update(final=packet['private_mapping']['X'],
                        selector_error=type(exc).__name__,fallback='fixed_anonymous_X')
                    write_json(folder/'error.json',exception_chain(exc))
                result.update(accounting=accounting(ctx),stop_run=ctx.get('stop_run',False),
                    stop_reason=ctx.get('stop_reason') or ctx.get('money_status'))
                write_json(folder/'messages.json',messages_to_dict(messages))
                write_json(folder/'context.json',saved_context(ctx))
            result['timing']={'started_utc':started,'ended_utc':now(),'elapsed_s':round(time.monotonic()-began,3)}
            write_json(folder/'terminal.json',result)
            append(out/'results.jsonl',result)
            completed[qid]=result
            print(json.dumps({'event':'case_finished','completed_n':len(completed),'route':route,
                'error':result['selector_error'],'elapsed_s':result['timing']['elapsed_s'],'utc':now()}),flush=True)
            if result['stop_run']:
                status('stopped',reason=result.get('stop_reason'))
                return 2
        # Final total is read once, solely for the completed-run cost report.
        final_state=json.loads(ledger_path.read_text(encoding='utf-8'))
        first=json.loads((out/'ledger_start.json').read_text(encoding='utf-8'))
        write_json(out/'ledger_final_summary.json',{'start_committed_cny':first['committed_cny'],
            'end_committed_cny':final_state['committed_cny'],
            'run_increment_cny':str(Decimal(final_state['committed_cny'])-Decimal(first['committed_cny'])),
            'recorded_utc':now(),'basis':'existing_assumed_rate_ledger_not_invoice'})
    status('generation_complete')
    return 0


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--prepare-only',action='store_true')
    p.add_argument('--api-key-stdin',action='store_true')
    a=p.parse_args(argv)
    cfg=json.loads(a.config.read_text(encoding='utf-8'))
    out=a.out.resolve();out.mkdir(parents=True,exist_ok=True)
    with run_lock(out):
        try:
            return run(a,cfg,out)
        except Exception as exc:
            write_json(out/'fatal_error.json',{'utc':now(),'chain':exception_chain(exc)})
            prior=json.loads((out/'status.json').read_text()) if (out/'status.json').exists() else {}
            write_json(out/'status.json',dict(prior,status='stopped',updated_utc=now(),reason=type(exc).__name__))
            raise


if __name__ == '__main__':
    raise SystemExit(main())
