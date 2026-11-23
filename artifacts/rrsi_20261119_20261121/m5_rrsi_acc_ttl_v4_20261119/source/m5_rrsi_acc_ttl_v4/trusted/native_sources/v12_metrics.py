"""Isolated V12 scoring after all shared first reads, then B and A, finish.

This module imports no inference component. It never opens reference labels until
the fixed-sixty completion and B-before-A terminal order checks have passed.
Saved predictions remain untouched; shared first-read resources are counted once.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from math import comb
from pathlib import Path

try:
    from . import v9_metrics as base
    from .v10_metrics import CATEGORIES, _categories
except ImportError:
    import v9_metrics as base
    from v10_metrics import CATEGORIES, _categories

GROUPS = ('B', 'A')


def _selection(selection):
    rows = selection.get('rows', [])
    if not isinstance(rows, list) or not rows:
        raise ValueError('Selection must contain planned rows')
    planned = [base._qid(row) for row in rows]
    if len(planned) != len(set(planned)):
        raise ValueError('Selection contains duplicate questions')
    if selection.get('planned_n', len(planned)) != len(planned):
        raise ValueError('selection.planned_n differs from its rows')
    categories = {base._qid(row): _categories(row) for row in rows}
    return planned, categories


def _terminals(rows, planned, *, grouped=False):
    indexed, order = {}, []
    for row in rows:
        if row.get('record_type') in ('start', 'started'):
            continue
        qid = base._qid(row)
        if qid not in planned:
            raise ValueError(f'Unplanned question: {qid}')
        group = row.get('group')
        if grouped and group not in GROUPS:
            raise ValueError(f'Unknown V12 group: {group}')
        key = (qid, group) if grouped else qid
        if key in indexed:
            raise ValueError(f'Duplicate terminal: {key}')
        if row.get('status') in ('running', 'initializing', 'started', 'not_run', 'pending'):
            raise ValueError(f'Nonterminal status in result: {key}')
        indexed[key] = row
        if grouped:
            order.append(group)
    return indexed, order


def validate_terminals(selection, initial_rows, branch_rows, *, fixed_sixty=False):
    planned, categories = _selection(selection)
    if fixed_sixty and len(planned) != 60:
        raise ValueError('V12 reporting requires the frozen 60-question selection')
    initial, _ = _terminals(initial_rows, planned)
    branches, order = _terminals(branch_rows, planned, grouped=True)
    if len(initial) != len(planned) or len(branches) != len(planned)*2:
        raise ValueError('Generation is incomplete; isolated labels have not been opened')
    if order != ['B']*len(planned) + ['A']*len(planned):
        raise ValueError('V12 requires all B terminals before all A terminals')
    for (qid, group), row in branches.items():
        fallback = row.get('status') == 'fallback_initial'
        if bool(row.get('fallback_to_initial')) != fallback:
            raise ValueError(f'Inconsistent fallback status: {qid}:{group}')
        if fallback:
            first = base.letter(initial[qid].get('first_answer'))
            if first is None or base.letter(row.get('answer')) != first or row.get('solver_answer') is not None:
                raise ValueError(f'Fallback must preserve a legal initial answer without a solver answer: {qid}:{group}')
    return planned, categories, initial, branches


def _prediction(row, key):
    # The retained legal option is scored even when a nonfatal action warning is
    # recorded. Only an explicitly recorded controller fallback retains the first
    # answer; the scorer never fills a missing prediction itself.
    return base.letter(row.get(key)) if row else None


def paired(initial, final, labels, qids):
    names = ('correct_to_correct', 'correct_to_wrong', 'correct_to_missing',
             'legal_wrong_to_correct', 'legal_wrong_to_wrong', 'legal_wrong_to_missing',
             'initial_missing_to_correct', 'initial_missing_to_wrong', 'initial_missing_to_missing')
    ids = {name: [] for name in names}
    for qid in qids:
        first, answer, gold = initial[qid], final[qid], labels[qid]
        source = 'initial_missing' if first is None else 'correct' if first == gold else 'legal_wrong'
        destination = 'missing' if answer is None else 'correct' if answer == gold else 'wrong'
        ids[source + '_to_' + destination].append(qid)
    counts = {name: len(values) for name, values in ids.items()}
    legal_corrections = counts['legal_wrong_to_correct']
    recoveries = counts['initial_missing_to_correct']
    legal_harms = counts['correct_to_wrong']
    missing_harms = counts['correct_to_missing']
    total_net = legal_corrections + recoveries - legal_harms - missing_harms
    return {
        'planned_n': len(qids),
        'corrections_from_legal_wrong': legal_corrections,
        'initial_failure_recoveries': recoveries,
        'harms_to_legal_wrong': legal_harms,
        'correct_to_missing': missing_harms,
        'all_harms': legal_harms + missing_harms,
        'total_net': total_net,
        'net_excluding_failure_recovery': legal_corrections - legal_harms - missing_harms,
        'accuracy_difference_over_planned': base._ratio(total_net, len(qids)),
        'transitions': counts,
        'question_ids': ids,
    }


def _comparison(a, b, labels, qids):
    buckets = {name: [] for name in ('both_correct', 'A_only_correct', 'B_only_correct', 'both_not_correct')}
    for qid in qids:
        ac, bc = a[qid] == labels[qid], b[qid] == labels[qid]
        name = 'both_correct' if ac and bc else 'A_only_correct' if ac else 'B_only_correct' if bc else 'both_not_correct'
        buckets[name].append(qid)
    counts = {name: len(values) for name, values in buckets.items()}
    discordant = counts['A_only_correct'] + counts['B_only_correct']
    smaller = min(counts['A_only_correct'], counts['B_only_correct'])
    exact_p = min(1.0, 2*sum(comb(discordant, i) for i in range(smaller+1))/(2**discordant)) if discordant else 1.0
    net = counts['B_only_correct'] - counts['A_only_correct']
    return {**counts, 'planned_n': len(qids), 'B_minus_A_correct': net,
            'B_minus_A_accuracy_over_planned': base._ratio(net, len(qids)),
            'exact_mcnemar_two_sided_p': round(exact_p, 8),
            'question_ids': buckets,
            'note': 'Descriptive paired development comparison. B jointly adds knowledge and experience; this does not isolate their individual effects. Fixed B-then-A execution order is not randomized.'}


def score(selection, initial_rows, branch_rows, labels, *, protocol=None):
    """Pure completed-run calculation; smaller synthetic selections support tests."""
    planned, categories, initial_records, branch_records = validate_terminals(selection, initial_rows, branch_rows)
    if set(labels) != set(planned) or any(base.letter(labels[qid]) is None for qid in planned):
        raise ValueError('Labels must cover exactly the planned questions')
    labels = {qid: base.letter(labels[qid]) for qid in planned}
    first = {qid: _prediction(initial_records[qid], 'first_answer') for qid in planned}
    predictions = {group: {qid: _prediction(branch_records[qid, group], 'answer') for qid in planned} for group in GROUPS}
    candidates = {group: {qid: _prediction(branch_records[qid, group], 'candidate_answer') for qid in planned} for group in GROUPS}
    solvers = {group: {qid: (_prediction(branch_records[qid, group], 'solver_answer')
                          if 'solver_answer' in branch_records[qid, group]
                          else predictions[group][qid])
                         if branch_records[qid, group].get('status') == 'completed' else None
                         for qid in planned} for group in GROUPS}
    groups = {}
    for group in GROUPS:
        records = [branch_records[qid, group] for qid in planned]
        groups[group] = {
            'terminal_n': len(records),
            'candidate': base._summary(candidates[group], labels, planned),
            'candidate_paired': paired(first, candidates[group], labels, planned),
            'final': base._summary(predictions[group], labels, planned),
            'paired': paired(first, predictions[group], labels, planned),
            'final_vs_candidate': paired(candidates[group], predictions[group], labels, planned),
            'solver': base._summary(solvers[group], labels, planned),
            'resources': base._resources(records),
            'execution': {'status_counts': dict(Counter(str(r.get('status', 'unspecified')) for r in records)),
                          'records_with_error': sum(bool(r.get('error')) for r in records),
                          'solver_completed_count': sum(r.get('status') == 'completed' for r in records),
                          'fallback_count': sum(r.get('status') == 'fallback_initial' for r in records),
                          'fallback_correct_count': sum(branch_records[q, group].get('status') == 'fallback_initial'
                                                        and predictions[group][q] == labels[q] for q in planned)},
            'knowledge_injection_n': sum(bool(r.get('k_ids')) for r in records),
            'experience_injection_n': sum(bool(r.get('e_ids')) for r in records),
            'categories': {c: {
                'initial': base._summary(first, labels, [q for q in planned if c in categories[q]]),
                'candidate': base._summary(candidates[group], labels, [q for q in planned if c in categories[q]]),
                'candidate_paired': paired(first, candidates[group], labels, [q for q in planned if c in categories[q]]),
                'final': base._summary(predictions[group], labels, [q for q in planned if c in categories[q]]),
                'paired': paired(first, predictions[group], labels, [q for q in planned if c in categories[q]]),
                'fallback_count': sum(branch_records[q, group].get('status') == 'fallback_initial'
                                      for q in planned if c in categories[q])}
                for c in CATEGORIES},
        }
    per_question = []
    for qid in planned:
        item = {'question_id': qid, 'official_categories': sorted(categories[qid]), 'reference_answer': labels[qid],
                'initial': {'answer': first[qid], 'correct': first[qid] == labels[qid],
                            'status': initial_records[qid].get('status'), 'error': initial_records[qid].get('error')}}
        for group in GROUPS:
            row = branch_records[qid, group]
            transitions = paired(first, predictions[group], labels, [qid])['transitions']
            candidate_transitions = paired(first, candidates[group], labels, [qid])['transitions']
            item[group] = {'answer': predictions[group][qid], 'correct': predictions[group][qid] == labels[qid],
                           'candidate_answer': candidates[group][qid], 'candidate_correct': candidates[group][qid] == labels[qid],
                           'solver_answer': solvers[group][qid], 'solver_correct': solvers[group][qid] == labels[qid],
                           'fallback_to_initial': row.get('status') == 'fallback_initial',
                           'status': row.get('status'), 'error': row.get('error'),
                           'transition_from_initial': next(k for k, count in transitions.items() if count),
                           'candidate_transition_from_initial': next(k for k, count in candidate_transitions.items() if count),
                           'k_ids': row.get('k_ids', []), 'e_ids': row.get('e_ids', [])}
        per_question.append(item)
    output = {
        'schema_version': 2, 'implementation': 'v12-full-option-rematching-with-explicit-fallback',
        'created_utc': datetime.now(timezone.utc).isoformat(), 'run_status': 'completed',
        'planned_n': len(planned), 'execution_order': list(GROUPS),
        'initial_terminal_n': len(initial_records), 'branch_terminal_n': len(branch_records),
        'initial': base._summary(first, labels, planned),
        'initial_resources': base._resources(initial_records.values()),
        'groups': groups, 'paired_B_vs_A': _comparison(predictions['A'], predictions['B'], labels, planned),
        'candidate_B_vs_A': _comparison(candidates['A'], candidates['B'], labels, planned),
        'total_new_resources': base._resources([*initial_records.values(), *branch_records.values()]),
        'category_denominators': {c: sum(c in v for v in categories.values()) for c in CATEGORIES},
        'category_B_vs_A': {c: _comparison(predictions['A'], predictions['B'], labels, [q for q in planned if c in categories[q]]) for c in CATEGORIES},
        'protocol': protocol or {}, 'historical_v10': {'status': 'not_requested'},
        'limitations': [
            'All planned questions remain in the denominator; a missing answer is not correct.',
            'Initial, targeted-read candidate and final-controller answers are separate stages, each with the full planned denominator.',
            'On execution failure only an explicitly saved controller fallback retains the legal initial answer. It is not a new solver success or an initial-failure recovery.',
            'Candidate or solver answers are never synthesized by scoring; final-versus-candidate missing-answer recovery can include controller fallback and is not a new-solver recovery claim.',
            'Legal wrong-answer correction, initial missing-answer recovery, legal harm and correct-to-missing failure are separate.',
            'Seven task categories overlap; their counts/accuracies must not be summed or averaged into Overall.',
            'Shared first-read calls/costs are counted once; A/B resources include only their additional stages.',
            'Resource values use saved accounting, not a fresh ledger scan or supplier invoice.',
            'A/B use a common initial cache and configured equal caps, but realized call counts may differ.',
            'B is run before A; temporal/provider variation is not randomized away.',
            'The fixed sixty are a repeatedly inspected development set, not an independent blind test.',
            'V10 is a historical protocol comparison, not an equal-budget controlled contrast with V12.',
            'The separate qwen3.8-max cached adjudication experiment is outside this report.',
            'No prediction record is modified by scoring; labels are read only after complete generation.',
        ],
    }
    return output, per_question


def _historical_v10(run, planned):
    """Read the already completed V10 aggregate; do not re-run V10 scoring."""
    run = Path(run)
    selection = json.loads((run/'selection.json').read_text(encoding='utf-8-sig'))
    if set(base._qid(r) for r in selection['rows']) != set(planned):
        raise ValueError('Historical V10 selection differs from V12 fixed inputs')
    data = json.loads((run/'paired_metrics.json').read_text(encoding='utf-8-sig'))
    if data.get('run_status') != 'completed' or data.get('planned_n') != len(planned):
        raise ValueError('Historical V10 metrics are not complete for the same selection')
    return {'status': 'completed_historical_reference', 'source_run': run.name,
            'source_file': 'paired_metrics.json',
            'results': {'P0': data['p0'], **{g: data['groups'][g]['final'] for g in ('V', 'VK', 'VKE')}},
            'historical_resources_excluded_from_v12_total': True,
            'note': 'Previously completed original protocol; no cached V10 costs or predictions are added to V12 new execution resources. Different protocol/model-call allocation prevents causal attribution to version alone.'}


def markdown(payload):
    n = payload['planned_n']; initial = payload['initial']; pct = base._percent
    lines = ['# V12 完整 60 题结果', '',
             f"状态：**{payload['run_status']}**。固定分母 **{n}**，顺序 B→A，共用首次读图缓存。", '',
             '| 组 | 正确/固定分母 | 正确率 | 合法错答纠正 | 首答缺答恢复 | 正确→合法错答 | 正确→缺答 | 总净增益 | 排除恢复后净增益 |',
             '|---|---:|---:|---:|---:|---:|---:|---:|---:|',
             f"| 首答 | {initial['correct']}/{n} | {pct(initial['accuracy_over_planned'])} | — | — | — | — | — | — |"]
    for g in GROUPS:
        d=payload['groups'][g]
        for stage, summary_key, paired_key in [('取证后候选','candidate','candidate_paired'),('最终（含明确回退）','final','paired')]:
            p=d[paired_key];s=d[summary_key]
            lines.append(f"| V12-{g} {stage} | {s['correct']}/{n} | {pct(s['accuracy_over_planned'])} | {p['corrections_from_legal_wrong']} | {p['initial_failure_recoveries']} | {p['harms_to_legal_wrong']} | {p['correct_to_missing']} | {p['total_net']:+d} | {p['net_excluding_failure_recovery']:+d} |")
    p=payload['paired_B_vs_A']
    lines+=['', f"B−A：**{p['B_minus_A_correct']:+d}/{n}**；只有 B 正确 {p['B_only_correct']} 题，只有 A 正确 {p['A_only_correct']} 题。探索性 exact McNemar p={p['exact_mcnemar_two_sided_p']}。", '',
            'B 同时增加知识与经验，因此本轮不分离两者的独立贡献。固定 B→A 顺序也没有消除时段差异。', '',
            '| 组 | 最终求解完成 | 最终求解正确/完整分母 | 失败后回退首答 | 回退中正确 | 仍无最终答案 |',
            '|---|---:|---:|---:|---:|---:|']
    for g in GROUPS:
        d=payload['groups'][g];e=d['execution']
        lines.append(f"| {g} | {e['solver_completed_count']} | {d['solver']['correct']}/{n} | {e['fallback_count']} | {e['fallback_correct_count']} | {d['final']['missing']} |")
    lines+=['','回退仅由控制器保留已有合法首答，首答不进入模型输入；回退不计作新的求解成功或首答失败恢复。候选缺答也保留在完整分母中。', '',
            '## 七类重叠任务结果', '', '| 类别 | N | 首答正确 | B 候选 | B 最终 | A 候选 | A 最终 | 最终 B−A |', '|---|---:|---:|---:|---:|---:|---:|---:|']
    for c in CATEGORIES:
        b=payload['groups']['B']['categories'][c]; a=payload['groups']['A']['categories'][c]
        lines.append(f"| {c} | {payload['category_denominators'][c]} | {b['initial']['correct']} | {b['candidate']['correct']} | {b['final']['correct']} | {a['candidate']['correct']} | {a['final']['correct']} | {payload['category_B_vs_A'][c]['B_minus_A_correct']:+d} |")
    lines+=['','各类可重叠，Overall 只计每题一次。','','## 新增资源与耗时','','| 阶段 | 终态数 | 模型调用 | 工具尝试 | 输入 token | 输出 token | 逻辑费用 CNY | 题内耗时之和(秒) |','|---|---:|---:|---:|---:|---:|---:|---:|']
    resources=[('共享首读',payload['initial_resources'])]+[(g,payload['groups'][g]['resources']) for g in GROUPS]+[('新增合计，首读计一次',payload['total_new_resources'])]
    for name,r in resources:
        vals=[r[k]['sum_observed'] for k in ['model_calls','tool_calls','input_tokens','output_tokens','logical_cost_cny','elapsed_s']]
        lines.append('| '+ ' | '.join(map(str,[name,r['records_n']]+['N/A' if v is None else v for v in vals]))+' |')
    lines+=['','题内耗时求和不等同端到端墙钟；未知用量字段没有当成零。费用是保存的原记账口径，不是供应商账单。共享首读没有重复计入 A/B。','','## V10 历史对照','']
    history=payload['historical_v10']
    if history['status']=='completed_historical_reference':
        lines+=['| 历史组 | 正确/固定分母 |','|---|---:|']
        for name,r in history['results'].items():lines.append(f"| V10 {name} | {r['correct']}/{r['planned_n']} |")
        lines+=['','V10 调用协议不同，以上仅作历史描述；其费用不进入本轮新增合计。']
    else:lines+=['本次未指定历史 V10 结果目录。']
    lines+=['','## 范围与限制','']+['- '+x for x in payload['limitations']]
    return '\n'.join(lines)+'\n'


def generate_report(run, labels_path, *, v10_run=None):
    run=Path(run)
    selection=json.loads((run/'selection.json').read_text(encoding='utf-8-sig'))
    initial=base.read_jsonl(run/'initial_results.jsonl')
    branches=base.read_jsonl(run/'branch_results.jsonl')
    status_path=run/'status.json'
    status=json.loads(status_path.read_text(encoding='utf-8-sig')) if status_path.exists() else {}
    if status.get('status')!='generation_complete':
        raise ValueError('Generation is incomplete; isolated labels have not been opened')
    planned,_,_,_=validate_terminals(selection,initial,branches,fixed_sixty=True)
    # All completion/uniqueness/order checks precede the first reference read.
    labels=base._labels(labels_path,planned)
    cfg_path=run/'effective_config.json'
    protocol=json.loads(cfg_path.read_text(encoding='utf-8-sig')) if cfg_path.exists() else {}
    payload, per_question=score(selection,initial,branches,labels,protocol=protocol)
    if v10_run is not None:payload['historical_v10']=_historical_v10(v10_run,planned)
    base._atomic(run/'metrics.json',json.dumps(payload,ensure_ascii=False,indent=2)+'\n')
    base._atomic(run/'metrics.md',markdown(payload))
    base._atomic(run/'per_question.json',json.dumps({'post_generation_only':True,'planned_n':len(planned),'records':per_question},ensure_ascii=False,indent=2)+'\n')
    return payload


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run',type=Path,required=True)
    p.add_argument('--labels',type=Path,required=True)
    p.add_argument('--v10-run',type=Path)
    args=p.parse_args(argv)
    result=generate_report(args.run,args.labels,v10_run=args.v10_run)
    print(json.dumps({'status':result['run_status'],'planned_n':result['planned_n'],
                      'initial_correct':result['initial']['correct'],
                      'candidate_correct':{g:result['groups'][g]['candidate']['correct'] for g in GROUPS},
                      'final_correct':{g:result['groups'][g]['final']['correct'] for g in GROUPS},
                      'fallback_count':{g:result['groups'][g]['execution']['fallback_count'] for g in GROUPS},
                      'B_minus_A':result['paired_B_vs_A']['B_minus_A_correct']}))
    return 0


if __name__=='__main__':raise SystemExit(main())
