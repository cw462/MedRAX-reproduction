"""Make readable tables from the completed zero-paid comparison, no inference."""
from pathlib import Path
import json

import numpy as np

from analyze_cxr_author_alignment import EXPECTED, REPORT, ROOT, registry, read
from score_cxr_vqa_extension import bootstrap, cluster_keys, rows

LABELS = [
    ('original_D','D：模型直接回答'),('original_M','M：工具循环Agent'),
    ('M-R','M−R：移除部分工具可靠性提醒'),('original_C','C：CXRAgent流程迁移'),
    ('original_X','X：X-Ragent机制迁移'),('O','O：原生MedRAX流程适配'),
    ('M-S','M-S：源Skill'),('M-E','M-E：源病例经验'),
    ('v32_M-A','v3.2 M-A：行动Agent无Skill'),('v32_M-AS','v3.2 M-AS：行动Agent＋Skill'),
    ('M-C41','R4.1 M-C41：无卡对照'),('M-S41','R4.1 M-S41：任务Skill卡'),
    ('M42','R4.2 M42：M二元答案续答'),('M43','R4.3 M43：最好整臂任务完成'),
    ('D-Q','D-Q：同图联合直接答'),('M-Q','M-Q：同图联合Agent')]


def cell(correct, n):
    return f'{100*correct/n:.2f}%（{correct}）'


def direct_comparison():
    path=REPORT/'results/direct_comparison.json'
    if path.exists():
        return read(path)
    details=rows(REPORT/'results/per_question.jsonl')
    results=[]
    for ds,method in [('chexbench','M43'),('slake','M43'),('vqarad','M42')]:
        left={x['question_id']:x for x in details if x['dataset']==ds and x['method']==method}
        right={x['question_id']:x for x in details if x['dataset']==ds and x['method']=='original_D'}
        inputs=rows(ROOT/'reports/cxr_action_r41_20261108/results'/ds/'inputs.jsonl')
        assert set(left)==set(right)=={x['question_id'] for x in inputs}
        delta=np.array([int(left[x['question_id']]['aligned_correct'])-int(right[x['question_id']]['aligned_correct']) for x in inputs])
        results.append({'dataset':ds,'method':method,'baseline':'original_D','questions':len(inputs),
                        'direct_correct':sum(x['aligned_correct'] for x in right.values()),
                        'agent_correct':sum(x['aligned_correct'] for x in left.values()),
                        'corrections':int(sum(delta>0)),'harms':int(sum(delta<0)),'net':int(delta.sum()),
                        'micro_delta_pp':100*float(delta.mean()),
                        'confidence':bootstrap(delta,cluster_keys(inputs),np.array([x.get('source',{}).get('subset','all') for x in inputs])),
                        'comparison_scope':'User-requested descriptive fixed-whole-arm comparison, unequal workflow budgets/information/epochs; not isolated causal agent effect.'})
    path.write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return results


def matrix(summary, strict=False):
    index={(x['dataset'],x['key']):x for x in summary['arms']}
    lines=['| 方法 | Rad-Restruct /115 | CheX-SLAKE /123 | OpenI /380 | CheX宏平均：主指标 | CheX总准确率 /618 | 独立SLAKE /114 | VQA-RAD /116 |',
           '|---|---:|---:|---:|---:|---:|---:|---:|']
    for key,label in LABELS:
        row=[]
        c=index.get(('chexbench',key))
        if c and c['full_comparison']:
            field='strict_correct' if strict else 'aligned_correct'
            row.extend(cell(c['subsets'][name][field],c['subsets'][name]['n']) for name in ['Rad-Restruct','SLAKE','OpenI'])
            macro=sum(100*x[field]/x['n'] for x in c['subsets'].values())/len(c['subsets'])
            row += [f'{macro:.2f}%',cell(c[field],618)]
        else:
            row += ['—']*5
        for ds in ['slake','vqarad']:
            x=index.get((ds,key))
            row.append(cell(x['strict_correct' if strict else 'aligned_correct'],x['questions'])
                       if x and x['full_comparison'] else '—')
        lines.append('| '+label+' | '+' | '.join(row)+' |')
    return '\n'.join(lines)


