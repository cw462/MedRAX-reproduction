"""Join native task labels to completed K9 outcomes; no inference or rescoring."""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path


CATEGORIES = {
    'detection': '检测', 'classification': '分类', 'localization': '定位',
    'comparison': '比较', 'relationship': '关系判断', 'diagnosis': '诊断',
    'characterization': '特征描述',
}


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def summarize(report):
    labels = read(report / 'official_category_labels.json')
    outcomes = read(report / 'phase2/per_question.json')['records']
    native = {r['question_id']: r for r in labels['rows']}
    assert len(native) == len(labels['rows']) == len(outcomes) == 402
    assert set(native) == {r['question_id'] for r in outcomes}
    records = []
    for row in outcomes:
        source = native[row['question_id']]
        assert str(source['case_id']) == str(row['case_id'])
        tags = [tag.strip().lower() for tag in source['categories'].split(',') if tag.strip()]
        assert len(tags) == len(set(tags)) and set(tags) <= set(CATEGORIES) | {'reasoning'}
        core = [cat for cat in CATEGORIES if cat in tags]
        assert core
        answer = row['answers']['S0/K9']
        assert answer is not None
        records.append({
            'question_id': row['question_id'], 'case_id': row['case_id'],
            'native_categories': source['categories'], 'core_categories': core,
            'reasoning_tag': 'reasoning' in tags, 'reference': row['reference'],
            'K9_answer': answer, 'K9_correct': answer == row['reference'],
            'D_answer': row['answers']['D'], 'D_correct': row['answers']['D'] == row['reference'],
            'K1_answer': row['answers']['S0/K1'],
            'K1_correct': row['answers']['S0/K1'] == row['reference'],
        })
    wrong = [r for r in records if not r['K9_correct']]
    assert len(wrong) == 106
    totals = []
    for cat, name in CATEGORIES.items():
        group = [r for r in records if cat in r['core_categories']]
        errors = [r for r in group if not r['K9_correct']]
        totals.append({
            'category': cat, 'name_zh': name, 'planned_n': len(group),
            'K9_wrong': len(errors), 'K9_correct': len(group) - len(errors),
            'K9_error_rate': len(errors) / len(group) if group else None,
            'K9_accuracy': (len(group) - len(errors)) / len(group) if group else None,
            'share_of_106_errors': len(errors) / len(wrong),
            'share_of_402_questions': len(group) / len(records),
            'D_correct': sum(r['D_correct'] for r in group),
            'K1_correct': sum(r['K1_correct'] for r in group),
            'wrong_question_ids': [r['question_id'] for r in errors],
        })
    totals.sort(key=lambda x: (-x['K9_wrong'], x['category']))
    combos = Counter(tuple(r['core_categories']) for r in records)
    wrong_combos = Counter(tuple(r['core_categories']) for r in wrong)
    combination_stats = [
        {'categories': list(key), 'name_zh': '＋'.join(CATEGORIES[x] for x in key),
         'planned_n': count, 'K9_wrong': wrong_combos[key], 'K9_correct': count - wrong_combos[key],
         'K9_error_rate': wrong_combos[key] / count, 'share_of_106_errors': wrong_combos[key] / 106,
         'wrong_question_ids': [r['question_id'] for r in wrong if tuple(r['core_categories']) == key]}
        for key, count in combos.items()]
    combination_stats.sort(key=lambda x: (-x['K9_wrong'], x['categories']))
    multiplicity = Counter(len(r['core_categories']) for r in wrong)
    reason = [r for r in records if r['reasoning_tag']]
    summary = {
        'scope': 'Completed fixed K9 on the 99-case, 402-question tuning set',
        'planned_n': 402, 'case_n': len({r['case_id'] for r in records}),
        'K9_correct': 296, 'K9_wrong': 106, 'K9_missing': 0,
        'source_provenance': labels['provenance'],
        'official_core_categories': list(CATEGORIES),
        'category_membership_is_overlapping': True,
        'error_category_memberships': sum(r['K9_wrong'] for r in totals),
        'question_category_memberships': sum(r['planned_n'] for r in totals),
        'wrong_questions_by_core_tag_count': dict(sorted(multiplicity.items())),
        'reasoning_tag': {'planned_n': len(reason), 'wrong': sum(not r['K9_correct'] for r in reason)},
        'by_category': totals, 'by_exact_core_category_combination': combination_stats,
        'all_402_outcomes_with_categories': records,
        'notes': ['Each question counts once in every native core category it carries.',
                  'Error share uses 106 as denominator; within-category error rate uses category planned_n.',
                  'Exact combinations are mutually exclusive and sum to 106 wrong / 402 total.',
                  'Native reasoning tag is retained and reported separately from the seven core categories.',
                  'These are question task labels, not adjudicated causes of model error.',
                  'No model request, prediction modification, parser change, or scorer rerun.'],
    }
    (report / 'official_category_errors.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    table = '\n'.join(
        f"|{r['name_zh']}（{r['category']}）|{r['planned_n']}|{r['K9_wrong']}|{r['share_of_106_errors']:.2%}|{r['K9_error_rate']:.2%}|{r['K9_accuracy']:.2%}|"
        for r in totals)
    combination_table = '\n'.join(
        f"|{r['name_zh']}|{r['planned_n']}|{r['K9_wrong']}|{r['share_of_106_errors']:.2%}|{r['K9_error_rate']:.2%}|"
        for r in combination_stats)
    wrong_table = '\n'.join(
        f"|`{r['question_id']}`|{'＋'.join(CATEGORIES[x] for x in r['core_categories'])}|{r['reference']}|{r['K9_answer']}|{r['D_answer']}|{r['K1_answer']}|"
        for r in wrong)
    most = totals[0]
    hardest = max(totals, key=lambda r: r['K9_error_rate'])
    md = f'''# 106道K9错题的官方任务标签分布

**按错题数量，{most['name_zh']}标签最多：{most['K9_wrong']}题；按类别内错误率，{hardest['name_zh']}最高：{hardest['K9_wrong']}/{hardest['planned_n']}（{hardest['K9_error_rate']:.2%}）。** 全部402题中296题正确、106题错误、题级缺答0。这是同一轮K9最终结果的标签分层，没有新增推理或重新评分。

## 单个标签统计：类别可以重叠

官方源metadata的`categories`为逗号分隔多标签。一道题可以同时涉及检测、定位、特征描述等。本文逐字保留402题的原字段，并以question_id、case_id和原题文本对应本轮输入；没有用关键词猜类别。本轮402题每题恰好带三个核心任务标签及reasoning；106道错题因此对应318次核心标签归属。

|官方任务类别|该类总题数|K9错题数|占全部106错题|该类错误率|该类准确率|
|---|---:|---:|---:|---:|---:|
{table}

“占全部106错题”回答错误出现在哪些标签；“该类错误率”回答带该标签的题有多容易答错。两列分母不同。七类错题数合计 **{summary['error_category_memberships']}次标签归属**，不是{summary['error_category_memberships']}道不同错题；实际仍是106题，因此各类错误占比不能相加为100%。七类总题数也存在重叠。

源metadata还包含`reasoning`标签：本402题中{len(reason)}题带该标签，其中{sum(not r['K9_correct'] for r in reason)}题错误。官方将推理与七项核心能力并列描述；这里单独保留，不将其混成第八项互斥任务类别。

## 精确标签组合：互斥分组

官方[基准生成代码](https://github.com/bowang-lab/MedRAX/blob/main/benchmark/create_benchmark.py#L46-L52)使用这五种组合，每组含三个核心能力及reasoning。本轮标签也恰好落在这五组。以下按每题七项核心标签的完整组合分组；每题仅出现一次，所以总题数恰为402，错题数恰为106，错题占比合计100%。`reasoning`作为上面的附加标签单列。

|原生核心标签组合|总题数|错题数|占106错题|组内错误率|
|---|---:|---:|---:|---:|
{combination_table}

## 106道错题逐题清单

保留原参考答案与已保存D、K1和K9选项。完整题干、选项、原图和每次响应见[阶段2证据索引](phase2/evidence/cases.json)；每类题号列表及402题全量标签对应见[机器可读结果](official_category_errors.json)。

|题号|官方核心任务标签|参考|K9|原D|同温度K1|
|---|---|---|---|---|---|
{wrong_table}

## 来源、边界与复现

- [原生402题标签](official_category_labels.json)直接摘录本轮源metadata的categories字段；已对应全部402题，无缺失/重复/未知标签。参考答案使用已完成评分的[per_question.json](phase2/per_question.json)，不重新读取源metadata的答案字段。
- 官方[ChestAgentBench数据卡](https://huggingface.co/datasets/wanglab/chest-agent-bench/blob/921e60440927f9893228d843c0206b755744252a/README.md)及[MedRAX仓库](https://github.com/bowang-lab/MedRAX)列出七类：Detection、Classification、Localization、Comparison、Relationship、Diagnosis、Characterization，并描述推理要求。
- 统计的是错题所带的任务标签。多标签题答错时，单凭这些标签不能确定具体是检测、定位还是推理环节出错。类别样本数也不同；此表为描述性分布，不构成类别间能力差异的显著性结论。
- 402题为99病例调参集；1002题留出集未用于本分析。原3个请求失败、5个unparsed样本及所有终态不变，最终题级缺答仍为0。

在仓库根目录仅用公开文件复现：

```powershell
python -X utf8 experiments/summarize_qwen37_categories.py --report-root reports/qwen37_token_plan_20261102
```

[全轮结果](README.md) · [统计与投票分析](results_analysis.md) · [执行与成本](execution_summary.md)
'''
    (report / 'official_category_errors.md').write_text(md, encoding='utf-8')
    print(json.dumps({key: summary[key] for key in ['K9_wrong', 'error_category_memberships', 'wrong_questions_by_core_tag_count', 'reasoning_tag']}, ensure_ascii=False))
    print(json.dumps([{k: v for k, v in r.items() if k != 'wrong_question_ids'} for r in totals], ensure_ascii=False, indent=2))
    print(json.dumps([{k: v for k, v in r.items() if k != 'wrong_question_ids'} for r in combination_stats], ensure_ascii=False, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report-root', type=Path, default=Path(__file__).resolve().parents[1] / 'reports/qwen37_token_plan_20261102')
    summarize(parser.parse_args().report_root.resolve())
