"""User-authorized E2/E1-only scoring from completed public artifacts.

No E3/E0 data, provider, ledger, or generation modules are opened.
Run from repository root: python experiments/score_case_information_interim.py
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from score_votes import load_complete_run, read, read_labels, vote, write
from score_case_information import compare_views, accuracy_interval


def score(root):
    root = Path(root)
    report = root / 'reports/case_information_20261103'
    out = report / 'interim_E2_E1'
    if out.exists() and any(out.iterdir()):
        raise ValueError('refusing_to_overwrite_interim_results')
    sources = {
        'E2_Batch': '01_E2/arms/E2_Batch/question_view',
        'E2_Sequential': '01_E2/arms/E2_Sequential',
        'E1_DeepSeek': '02_E1/arms/E1_DeepSeek',
        'E1_QwenFlash': '02_E1/arms/E1_QwenFlash',
    }
    runs = {name: load_complete_run(report / path) for name, path in sources.items()}
    rows = runs['E2_Batch']['rows']
    qids = [str(r['question_id']) for r in rows]
    cases = {str(r['question_id']): str(r['case_id']) for r in rows}
    if len(qids) != 402 or len(set(cases.values())) != 99:
        raise ValueError('requires_completed_402_question_99_case_tuning_set')
    for name, run in runs.items():
        if set(run['qids']) != set(qids) or run['samples'] != 1:
            raise ValueError('incomplete_question_denominator:' + name)
    # Only completed E2/E1 inputs above are opened before frozen public references.
    baseline = root / 'reports/qwen37_token_plan_20261102/phase1/per_question.json'
    labels = read_labels(baseline, qids)
    old = {str(r['question_id']): r['answers']['D'] for r in read(baseline)['records']}
    views = {'D': {q: old[q] for q in qids}}
    views.update({name: {q: run['answers'][q, 1] for q in qids}
                  for name, run in runs.items()})
    views['E1_Ensemble'] = {q: vote([views[n][q] for n in
        ('D', 'E1_DeepSeek', 'E1_QwenFlash')], tie_answer=views['D'][q]) for q in qids}
    result = compare_views(views, labels, rows)
    for name, pred in views.items():
        result['totals'][name].update(accuracy_interval(pred, labels, qids, cases))
    result.update(
        status='completed_interim_E2_E1_only', created_utc=datetime.now(timezone.utc).isoformat(),
        authorization='User explicitly requested completed E2/E1 scoring and GitHub publication before all arms finish.',
        scope=['E2_Batch', 'E2_Sequential', 'E1_DeepSeek', 'E1_QwenFlash', 'E1_Ensemble'],
        all_scored_generation_complete_before_labels=True, E3_E0_results_opened=False,
        new_inference_requests=0, reused_D_new_requests=0, actual_token_plan_credits=None,
        baseline_source='../../qwen37_token_plan_20261102/phase1/per_question.json',
        source_paths={n: '../' + p for n, p in sources.items()},
        ensemble_rule='D + DeepSeek + QwenFlash, equal votes; D breaks tied leaders only; no vote when all missing.',
        multiplicity='Five exploratory comparisons to D, unadjusted intervals and p-values; no independent validation.',
        usage={**read(report/'01_E2/summary.json')['usage'], **read(report/'02_E1/summary.json')['usage']},
        usage_note='Published original request-unit usage, counted once; batch child projections incur no extra cost.')
    write(out/'metrics.json', result)
    records = []
    for q in qids:
        changes = {}
        for name, pred in views.items():
            if name == 'D':
                continue
            a, b, gold = views['D'][q], pred[q], labels[q]
            change = ('missing_to_correct' if a is None and b == gold else
                      'legal_wrong_to_correct' if a != gold and b == gold else
                      'correct_to_missing' if a == gold and b is None else
                      'correct_to_legal_wrong' if a == gold and b != gold else
                      'both_correct' if a == gold else 'both_incorrect')
            changes[name] = change
        records.append({'question_id': q, 'case_id': cases[q], 'reference': labels[q],
                        'predictions': {n: p[q] for n,p in views.items()},
                        'correct': {n: p[q] == labels[q] for n,p in views.items()},
                        'changes_from_D': changes})
    write(out/'per_question.json', {'records': records})
    case_records = []
    for c in sorted(set(cases.values())):
        qs = [q for q in qids if cases[q] == c]
        case_records.append({'case_id': c, 'question_ids': qs, 'planned_n': len(qs),
            'correct': {n: sum(p[q] == labels[q] for q in qs) for n,p in views.items()}})
    write(out/'per_case.json', {'records': case_records})
    lines = ['# E2、E1 阶段评分（用户授权提前分析）', '',
        '仅评分已完成并公开的 E2、E1；复用原 Qwen3.7-Plus D 单答。未读取 E3 或 E0 结果，未新增推理请求，也未改写任何终态。后续实验继续使用冻结方案。', '',
        '全部结果使用同一 402 题、99 病例调参集，缺答计错。E2_Batch 使用 402 个题级投影，而非把 99 次病例请求当成 99 题。', '',
        '|臂|正确/402|准确率|病例 bootstrap 95% CI（准确率）|缺答|',
        '|---|---:|---:|---:|---:|']
    for n,t in result['totals'].items():
        lo,hi=t['accuracy_ci95']
        lines.append(f"|{n}|{t['correct']}/402|{t['accuracy']:.2%}|{lo:.2%}–{hi:.2%}|{t['missing']}|")
    lines += ['', '|相对 D|合法错答→正确|正确→合法错答|缺答→正确|正确→缺答|净增题数|变化（pp）|配对病例 95% CI（pp）|精确 McNemar p|',
              '|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
    for n,p in result['comparisons_to_D'].items():
        lo,hi=p['bootstrap']['delta_ci95_pp']
        lines.append(f"|{n}|{p['legal_wrong_to_correct']}|{p['correct_to_legal_wrong']}|{p['missing_to_correct']}|{p['correct_to_missing']}|{p['net']:+d}|{p['delta_pp']:+.2f}|{lo:+.2f}–{hi:+.2f}|{p['exact_mcnemar_p']:.4g}|")
    lines += ['', '## 结果解读', '',
        'E2_Batch 的观测准确率最高：纠正 69 题，误改合法答案 8 题，另使 2 个原正确答案变成缺答，净增 59 题。E2_Sequential 净增 41 题。两者的配对病例区间均高于零，但尚不能把病例上下文、共享图像和同病例问题提示的贡献分别归因，也未检验 Batch 与 Sequential 的直接差异。', '',
        'Qwen Flash 单模净增 25 题；预定三模型投票净增 22 题，点估计低于 Qwen Flash 单模 3 题，不能据此宣称集成优于最佳单模。DeepSeek 净增 11 题，但配对病例区间跨零。此次结果不用于修改正在执行的 E3/E0 方案。', '',
        '## 统计口径与边界', '',
        '以病例为单位有放回抽样 2,000 次（seed=20261103），每次保留该病例全部问题，计算题数加权准确率与配对差值，报告百分位 95% 区间。表中两种区间分别回答“准确率有多不确定”和“相对 D 的变化有多不确定”。', '',
        'McNemar 为题级双侧精确检验，并不处理同病例题目相关性；主要结合病例级配对区间判断。五项比较均为探索性、未作多重比较调整；这是调参集结果，不能宣称独立泛化效果或确认性显著增益。', '',
        'E1_DeepSeek=deepseek-v4.1-flash-1017；E1_QwenFlash=qwen3.8-flash。E1_Ensemble 按原方案将 D 和两个 Flash 等权投票；D 只在并列领先选项中打破平票，不按本次分数改权重。E2 两臂沿用 qwen3.7-plus，分别为同病例整批作答与逐题保留病例历史。', '',
        f"原 D 错误 {result['complementarity']['D_wrong_n']} 题，其中至少一个 Flash 答对 {result['complementarity']['D_errors_correct_in_at_least_one_new_model']} 题。这只是互补性诊断，不是可直接实现的集成准确率。", '',
        '## 用量与证据', '',
        '|臂|原始请求|输入 tokens|输出 tokens|已保存记账代理（CNY）|首末请求跨度（分钟）|',
        '|---|---:|---:|---:|---:|---:|']
    for n,u in result['usage'].items():
        if isinstance(u,dict) and 'saved_attempts' in u:
            lines.append(f"|{n}|{u['saved_attempts']}|{u['input_tokens']}|{u['output_tokens']}|{u['saved_settlement_cny']}|{u.get('wall_seconds',0)/60:.2f}|")
    lines += ['', '费用和时间复用已发布请求级记录；批量子题不重复计费。CNY 为继承记账代理，非供应商实际费率或 Credits 换算；实际 Token Plan Credits 未知。此次评分新增 API 请求为 0。原始失败与解析缺答不修补，缺答来源可在原终态追溯。', '',
        '[完整统计与纠正/误改题号](metrics.json) · [402 题参考/预测/变化](per_question.json) · [99 病例明细](per_case.json)', '',
        '[E2 完整题干、选项、原图、请求响应](../01_E2/README.md) · [E1 完整证据及首请求图像审阅](../02_E1/README.md) · [原 D 基线](../../qwen37_token_plan_20261102/README.md)', '',
        '复现：在仓库根目录执行 `python experiments/score_case_information_interim.py`（输出目录已存在时拒绝覆盖）；程序只读取上述已公开材料。', '']
    (out/'README.md').write_text('\n'.join(lines),encoding='utf-8')
    return {n: {'correct':t['correct'],'accuracy':t['accuracy'],'missing':t['missing']} for n,t in result['totals'].items()}


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1])
    print(json.dumps(score(parser.parse_args().root),ensure_ascii=False))