def write_tables(summary):
    main='''# 当前胸片主线：全部数据集与方法总表

以下是已完成预测的统一离线比较，**不是新跑模型**。全部45组主模型协议绑定qwen3.7-plus，包含41个完整队列方法及4个部分联合队列。这里将显式答案与reason/JSON工程合规分开，所有方法使用同一适配器；指标为“作者指标＋共同显式答案适配”，不冒称所有作者未经修改的官方解析器。空白表示该完整队列未运行，不是0分。

百分比后括号为正确题数。CheXbench主指标为三个子集等权宏平均，总准确率为618题微平均。独立SLAKE和VQA分别以114/116为完整分母；未作答、非终态、冲突和技术失败仍计入分母，不猜答案。

'''+matrix(summary)+'''

D是单题直接模型；D-Q为同图多题一起直接回答，输入信息不同。M−R不是RAG或记忆检索。C/X为本项目的流程/机制迁移，不是原论文全部训练、模型和数据的精确复现。R42只跑VQA；R43只干预CheX与独立SLAKE，不能把VQA100写作R43新结果。

## 部分联合队列，单列分母

| 数据集 | 方法 | 已运行题数 | 统一准确率 | 原旧协议正确数 |
|---|---|---:|---:|---:|
'''
    for x in summary['arms']:
        if not x['full_comparison']:
            main += f"| {x['dataset']} | {x['key']} | {x['questions']} | {cell(x['aligned_correct'],x['questions'])} | {x['strict_correct']} |\n"
    main+='''
CheX联合队列仅204题，VQA仅94题；不能拿其百分比与618/116完整结果排名。独立SLAKE的D-Q/M-Q已覆盖全114题，因此主表列出。旧D-Q的0分主要是原输出字典接口不符合旧解析要求，不能解释成模型一题都不会。现在统一按当前题号提取显式answer，并保留矛盾/未完成状态。

## 直接回答与当前最好完整整臂

| 数据集 | 直接D | 当前最好观测 | 净多正确题 | 准确率差 | 纠正/误改 |
|---|---:|---:|---:|---:|---:|
'''
    for x in read(REPORT/'results/direct_comparison.json'):
        main+=f"| {x['dataset']} | {x['direct_correct']}/{x['questions']} | {x['method']}：{x['agent_correct']}/{x['questions']} | +{x['net']} | +{x['micro_delta_pp']:.2f}pp | {x['corrections']}/{x['harms']} |\n"
    main+='''
SLAKE的M−R、M-S41、M43并列108。CheX的X在Rad-Restruct为82/115，超过整体最好M43的73/115，也高于D77/115；总体最好不等于每个子集最好。本表按整臂列结果，不逐题oracle拼接。各方案工具预算、可见上下文、运行时段不同，这些是描述性成绩差，不能把差值直接当作同预算Agent或Skill的因果收益。

## 与截图旧数字的关系

[完整旧协议总表](LEGACY_STRICT_TABLE.md)保留截图所属旧记录：CheX D410、M452、M-C41458、M43466；统一后分别411、455、461、466。全部旧预测/旧成绩不动。R43相对其固定前驱现在是CheX+5、SLAKE0；VQA M42仍比原M多1。这一轮没有新模型调用，口径差异不是新能力进步。

旧的402题/1002题病例问答主线和60题开发试跑见[其他已完成队列](OTHER_COHORTS.md)，按各自分母/原协议单列，没有冒充本次CXR统一重算。

[总报告](README.md) · [逐题完整结果](results/per_question.jsonl) · [机器可读全表/区间](results/summary.json) · [来源、题干、原图和工具证据](SOURCE_EVIDENCE.md)。
'''
    (REPORT/'TABLES.md').write_text(main,encoding='utf-8')
    (REPORT/'LEGACY_STRICT_TABLE.md').write_text('# 各方法原冻结协议成绩：保留历史口径\n\n本表读取各方法已发布预测状态与答案，原正确数逐臂与其缓存摘要完全相同。不同方法的旧输出接口并非一律同一两键JSON；不把格式失败当临床能力失败。新统一表另列，不覆盖旧记录。\n\n'+matrix(summary,strict=True)+'\n\n—表示未运行该完整分母；部分Q另列。\n',encoding='utf-8')


