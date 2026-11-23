"""Isolated scoring only after all Plus H1/Reflection/S1/HS runs complete."""
import argparse
from collections import defaultdict
from pathlib import Path

from history_skills import ID,merge_skills
from score_votes import load_complete_run,read,read_labels,totals,paired,resources,write
from score_case_information import accuracy_interval


def score(root):
    root=Path(root);base=root/'runs'/ID;out=root/'reports'/ID/'analysis'
    if (out/'scoring_complete.json').exists():return
    runs={n:load_complete_run(base/'arms'/n) for n in ('H1','Reflection','S1','HS')}
    rows=runs['H1']['rows'];qids=runs['H1']['qids'];cases={r['question_id']:r['case_id'] for r in rows}
    if any(runs[n]['qids']!=qids for n in ('S1','HS')):raise ValueError('same_fixed_denominator_required')
    labels_path=root/'reports/qwen37_token_plan_20261102/phase1/per_question.json'
    labels=read_labels(labels_path,qids)
    old={r['question_id']:r['answers']['D'] for r in read(labels_path)['records']}
    views={'D':{q:old[q] for q in qids},**{n:{q:runs[n]['answers'][q,1] for q in qids} for n in ('H1','S1','HS')}}
    flags=read(base/'inputs/history_flags.json')['cases'];clean=[q for q in qids if not flags[cases[q]]['flagged']]
    cats=read(base/'inputs/categories.json')
    metrics={'status':'completed','experiment_id':ID,'model':'qwen3.7-plus','baseline':'D','all_answer_generation_complete_before_scoring':True,'reference_exception':'Source-fold reflection training reads training references; never answer workers.',
             'totals':{n:{**totals(v,labels,qids),**accuracy_interval(v,labels,qids,cases)} for n,v in views.items()},
             'comparisons_to_D':{n:paired(old,views[n],labels,qids,cases,2000,20261103) for n in ('H1','S1','HS')},
             'unflagged_subset':{'questions':len(clean),'cases':len({cases[q] for q in clean}),'question_ids':clean,'comparisons':{n:paired(old,views[n],labels,clean,cases,2000,20261103) for n in ('H1','S1','HS')} if len({cases[q] for q in clean})>=2 else None},
             'HS_vs_S1':paired(views['S1'],views['HS'],labels,qids,cases,2000,20261103),
             'usage':{n:resources(r['records']) for n,r in runs.items()},'actual_token_plan_credits':None,
             'multiple_comparisons':'Three exploratory tuning candidates, unadjusted; no independent generalization claim.'}
    metrics['passes_gate']={n:metrics['comparisons_to_D'][n]['bootstrap']['delta_ci95'][0]>0 and (n=='S1' or bool(metrics['unflagged_subset']['comparisons']) and metrics['unflagged_subset']['comparisons'][n]['bootstrap']['delta_ci95'][0]>0) for n in ('H1','S1','HS')}
    eligible=[n for n in ('H1','S1','HS') if metrics['passes_gate'][n]]
    metrics['provisional_tuning_choice']=max(eligible,key=lambda n:(metrics['totals'][n]['correct'],-['H1','S1','HS'].index(n))) if eligible else 'D'
    metrics['next_action']='Report to user; no automatic Flash, heldout, full benchmark or control execution.'
    categories={}
    for cat in sorted({c for values in cats.values() for c in values}):
        qs=[q for q in qids if cat in cats[q]]
        categories[cat]={'n':len(qs),'totals':{n:totals(v,labels,qs) for n,v in views.items()},'paired_to_D':{n:paired(old,views[n],labels,qs,cases,2000,20261103) for n in ('H1','S1','HS')}}
    write(out/'categories.json',{'multilabel_overlaps_do_not_sum_to_402':True,'categories':categories})
    stores=read(base/'skills/crossfit_stores.json')['stores'];utility=defaultdict(lambda:{'retrieval_n':0,'corrections':0,'harms':0})
    for q in qids:
        retrieval=read(base/'arms/S1/retrieval'/(q+'.json'))
        for sid in retrieval['skill_ids']:
            u=utility[sid];u['retrieval_n']+=1;u['corrections']+=int(old[q]!=labels[q] and views['S1'][q]==labels[q]);u['harms']+=int(old[q]==labels[q] and views['S1'][q]!=labels[q])
    candidates=[];credits=[]
    for skills in stores.values():
        for skill in skills:
            u=utility[skill['skill_id']];value=u['corrections']-u['harms'] if u['retrieval_n'] else None
            credits.append(dict(u,skill_id=skill['skill_id'],utility=value,causal_credit=False))
            if value is not None and value>=0:candidates.append(dict(skill,utility=value))
    # This final diagnostic library is never substituted into saved crossfit answers.
    final,rejected=merge_skills(candidates,60,utility_order=True)
    write(out/'skill_utility.json',{'records':credits,'interpretation':'S1 retrieval association only; co-retrieved skills share credit.'})
    write(out/'final_skill_candidates.json',{'skills':final,'rejected':rejected,'future_evaluation_requires_separate_user_instruction':True})
    write(out/'per_question.json',{'records':[{'question_id':q,'case_id':cases[q],'reference':labels[q],'history_flagged':flags[cases[q]]['flagged'],'categories':cats[q],'predictions':{n:v[q] for n,v in views.items()},'correct':{n:v[q]==labels[q] for n,v in views.items()}} for q in qids]})
    write(out/'metrics.json',metrics)
    text='# Plus H1/S1/HS: completed tuning scoring\n\n'
    text+='|Arm|Correct/402|Accuracy|Missing|\n|---|---:|---:|---:|\n'
    for n,t in metrics['totals'].items():text+=f"|{n}|{t['correct']}/402|{t['accuracy']:.2%}|{t['missing']}|\n"
    text+='\n|Versus D|Corrections|Harms|Net|Paired case 95% CI pp|\n|---|---:|---:|---:|---|\n'
    for n,p in metrics['comparisons_to_D'].items():
        lo,hi=p['bootstrap']['delta_ci95_pp'];text+=f"|{n}|{p['legal_wrong_to_correct']+p['missing_to_correct']}|{p['correct_to_legal_wrong']+p['correct_to_missing']}|{p['net']:+d}|{lo:+.2f} to {hi:+.2f}|\n"
    text+='\n[Metrics and unflagged history subset](metrics.json) · [402 question results](per_question.json) · [Official multilabel categories](categories.json) · [Skill utility](skill_utility.json).\n\nSame 99 tuning cases; no heldout/Flash/control calls. CNY amounts are inherited proxies, not actual Token Plan Credits or an invoice. Missing outcomes remain missing; source-fold supervised reflection and crossfit evaluation are disclosed.\n'
    (out/'README.md').write_text(text,encoding='utf-8')
    write(out/'scoring_complete.json',{'status':'completed','new_inference_calls':0})


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);score(p.parse_args().root)
