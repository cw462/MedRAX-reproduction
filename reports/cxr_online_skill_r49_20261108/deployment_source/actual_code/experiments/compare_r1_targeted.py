"""Post-generation R1 scoring and allowlisted case/trace publication.

Uses frozen public references only after generation_complete and all60 terminals.
Never opens the live ledger or makes an inference request.
"""
from __future__ import annotations
import argparse
from collections import Counter
from datetime import datetime
from decimal import Decimal
import json
from math import comb
from pathlib import Path
import re
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from run_direct_vlm import read,write,read_lines
from compare_direct_vlm import paired,counts


def saved_packets(run,qid):
    folder=run/'checkpoints'/qid
    names=('terminal.json','action_plan.json','action.json','images.json','observer_action.json')
    packet={name:read(folder/name) for name in names if (folder/name).exists()}
    for phase in ('plan','observe'):
        base=folder/phase
        if (base/'request.json').exists():packet[phase+'/request.json']=read(base/'request.json')
        for attempt in sorted(base.glob('attempt_*')):
            for name in ('started.json','response.json','result.json'):
                if (attempt/name).exists():packet[phase+'/'+attempt.name+'/'+name]=read(attempt/name)
        for p in sorted(base.glob('reserve_error_*.json')):packet[phase+'/'+p.name]=read(p)
    return packet


