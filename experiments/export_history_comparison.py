"""Join already completed experiments by question ID; no inference or ledger access."""
import json
from pathlib import Path

def read(p):return json.loads(p.read_text(encoding='utf-8'))
def main():
    base=Path('reports');out=base/'history'
    v11=read(base/'v11/per-question-outcomes.json')['records']
    v10={r['question_id']:r for r in read(base/'v10/per-question-outcomes.json')}
    v9p={r['question_id']:r for r in read(base/'v9/p0_outcomes.json')}
    v9b={(r['question_id'],r['group']):r for r in read(base/'v9/branch_outcomes.json')}
    v7={r['question_id']:r for r in read(out/'early/v7-fixed-denominator.json')['questions']}
    v4={}
    for arm in 'ABC':
        records=[json.loads(l) for l in (out/f'early/records/v4_{arm}_r1/results.jsonl').read_text(encoding='utf-8').splitlines() if l.strip()]
        v4[arm]={r['question_id']:r for r in records if r.get('record_type')=='terminal'}
    rows=[]
    for r in v11:
        q=r['question_id'];gold=r['reference_answer']
        def item(answer,status=None):return {'answer':answer,'correct':answer==gold if answer else False,'status':status}
        experiments={'V4_S2_round1':{a:item(v4[a][q].get('answer_letter'),v4[a][q].get('status')) for a in 'ABC'},
                     'V7_round2':{a:item(v7[q]['letters'].get(a)) for a in ['P0','P1','PB','PC','GB','GC']},
                     'V9':None,
                     'V10':{'P0':item(v10[q]['p0'],v10[q]['p0_status'])},
                     'V11':{a:item(r['answers'][a]) for a in ['S1','S2','S3']}}
        if q in v9p:
            experiments['V9']={'P0':item(v9p[q]['initial'],v9p[q]['status'])}
            for a in ['D','DK','DKB','DKC']:
                b=v9b[q,a];experiments['V9'][a]={'candidate':item(b['candidate']),'final':item(b['final']), 'fallback':b.get('fallback')}
        for a,b in v10[q]['branches'].items():experiments['V10'][a]={'candidate':item(b['candidate']),'final':item(b['final']),'fallback':b.get('fallback')}
        links={'case_images':f'../v11/cases/{q}.md','early_record':f'early/cases/{q}.json','v10_case':f'../v10/cases/{q}.md',
               'v11_S1_trace':f'../v11/traces/S1/{q}.json','v11_S2_trace':f'../v11/traces/S2/{q}.json','v11_S3_trace':f'../v11/traces/S3/{q}.json'}
        if q in v9p:links['v9_case']=f'../v9/cases/{q}.md'
        rows.append({'question_id':q,'reference_answer':gold,'source_links':links,'experiments':experiments})
    payload={'scope':'Fixed 60-question historical join after all runs completed. experiments.V9=null means not selected in V9; answer=null means no legal answer was retained; status=null means execution status is not represented in this joined summary and must be read from the linked source.',
             'comparison_limit':'V4, V7, V9, V10 generated their own baselines under different protocols/times. Cross-version differences are descriptive and are not causal gains. V11 reuses V10 frozen P0/VKE.',
             'reference_source':'V11 completed independent scoring export; used only for retrospective publication. Missing answers count as incorrect in planned-denominator summaries.',
             'records':rows}
    (out/'cross-version-outcomes.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    lines=['# 同一 60 题的历史答案对照','','[历史总索引](README.md) · [完整 JSON](cross-version-outcomes.json)','','✓ 为参考选项匹配，× 为不匹配，缺答记为错误；“未运行”不进入该轮分母。题号链接到原图、完整选项及 V11 复盘。V4/V7/V9/V10 各自生成了 P0 或无记忆基线，跨轮分数变化混合了协议、调用、时间和抽样变化，不能直接声称是版本增益。V11 只复用 V10 的 P0/VKE 候选。','','## V4 与 V7','','| 题目 | 参考 | V4 A/B/C | V7 P0/P1/PB/PC/GB/GC |','|---|---|---|---|']
    def cell(i):return (i['answer'] or '缺答')+('✓' if i['correct'] else '×')
    for r in rows:
        e=r['experiments'];q=r['question_id']
        lines.append(f"| [{q}]({r['source_links']['case_images']}) | {r['reference_answer']} | {' / '.join(cell(i) for i in e['V4_S2_round1'].values())} | {' / '.join(cell(i) for i in e['V7_round2'].values())} |")
    lines+=['','## V9、V10 与 V11','','V9 列顺序 P0/D/DK/DKB/DKC；V10 为 P0/V/VK/VKE 最终答案；V11 为 S1/S2/S3。原始候选、错误/回退状态与逐轮记录链接在 JSON 内。','','| 题目 | V9 最终 | V10 最终 | V11 最终 |','|---|---|---|---|']
    for r in rows:
        e=r['experiments'];q=r['question_id'];a=e['V9'];b=e['V10']
        c9='未运行' if a is None else ' / '.join([cell(a['P0'])]+[cell(a[k]['final']) for k in ['D','DK','DKB','DKC']])
        c10=' / '.join([cell(b['P0'])]+[cell(b[k]['final']) for k in ['V','VK','VKE']])
        lines.append(f"| [{q}]({r['source_links']['case_images']}) | {c9} | {c10} | {' / '.join(cell(i) for i in e['V11'].values())} |")
    (out/'cross-version-outcomes.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps({'joined_questions':len(rows),'v9_run_questions':sum(r['experiments']['V9'] is not None for r in rows)}))
if __name__=='__main__':main()
