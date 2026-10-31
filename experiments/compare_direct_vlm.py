"""Post-generation D0 scoring and public comparison against frozen caches.

Labels are read only here, after generation_complete and 60 terminal records.
No provider, network, tools or real ledger is opened by this process.
"""
from __future__ import annotations
import argparse
from collections import Counter
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from run_direct_vlm import read, write, read_lines


def paired(old, new, labels, qids):
    buckets = {k: [] for k in ('legal_wrong_to_correct', 'correct_to_legal_wrong', 'missing_to_correct', 'correct_to_missing')}
    for q in qids:
        a, b, gold = old[q], new[q], labels[q]
        if a is not None and a != gold and b == gold: buckets['legal_wrong_to_correct'].append(q)
        if a == gold and b is not None and b != gold: buckets['correct_to_legal_wrong'].append(q)
        if a is None and b == gold: buckets['missing_to_correct'].append(q)
        if a == gold and b is None: buckets['correct_to_missing'].append(q)
    counts = {k: len(v) for k, v in buckets.items()}
    net = counts['legal_wrong_to_correct']-counts['correct_to_legal_wrong']+counts['missing_to_correct']-counts['correct_to_missing']
    assert net == sum(new[q] == labels[q] for q in qids)-sum(old[q] == labels[q] for q in qids)
    return dict(counts, net=net, planned_n=len(qids), question_ids=buckets)


def counts(predictions, labels, qids):
    correct = sum(predictions[q] == labels[q] for q in qids)
    valid = sum(predictions[q] is not None for q in qids)
    return {'correct': correct, 'planned_n': len(qids), 'accuracy': correct/len(qids), 'valid': valid, 'missing': len(qids)-valid}


def resource_summary(records):
    attempts = [a for r in records for a in r['attempts']]
    costs = [a.get('settlement', {}).get('charged_cny') for a in attempts if a.get('settlement')]
    return {'model_requests': len(attempts), 'technical_extra_requests': sum(a['ordinal'] > 1 for a in attempts),
            'medical_tool_calls': 0, 'crop_calls': 0, 'retrieval_calls': 0,
            'input_tokens': sum((a.get('usage') or {}).get('input_tokens', 0) for a in attempts),
            'output_tokens': sum((a.get('usage') or {}).get('output_tokens', 0) for a in attempts),
            'usage_missing_attempts': sum(not a.get('usage') for a in attempts),
            'saved_settlement_cny': str(sum((Decimal(c) for c in costs), Decimal(0))),
            'settlement_missing_attempts': len(attempts)-len(costs),
            'stage_elapsed_s_sum': round(sum(r['elapsed_s'] for r in records), 3),
            'started_utc': records[0]['started_utc'], 'ended_utc': records[-1]['ended_utc'],
            'price_basis': 'existing_provider_profile_assumptions_not_invoice'}


