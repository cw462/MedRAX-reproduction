"""M1 post-stream scoring/publication; no inference or live ledger access."""
from collections import Counter
from datetime import datetime
from decimal import Decimal
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from evo_memory.io import read,write,lines,jsonl
from experiments.compare_direct_vlm import paired,counts


def call_packet(folder):
    value={}
    if not folder.exists():return value
    for name in ('request.json',):
        if (folder/name).exists():value[name]=read(folder/name)
    for attempt in sorted(folder.glob('attempt_*')):
        for name in ('started.json','response.json','result.json'):
            if (attempt/name).exists():value[attempt.name+'/'+name]=read(attempt/name)
    for p in folder.glob('reserve_error_*.json'):value[p.name]=read(p)
    return value


def existing_assets(reports,out):
    """Use saved publication indexes; never hash-scan image trees."""
    found={}
    for manifest in reports.rglob('*manifest*.json'):
        if manifest.is_relative_to(out):continue
        try:payload=read(manifest)
        except (ValueError,OSError):continue
        def visit(value,hint=None):
            if isinstance(value,dict):
                digest=value.get('sha256',hint)
                if isinstance(digest,str) and re.fullmatch('[0-9a-f]{64}',digest):
                    for key in ('path','public_path','relative_path','file'):
                        name=value.get(key)
                        if isinstance(name,str) and Path(name).suffix.lower() in {'.jpg','.jpeg','.png','.webp'}:
                            for p in (manifest.parent/name,reports.parent/name,reports/name):
                                p=p.resolve()
                                if p.is_relative_to(reports.parent.resolve()) and p.is_file():found.setdefault(digest,p);break
                for k,v in value.items():visit(v,k if re.fullmatch('[0-9a-f]{64}',str(k)) else None)
            elif isinstance(value,list):
                for v in value:visit(v)
        visit(payload)
    return found