def generate(run,d0,v12,out):
    status=read(run/'status.json')
    if status.get('status')!='generation_complete' or status.get('completed_n')!=60:raise ValueError('R1_generation_not_complete')
    rows=read(run/'selection.json')['rows'];qids=[r['question_id'] for r in rows]
    terminal_rows=read_lines(run/'predictions.jsonl');records={r['question_id']:r for r in terminal_rows}
    if len(terminal_rows)!=60 or set(records)!=set(qids):raise ValueError('all60_unique_R1_terminals_required')
    baseline=read(run/'baseline_cache.json');protocol=read(run/'protocol.json')
    # The first reference/old outcome access occurs only after the checks above.
    old={r['question_id']:r for r in read(d0/'per_question.json')['records']}
    if set(old)!=set(qids):raise ValueError('frozen_comparison_ID_mismatch')
    labels={q:old[q]['reference'] for q in qids}
    if any(baseline[q]['answer']!=old[q]['D0_derived']['answer'] for q in qids):raise ValueError('cached_D0_explicit_choices_differ_from_published_derived')
    views={'D0_explicit_cache':{q:baseline[q]['answer'] for q in qids},
           'R1_solver':{q:records[q]['solver_answer'] for q in qids},
           'R1_adopted':{q:records[q]['answer'] for q in qids},
           'V12_initial':{q:old[q]['V12']['initial']['answer'] for q in qids},
           'V12_A_candidate':{q:old[q]['V12']['A']['candidate_answer'] for q in qids},
           'V12_B_candidate':{q:old[q]['V12']['B']['candidate_answer'] for q in qids},
           'V12_A_final':{q:old[q]['V12']['A']['answer'] for q in qids},
           'V12_B_final':{q:old[q]['V12']['B']['answer'] for q in qids}}
    totals={name:counts(value,labels,qids) for name,value in views.items()}
    transitions={name+'_to_R1_adopted':paired(value,views['R1_adopted'],labels,qids) for name,value in views.items() if name!='R1_adopted'}
    transitions['D0_explicit_cache_to_R1_solver']=paired(views['D0_explicit_cache'],views['R1_solver'],labels,qids)
    t=transitions['D0_explicit_cache_to_R1_adopted'];discordant=t['legal_wrong_to_correct']+t['correct_to_legal_wrong']+t['missing_to_correct']+t['correct_to_missing']
    left=t['legal_wrong_to_correct']+t['missing_to_correct'];right=t['correct_to_legal_wrong']+t['correct_to_missing']
    p=min(1.,2*sum(comb(discordant,k) for k in range(min(left,right)+1))/2**discordant) if discordant else 1.
    categories={}
    # Categories belong to the outer V12 outcome, not its initial-answer object.
    v12_outcomes={r['question_id']:r for r in read(v12/'per_question.json')['records']}
    for name in sorted({c for q in qids for c in v12_outcomes[q]['official_categories']}):
        ids=[q for q in qids if name in v12_outcomes[q]['official_categories']]
        categories[name]={'N':len(ids),**{view:sum(values[q]==labels[q] for q in ids) for view,values in views.items()}}
    requested=Counter(r['requested_action'] for r in terminal_rows)
    executed=Counter(r['action'].get('executed_kind','not_executed') for r in terminal_rows)
    attributes=Counter(r['attribute'] for r in terminal_rows)
    tools=Counter(r['action'].get('tool') for r in terminal_rows if r['action'].get('medical_tool_calls'))
    crop_checks=[r['action']['crop_audit'] for r in terminal_rows if r['action'].get('crop_audit')]
    execution={'requested_action_counts':requested,'executed_action_counts':executed,
               'target_attribute_counts':attributes,'medical_tool_attempts_by_name':tools,
               'medical_tool_attempts':sum(r['action'].get('medical_tool_calls',0) for r in terminal_rows),
               'crop_calls':sum(r['action'].get('crop_calls',0) for r in terminal_rows),
               'crop_binding_checks':len(crop_checks),'crop_binding_allowed':sum(c['allowed'] for c in crop_checks),
               'crop_rejection_reasons':Counter(c['reason'] for c in crop_checks if not c['allowed']),
               'action_error_n':sum(r['action'].get('status')=='error' for r in terminal_rows),
               'fallback_n':sum(r['fallback_to_D0'] for r in terminal_rows),
               'fallback_correct_n':sum(r['fallback_to_D0'] and r['answer']==labels[r['question_id']] for r in terminal_rows),
               'D0_choices_or_reasons_sent_to_models':False,'confidence_gate':False,'voting':False,'extra_final_resolve':False}
    packets={q:saved_packets(run,q) for q in qids}
    from v12_evidence import question_parts
    for row in rows:
        q=row['question_id'];legal=question_parts(row['question'])[1];r=records[q]
        if r['solver_answer'] is not None and r['solver_answer'] not in legal:raise ValueError('illegal_R1_solver_answer')
        if r['answer'] not in legal:raise ValueError('illegal_R1_adopted_answer')
        if r['fallback_to_D0']:
            if r['solver_answer'] is not None or r['answer']!=baseline[q]['answer']:raise ValueError('inconsistent_controller_fallback')
        elif r['answer']!=r['solver_answer']:raise ValueError('legal_solver_answer_not_adopted')
    execution['planner_neutralization_warnings']=Counter(w for packet in packets.values() for w in packet.get('action_plan.json',{}).get('warnings',[]))
    attempts=[value for packet in packets.values() for key,value in packet.items() if key.endswith('/result.json')]
    costs=[a['settlement']['charged_cny'] for a in attempts if a.get('settlement')]
    resources={'central_model_requests':len(attempts),'technical_extra_requests':sum(a['ordinal']>1 for a in attempts),
               'input_tokens':sum((a.get('usage') or {}).get('input_tokens',0) for a in attempts),
               'output_tokens':sum((a.get('usage') or {}).get('output_tokens',0) for a in attempts),
               'usage_missing_n':sum(not a.get('usage') for a in attempts),
               'saved_settlement_cny':str(sum((Decimal(c) for c in costs),Decimal(0))),
               'settlement_missing_n':len(attempts)-len(costs),
               'ledger_saved_summary':read(run/'ledger_final_summary.json'),
               'medical_tool_attempts':execution['medical_tool_attempts'],'crop_calls':execution['crop_calls'],
               'local_tool_cost_note':'Local tool/GPU time included in wall time; no provider monetary charge inferred for local models.',
               'started_utc':terminal_rows[0]['started_utc'],'ended_utc':terminal_rows[-1]['ended_utc'],
               'stage_elapsed_s_sum':round(sum(r['elapsed_s'] for r in terminal_rows),3)}
    resources['wall_elapsed_s']=(datetime.fromisoformat(resources['ended_utc'])-datetime.fromisoformat(resources['started_utc'])).total_seconds()
    metrics={'status':'completed','planned_n':60,'totals':totals,'primary_paired_D0_to_R1':t,
             'exploratory_exact_mcnemar_two_sided_p':p,'categories_overlapping':categories,'execution':execution,
             'source_cache_commit':protocol['source_cache_commit'],'generation_commit':protocol['implementation_commit']}
    out.mkdir(parents=True,exist_ok=True)
    from export_v12_public import PublicAssets
    class R1Assets(PublicAssets):
        def put(self,data):
            import hashlib
            digest=hashlib.sha256(data).hexdigest();old_asset=list((v12/'assets').glob(digest+'.*'))
            if len(old_asset)==1:
                public='../v12/results/assets/'+old_asset[0].name
                self.manifest[digest]={'path':public,'bytes':len(data),'reuse':True};return public
            return super().put(data)
    remote_run=str(Path(protocol['root'])/'runs/r1_qwen60').replace('\\','/')
    assets=R1Assets(out,run,mappings=[(remote_run,run)])
    for packet in packets.values():assets.collect(packet)
    def collect_referenced_files(value):
        if isinstance(value,dict):
            for x in value.values():collect_referenced_files(x)
        elif isinstance(value,list):
            for x in value:collect_referenced_files(x)
        elif isinstance(value,str) and value.startswith(remote_run+'/') and '\n' not in value and Path(value).suffix.lower() in {'.png','.jpg','.jpeg','.webp'}:
            assets.resolve(value)
    for packet in packets.values():collect_referenced_files(packet)
    combined=[]
    for row in rows:
        q=row['question_id'];folder=Path('cases');packet=packets[q]
        write(out/'traces'/f'{q}.json',assets.clean({'question_id':q,'records':packet},Path('traces')))
        entry={'question_id':q,'question':row['question'],'reference':labels[q],
               'D0':baseline[q],'R1':records[q],
               'historical':{name:views[name][q] for name in views if name not in {'D0_explicit_cache','R1_solver','R1_adopted'}},
               'original_images_and_V12':f'../../v12/results/cases/{q}.md','D0_raw_response':f'../../direct_qwen60/responses/{q}_1.json',
               'trace':f'../traces/{q}.json'}
        write(out/'cases'/f'{q}.json',assets.clean(entry,folder))
        root_entry=dict(entry,original_images_and_V12=f'../v12/results/cases/{q}.md',
                        D0_raw_response=f'../direct_qwen60/responses/{q}_1.json',trace=f'traces/{q}.json')
        combined.append(assets.clean(root_entry))
        text=f"# R1：{q}\n\n[全部题目](README.md) · [完整可观察记录](../traces/{q}.json) · [D0原回复](../../direct_qwen60/responses/{q}_1.json)\n\n"
        text+=f"D0明确Answer缓存 **{baseline[q]['answer']}**；R1观察求解 **{records[q]['solver_answer']}**；控制器采用 **{records[q]['answer']}**；参考 **{labels[q]}**；回退 **{records[q]['fallback_to_D0']}**。\n\n"
        text+='## 完整题干与选项\n\n```text\n'+row['question']+'\n```\n\n## 原图与本轮局部\n\n'
        image_registry=packet.get('images.json',{})
        for im in image_registry.get('originals',[])+image_registry.get('derived',[]):
            public=assets.aliases.get(im['path'])
            if public:text+='**'+im['image_id']+' — '+str(im.get('figure_label',''))+'**\n\n!['+im['image_id']+']('+assets.relative(public,folder)+')\n\n'
        text+=f"[基准来源及V12历史过程](../../v12/results/cases/{q}.md)。模型/工具输出不是人工确认的患者事实。\n\n## 单次观察与方向绑定\n\n"
        plan=packet.get('action_plan.json',{});text+='```json\n'+json.dumps(assets.clean(plan,folder),ensure_ascii=False,indent=2)+'\n```\n\n'
        action=records[q]['action'];text+='```json\n'+json.dumps(assets.clean(action,folder),ensure_ascii=False,indent=2)+'\n```\n\n'
        raw=next((v.get('content','') for k,v in reversed(list(packet.items())) if k.startswith('observe/') and k.endswith('/response.json')),'No saved observation response.')
        text+='## 独立观察后的原始短答\n\n```text\n'+str(assets.clean(raw,folder))+'\n```\n'
        (out/'cases'/f'{q}.md').parent.mkdir(parents=True,exist_ok=True);(out/'cases'/f'{q}.md').write_text(text,encoding='utf-8')
    with (out/'predictions.jsonl').open('w',encoding='utf-8',newline='\n') as f:
        for r in terminal_rows:f.write(json.dumps(assets.clean(r),ensure_ascii=False)+'\n')
    write(out/'per_question.json',{'planned_n':60,'records':combined});write(out/'transitions.json',transitions)
    write(out/'metrics.json',metrics);write(out/'cost_timing.json',resources);write(out/'execution.json',execution)
    write(out/'protocol.json',assets.clean(protocol));write(out/'baseline_cache.json',baseline);write(out/'asset-manifest.json',list(assets.manifest.values()))
    if (run/'runtime_tools.json').exists():write(out/'runtime_tools.json',assets.clean(read(run/'runtime_tools.json')))
    index='# R1 全部60题\n\n[总报告](../README.md)\n\n'+''.join(f"- [{q}]({q}.md)\n" for q in qids)
    (out/'cases/README.md').write_text(index,encoding='utf-8')
    table=['| 组 | 正确/60 | 准确率 | 有效答 | 缺答 |','|---|---:|---:|---:|---:|']
    for name,value in totals.items():table.append(f"| {name} | {value['correct']}/60 | {value['accuracy']:.1%} | {value['valid']} | {value['missing']} |")
    text='# R1：一次独立针对性取证结果\n\n'
    text+=f"**R1控制器采用 {totals['R1_adopted']['correct']}/60，独立观察求解器 {totals['R1_solver']['correct']}/60；D0明确Answer缓存 {totals['D0_explicit_cache']['correct']}/60，净变化 {t['net']:+d}。**\n\n"+'\n'.join(table)+'\n\n'
    text+=f"相对D0：合法错答纠正 {t['legal_wrong_to_correct']}，正确答误改 {t['correct_to_legal_wrong']}，缺答恢复 {t['missing_to_correct']}，正确答变缺答 {t['correct_to_missing']}。探索性精确McNemar p={p:.8g}。控制器回退 {execution['fallback_n']} 次，其中正确 {execution['fallback_correct_n']} 次，不能算模型新解对。\n\n"
    text+='| 重叠任务类别 | N | D0缓存 | R1求解 | R1采用 | A候选 | B候选 | A最终 | B最终 |\n|---|---:|---:|---:|---:|---:|---:|---:|---:|\n'
    for name,value in categories.items():
        text+=f"| {name} | {value['N']} | {value['D0_explicit_cache']} | {value['R1_solver']} | {value['R1_adopted']} | {value['V12_A_candidate']} | {value['V12_B_candidate']} | {value['V12_A_final']} | {value['V12_B_final']} |\n"
    text+='\n类别有重叠，不可相加；总体始终每题计一次、完整60分母。\n\n'
    text+=f"实际中央模型请求 {resources['central_model_requests']}，技术额外重试 {resources['technical_extra_requests']}；医学工具尝试 {execution['medical_tool_attempts']}，crop {execution['crop_calls']}。请求/执行动作分布、工具名、目标属性和失败均见[执行明细](execution.json)。\n\n"
    text+=f"裁剪方向/框检查 {execution['crop_binding_checks']} 次，通过 {execution['crop_binding_allowed']} 次，拒绝原因 {dict(execution['crop_rejection_reasons'])}。拒绝只将动作退回原图，不对答案做置信度拦截。通过只证明模型报告的标记和框几何相符，不证明标记本身被读对；原图始终同屏，未翻转/旋转。\n\n"
    if not execution['crop_binding_checks']:text+='本轮未请求crop，因此这次真实实验没有覆盖裁剪侧别修正；相关修正只有事前合成像素/几何测试，不能据此归因成绩变化。\n\n'
    text+=f"保存结算费用 {resources['saved_settlement_cny']} CNY，原账本保存的本轮增量 {resources['ledger_saved_summary'].get('run_increment_cny')} CNY；不打开真实账本、不补写记录，计价假设不是供应商账单。墙钟耗时 {resources['wall_elapsed_s']:.1f} 秒；本地医学工具/GPU时间包含其中，未虚构货币费用。D0旧费用不重复加入本轮。\n\n"
    text+='[运行协议](protocol.md) · [机器协议](protocol.json) · [全部60题原图/局部/回复](cases/README.md) · [四项转换](transitions.json) · [逐题结构化对照](per_question.json) · [失败分析](failure_analysis.md) · [费用耗时](cost_timing.json)\n\n'
    text+='模型参数与D0一致。新推理覆盖全部60题，规划和观察均不接收D0答案、理由或旧观察；没有K/E、投票、置信度门槛或额外最终重答。采用全部合法独立观察答案，技术无答才由控制器回退D0。D0缓存使用已发布的明确Answer派生解析口径，旧原解析17/60记录仍保留，不能将本轮比较解释为改写旧成绩。该60题为反复使用开发集，本轮一个固定顺序/单次采样不能分离规划、裁剪、工具或模型随机性的因果贡献。\n\n'
    text+='这里的“独立”仅指会话与输入隔离，不代表不同模型家族，也不保证统计独立的判断错误。若动作主要为visual，新增的是选项差异导向的重新观察，并没有取得新的原始像素信息；不能将分数变化算作外部医学工具贡献。\n\n'
    run_cli='experiments/run_r1_targeted.py --config configs/r1_qwen60.json --out "$R/runs/r1_qwen60" --resume --api-key-stdin'
    text+=f"生成提交 `{protocol['implementation_commit']}`；旧缓存固定 `{protocol['source_cache_commit']}`。复现入口 `{run_cli}`，工作目录 `$R/code_r1`，Python `$R/.venv/bin/python`，R取配置root。后置评分：`python experiments/compare_r1_targeted.py --run local_assets/r1_qwen60 --d0-public reports/direct_qwen60 --v12-public reports/v12/results --out reports/r1_qwen60`。\n"
    (out/'README.md').write_text(text,encoding='utf-8')
    analysis='# R1 定向错误与互补分析\n\n'
    analysis+='主配对结果、全部差异ID见[transitions.json](transitions.json)；以下先保留定向阅读入口，人工分析只能依据保存输出，不能将模型解释当作已验证影像事实。\n\n'
    for name in ('legal_wrong_to_correct','correct_to_legal_wrong','missing_to_correct','correct_to_missing'):
        analysis+='## '+name+'\n\n'+''.join(f'- [{q}](cases/{q}.md)\n' for q in t['question_ids'][name])+'\n'
    analysis+='## 预先讨论的互补类型（不参与运行路由）\n\n'
    for q in ('13238_8353800603808','13935_8353800618951','3436_8353801521068'):
        analysis+=f"- [{q}](cases/{q}.md)：D0 {baseline[q]['answer']}；R1求解 {records[q]['solver_answer']}；采用 {records[q]['answer']}；参考 {labels[q]}。\n"
    (out/'failure_analysis.md').write_text(analysis,encoding='utf-8')
    write(out/'publication-manifest.json',{'planned_n':60,'case_pages':60,'trace_bundles':60,
          'new_model_calls_by_scorer_or_exporter':0,'original_prediction_records_modified':False,
          'assets':list(assets.manifest.values()),'transform':'Saved observable records only; strip credential fields/private paths; reference reused originals and exact saved derived pixel bytes.',
          'ledger_access':'saved run increment summary only; no live ledger opened'})
    print(json.dumps({'status':'scored','D0_correct':totals['D0_explicit_cache']['correct'],
        'R1_solver_correct':totals['R1_solver']['correct'],'R1_adopted_correct':totals['R1_adopted']['correct'],'net':t['net'],'execution':execution},ensure_ascii=True))


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run',type=Path,required=True);p.add_argument('--d0-public',type=Path,required=True)
    p.add_argument('--v12-public',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args(argv);generate(a.run,a.d0_public,a.v12_public,a.out)


if __name__=='__main__':main()
