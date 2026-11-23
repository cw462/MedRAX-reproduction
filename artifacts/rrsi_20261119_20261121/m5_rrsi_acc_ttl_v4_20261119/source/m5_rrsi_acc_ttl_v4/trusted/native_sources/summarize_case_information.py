"""Add publication interpretation to completed offline case-information scores.

Reads public final scores only; preserves scorer metrics and all predictions.
"""
from collections import Counter
from datetime import datetime
from decimal import Decimal
from pathlib import Path
import argparse

from score_votes import read, write, paired, totals
from score_case_information import accuracy_interval


def summarize(root):
    root = Path(root)
    base = root/'reports/case_information_20261103'
    out = base/'final_analysis'
    metrics = read(out/'metrics.json')
    if metrics['status'] != 'completed':
        raise ValueError('requires_completed_final_scoring')
    records = read(out/'per_question.json')['records']
    qids = [r['question_id'] for r in records]
    cases = {r['question_id']: r['case_id'] for r in records}
    labels = {r['question_id']: r['reference'] for r in records}
    names = list(metrics['totals'])
    views = {n: {r['question_id']: r['predictions'][n] for r in records} for n in names}
    # Reuse published intervals for previously analyzed arms; only E3 is new here.
    interim = read(base/'interim_E2_E1/metrics.json')
    intervals = {}
    for n in names:
        if n in interim['totals']:
            old = interim['totals'][n]
            intervals[n] = {k: old[k] for k in ('method','case_n','repeats','seed','accuracy_ci95')}
        else:
            intervals[n] = accuracy_interval(views[n], labels, qids, cases)
    subsets = {}
    for arm, cov in metrics['E3_evidence_coverage'].items():
        evidence = set(cov['evidence_question_ids'])
        groups = {'actual_evidence': [q for q in qids if q in evidence],
                  'no_evidence': [q for q in qids if q not in evidence]}
        if arm == 'E3_Evidence':
            groups['positive_tool_agreement'] = cov['agreement_question_ids']
        subsets[arm] = {}
        for group, qs in groups.items():
            p = (cov['paired_on_evidence_subset'] if group == 'actual_evidence' else
                 paired(views['D'], views[arm], labels, qs, cases, 2000, 20261103)) if qs else None
            subsets[arm][group] = {'planned_n': len(qs), 'case_n': len({cases[q] for q in qs}),
                'D': totals(views['D'], labels, qs) if qs else None,
                'arm': totals(views[arm], labels, qs) if qs else None, 'paired': p,
                'role': 'descriptive_posthoc_subset_not_a_selection_rule'}
    usage = {k:v for k,v in metrics['usage'].items() if isinstance(v,dict)}
    starts = [datetime.fromisoformat(u['first_started_utc']) for u in usage.values()]
    ends = [datetime.fromisoformat(u['last_ended_utc']) for u in usage.values()]
    elapsed = (max(ends)-min(starts)).total_seconds()
    spans = sum(u['wall_seconds'] for u in usage.values())
    resources = {
        'model_requests': sum(u['saved_attempts'] for u in usage.values()),
        'technical_extra_model_requests': sum(u['technical_extra_requests'] for u in usage.values()),
        'input_tokens': sum(u['input_tokens'] for u in usage.values()),
        'output_tokens': sum(u['output_tokens'] for u in usage.values()),
        'saved_settlement_proxy_cny': str(sum((Decimal(u['saved_settlement_cny']) for u in usage.values()),Decimal(0))),
        'actual_token_plan_credits': None,
        'generation_first_start_utc': min(starts).isoformat(),
        'generation_last_end_utc': max(ends).isoformat(),
        'generation_elapsed_seconds': elapsed,
        'sum_arm_wall_seconds': spans,
        'inter_arm_gap_seconds': elapsed-spans,
        'timing_note': 'Arm spans include any within-arm image review/resume pause. Gaps include publication and transitions; not pure API latency. Tool cache preparation and final publication time excluded.',
        'tool_invocations_including_failed_persistence': 348,
        'classifier_invocations': 232, 'report_invocations': 116,
        'tool_cost_cny': None,
        'raw_terminal_status_counts': dict(sum((Counter(u['sample_status_counts']) for u in usage.values()), Counter())),
        'budget_cap_changed': False, 'ledger_integrity_validation_reintroduced': False,
    }
    case_rows=[]
    for c in sorted(set(cases.values())):
        qs=[q for q in qids if cases[q]==c]
        correct={n:sum(views[n][q]==labels[q] for q in qs) for n in names}
        case_rows.append({'case_id':c,'question_ids':qs,'planned_n':len(qs),
                          'correct':correct,'net_vs_D':{n:v-correct['D'] for n,v in correct.items() if n!='D'}})
    supplement={'status':'completed_publication_supplement','accuracy_intervals':intervals,
        'E3_subset_descriptions':subsets,'resources':resources,
        'interim_disclosure':'E2/E1 were scored at user request before E3/E0 finished. Final all-arm scorer ran after all generation; no subsequent prompts, model choices or rules were changed.',
        'multiplicity':'Eight exploratory comparisons to D; intervals and p-values unadjusted. Posthoc evidence/agreement subsets are descriptive only.'}
    write(out/'publication_summary.json',supplement)
    write(out/'per_case.json',{'records':case_rows})
    lines=['# E0–E3 完整实验结果与解释','',
        '**本轮已完成全部 3,513 次模型请求与离线评分。最强观测结果是 E2 同病例批量作答：354/402（88.06%），相对原 D 净增 59 题。E3 三个工具分支均未显示正向净增；E0 仅评估固定 D，得到 793/1002（79.14%）。**','',
        '## 完整分母与主要比较','',
        'E1–E3 共用 402 题、99 个调参病例。D 是上一轮 qwen3.7-plus 单答 295/402，直接复用，不是 K9 的 296/402。缺答计错，不删除困难题。E2_Batch 的 99 次病例请求投影成 402 个题级答案；费用只计原始 99 次。','',
        '|配置|正确/402|准确率|准确率病例 95% CI|缺答|','|---|---:|---:|---:|---:|']
    for n,t in metrics['totals'].items():
        lo,hi=intervals[n]['accuracy_ci95']
        lines.append(f"|{n}|{t['correct']}/402|{t['accuracy']:.2%}|{lo:.2%}–{hi:.2%}|{t['missing']}|")
    lines+=['','|相对原 D|合法错答→正确|正确→合法错答|缺答→正确|正确→缺答|净增题|变化 pp|配对病例 95% CI（pp）|McNemar p|',
            '|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
    for n,p in metrics['comparisons_to_D'].items():
        lo,hi=p['bootstrap']['delta_ci95_pp']
        lines.append(f"|{n}|{p['legal_wrong_to_correct']}|{p['correct_to_legal_wrong']}|{p['missing_to_correct']}|{p['correct_to_missing']}|{p['net']:+d}|{p['delta_pp']:+.2f}|{lo:+.2f}–{hi:+.2f}|{p['exact_mcnemar_p']:.4g}|")
    lines+=['','病例 bootstrap 按病例有放回抽样 2,000 次，保留每个病例全部问题，计算题数加权准确率及配对差值；seed=20261103，百分位 95% CI。McNemar 是题级双侧精确检验，不能代替病例相关性处理。八项相对 D 比较未作多重比较调整，属于探索性调参结果。','',
        '## 可以得出的结论','',
        '- **E2 的病例信息方案最有希望。** Batch 纠正 69 题，产生 8 个合法误改和 2 个原正确→缺答，净增 59；Sequential 纠正 51、误改 10，净增 41。两者相对 D 的病例区间均高于零。Batch 点估计高于 Sequential，但本次主要比较不是两者直接对照，不能仅凭各自对 D 的区间宣布两者差异显著。','',
        '- E2 同时改变病例内信息共享、可见同病例题干与图像上下文；这支持“病例信息可帮助答题”，不等于证明图像感知能力改善，也不能分别归因于共享图像、兄弟问题线索或历史回答。Sequential 还可能传播此前模型错误。没有参考答案被送给生成 worker。','',
        '- **E1 Qwen Flash 单模 320/402，预定等权集成 317/402。** 集成高于原 D，但比 Qwen Flash 单模少 3 题，不能声称超过最强单模。DeepSeek-1017 为 306/402，相对 D 区间跨零。D 的 107 道错题中，两个 Flash 至少一个答对 54 题只是 oracle 互补性上限诊断，不是实际投票收益。','',
        '- 两个 Flash 首次真实请求均保存图像审阅回执及实际图像 token usage，无额外付费探测。它证明接口接受并处理图像；不是图像消融，也不证明每道答案都由图像决定。','',
        '- **E3 当前没有支持继续扩大工具调用的正向结果。** 三臂净增为 −2、−2、−6，区间均跨零；不能把负点估计说成确定伤害，也不能把工具缓存修复说成方法收益。按用户预定开发顺序，目前没有满足正向病例区间条件的工具，暂不据此开发多轮接地、分割、学习规则或记忆。','',
        '## E3 实际证据覆盖与工具贡献','',
        '图注模态清单只让确认为胸片的图像触发工具；未知、CT、US 不作为胸片调用。最终缓存保留 116 张胸片的分类器和报告返回。分类器仅向主模型展示 ≥0.8 的强结果，该值是 XRV operating-point 归一化分数，**不是校准概率**。组合臂的“一致”是保守词面肯定陈述匹配，不是真值，未匹配也不等于矛盾。','',
        '|臂|实际获证据题数/402|有证据病例/99|无证据题数|有证据子集：纠正/误改/净增|子集变化 95% CI（pp）|',
        '|---|---:|---:|---:|---:|---:|']
    for n,cov in metrics['E3_evidence_coverage'].items():
        p=cov['paired_on_evidence_subset'];lo,hi=p['bootstrap']['delta_ci95_pp']
        lines.append(f"|{n}|{cov['questions_with_actual_evidence']}/402|{cov['evidence_case_count']}/99|{cov['no_evidence_questions']}|{p['legal_wrong_to_correct']}/{p['correct_to_legal_wrong']}/{p['net']:+d}|{lo:+.2f}–{hi:+.2f}|")
    lines+=['','同病例证据可以被兄弟问题使用；覆盖数表示请求实际获得工具证据，不表示每道题自己都含胸片，也不表示证据有效。无证据题仍进行独立模型调用；其与原 D 的答案变化不能归因于工具。以下均为描述性子集，未用于重选阈值或修改方案。','',
        '|臂/子集|题数|D 正确|该臂正确|纠正|误改|净增|','|---|---:|---:|---:|---:|---:|---:|']
    for n,groups in subsets.items():
        for group,x in groups.items():
            if group=='actual_evidence' or not x['planned_n']:continue
            p=x['paired']
            lines.append(f"|{n}/{group}|{x['planned_n']}|{x['D']['correct']}|{x['arm']['correct']}|{p['legal_wrong_to_correct']}|{p['correct_to_legal_wrong']}|{p['net']:+d}|")
    lines+=['','|工具臂直接比较|纠正|误改|净增|配对病例 95% CI（pp）|','|---|---:|---:|---:|---:|']
    for n,p in metrics['E3_tool_contrasts'].items():
        lo,hi=p['bootstrap']['delta_ci95_pp']
        lines.append(f"|{n}|{p['legal_wrong_to_correct']}|{p['correct_to_legal_wrong']}|{p['net']:+d}|{lo:+.2f}–{hi:+.2f}|")
    h=metrics['E0_Heldout'];lo,hi=h['accuracy_ci95']
    lines+=['','每题的分类器/报告/组合答案、纠正/误改、实际获证据与正向一致标记均在 [tool_credit_table.json](tool_credit_table.json)。这些是观测关联，不能当作因果工具信用或直接训练筛选规则。','',
        '## E0：固定直接回答的保留集结果','',
        f"**{h['correct']}/{h['planned_n']}（{h['accuracy']:.2%}），241 病例，病例 bootstrap 95% CI {lo:.2%}–{hi:.2%}，缺答 {h['missing']}。**",'',
        'E0 只运行冻结的 qwen3.7-plus D 单答，不运行 E2、Flash 集成或 E3。因此它支持固定 D 在保留集的表现估计，不能验证 E2 的调参集增益或为任何工具收益背书。保留集与 402 题调参集难度/病例构成不同，79.14% 与 73.38% 不是方法间配对提升。','',
        '## 用量、时间与执行修订','',
        '|臂|模型请求|输入 tokens|输出 tokens|保存的记账代理 CNY|首末请求跨度 min|','|---|---:|---:|---:|---:|---:|']
    for n,u in usage.items():
        lines.append(f"|{n}|{u['saved_attempts']}|{u['input_tokens']}|{u['output_tokens']}|{u['saved_settlement_cny']}|{u['wall_seconds']/60:.2f}|")
    lines += ['',f"合计 **{resources['model_requests']} 次模型请求，额外技术重试 {resources['technical_extra_model_requests']} 次；输入 {resources['input_tokens']:,}、输出 {resources['output_tokens']:,} tokens；保存的本轮结算记账代理 {resources['saved_settlement_proxy_cny']} CNY**。复用 D 和离线投票/评分没有新增请求。原累计预算未增加，未恢复已取消的 V12 完整性检验。",'',
        f"首条模型请求到最后模型响应共 {elapsed/60:.2f} 分钟（北京时间 11:33:20–14:25:37）；各臂首末请求跨度合计 {spans/60:.2f} 分钟，臂间间隔 {resources['inter_arm_gap_seconds']/60:.2f} 分钟，包含阶段发布与衔接。臂内跨度也包含图像审阅暂停，不是纯 API 时间。工具预处理及最终评分/发布不在这个时间窗统计内。",'',
        '模型请求原始终态为 3,512 completed + 1 unparsed，没有 request_failed；另外，已成功保存的 Batch 请求中有 4 个题级答案无法解析，仍计缺答。没有重发补票、重解析覆盖终态或中途按分数改提示。','',
        '工具端共 348 次实际调用：232 次分类器（含最初 116 次 NumPy 标量结果保存失败）+116 次报告。只修复传输序列化、补取分类器；原报告返回复用，原失败保留。缓存恢复不是额外模型 API 请求，也不是工具方法增益。GPU 成本未据实计价，不能把模型代理金额称为实验实际总成本。','',
        '所有 CNY 数值是继承 4/12 每百万输入/输出 token 的记账代理，不是实际供应商费率、收费上界或 Credits 换算。真实 Token Plan Credits 未知；没有为本报告重复读取或扫描账户账本。','',
        '最初计划全部生成后统一评分；用户随后明确授权 E2/E1 完成后提前评分并发布。该阶段分析已经公开，E3/E0 保持原冻结配置；最终全臂评分是在所有生成完成后执行。不能把整个研究过程描述成“所有结果始终未被查看”。','',
        '## 完整公开材料与复现','',
        '- [E2 全题干、选项、原图及请求响应](../01_E2/README.md)；[E1 及首次真实图像审阅](../02_E1/README.md)。',
        '- [E3 全部工具返回、证据投影与故障记录](../03_E3/README.md)；[E0 全部 1,002 题及实际请求响应](../04_E0/README.md)。',
        '- [原始最终评分指标](metrics.json)；[402 题预测与参考](per_question.json)；[1,002 题结果](heldout_per_question.json)；[99 病例汇总](per_case.json)。',
        '- [区间、子集及资源汇总](publication_summary.json)；[逐题工具信用表](tool_credit_table.json)；[此前 E2/E1 阶段评分](../interim_E2_E1/README.md)。','',
        '生成配置保存在各节点 configuration/protocol 文件。原始评分程序为 `experiments/score_case_information.py`；本解释与补充表由 `python experiments/summarize_case_information.py` 仅从已公开最终评分与阶段结果生成，不调用模型或工具，不覆盖原始 metrics/终态。','']
    (out/'interpretation.md').write_text('\n'.join(lines),encoding='utf-8')
    return resources


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1])
    print(summarize(p.parse_args().root))
