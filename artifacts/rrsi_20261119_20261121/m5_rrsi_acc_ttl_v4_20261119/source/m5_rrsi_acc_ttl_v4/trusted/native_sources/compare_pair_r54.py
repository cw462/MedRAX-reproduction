"""Score only two complete, matched runs; separate skill-package effect from tool effects."""
import argparse,json
from pathlib import Path
from report_skill_r54 import report,adapt_run
from online_memory_r49 import read,save_once

def compare(off,on):
    off,on=Path(off),Path(on);a,b=read(off/'manifest.json'),read(on/'manifest.json')
    for k in ('inputs','order','protocol','runtime','defaults','embedding_model','embedding_base_url','dataset','implementation_files'):
        if a[k]!=b[k]:raise ValueError('pair_mismatch:'+k)
    if a['skill_enabled'] or not b['skill_enabled']:raise ValueError('wrong_pair_modes')
    counts={'chexbench':618,'slake':114,'vqarad':116}
    for root,manifest in ((off,a),(on,b)):
        if (root/'generation.exitcode').read_text().strip()!='0':raise ValueError('actual_full_runner_zero_required')
        if not (root/'complete.json').is_file() or len(manifest['inputs'])!=counts[manifest['dataset']]:raise ValueError('full_paired_cohort_required')
        if {p.stem for p in (root/'predictions'/manifest['arm']).glob('*.json')}!={x['question_id'] for x in manifest['inputs']}:raise ValueError('complete_prediction_membership_required')
    # Adapt BOTH raw arms before either report opens feedback or references.
    adapted_a=adapt_run(off);adapted_b=adapt_run(on)
    sa,da=report(off,adapted=adapted_a);sb,db=report(on,adapted=adapted_b)
    aa={x['question_id']:x for x in da};bb={x['question_id']:x for x in db}
    if aa.keys()!=bb.keys():raise ValueError('cohort_mismatch')
    corrected=[q for q in aa if not aa[q]['correct'] and bb[q]['correct']]
    harmed=[q for q in aa if aa[q]['correct'] and not bb[q]['correct']]
    result={'dataset':a['dataset'],'denominator':len(aa),'no_skill':sa,'skill':sb,'corrected_ids':corrected,'harmed_ids':harmed,
      'net':len(corrected)-len(harmed),'delta_pp':100*(len(corrected)-len(harmed))/len(aa),
      'raw_adaptation_before_any_scoring_labels':True,
      'interpretation':'Matched online-GT comparison of the full S54 Skill package, including its extra META compute. Same-image model predictions/tool history can diverge downstream. Not pure per-question skill causality; historical R49 also differs in tool capability.'}
    return result,da,db
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--off',required=True);p.add_argument('--on',required=True);p.add_argument('--out',required=True);a=p.parse_args()
    result,off_details,on_details=compare(a.off,a.on)
    for root,summary,details in ((a.off,result['no_skill'],off_details),(a.on,result['skill'],on_details)):
        save_once(Path(root)/'analysis/summary.json',summary);save_once(Path(root)/'analysis/per_question.json',details)
    save_once(Path(a.out),result)
    print(json.dumps({'dataset':result['dataset'],'n':result['denominator'],'off_correct':result['no_skill']['correct'],
        'on_correct':result['skill']['correct'],'corrected':len(result['corrected_ids']),'harmed':len(result['harmed_ids']),
        'net':result['net'],'delta_pp':result['delta_pp']},ensure_ascii=False))