def generate(run, v12, p0_path, out):
    if read(run/'status.json').get('status') != 'generation_complete': raise ValueError('generation_not_complete')
    selection = read(run/'selection.json')['rows']; qids = [r['question_id'] for r in selection]
    records = read_lines(run/'predictions.jsonl'); direct = {r['question_id']: r for r in records}
    if len(records) != 60 or set(direct) != set(qids): raise ValueError('all60_terminals_required')
    if any(r['status'] not in {'completed', 'invalid_answer', 'request_failed'} for r in records): raise ValueError('nonterminal_record')
    # First label access: already scored, frozen public V12 outcomes.
    v12_records = {r['question_id']: r for r in read(v12/'per_question.json')['records']}
    p0_records = {r['question_id']: r for r in read(p0_path)}
    if set(v12_records) != set(qids) or set(p0_records) != set(qids): raise ValueError('historical_id_mismatch')
    labels = {q: v12_records[q]['reference_answer'] for q in qids}
    if any(p0_records[q]['reference_answer'] != labels[q] for q in qids): raise ValueError('historical_reference_conflict')
    views = {'D0': {q: direct[q]['answer'] for q in qids},
             'V12_initial': {q: v12_records[q]['initial']['answer'] for q in qids},
             'V10_P0': {q: p0_records[q]['p0'] for q in qids}}
    for g in ('A', 'B'):
        for stage, field in [('candidate', 'candidate_answer'), ('solver', 'solver_answer'), ('final', 'answer')]:
            views[f'V12_{g}_{stage}'] = {q: v12_records[q][g].get(field) for q in qids}
    totals = {name: counts(values, labels, qids) for name, values in views.items()}
    transitions = {name+'_to_D0': paired(values, views['D0'], labels, qids) for name, values in views.items() if name != 'D0'}
    for g in ('A', 'B'):
        for old, new in [('V12_initial', f'V12_{g}_candidate'), (f'V12_{g}_candidate', f'V12_{g}_solver'),
                         (f'V12_{g}_candidate', f'V12_{g}_final'), (f'V12_{g}_solver', f'V12_{g}_final')]:
            transitions[old+'_to_'+new] = paired(views[old], views[new], labels, qids)
    subsets = {
        'D0_correct_initial_not': [q for q in qids if views['D0'][q] == labels[q] and views['V12_initial'][q] != labels[q]],
        'initial_correct_lost_A_or_B': [q for q in qids if views['V12_initial'][q] == labels[q] and any(views[f'V12_{g}_final'][q] != labels[q] for g in ('A','B'))],
        'D0_not_correct_agent_correct': [q for q in qids if views['D0'][q] != labels[q] and any(views[f'V12_{g}_final'][q] == labels[q] for g in ('A','B'))],
        'D0_new_common_error_recovery': [q for q in qids if views['D0'][q] == labels[q] and all(views[n][q] != labels[q] for n in ('V10_P0','V12_initial','V12_A_final','V12_B_final'))],
        'all_five_not_correct': [q for q in qids if all(views[n][q] != labels[q] for n in ('D0','V10_P0','V12_initial','V12_A_final','V12_B_final'))]}
    out.mkdir(parents=True, exist_ok=True)
    # Reuse exactly the already public original pixels. Every outgoing image data
    # URI must resolve to a previously published V12 asset, avoiding new copies.
    from export_v12_public import PublicAssets
    class ReusedAssets(PublicAssets):
        def put(self, data):
            digest = hashlib.sha256(data).hexdigest()
            paths = list((v12/'assets').glob(digest+'.*'))
            if len(paths) != 1: raise ValueError('D0_image_not_in_frozen_V12_assets')
            public = '../v12/results/assets/'+paths[0].name
            self.manifest[digest] = {'path': public, 'bytes': len(data), 'reuse': True}
            return public
    assets = ReusedAssets(out, run)
    comparisons = []
    for row in selection:
        q = row['question_id']; request = read(run/'checkpoints'/q/'request.json')
        assets.collect(request)
        write(out/'requests'/f'{q}.json', assets.clean(request, Path('requests')))
        for a in direct[q]['attempts']:
            path = run/'checkpoints'/q/f"attempt_{a['ordinal']}"/'response.json'
            if path.exists(): write(out/'responses'/f"{q}_{a['ordinal']}.json", assets.clean(read(path), Path('responses')))
        comparisons.append({'question_id': q, 'reference': labels[q], 'question': row['question'],
            'D0': {'answer': direct[q]['answer'], 'status': direct[q]['status'], 'reason_missing': direct[q]['reason_missing'],
                   'request': f'requests/{q}.json', 'responses': [f"responses/{q}_{a['ordinal']}.json" for a in direct[q]['attempts'] if a.get('response_received')]},
            'V10_P0': {'answer': p0_records[q]['p0'], 'status': p0_records[q]['p0_status']},
            'V12': {k: v12_records[q][k] for k in ('initial','A','B')},
            'original_images_and_V12_traces': f'../v12/results/cases/{q}.md'})
    clean_records = [assets.clean(r) for r in records]
    with (out/'predictions.jsonl').open('w',encoding='utf-8',newline='\n') as f:
        for r in clean_records: f.write(json.dumps(r,ensure_ascii=False)+'\n')
    protocol = read(run/'protocol.json')
    write(out/'protocol.json', assets.clean(protocol)); write(out/'per_question.json', {'planned_n':60, 'records': comparisons})
    write(out/'transitions.json', {'comparisons':transitions,'difference_sets':subsets})
    resources = resource_summary(records)
    resources['ledger_saved_summary'] = read(run/'ledger_final_summary.json')
    from datetime import datetime
    resources['wall_elapsed_s'] = (datetime.fromisoformat(resources['ended_utc'])-datetime.fromisoformat(resources['started_utc'])).total_seconds()
    metrics = read(v12/'metrics.json')
    resources['historical_V12'] = {'shared_initial': metrics['initial_resources'],
                                  'A_incremental': metrics['groups']['A']['resources'], 'B_incremental': metrics['groups']['B']['resources'],
                                  'shared_cost_note': 'Shared initial counted once for entire V12; arm resources are incremental, not new D0 costs.'}
    resources['historical_P0'] = {'model_calls': None, 'cost_cny': None, 'note': 'Not present in the public per-question outcome cache; not imputed.'}
    write(out/'cost_timing.json',resources); write(out/'metrics.json',{'status':'completed','totals':totals,'source_cache_commit':protocol['historical_cache_commit']})
    write(out/'asset-references.json',list(assets.manifest.values()))
    # One next intervention, selected by the observed diagnostic contrast.
    gain = transitions['V12_initial_to_D0']['net']
    if gain >= 3:
        next_step = '优先把下一版 Agent 的首读改为本轮简洁独立答案与短依据；后续仅在存在明确待判属性时规划一次针对性观察，并在独立样本验证。'
    else:
        next_step = '优先改最终证据整合与停止机制：只有新增观察明确解决了选项间的待判属性时才触发改答，其余保留已有合法选择；不得用参考答案决定是否改答，并在独立样本验证。'
    headline = f"D0 正确 {totals['D0']['correct']}/60，相对 V12 首答净变化 {gain:+d} 题；这是固定开发集上的提示/输出协议对照，不是工具或记忆贡献。"
    table = ['| 组 | 正确/60 | 准确率 | 有效回答 | 缺答 |','|---|---:|---:|---:|---:|']
    for name in ('D0','V12_initial','V12_A_final','V12_B_final','V10_P0'):
        v=totals[name]; table.append(f"| {name} | {v['correct']}/60 | {v['accuracy']:.1%} | {v['valid']} | {v['missing']} |")
    text = '# D0 无工具直接作答对照\n\n'+headline+'\n\n'+'\n'.join(table)+'\n\n'
    text += f"D0 实际请求 {resources['model_requests']} 次，技术额外请求 {resources['technical_extra_requests']} 次，医学工具调用 **0** 次；输入/输出 tokens 为 {resources['input_tokens']}/{resources['output_tokens']}。保存结算费用 {resources['saved_settlement_cny']} CNY，账本本轮增量 {resources['ledger_saved_summary']['run_increment_cny']} CNY；均为既有计价假设，不是供应商账单。墙钟耗时 {resources['wall_elapsed_s']:.1f} 秒。\n\n"
    text += '**下一轮唯一最高优先级改动：**'+next_step+'\n\n'
    text += '[协议](protocol.json) · [完整逐题对照](per_question.md) · [四项转换与差异集合](transitions.json) · [失败分析](failure_analysis.md) · [调用与费用](cost_timing.json) · [原始预测](predictions.jsonl)\n\n'
    text += '生成进程不读取参考答案或旧预测，评分仅在全部60个终态完成后执行。固定旧缓存提交为 `'+protocol['historical_cache_commit']+'`。V12 候选、真实求解器与控制器采用答案分别列出，回退不能算作模型新解对。D0 与 V12 首答比较仍同时改变了提示与输出要求，不能唯一归因为减少结构化字段；D0 与 P0 只是不同图像/提示协议下的历史参考。该60题为多轮使用开发集，单次非随机对照不能证明泛化或唯一因果。\n\n'
    text += '运行：`python experiments/run_direct_vlm.py --config configs/direct_qwen60.json --out runs/direct_qwen60 --resume --api-key-stdin`。评分/导出：`python experiments/compare_direct_vlm.py --run local_assets/direct_qwen60 --v12-public reports/v12/results --p0-public reports/v10/per-question-outcomes.json --out reports/direct_qwen60`。\n'
    (out/'README.md').write_text(text,encoding='utf-8')
    lines=['# 完整60题逐题对照','','字母为原完整选项；缺答为 —。独立路径之间的变化不代表模型看到并修改了旧答案。','','| 题号 | 参考 | D0 | P0 | 首答 | A候选 | A求解 | A采用 | A回退 | B候选 | B求解 | B采用 | B回退 |','|---|---|---|---|---|---|---|---|---|---|---|---|---|']
    for r in comparisons:
        v=r['V12']; vals=[r['reference'],r['D0']['answer'],r['V10_P0']['answer'],v['initial']['answer']]
        for g in ('A','B'): vals += [v[g].get('candidate_answer'),v[g].get('solver_answer'),v[g]['answer'],v[g]['fallback_to_initial']]
        lines.append('| ['+r['question_id']+']('+r['original_images_and_V12_traces']+') | '+' | '.join('—' if x is None else str(x) for x in vals)+' |')
    lines += ['','完整原题与所有选项在上表病例链接及 [结构化对照](per_question.json) 中；D0请求和原回复按题号保存在 requests/ 与 responses/。']
    (out/'per_question.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    chosen=[]
    for ids in subsets.values():
        for q in ids[:2]:
            if q not in chosen:chosen.append(q)
    chosen=chosen[:10]
    analysis=['# D0 差异集合与失败定位','',headline,'','以下模型短依据是保存输出，并未被当作已确认患者事实；归因需要核对所列图像与选项，不能只凭回复定论。','', '| 差异集合 | 题数 |','|---|---:|']
    analysis += [f'| {k} | {len(v)} |' for k,v in subsets.items()]
    analysis += ['','缓存阶段的四项转换见 [transitions.json](transitions.json)，包含首答→候选、候选→求解器、候选→采用答案以及求解器→控制器回退。旧 schema 解析损失保持原成绩；V12 3436 的首读缺答及 A/B 输出解析故障详见[已发布失败分析](../v12/error-cases.md)。','']
    for q in chosen:
        r=next(r for r in comparisons if r['question_id']==q)
        raw=next((a.get('raw_content','') for a in reversed(direct[q]['attempts']) if a.get('response_received')), '')
        analysis += ['## '+q,'','[原图、完整选项与V12过程]('+r['original_images_and_V12_traces']+') · [D0请求](requests/'+q+'.json)','',row_by_id(selection,q)['question'],'','D0 保存的原始短答：','```text',str(raw),'```','',f"参考 {labels[q]}；D0 {views['D0'][q]}；首答 {views['V12_initial'][q]}；A采用 {views['V12_A_final'][q]}；B采用 {views['V12_B_final'][q]}。",'']
    analysis += ['## 下一轮','',next_step,'','正确答案并集只可作为依赖标签的候选覆盖潜力，不能报告为已实现的集成准确率。']
    (out/'failure_analysis.md').write_text('\n'.join(analysis)+'\n',encoding='utf-8')
    print(json.dumps({'status':'scored','correct':totals['D0']['correct'],'valid':totals['D0']['valid'],'net_vs_initial':gain,'difference_set_sizes':{k:len(v) for k,v in subsets.items()}}))


def row_by_id(rows, qid): return next(r for r in rows if r['question_id']==qid)


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run',type=Path,required=True);p.add_argument('--v12-public',type=Path,required=True)
    p.add_argument('--p0-public',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args(argv);generate(a.run,a.v12_public,a.p0_public,a.out)


if __name__=='__main__': main()
