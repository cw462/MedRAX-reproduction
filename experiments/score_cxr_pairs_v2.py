"""Offline paired scores using the repository's frozen grade and bootstrap.
Generation must have completed before this script is run. It reads references.
Each --arm is NAME=prediction_dir; supports published jsonl and local predictions/NAME.
For Q comparisons, --published MUST be the Q subset directory, never full 618 inputs.
"""
import argparse
import json
from pathlib import Path
import numpy as np
from score_cxr_vqa_extension import grade, bootstrap, cluster_keys, rows

def predictions(path,arm):
    f=path/('predictions_'+arm+'.jsonl')
    if f.exists():return rows(f)
    return [json.loads(p.read_text(encoding='utf-8')) for p in sorted((path/'predictions'/arm).glob('*.json'))]

def main():
    p=argparse.ArgumentParser();p.add_argument('--published',type=Path,required=True)
    p.add_argument('--arm',action='append',required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--allow-superset',action='store_true',help='Only for restricting full single-question controls to frozen Q IDs')
    a=p.parse_args();inputs=rows(a.published/'inputs.jsonl');ids={r['question_id'] for r in inputs}
    refs={r['question_id']:r['answer'] for r in rows(a.published/'references.jsonl')}
    if len(ids)!=len(inputs) or set(refs)!=ids:raise ValueError('cohort_mismatch')
    subsets=np.array([r.get('source',{}).get('subset','all') for r in inputs]);clusters=cluster_keys(inputs)
    evaluated={};report={'questions':len(inputs),'arms':{},'comparisons':{}}
    for spec in a.arm:
        arm,path=spec.split('=',1)
        if arm in evaluated:raise ValueError('duplicate_arm')
        records=predictions(Path(path),arm);pred={r['question_id']:r for r in records}
        if len(pred)!=len(records) or not ids<=set(pred) or (not a.allow_superset and ids!=set(pred)):raise ValueError('prediction_ids:'+arm)
        correct,missing=zip(*(grade(r,pred[r['question_id']],refs[r['question_id']]) for r in inputs))
        values=np.array(correct,dtype=int);evaluated[arm]=values
        by_subset={str(s):{'n':int(sum(subsets==s)),'correct':int(sum(values[subsets==s])),
                          'accuracy_pct':float(values[subsets==s].mean()*100)} for s in sorted(set(subsets))}
        report['arms'][arm]={'correct':int(values.sum()),'missing':int(sum(missing)),
                            'micro_pct':float(values.mean()*100),'macro_pct':float(np.mean([v['accuracy_pct'] for v in by_subset.values()])),
                            'subsets':by_subset}
    first=next(iter(evaluated))
    for arm,values in evaluated.items():
        if arm==first:continue
        delta=values-evaluated[first]
        report['comparisons'][arm+' vs '+first]={'corrections':int(sum(delta>0)),'harms':int(sum(delta<0)),
                                                'net':int(sum(delta)),'confidence':bootstrap(delta,clusters,subsets)}
    if a.out.exists():raise ValueError('new_score_output_required')
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(report,ensure_ascii=False,indent=2,default=lambda x:x.tolist()),encoding='utf-8')
    print(a.out)

if __name__=='__main__':main()
