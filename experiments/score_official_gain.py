"""Post-completion D/M/P scoring and observable publication; no inference."""
import argparse,json,os,sys
from collections import Counter,defaultdict
from datetime import datetime
from decimal import Decimal
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from official_gain.runtime import read,write,lines
from experiments.compare_direct_vlm import counts,paired
from experiments.official_gain_answer_scoring import explicit_answer

def score(run,out):
 status=read(run/'status.json');protocol=read(run/'protocol.json');rows=read(run/'selection.json')['rows'];qids=[r['question_id'] for r in rows]
 if status.get('status')!='generation_complete' or status.get('completed')!={'D':60,'M':60,'P':60}:raise ValueError('all180_completed_required_before_reference_access')
 predictions=lines(run/'predictions.jsonl');by={(r['question_id'],r['arm']):r for r in predictions}
 if len(predictions)!=180 or set(by)!={(q,a) for q in qids for a in ('D','M','P')}:raise ValueError('prediction_coverage')
 # Read existing public references only now; generation never loads this file.
 old={r['question_id']:r for r in read(out.parent/'direct_qwen60/per_question.json')['records']};labels={q:old[q]['reference'] for q in qids}
 frozen_views={a:{q:by[q,a]['answer'] for q in qids} for a in ('D','M','P')}
 frozen_totals={a:counts(v,labels,qids) for a,v in frozen_views.items()}
 extraction={a:{q:explicit_answer(by[q,a]['raw_response'],set('ABCDEF')) for q in qids} for a in ('D','M','P')}
 views={a:{q:extraction[a][q][0] for q in qids} for a in ('D','M','P')};totals={a:counts(v,labels,qids) for a,v in views.items()}
 scoring={'basis':'post_run_explicit_answer_only_no_inference','raw_terminals_unchanged':True,'frozen_runtime_totals':frozen_totals,'explicit_text_totals':totals,'rules':'Answer/Return Answer/Final Answer followed by one legal letter; otherwise final isolated option paragraph or single opening option plus explanation; conflicting labels/refusal/no committed option remain missing. Rules do not consume reference labels.','records':[{'question_id':q,'arm':a,'frozen_answer':by[q,a]['answer'],'scored_answer':views[a][q],'rule':extraction[a][q][1]} for q in qids for a in ('D','M','P')]}
 transitions={'D_to_M':paired(views['D'],views['M'],labels,qids),'D_to_P':paired(views['D'],views['P'],labels,qids),'M_to_P':paired(views['M'],views['P'],labels,qids)}
 resources={};attempts=[]
 for path in (run/'predictions').glob('*/*/calls/*/attempt_*/result.json'):
  result=read(path);arm=path.relative_to(run/'predictions').parts[1];phase=path.parent.parent.name
  k=arm+':'+phase;v=resources.setdefault(k,dict(requests=0,extra=0,input_tokens=0,output_tokens=0,cny='0',settlement_missing=0));v['requests']+=1;v['extra']+=int(result['ordinal']>1)
  usage=result.get('usage') or {};v['input_tokens']+=usage.get('input_tokens',0);v['output_tokens']+=usage.get('output_tokens',0)
  v['cny']=str(Decimal(v['cny'])+Decimal((result.get('settlement') or {}).get('charged_cny','0')));v['settlement_missing']+=int(not result.get('settlement'));attempts.append(result)
 total=sum((Decimal(v['cny']) for v in resources.values()),Decimal(0));ledger=read(run/'ledger_final_summary.json')
 start=read(run/'ledger_start.json')['utc'];end=ledger['utc']
 cost={'new_run_cny':str(total),'ledger_run_increment_cny':ledger['run_increment_cny'],'ledger_minus_saved_cny':str(Decimal(ledger['run_increment_cny'])-total),'phases':resources,'new_requests':len(attempts),'technical_retries':sum(a['ordinal']>1 for a in attempts),'elapsed_including_initialization_and_recovery_s':(datetime.fromisoformat(end)-datetime.fromisoformat(start)).total_seconds(),'price_basis':ledger['price_basis'],'provider_invoice':False,'D_cache_reused':protocol['direct_cache_reused'],'cached_D_original_fee_cny':'0.326016' if protocol['direct_cache_reused'] else None,'historical_D_fee_not_charged_again':protocol['direct_cache_reused']}
 tools={a:{'requested':sum(by[q,a].get('tool_requested',0) for q in qids),'actual_new_execution':sum(by[q,a].get('tool_actual',0) for q in qids),'exact_raw_cache_hits':sum(by[q,a].get('tool_cache_hits',0) for q in qids),'questions_with_requested_tools':sum(by[q,a].get('tool_requested',0)>0 for q in qids),'new_visual_inputs':sum(by[q,a].get('new_visual_inputs',0) for q in qids),'roi_or_pair_views':sum(by[q,a].get('new_roi_or_pair_views',0) for q in qids)} for a in ('M','P')}
 metrics={'status':'completed','planned_n':60,'scoring_basis':scoring['basis'],'frozen_runtime_totals':frozen_totals,'totals':totals,'paired':transitions,'tools':tools,'P_stop_or_fallback_reasons':dict(Counter(by[q,'P'].get('fallback_reason') for q in qids if by[q,'P'].get('fallback'))),'P_initial_or_final_correct_union_diagnostic_only':sum(views['D'][q]==labels[q] or views['P'][q]==labels[q] for q in qids),'new_memory_or_feedback':False,'goal75':totals['P']['correct']>=45,'goal80':totals['P']['correct']>=48,'P_exceeds_both_D_and_M':totals['P']['correct']>max(totals['D']['correct'],totals['M']['correct']),'cost':cost}
 out.mkdir(parents=True,exist_ok=True)
 from experiments.export_v12_public import PublicAssets
 # Reuse already-published exact image bytes through their saved manifest index.
 from experiments.score_evo_memory import existing_assets
 import hashlib
 existing=existing_assets(out.parent,out)
 class Assets(PublicAssets):
  def put(self,data):
   h=hashlib.sha256(data).hexdigest();p=existing.get(h)
   if p is not None and p.stat().st_size==len(data) and p.read_bytes()==data:
    name=os.path.relpath(p,self.out).replace('\\','/');self.manifest[h]={'path':name,'bytes':len(data),'reuse':True};return name
   return super().put(data)
 assets=Assets(out,run,mappings=[(protocol['root']+'/runs/official_gain60',run)])
 bundles={}
 for row in rows:
  q=row['question_id'];value={'input':row,'reference':labels[q],'post_run_explicit_answers':{a:{'answer':views[a][q],'rule':extraction[a][q][1]} for a in ('D','M','P')}}
  for arm in ('D','M','P'):
   folder=run/'predictions'/q/arm
   value[arm]={str(p.relative_to(folder)).replace('\\','/'):read(p) for p in folder.rglob('*.json') if p.name!='started.json'}
  bundles[q]=value;assets.collect(value)
 # Only actual experiment artifacts; synthetic preflight pixels are separate.
 for p in (run/'artifacts').rglob('*'):
  if p.is_file() and p.suffix.lower() in ('.png','.jpg','.jpeg') and 'preflight' not in p.relative_to(run/'artifacts').parts:
   private=protocol['root']+'/runs/official_gain60/'+p.relative_to(run).as_posix();assets.file(p,private)
 records=[]
 for row in rows:
  q=row['question_id'];value=bundles[q];write(out/'traces'/f'{q}.json',assets.clean(value,Path('traces')))
  record={'question_id':q,'question':row['question'],'reference':labels[q],'post_run_explicit_answers':value['post_run_explicit_answers'],**{a:by[q,a] for a in ('D','M','P')}};records.append(assets.clean(record))
  text=f"# Official gain: {q}\n\nPost-run explicit answers: D **{views['D'][q]}**, M **{views['M'][q]}**, P **{views['P'][q]}**, reference **{labels[q]}**. Frozen runtime answers: D {by[q,'D']['answer']}, M {by[q,'M']['answer']}, P {by[q,'P']['answer']}; original records unchanged.\n\n[Complete observable requests, tools and stages](../traces/{q}.json) · [Original benchmark case](../../v12/results/cases/{q}.md) · [D cached original observable request](../../direct_qwen60/requests/{q}.json)\n\n```text\n"+row['question']+'\n```\n\n'
  for source in row['images']:
   if source in assets.source_names:text+='!['+source+']('+assets.relative(assets.source_names[source],Path('cases'))+')\n\n'
  for a in ('D','M','P'):
   text+='## '+a+'\n\n```text\n'+str(assets.clean(by[q,a]['raw_response'],Path('cases')))+'\n```\n\n'
  p=out/'cases'/f'{q}.md';p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text,encoding='utf-8')
 write(out/'metrics.json',metrics);write(out/'answer_extraction.json',scoring);write(out/'cost_timing.json',cost);write(out/'transitions.json',transitions);write(out/'per_question.json',{'records':records});write(out/'protocol.json',assets.clean(protocol));write(out/'asset-manifest.json',list(assets.manifest.values()))
 (out/'predictions.jsonl').write_text(''.join(json.dumps(assets.clean(r),ensure_ascii=False)+'\n' for r in predictions),encoding='utf-8')
 for name in ('runtime_tools.json','official_prompt.json','budget_preflight.json','status.json'):
  if (run/name).exists():write(out/name,assets.clean(read(run/name)))
 for directory in ('runtime_amendments','recovery_history','execution_logs'):
  for p in (run/directory).rglob('*.json'):
   write(out/p.relative_to(run),assets.clean(read(p),p.relative_to(run).parent))
  for p in (run/directory).rglob('*.log'):
   target=out/p.relative_to(run);target.parent.mkdir(parents=True,exist_ok=True);target.write_text(assets.clean(p.read_text(encoding='utf-8',errors='replace'),p.relative_to(run).parent),encoding='utf-8')
 write(out/'publication-manifest.json',{'cases':60,'traces':60,'predictions':180,'original_predictions_modified':False,'inference_by_exporter':0,'assets':list(assets.manifest.values())})
 (out/'cases/README.md').write_text('# Full 60 cases\n\n'+''.join(f'- [{q}]({q}.md)\n' for q in qids),encoding='utf-8')
 text='# 官方 ReAct 与选项差异视觉取证：D/M/P\n\n|组|正确/60|准确率|有效答案|缺答|\n|---|---:|---:|---:|---:|\n'
 for a,v in totals.items():text+=f"|{a}|{v['correct']}/60|{v['accuracy']:.1%}|{v['valid']}|{v['missing']}|\n"
 text+='\n上表为评分后从已保存回复提取明确选项的口径，无推理、无重跑，规则统一适用于三组且不读取参考。原运行解析器过严，冻结终态计分D/M/P为42/3/28，缺答0/56/2；51条M及1条P回复有明确选项但未被运行解析器接受。两套结果均保留，不能把原M的3/60当作模型医学判断能力。提取规则及逐条映射见[answer_extraction.json](answer_extraction.json)。\n\n**当前结果不支持提分：P低于D与M。P存在定位框坐标及动作契约实现缺陷，M也有历史工具输出丢失；本轮不能隔离方法本身的因果效果。**\n'
 text+='\nD为匹配直接首答；M使用未改写的官方Agent ReAct；P使用差异驱动动作、独立短观察和真实视觉输入回传。主模型统一qwen3-vl-plus。两组每题最多4中央模型调用、4医学工具调用；P含共享D首答，新增最多3中央调用、2个ROI/配对视图。这些是新实验预算，不是论文原设定。\n\n'
 for name,t in transitions.items():text+=f"{name}: 纠正{t['legal_wrong_to_correct']}、误改{t['correct_to_legal_wrong']}、缺答恢复{t['missing_to_correct']}、正确变缺答{t['correct_to_missing']}，净{t['net']:+d}。\n\n"
 text+=f"新增请求{cost['new_requests']}，技术重试{cost['technical_retries']}，保存结算{cost['new_run_cny']} CNY，账本增量{cost['ledger_run_increment_cny']} CNY，耗时（含初始化及恢复）{cost['elapsed_including_initialization_and_recovery_s']/60:.1f}分钟。工具与各阶段费用见[metrics](metrics.json)/[费用](cost_timing.json)。费用是既有计价假设而非供应商账单。\n\n"
 if protocol['direct_cache_reused']:text+='逐题实际请求及解码完全匹配才复用D缓存；本轮没有重付D费用。缓存D原记录费用0.326016 CNY，完整P逻辑路径费用需同时考虑这笔共享首答，不能把新增P费用当整个路径费用。\n\n'
 text+='[完整60题及图像/过程](cases/README.md) · [运行及恢复协议](protocol.md) · [冻结配置](protocol.json) · [具体差异分析](outcome_interpretation.md) · [工具执行与实现缺陷](tool_execution_analysis.md) · [全部转换题](failure_analysis.md)。\n\n未改专家权重；沿用既有离线加载和bf16兼容工作进程，因此不是论文GPT-4o环境的严格数值复现。官方Agent本身不新增图像回传；P才将工具视觉产物作为真正图像输入。M保留官方自主首轮与通用工具提示，另有统一调用预算及简短输出格式适配。这个60题为反复使用开发集，无在线答案反馈，不支持独立泛化结论。P须同时超过D与M才支持当前设置收益；本轮不满足，且执行缺陷混杂。不会据此自动增加记忆、投票、裁决器或付费重跑。\n\n第三方基准原图来自ChestAgentBench/Eurorad，来源及条款见原病例页；未公开模型权重或凭据。\n'
 (out/'README.md').write_text(text,encoding='utf-8')
 analysis='# 差异题与取证分析\n\n这是评分后定向分析入口，需结合实际轨迹补充具体机制判断。初答与终答正确并集只供诊断，不能作为部署准确率。\n\n'
 for name,t in transitions.items():
  analysis+='## '+name+'\n\n'
  for k,ids in t['question_ids'].items():analysis+=k+': '+', '.join(f'[{q}](cases/{q}.md)' for q in ids)+'\n\n'
 analysis+='检查实际新观察是否解决选项差异；若已有正确观察但终答错误，单列整合失败；若没有新增正确证据，不能靠再加裁决或提示微调宣称提分。工具框不是病灶真值、分割区域不是病灶面积、分类分数不是答案概率。\n'
 (out/'failure_analysis.md').write_text(analysis,encoding='utf-8')
 print(json.dumps({'status':'scored','scores':{a:v['correct'] for a,v in totals.items()},'new_requests':cost['new_requests'],'new_cny':cost['new_run_cny'],'tools':tools},ensure_ascii=False))

def main():
 p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--out',type=Path,default=Path('reports/official_gain60'));a=p.parse_args();score(a.run,a.out)
if __name__=='__main__':main()
