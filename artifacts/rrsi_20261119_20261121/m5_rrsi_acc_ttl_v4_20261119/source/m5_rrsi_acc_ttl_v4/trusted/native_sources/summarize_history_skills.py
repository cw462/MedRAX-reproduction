"""Publication-only interpretation from saved completed Plus scores; no API."""
import argparse
from collections import Counter
from datetime import datetime
from decimal import Decimal
import json
from pathlib import Path
from score_votes import read,write,paired,totals


def summarize(root):
    base=Path(root)/'reports/history_skills_plus_20261103/results';out=base/'analysis'
    m=read(out/'metrics.json')
    if m['status']!='completed':raise ValueError('complete_scoring_required')
    records=read(out/'per_question.json')['records'];qids=[r['question_id'] for r in records]
    cases={r['question_id']:r['case_id'] for r in records};gold={r['question_id']:r['reference'] for r in records}
    views={n:{r['question_id']:r['predictions'][n] for r in records} for n in ('D','H1','S1','HS')}
    flagged=[r['question_id'] for r in records if r['history_flagged']]
    flagged_results={n:{'totals':totals(views[n],gold,flagged),'vs_D':paired(views['D'],views[n],gold,flagged,cases,2000,20261103)} for n in ('H1','S1','HS')}
    hs_h1=paired(views['H1'],views['HS'],gold,qids,cases,2000,20261103)
    stores=read(base/'skills/crossfit_stores.json')['stores'];audit=read(base/'skills/filter_audit.json')['records'];credits=read(out/'skill_utility.json')['records']
    reflection=[json.loads(line) for line in (base/'arms/Reflection/predictions.jsonl').read_text(encoding='utf-8').splitlines()]
    coverage={}
    for arm in ('S1','HS'):
        retrievals=[read(base/'arms'/arm/'retrieval'/(q+'.json')) for q in qids]
        coverage[arm]={'questions_with_skills':sum(bool(r['skill_ids']) for r in retrievals),'total_skill_retrievals':sum(len(r['skill_ids']) for r in retrievals),'unique_retrieved_skills':len({s for r in retrievals for s in r['skill_ids']}),'skill_count_per_question':dict(Counter(len(r['skill_ids']) for r in retrievals))}
    usage=m['usage'];starts=[datetime.fromisoformat(u['first_started_utc']) for u in usage.values()];ends=[datetime.fromisoformat(u['last_ended_utc']) for u in usage.values()]
    costs=sum((Decimal(u['saved_settlement_cny']) for u in usage.values()),Decimal(0))
    input_tokens=sum(u['input_tokens'] for u in usage.values());output_tokens=sum(u['output_tokens'] for u in usage.values())
    result={'scope':'completed Plus tuning only','HS_vs_H1_posthoc':hs_h1,'flagged_subset_posthoc':{'n':len(flagged),'cases':len({cases[q] for q in flagged}),'D':totals(views['D'],gold,flagged),'arms':flagged_results},
        'skills':{'per_fold_count':{k:len(v) for k,v in stores.items()},'reflection_tasks':len(reflection),'raw_generated_skills':sum(len(r.get('skills',[])) for r in reflection),'empty_skill_outputs':sum(not r.get('skills') for r in reflection),'filter_counts':dict(Counter(a['reason'] for a in audit)),
        'coverage':coverage,'utility_sign':dict(Counter('unretrieved' if r['utility'] is None else 'negative' if r['utility']<0 else 'zero' if r['utility']==0 else 'positive' for r in credits)),'final_diagnostic_skill_candidates':len(read(out/'final_skill_candidates.json')['skills']),'pruned_store_was_evaluated':False},
        'resources':{'requests':sum(u['saved_attempts'] for u in usage.values()),'technical_extras':sum(u['technical_extra_requests'] for u in usage.values()),'input_tokens':input_tokens,'output_tokens':output_tokens,'saved_settlement_proxy_cny':str(costs),'usage_proxy_cny':str((Decimal(input_tokens)*4+Decimal(output_tokens)*12)/1000000),'actual_credits':None,'generation_elapsed_seconds':(max(ends)-min(starts)).total_seconds(),'first_started_utc':min(starts).isoformat(),'last_ended_utc':max(ends).isoformat()},
        'scope_note':'New subgroup and HS-vs-H1 contrasts are descriptive, after all generation. No frozen prompts, gate or saved predictions changed.'}
    write(out/'publication_summary.json',result)
    case_rows=[]
    for case in sorted(set(cases.values())):
        qs=[q for q in qids if cases[q]==case]
        case_rows.append({'case_id':case,'planned_n':len(qs),'question_ids':qs,'correct':{n:sum(p[q]==gold[q] for q in qs) for n,p in views.items()}})
    write(out/'per_case.json',{'records':case_rows})
    lines=['# Plus 历史与跨折技能：完整结果','',
        '**H1 历史 316/402（78.61%），S1 技能 279/402（69.40%），HS 历史＋技能 300/402（74.63%）；原 D 为295/402（73.38%）。H1整体有正向增益，但未标记历史子集区间跨零，因此三个候选均未通过预先门槛，按固定规则仍保留 D。**','',
        '本轮只使用 qwen3.7-plus，402题/99病例，独立上下文单答。不是此前同病例批量 E2（354/402），也不是Flash。全部回答、205次反思及离线评分均已完成，无新增缺答或技术补票。没有自动运行Flash、控制臂、保留集或全量。','',
        '|配置|正确/402|准确率|病例95%准确率CI|纠正|误改|净增|对D增益病例95%CI（pp）|McNemar p|',
        '|---|---:|---:|---|---:|---:|---:|---|---:|']
    for n,t in m['totals'].items():
        lo,hi=t['accuracy_ci95']
        if n=='D':lines.append(f"|D|295/402|{t['accuracy']:.2%}|{lo:.2%}–{hi:.2%}|—|—|—|—|—|");continue
        p=m['comparisons_to_D'][n];a,b=p['bootstrap']['delta_ci95_pp']
        lines.append(f"|{n}|{t['correct']}/402|{t['accuracy']:.2%}|{lo:.2%}–{hi:.2%}|{p['legal_wrong_to_correct']}|{p['correct_to_legal_wrong']}|{p['net']:+d}|{a:+.2f}～{b:+.2f}|{p['exact_mcnemar_p']:.4g}|")
    lines+=['','全体缺答均为0，纠正/误改均是合法选项变化，没有技术失败恢复混入增益。CI为病例有放回抽样2000次、seed20261103、题数加权百分位区间；McNemar为题级双侧精确检验，不处理病例内相关性，主要结合病例bootstrap判断。三候选探索性比较未作多重比较调整。','',
        '## 历史风险分层与门槛','',
        '运行前固定标记50病例/205题的历史可能含影像词或与诊断共享词；其余49病例/197题未标记。标记由固定规则生成，诊断只在隔离准备步骤用于生成布尔标记，不进入回答请求。H1/HS只收到age、gender、history；各题选项、原图与原D规则保留。','',
        '|子集|分母|D正确|H1正确|S1正确|HS正确|', '|---|---:|---:|---:|---:|---:|']
    clean=[q for q in qids if q not in set(flagged)]
    for label,qs in [('未标记历史',clean),('标记历史',flagged)]:
        counts=[sum(v[q]==gold[q] for q in qs) for v in views.values()]
        lines.append('|'+label+'|'+str(len(qs))+'|'+'|'.join(str(n) for n in counts)+'|')
    lines+=['','|未标记197题相对D|纠正|误改|净增|增益病例95%CI（pp）|','|---|---:|---:|---:|---|']
    for n,p in m['unflagged_subset']['comparisons'].items():
        a,b=p['bootstrap']['delta_ci95_pp'];lines.append(f"|{n}|{p['legal_wrong_to_correct']}|{p['correct_to_legal_wrong']}|{p['net']:+d}|{a:+.2f}～{b:+.2f}|")
    lines+=['','H1的21题净增分布为标记子集+18、未标记子集+3。它支持“提供当前这份history文本时整体成绩上升”，但未满足“未标记子集增益区间下界也>0”的预定条件。因此不能把全部增益称为干净的临床历史作用。标记也不是泄漏的人工确诊，病例难度和文本内容同时不同；这不是随机分组因果分析，未标记子集也可能漏掉线索。','',
        'S1对D净减16题，配对区间为−7.71～−0.50pp，提示此实现的技能注入在这批调参题上表现较差。HS对D仅+5题，区间跨零。HS相对S1的+21题表示加入历史有帮助，但不能据此说组合优于历史单独使用。','',
        '|额外比较|纠正|误改|净增|病例95%CI（pp）|','|---|---:|---:|---:|---|']
    for label,p in [('HS vs S1（预定比较）',m['HS_vs_S1']),('HS vs H1（完成后描述性比较）',hs_h1)]:
        a,b=p['bootstrap']['delta_ci95_pp'];lines.append(f"|{label}|{p['legal_wrong_to_correct']}|{p['correct_to_legal_wrong']}|{p['net']:+d}|{a:+.2f}～{b:+.2f}|")
    lines+=['','## 技能实际训练与使用','',
        '固定50/49病例分折，所有同病例题目留在同一折。205反思输入来自原D的107错题＋随机98对题，包含源折原图、题干、D答案/理由和训练参考；只有反思适配器读取训练参考，H1/S1/HS回答不读取。A的问题只检索B技能，反向同理。S1/HS使用同一预效用库，生成前没有用目标折成绩挑选技能。','',
        f"205反思生成 {result['skills']['raw_generated_skills']} 条技能，空技能输出 {result['skills']['empty_skill_outputs']} 条请求。过滤数字/患者特有风险17条、标识/选项/图号风险10条，因每折40条上限再排除151条，最终A/B各40条。没有新增模型合并调用。过滤是本地规则，不能保证涵盖所有形式的病例特有表述。",'',
        '|臂|获得技能的问题/402|技能检索总次数|不同技能条数|','|---|---:|---:|---:|']
    for n,c in coverage.items():lines.append(f"|{n}|{c['questions_with_skills']}/402|{c['total_skill_retrievals']}|{c['unique_retrieved_skills']}|")
    lines+=['','检索使用当前题与官方类别（多标签），同类别最多3条、general最多2条，TF-IDF匹配。首轮没有独立效用数据，general也用同一匹配排序，稳定ID裁决并列；这不同于提前知道哪些general最有用，已在计划披露。','',
        'S1完成后的关联效用：11条正、29条负、34条零、6条未检索。按预定规则移除负效用与未检索，形成45条后续候选，但**这个裁剪库没有重新评估**，不能把其潜在效果当成已测收益。同题检索多个技能时共享纠正/误改，不能给每条技能作因果归因。','',
        '## 官方类别分层','',
        '|类别|题数|D正确|H1正确（净增）|S1正确（净增）|HS正确（净增）|','|---|---:|---:|---:|---:|---:|']
    for category,c in read(out/'categories.json')['categories'].items():
        t=c['totals'];d=t['D']['correct'];lines.append(f"|{category}|{c['n']}|{d}|"+'|'.join(f"{t[n]['correct']} ({t[n]['correct']-d:+d})" for n in ('H1','S1','HS'))+'|')
    lines+=['','官方类别为重叠多标签，不能相加当作402题互斥分组。类别内完整纠正、误改、区间和题号在 [categories.json](categories.json)；不按本轮类别分数重选方法。','',
        '## 资源与时间','',
        '|阶段|请求数|输入tokens|输出tokens|结算记账代理CNY|首末请求跨度min|','|---|---:|---:|---:|---:|---:|']
    for n,u in usage.items():lines.append(f"|{n}|{u['saved_attempts']}|{u['input_tokens']}|{u['output_tokens']}|{u['saved_settlement_cny']}|{u['wall_seconds']/60:.2f}|")
    lines+=['',f"合计 **{result['resources']['requests']} 次请求，技术额外 {result['resources']['technical_extras']} 次；输入 {input_tokens:,}、输出 {output_tokens:,} tokens；本轮保存结算代理 {costs} CNY**，与这些保存usage按4/12每百万的代理计算一致。未为发布重开或扫描账户账本。所有1,411个请求终态completed，三个回答臂缺答均为0；空技能反思属于有效训练输出，不是题目答对。",'',
        f"生成时间：北京时间16:47:34–17:59:50，共 {result['resources']['generation_elapsed_seconds']/60:.2f} 分钟；统一评分17:59:54结束。该时间不含执行前代码准备和之后发布。原累计200授权及cap未增加，没有恢复已取消的V12完整性/全表校验。",'',
        'CNY仅为继承记账代理，不是实际费率、收费上界或Credits换算。真实Token Plan Credits未知。未启动Flash、控制臂、保留集、全量或任何工具。','',
        '## 公开记录与下一步边界','',
        '本轮没有候选同时通过所有预定条件，因此暂定仍保留原D。H1的整体增益值得报告，技能方案当前未显示正向作用。是否补Flash、修订技能或进入新数据，需要用户后续指令，不能自动把三个调参臂扩成完整旧计划。这里不宣称独立泛化，也不把本实现结果推广为所有技能记忆都无效。','',
        '[原始评分](metrics.json) · [逐题预测/参考/风险标记](per_question.json) · [逐病例结果](per_case.json) · [补充统计](publication_summary.json) · [技能效用](skill_utility.json) · [未评估的裁剪候选库](final_skill_candidates.json)', '',
        '[完整题干/选项/原图](../cases.json) · [H1实际请求与响应](../arms/H1/predictions.jsonl) · [S1实际请求与响应](../arms/S1/predictions.jsonl) · [HS实际请求与响应](../arms/HS/predictions.jsonl) · [反思训练终态](../arms/Reflection/predictions.jsonl) · [技能来源](../skills/crossfit_stores.json) · [过滤记录](../skills/filter_audit.json) · [冻结输入摘要](../input_freeze.json)', '',
        '完整请求、每次实际响应与usage见各arm/checkpoints；训练参考位于独立training目录，不作为盲评输入。复现解释：在仓库根目录运行 `python experiments/summarize_history_skills.py`，只读取已公开的完成结果，不调用模型。', '']
    # Add narrative above original scorer report, retaining its tables below.
    (out/'interpretation.md').write_text('\n'.join(lines),encoding='utf-8')
    write(out/'publication_summary.json',result)
    return result['resources']


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1]);print(summarize(p.parse_args().root))
