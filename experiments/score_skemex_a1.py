"""Compare completed crossfit A1 with the user-confirmed A0=D and old S1/HS."""
import argparse
from pathlib import Path
from collections import Counter
from score_votes import read,write,read_labels,totals,paired,resources
from score_case_information import accuracy_interval
from skemex_adapter.transport import ID


def score(root):
    root=Path(root);base=root/'runs'/ID;out=root/'reports'/ID/'analysis'
    if (out/'scoring_complete.json').exists():return
    rows=read(base/'inputs/rows.json');qids=[r['question_id'] for r in rows];cases={r['question_id']:r['case_id'] for r in rows}
    if len(qids)!=402 or not all((base/'predictions'/(q+'.json')).exists() for q in qids):raise ValueError('all402_A1_terminals_required_before_labels')
    pred={q:read(base/'predictions'/(q+'.json')) for q in qids}
    labels_path=root/'reports/qwen37_token_plan_20261102/phase1/per_question.json'
    labels=read_labels(labels_path,qids)
    old={r['question_id']:r['answers']['D'] for r in read(labels_path)['records']}
    views={'D_A0':old,'A1':{q:p['answer'] for q,p in pred.items()}}
    previous=read(root/'reports/history_skills_plus_20261103/analysis/per_question.json')['records']
    for name in ('S1','HS'):views['old_'+name]={r['question_id']:r['predictions'][name] for r in previous}
    comparisons={name:paired(values,views['A1'],labels,qids,cases,2000,20261103) for name,values in views.items() if name!='A1'}
    calls=[read(p) for p in (base/'calls').glob('*/checkpoints/*/sample_1/terminal.json')]
    usage_by_stage={stage:resources([r for r in calls if r.get('operation_stage')==stage]) for stage in []}
    # Operation directories distinguish source prediction, encoding/governance, target routing+answer.
    grouped={}
    for p in (base/'calls').glob('*/checkpoints/*/sample_1/terminal.json'):
        job=p.parents[3].name;stage={'s':'source_prediction_and_retrieval','e':'source_encoding_review','g':'source_governance','t':'target_A1_and_retrieval'}[job[0]]
        grouped.setdefault(stage,[]).append(read(p))
    m={'status':'completed','A0_is_D_user_clarification':True,'model':'qwen3.7-plus','n':402,'case_n':99,
       'totals':{n:{**totals(v,labels,qids),**accuracy_interval(v,labels,qids,cases)} for n,v in views.items()},
       'comparisons_A1_vs':comparisons,'goal_5pp_met':comparisons['D_A0']['net']>=21,'goal_10pp_met':comparisons['D_A0']['net']>=41,
       'positive_case_CI':comparisons['D_A0']['bootstrap']['delta_ci95'][0]>0,'usage':resources(calls),
       'usage_by_stage':{s:resources(v) for s,v in grouped.items()},'actual_credits':None,
       'declared_adoption_questions':sum(bool(p['declared_applied_skill_ids']) for p in pred.values()),
       'skill_context_questions':sum(bool(p['injected_skill_ids']) for p in pred.values()),
       'interpretation':'Development-set paired evidence after prior uses. Bootstrap conditions on these frozen predictions, not on memory training randomness. Old S1/HS not a retrieval-only ablation.'}
    if read(base/'config.json').get('tool_agent'):
        observations=[o for p in pred.values() for o in p.get('tool_observations',[])]
        m['interpretation']='Tool-enabled A1 vs direct D combines tools, extra decision calls and memory. No matched tool-agent without-memory control was run; memory-only gain cannot be identified. Development-set evidence only.'
        m['tool_usage']={'questions_with_selected_tools':sum(bool(p.get('tool_observations')) for p in pred.values()),
            'questions_with_usable_evidence':sum(any(o['usable'] for o in p.get('tool_observations',[])) for p in pred.values()),
            'selected_tool_calls':len(observations),'same_round_cache_hits':sum(o['same_round_cache_hit'] for o in observations),
            'fresh_inference_attempted':sum(o['fresh_inference_attempted'] for o in observations),
            'tool_plan_errors':sum(bool(p.get('tool_plan_error')) for p in pred.values())}
        source=[read(p) for p in (base/'source_predictions').glob('*/*.json')]
        backend=[read(p) for p in (base/'tool_cache/invocations').glob('*/*/*/result.json')]
        m['tool_usage']['source_questions_with_usable_evidence']=sum(any(o['usable'] for o in p.get('tool_observations',[])) for p in source)
        m['tool_usage']['unique_backend_inference_attempts']=sum(r.get('invoked') is True for r in backend)
        m['tool_usage']['backend_interrupted_unknown']=sum(r.get('invoked') is None for r in backend)
    write(out/'metrics.json',m)
    write(out/'per_question.json',{'records':[{'question_id':q,'case_id':cases[q],'reference':labels[q],'predictions':{n:v[q] for n,v in views.items()},'A1_details':pred[q]} for q in qids]})
    cats=read(base/'inputs/official_categories.json');by={}
    for cat in sorted({c for values in cats.values() for c in values}):
        qs=[q for q in qids if cat in cats[q]]
        by[cat]={'n':len(qs),'totals':{n:totals(v,labels,qs) for n,v in views.items()},'A1_vs_A0':paired(old,views['A1'],labels,qs,cases,2000,20261103)}
    write(out/'categories.json',{'overlapping_multilabel':True,'categories':by})
    text='# Official SkeMex A1: completed crossfit evaluation\n\nA0 is the user-confirmed direct D; no tool-agent baseline is claimed.\n\n|View|Correct/402|Accuracy|Missing|\n|---|---:|---:|---:|\n'
    for n,t in m['totals'].items():text+=f"|{n}|{t['correct']}/402|{t['accuracy']:.2%}|{t['missing']}|\n"
    text+='\n|A1 versus|Corrections|Harms|Net|Case CI pp|\n|---|---:|---:|---:|---|\n'
    for n,p in comparisons.items():
        lo,hi=p['bootstrap']['delta_ci95_pp'];text+=f"|{n}|{p['legal_wrong_to_correct']+p['missing_to_correct']}|{p['correct_to_legal_wrong']+p['correct_to_missing']}|{p['net']:+d}|{lo:+.2f} to {hi:+.2f}|\n"
    text+='\n[Metrics/usage](metrics.json) · [Per-question predictions](per_question.json) · [Official categories](categories.json). '+m['interpretation']+' Source-fold supervised evolution and all meta calls count toward cost. Target utility is frozen. CNY is an inherited accounting proxy, not actual Token Plan Credits.\n'
    (out/'README.md').write_text(text,encoding='utf-8');write(out/'scoring_complete.json',{'status':'completed','new_inference_calls':0})


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);score(p.parse_args().root)
