"""Score only two complete, matched runs; separate skill-package effect from tool effects."""
import argparse,json
from pathlib import Path
from report_skill_r54ds import report
from online_memory_r49 import read,save_once

def compare(off,on):
    off,on=Path(off),Path(on);a,b=read(off/'manifest.json'),read(on/'manifest.json')
    for k in ('inputs','order','protocol','runtime','defaults','embedding_model','embedding_base_url','dataset','implementation_files'):
        if a[k]!=b[k]:raise ValueError('pair_mismatch:'+k)
    if a['skill_enabled'] or not b['skill_enabled']:raise ValueError('wrong_pair_modes')
    sa,da=report(off);sb,db=report(on)
    aa={x['question_id']:x for x in da};bb={x['question_id']:x for x in db}
    if aa.keys()!=bb.keys():raise ValueError('cohort_mismatch')
    corrected=[q for q in aa if not aa[q]['correct'] and bb[q]['correct']]
    harmed=[q for q in aa if aa[q]['correct'] and not bb[q]['correct']]
    result={'dataset':a['dataset'],'denominator':len(aa),'no_skill':sa,'skill':sb,'corrected_ids':corrected,'harmed_ids':harmed,
      'net':len(corrected)-len(harmed),'delta_pp':100*(len(corrected)-len(harmed))/len(aa),
      'interpretation':'Matched online-GT comparison of the full S54 Skill package, including its extra META compute. Same-image model predictions/tool history can diverge downstream. Not pure per-question skill causality; historical R49 also differs in tool capability.'}
    return result
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--off',required=True);p.add_argument('--on',required=True);p.add_argument('--out',required=True);a=p.parse_args()
    result=compare(a.off,a.on);save_once(Path(a.out),result);print(json.dumps(result,ensure_ascii=False,indent=2))