def score(run,d0,out):
    status=read(run/'status.json');protocol=read(run/'protocol.json');selection=read(run/'eval_selection.json')
    if status.get('status')!='generation_complete' or status.get('predictions_committed')!={'E':60,'ES':60}:raise ValueError('both_full_stream_arms_required_before_score')
    rows=selection['rows'];case_map=selection['case_map'];qids=[r['question_id'] for r in rows]
    predictions=lines(run/'stream/predictions.jsonl');by={(r['question_id'],r['arm']):r for r in predictions}
    if len(predictions)!=120 or set(by)!={(q,a) for q in qids for a in ('E','ES')}:raise ValueError('duplicate_missing_or_extra_prediction')
    feedback={p.stem:read(p) for p in (run/'stream/feedback').glob('*.json')};labels={}
    for case,value in feedback.items():
        for q,reference in value['references'].items():
            if case_map.get(q)!=case:raise ValueError('feedback_wrong_case')
            for a in ('E','ES'):
                if by[q,a]['committed_utc']>value['released_utc']:raise ValueError('feedback_preceded_prediction_commit')
            labels[q]=reference['answer']
    if set(labels)!=set(qids):raise ValueError('completed_feedback_reference_coverage')
    old={r['question_id']:r for r in read(d0/'per_question.json')['records']}
    if any(old[q]['reference']!=labels[q] for q in qids):raise ValueError('reference_disagrees_with_frozen_D0_cache')
    views={'D0':{q:old[q]['D0_derived']['answer'] for q in qids},**{a:{q:by[q,a]['answer'] for q in qids} for a in ('E','ES')}}
    totals={a:counts(v,labels,qids) for a,v in views.items()}
    transitions={'D0_to_'+a:paired(views['D0'],views[a],labels,qids) for a in ('E','ES')}
    transitions['E_to_ES']=paired(views['E'],views['ES'],labels,qids)
    prefixes={a:[{'through_step':n,**counts(v,labels,qids[:n])} for n in (12,24,36,48,60)] for a,v in views.items()}
    blocks={a:[{'steps':[i+1,i+12],**counts(v,labels,qids[i:i+12])} for i in range(0,60,12)] for a,v in views.items()}
    v12=d0.parent/'v12/results';outcomes={r['question_id']:r for r in read(v12/'per_question.json')['records']}
    groups={r['question_id']:r['official_group'] for r in read(v12/'selection.json')['rows']}
    def group_name(value):return value if isinstance(value,str) else json.dumps(value,sort_keys=True,ensure_ascii=False)
    five={}
    for name in sorted({group_name(groups[q]) for q in qids}):
        ids=[q for q in qids if group_name(groups[q])==name]
        five[name]={'N':len(ids),**{a:counts(v,labels,ids) for a,v in views.items()}}
    seven={}
    for name in sorted({c for q in qids for c in outcomes[q]['official_categories']}):
        ids=[q for q in qids if name in outcomes[q]['official_categories']]
        seven[name]={'N':len(ids),**{a:sum(v[q]==labels[q] for q in ids) for a,v in views.items()}}
    seed_selection=read(run/'seed_selection.json');seed_packets={};eval_packets={};all_attempts=[]
    for item in seed_selection:
        q=item['row']['question_id'];folder=run/'seed/checkpoints'/q
        packet={'source':item}
        for name in ('historical_prediction.json','reflection_candidates.json','reflection_candidate_retrieval.json','done.json'):
            if (folder/name).exists():packet[name]=read(folder/name)
        for phase in ('predict','reflect'):
            packet[phase]=call_packet(folder/phase)
            all_attempts.extend(v for k,v in packet[phase].items() if k.endswith('/result.json'))
        seed_packets[q]=packet
    retrieval_stats={a:[] for a in ('E','ES')};violations=[]
    for row in rows:
        q=row['question_id'];case=case_map[q]
        for arm in ('E','ES'):
            folder=run/'stream/predictions'/q/arm
            packet={name:read(folder/name) for name in ('prediction.json','retrieval.json','memory_before.json')}
            packet['feedback']=feedback[case]
            for phase in ('answer','reflect'):
                packet[phase]=call_packet(run/'stream/calls'/q/arm/phase)
                all_attempts.extend(v for k,v in packet[phase].items() if k.endswith('/result.json'))
            update=run/'stream/updates'/arm/q/'done.json'
            if update.exists():packet['memory_update']=read(update)
            before=packet['memory_before.json'];step=by[q,arm]['step']
            for e in before['episodes']:
                if e['source_case_id']==case or e['available_after_step']>=step:violations.append([q,arm,e['id']])
                if e['source_phase']=='past_stream' and (e['source_case_id'] not in feedback or feedback[e['source_case_id']]['released_after_step']>=step):violations.append([q,arm,'future_episode'])
            for rule in before['rules']:
                if case in rule['source_case_ids'] or rule['available_after_step']>=step:violations.append([q,arm,rule['id']])
            if packet['retrieval.json']['context_token_estimate']>protocol['context_token_limit']:violations.append([q,arm,'context_over_limit'])
            retrieval_stats[arm].append({'question_id':q,'step':step,'visible_E_n':len(before['episodes']),'visible_S_n':len(before['rules']),
                 'selected_E_n':len(packet['retrieval.json']['selected_E_ids']),'selected_S_n':len(packet['retrieval.json']['selected_S_ids']),
                 'context_token_estimate':packet['retrieval.json']['context_token_estimate'],'memory_version':before['memory_version']})
            eval_packets[q,arm]=packet
    if violations:raise ValueError('memory_visibility_or_context_boundary_violation:'+str(violations[:2]))
    phase_resources={}
    for attempt in all_attempts:
        phase=attempt['phase'];r=phase_resources.setdefault(phase,{'requests':0,'technical_extra':0,'input_tokens':0,'output_tokens':0,'usage_missing':0,'saved_settlement_cny':'0','elapsed_s':0.})
        r['requests']+=1;r['technical_extra']+=int(attempt['ordinal']>1);usage=attempt.get('usage') or {}
        r['input_tokens']+=usage.get('input_tokens',0);r['output_tokens']+=usage.get('output_tokens',0);r['usage_missing']+=int(not usage)
        r['saved_settlement_cny']=str(Decimal(r['saved_settlement_cny'])+Decimal((attempt.get('settlement') or {}).get('charged_cny','0')))
        r['elapsed_s']+=attempt.get('elapsed_s') or 0
    total_cost=sum((Decimal(x['saved_settlement_cny']) for x in phase_resources.values()),Decimal(0))
    started=min(a['started_utc'] for a in all_attempts);ended=max(a.get('ended_utc') or a['started_utc'] for a in all_attempts)
    resources={'phase_resources':phase_resources,'central_requests':len(all_attempts),'technical_extra':sum(a['ordinal']>1 for a in all_attempts),
               'saved_settlement_cny':str(total_cost),'ledger_final_summary':read(run/'ledger_final_summary.json'),
               'started_utc':started,'ended_utc':ended,'wall_elapsed_s':(datetime.fromisoformat(ended)-datetime.fromisoformat(started)).total_seconds(),
               'medical_tool_calls':0,'shared_seed_cost_counted_once':True,'not_provider_invoice':True}
    resources['settlement_missing_n']=sum(not a.get('settlement') for a in all_attempts)
    increment=resources['ledger_final_summary'].get('run_increment_cny')
    resources['ledger_increment_minus_saved_settlements_cny']=str(Decimal(increment)-total_cost) if increment is not None else None
    seed_summary=read(run/'seed/summary.json');states={a:read(run/'stream/arms'/a/'state.json') for a in ('E','ES')}
    metrics={'status':'completed','planned_n':60,'totals':totals,'paired':transitions,'seed_summary':seed_summary,
             'feedback_condition':protocol['feedback_condition'],'prefixes_every12_postrun_only':prefixes,'all12_question_blocks':blocks,
             'last_three_12_question_blocks':{a:v[-3:] for a,v in blocks.items()},'five_task_combinations':five,'seven_overlapping_abilities':seven,
             'goal75':{a:totals[a]['correct']>=45 for a in ('E','ES')},'goal80':{a:totals[a]['correct']>=48 for a in ('E','ES')},
             'actual_memory_exposure':retrieval_stats,'final_memory_counts':{a:{'E':len(s['episodes']),'actionable_E':sum(e['actionable'] for e in s['episodes']),'S':len(s['rules'])} for a,s in states.items()},
             'source_generation_commit':protocol['implementation_commit'],'historical_cache_commit':protocol['source_cache_commit']}
    metrics['memory_update_status_counts']={'seed':Counter(p.get('done.json',{}).get('reflection_status','missing') for p in seed_packets.values()),
        **{a:Counter(eval_packets[q,a].get('memory_update',{}).get('status','skipped_last_feedback_case') for q in qids) for a in ('E','ES')}}
    out.mkdir(parents=True,exist_ok=True)
    from experiments.export_v12_public import PublicAssets
    existing=existing_assets(out.parent,out)
    class Assets(PublicAssets):
        def put(self,data):
            h=hashlib.sha256(data).hexdigest();p=existing.get(h)
            if p is not None and p.stat().st_size==len(data) and p.read_bytes()==data:
                relative=os.path.relpath(p,self.out).replace('\\','/')
                self.manifest[h]={'path':relative,'bytes':len(data),'reuse':True};return relative
            return super().put(data)
    assets=Assets(out,run)
    for packet in seed_packets.values():assets.collect(packet)
    for packet in eval_packets.values():assets.collect(packet)
    records=[]
    def link(target,folder):return os.path.relpath(out/target,out/folder).replace('\\','/')
    for item in seed_selection:
        row=item['row'];q=row['question_id'];packet=seed_packets[q]
        write(out/'traces/seed'/f'{q}.json',assets.clean(packet,Path('traces/seed')))
        text=f'# M1独立训练种子：{q}\n\n[原始预测/反思/规则候选](../../traces/seed/{q}.json)\n\n'
        case_number=q.split('_',1)[0]
        text+='来源：[ChestAgentBench固定版本](https://huggingface.co/datasets/wanglab/chest-agent-bench/tree/921e60440927f9893228d843c0206b755744252a) · [Eurorad病例](https://www.eurorad.org/case/'+case_number+')。数字前缀只用于来源链接，病例排除仍使用显式case_id派生hash。\n\n'
        text+='本例属于独立memory_train，未与评测病例共享case_hash。原参考标签只用于授权的训练预热；模型影像观察仍未独立验证。\n\n```text\n'+row['question']+'\n```\n\n'
        for name in row['images']:
            public=assets.source_names.get(name)
            if public:text+='!['+name+']('+assets.relative(public,Path('seed/cases'))+')\n\n'
        text+='参考选项全文：'+item['reference']['correct_choice_text']+'\n\n'
        if item['historical_prediction'] and not item['historical_prediction'].get('raw_response_available'):text+='原历史只保留合法选项，未保留完整理由；不得从反思推断当时真实思路。\n'
        (out/'seed/cases').mkdir(parents=True,exist_ok=True);(out/'seed/cases'/f'{q}.md').write_text(text,encoding='utf-8')
    for row in rows:
        q=row['question_id'];folder=Path('cases')
        record={'question_id':q,'case_id':case_map[q],'step':by[q,'E']['step'],'reference':labels[q],'D0':views['D0'][q],
                'E':by[q,'E'],'ES':by[q,'ES'],'feedback':feedback[case_map[q]],'question':row['question'],
                'task_combination':groups[q],'overlapping_abilities':outcomes[q]['official_categories']}
        records.append(assets.clean(record))
        text=f'# M1：{q}\n\nD0 **{views["D0"][q]}**；E **{views["E"][q]}**；ES **{views["ES"][q]}**；参考 **{labels[q]}**。\n\n'
        text+='[D0原回复](../../direct_qwen60/responses/'+q+'_1.json) · [基准来源/原图](../../v12/results/cases/'+q+'.md)\n\n```text\n'+row['question']+'\n```\n\n'
        for name in row['images']:
            public=assets.source_names.get(name)
            if public:text+='!['+name+']('+assets.relative(public,folder)+')\n\n'
        for arm in ('E','ES'):
            packet=eval_packets[q,arm];write(out/'traces/eval'/f'{q}_{arm}.json',assets.clean(packet,Path('traces/eval')))
            write(out/'memory/visible'/f'{q}_{arm}.json',assets.clean(packet['memory_before.json'],Path('memory/visible')))
            text+=f'## {arm}\n\n[请求/原回复/检索/反馈/反思/更新](../traces/eval/{q}_{arm}.json) · [作答前真实可见记忆](../memory/visible/{q}_{arm}.json)\n\n'
            retrieval=packet['retrieval.json'];text+='实际注入历史记忆：\n\n```text\n'+retrieval['memory_context']+'\n```\n\n'
            text+='本题提交后的原回复：\n\n```text\n'+str(assets.clean(packet['prediction.json']['raw_response'],folder))+'\n```\n\n'
            text+=f"提交时间：{packet['prediction.json']['committed_utc']}；本病例反馈时间：{feedback[case_map[q]]['released_utc']}，反馈释放位置{feedback[case_map[q]]['released_after_step']}。当前/未来病例未进入本次记忆投影。\n\n"
        (out/'cases').mkdir(parents=True,exist_ok=True);(out/'cases'/f'{q}.md').write_text(text,encoding='utf-8')
    for arm in ('E','ES'):
        write(out/'memory'/arm/'final_state.json',assets.clean(states[arm],Path('memory')/arm))
        for path in sorted((run/'stream/arms'/arm/'versions').glob('*.json')):
            write(out/'memory'/arm/'versions'/path.name,assets.clean(read(path),Path('memory')/arm/'versions'))
    jsonl(out/'seed/seed_E.jsonl',[assets.clean(x,Path('seed')) for x in lines(run/'seed/seed_E.jsonl')]);write(out/'seed/seed_S.json',assets.clean(read(run/'seed/seed_S.json'),Path('seed')))
    write(out/'seed/sources.json',assets.clean(seed_selection,Path('seed')));write(out/'protocol.json',assets.clean(protocol));write(out/'budget_preflight.json',assets.clean(read(run/'budget_preflight.json')))
    write(out/'metrics.json',metrics);write(out/'per_question.json',{'records':records});write(out/'transitions.json',transitions);write(out/'cost_timing.json',resources)
    jsonl(out/'predictions.jsonl',[assets.clean(p) for p in predictions]);write(out/'asset-manifest.json',list(assets.manifest.values()))
    write(out/'feedback-events.json',assets.clean(feedback));write(out/'case-order.json',{'rows':rows,'case_map':case_map})
    write(out/'publication-manifest.json',{'eval_case_pages':60,'seed_case_pages':len(seed_selection),'eval_trace_bundles':120,'seed_trace_bundles':len(seed_selection),
         'assets':list(assets.manifest.values()),'new_inference_by_exporter':0,'live_ledger_read':False,'original_predictions_modified':False,
         'feedback_condition':protocol['feedback_condition'],'transform':'Observable saved content retained; credentials/private paths removed; image data URIs linked to exact-byte existing/new assets.'})
    (out/'cases/README.md').write_text('# M1固定60题\n\n'+''.join(f'- [{q}]({q}.md)\n' for q in qids),encoding='utf-8')
    table=['| 组 | 正确/60 | 准确率 | 有效答 | 缺答 | 反馈条件 |','|---|---:|---:|---:|---:|---|']
    for a,v in totals.items():table.append(f"| {a} | {v['correct']}/60 | {v['accuracy']:.1%} | {v['valid']} | {v['missing']} | "+('无记忆/无顺序反馈，历史缓存' if a=='D0' else '独立训练标签预热＋已完成病例顺序反馈')+' |')
    text='# M1：Evo式病例经验与规则更新结果\n\n**本轮是有标签预热＋在线顺序答案反馈，不是无反馈盲测，也没有医学工具/裁剪。**\n\n'+'\n'.join(table)+'\n\n'
    for name,t in transitions.items():text+=f"{name}：合法纠正{t['legal_wrong_to_correct']}，误改{t['correct_to_legal_wrong']}，缺答恢复{t['missing_to_correct']}，正确变缺答{t['correct_to_missing']}，净变化{t['net']:+d}。\n\n"
    text+=f"实际预热{seed_summary['case_n']}病例，存储E={seed_summary['reflections_stored']}、可注入E={seed_summary['actionable_E_n']}、seed S={seed_summary['S_n']}。正常调用预期{protocol['expected_normal_requests']}，实际中央请求{resources['central_requests']}、技术额外{resources['technical_extra']}。保存费用合计{resources['saved_settlement_cny']} CNY，原账本保存增量{resources['ledger_final_summary']['run_increment_cny']} CNY；各阶段见[费用](cost_timing.json)，预热共用一次，不将完整Agent成本缩成最后一次作答费。计价假设不是供应商账单。墙钟约{resources['wall_elapsed_s']/60:.1f}分钟。\n\n"
    text+='| 阶段 | 实际请求 | 输入tokens | 输出tokens | 保存费用CNY |\n|---|---:|---:|---:|---:|\n'
    for name,value in phase_resources.items():text+=f"| {name} | {value['requests']} | {value['input_tokens']} | {value['output_tokens']} | {value['saved_settlement_cny']} |\n"
    seed_cost=sum((Decimal(v['saved_settlement_cny']) for k,v in phase_resources.items() if k.startswith('seed_')),Decimal(0))
    text+='\n共享seed构建费 '+str(seed_cost)+' CNY；E与ES正式作答/在线反思费用分别列出，完整单组路径需加共享seed，但整个实验汇总只计seed一次。缺失结算 '+str(resources['settlement_missing_n'])+' 次，账本增量与已保存结算差额 '+str(resources['ledger_increment_minus_saved_settlements_cny'])+' CNY，差额不补写原记录。\n\n'
    text+='## 每12题事后累计\n\n| 截至位置 | D0 | E | ES |\n|---|---:|---:|---:|\n'
    for i,n in enumerate((12,24,36,48,60)):text+=f"| {n} | {prefixes['D0'][i]['correct']}/{n} | {prefixes['E'][i]['correct']}/{n} | {prefixes['ES'][i]['correct']}/{n} |\n"
    text+='\n最后三个12题区段为25–36、37–48、49–60，各自完整分母12；完整5区段与实际题量见metrics.json，仅在流完成后计算，未据此调参。\n\n'
    text+='## 五种任务组合\n\n| 组合 | N | D0 | E | ES |\n|---|---:|---:|---:|---:|\n'
    for name,v in five.items():text+=f"| {name} | {v['N']} | {v['D0']['correct']} | {v['E']['correct']} | {v['ES']['correct']} |\n"
    text+='\n## 七种重叠能力\n\n| 类别 | N | D0 | E | ES |\n|---|---:|---:|---:|---:|\n'
    for name,v in seven.items():text+=f"| {name} | {v['N']} | {v['D0']} | {v['E']} | {v['ES']} |\n"
    text+='\n能力标签重叠，不能加总；总分始终60。\n\n'
    text+='[实现协议](protocol.md) · [机器协议](protocol.json) · [60题与每题真实记忆/全部过程](cases/README.md) · [seed来源](seed/sources.json) · [seed E](seed/seed_E.jsonl) · [seed S](seed/seed_S.json) · [配对转换](transitions.json) · [失败与具体记忆](failure_analysis.md)\n\n'
    text+='达到45/60才是相对42/60净+5个百分点，48/60才是+10。D0基线使用已发布明确Answer派生解析，旧原解析17/60未被改写。D0与M1还存在固定记忆使用提示、标签预算、反馈条件和服务时间差异；ES−E是本实现规则路径总增量，不是单条规则的因果贡献或步骤信用。\n\n'
    text+='病例排除用显式case_id派生case_hash，未新增全库像素/患者身份独立性审计。当前60题已被反复使用，只跑一个固定顺序；若观察到提升，冻结后仍需独立病例和明确固定记忆/反馈协议验证泛化。两组均不超过42时，不自动在同60题调K/提示重跑。在线记忆保留在本轮namespace，未进入旧memory_train池。\n\n'
    run_cli='python experiments/run_evo_pipeline.py --config configs/m1_evo_memory60.json --out "$R/runs/m1_evo_memory60" --resume --api-key-stdin'
    text+=f"生成提交`{protocol['implementation_commit']}`，旧缓存`{protocol['source_cache_commit']}`。实际服务器执行入口：`{run_cli}`，工作目录`$R/code_m1`，Python为`$R/.venv/bin/python`，MEDRAX_CODE_COMMIT取本协议。后置评分：`python experiments/score_evo_memory.py --run local_assets/m1_evo_memory60 --d0-public reports/direct_qwen60 --out reports/m1_evo_memory60`。\n"
    text+='\n基准媒体来自[ChestAgentBench固定版本](https://huggingface.co/datasets/wanglab/chest-agent-bench/tree/921e60440927f9893228d843c0206b755744252a)，病例页保留Eurorad来源链接。第三方媒体沿用原来源条款，不作为本仓库代码重新授权；公开仅包含本轮明确使用的病例/图像/可观察记录，不含凭据或模型权重。\n'
    (out/'README.md').write_text(text,encoding='utf-8')
    analysis='# M1：具体经验与差异分析\n\n以下是完成后的定向阅读入口。反思文字和模型观察不是人工确认的患者事实；参考诊断不证明所有相关征象可见。\n\n'
    for arm in ('E','ES'):
        t=transitions['D0_to_'+arm];analysis+='## '+arm+'的纠正与误改\n\n'
        for kind in ('legal_wrong_to_correct','correct_to_legal_wrong','missing_to_correct','correct_to_missing'):
            analysis+=kind+': '+', '.join(f'[{q}](cases/{q}.md)' for q in t['question_ids'][kind])+'\n\n'
    examples=[e for e in lines(run/'seed/seed_E.jsonl') if e['actionable']][:2]
    for arm in ('E','ES'):examples += [e for e in states[arm]['episodes'] if e['source_phase']=='past_stream' and e['actionable']][:2]
    analysis+='## 非通用经验示例（归档全文，非当前患者事实）\n\n'
    for episode in examples:analysis+='```json\n'+json.dumps(assets.clean(episode),ensure_ascii=False,indent=2)+'\n```\n\n'
    analysis+='## 后续人工定位\n\n只围绕差异题核对实际检索是否找到相同混淆、具体检查动作是否适用、是否将历史参考诊断直接套到当前患者，以及当前像素/题干是否足够区分；不得仅凭一段反思或正确性关联宣称因果。未超过42时交付真实失败，不自动重跑调参。\n'
    (out/'failure_analysis.md').write_text(analysis,encoding='utf-8')
    print(json.dumps({'status':'scored','D0':totals['D0']['correct'],'E':totals['E']['correct'],'ES':totals['ES']['correct'],
        'net_E':transitions['D0_to_E']['net'],'net_ES':transitions['D0_to_ES']['net'],'ES_minus_E':transitions['E_to_ES']['net'],
        'seed_n':seed_summary['case_n'],'requests':resources['central_requests'],'saved_cost_cny':resources['saved_settlement_cny']}))


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run',type=Path,required=True);p.add_argument('--d0-public',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();score(a.run,a.d0_public,a.out)


if __name__=='__main__':main()