def write_diagnostics(summary):
    lines=['# 同一旧档的适配与指标差异：不是新增模型能力\n',
           '| 数据集 | 方法 | 分母 | 原协议正确 | 统一正确 | 适配/指标净变化 | 无可提取答案 | 选项域无效 | 技术/图停止 | 可计入终态文本的整条JSON有效数 | 原M契约合规数 |',
           '|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
    for x in summary['arms']:
        lines.append(f"| {x['dataset']} | {x['key']} | {x['questions']} | {x['strict_correct']} | {x['aligned_correct']} | {x['adapter_metric_only_net']:+d} | {x['answer_absent']} | {x['domain_invalid']} | {x['technical_stops']} | {x['raw_whole_json_valid']} | {x['legacy_M_contract_compliant']} |")
    lines += ['\nJSON有效数只针对终态筛选后仍可用的文本，技术失败、原生工具计划或图停止先被屏蔽，因此不是所有原始末条消息的JSON语法统计。原M契约合规是“原M的两键/300字符工程规则”诊断，不是其他方法自有schema合规。两项都不作统一正确性的门槛。\n',
              'O由47/21/7恢复到448/103/89，主要揭示旧协议的格式/接口损失，不能说这次训练或推理进步。同一预测上指标变动与额外模型调用的作用必须分开。\n',
              '[字段定义](METRIC_NOTES.json) · [逐题原始来源和分类](results/per_question.jsonl) · [总表](TABLES.md)。']
    (REPORT/'ADAPTER_EFFECTS.md').write_text('\n'.join(lines),encoding='utf-8')
    lines=['# 作者旧解析器敏感性：随机信用不进入主表\n',
           'CheXagent旧通用解析器对“已提取的显式answer文本”抽首个括号大写字母；找不到时使用固定seed0回退。缺少实际显式答案者不随机补答。本列不是作者原提示/原输出的精确复现；同一个有效字母A与(A)在此旧接口可能表现不同，故仅作为接口敏感性诊断。\n',
           '| 方法 | 分母 | 主统一正确 | 旧括号解析不猜答正确 | seed0敏感性正确 | 随机回退次数 | 随机猜中贡献 |',
           '|---|---:|---:|---:|---:|---:|---:|']
    for x in summary['arms']:
        if x['dataset']=='chexbench':
            lines.append(f"| {x['key']} | {x['questions']} | {x['aligned_correct']} | {x['legacy_no_guess_correct']} | {x['legacy_seed0_correct']} | {x['legacy_random_draws']} | {x['legacy_random_correct']} |")
    lines+=['\n随机回退列不能作为医学能力或主要排名，也没有选择种子追高分。源码版本与顺序见[协议](PROTOCOL.json)。']
    (REPORT/'LEGACY_PARSER_SENSITIVITY.md').write_text('\n'.join(lines),encoding='utf-8')


def write_sources():
    def link(path):
        return Path(__import__('os').path.relpath(ROOT/path,REPORT)).as_posix()
    lines=['# 完整旧档、问题/选项/原图/工具证据\n',
           '本次所有数据来自既有公开档，不复制模型权重、不重新生成图像或工具。逐题结果的archive_call是仓库根目录相对路径，配合ordinal定位实际最后请求/回复；reuse_chain说明固定整臂继承，绝不指向变化后的私有SLAKE档。\n',
           '| 数据集 | 方法 | 预测 | 请求/回复 | 数据/原图与既有报告 |',
           '|---|---|---|---|---|']
    for spec in registry():
        folder=Path(spec['folder']);arm=spec['arm']
        report=next(parent/'README.md' for parent in [folder,folder.parent,folder.parent.parent]
                    if (ROOT/parent/'README.md').is_file())
        lines.append(f"| {spec['dataset']} | {spec['key']} | [完整预测]({link(folder/('predictions_'+arm+'.jsonl'))}) | [全部档案]({link(folder/'calls'/arm)}) | [问题与原图]({link(folder/'inputs.jsonl')}) · [既有报告]({link(report)}) |")
    lines += ['\n每数据集统一题面与参考使用R4.1冻结文件；旧R43/M42输出仍来自各自原始已发布回复。所有来源图像/派生图/工具返回继续保持原公共链接，不重复执行。\n']
    (REPORT/'SOURCE_EVIDENCE.md').write_text('\n'.join(lines),encoding='utf-8')


def main():
    summary=read(REPORT/'results/summary.json')
    direct_comparison()
    write_tables(summary)
    write_diagnostics(summary)
    write_sources()
    print('COMPLETE_CXR_METHOD_TABLES_WRITTEN')


if __name__=='__main__':
    main()
