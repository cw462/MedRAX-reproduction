"""Freeze label-blind mask and exact historical reuse; makes no API calls."""
import argparse,copy
from pathlib import Path
from cxr_action_skill_r41 import *
def main():
    p=argparse.ArgumentParser()
    for k in ('base-config','data','bank','historical','out'):p.add_argument('--'+k,type=Path,required=True)
    p.add_argument('--experiment-id',required=True);a=p.parse_args()
    if not a.experiment_id.startswith('action_r41_'):raise ValueError('experiment_id_prefix')
    if a.out.exists() and any(a.out.iterdir()):raise ValueError('fresh_directory_required')
    cfg=read(a.base_config);rt=read(cfg['runtime']);prot=read(cfg['protocol'])
    spec=copy.deepcopy(rt['arms']['M']);cards=load(a.bank,spec['tools'])
    if not any(c['kind']=='task' for c in cards):raise ValueError('reviewed_task_cards_required_for_R41')
    inputs=rows(a.data/'inputs.jsonl');hist=rows(a.historical)
    history={r['question_id']:r for r in hist};ids=[r['question_id'] for r in inputs]
    if len(set(ids))!=len(ids) or len(history)!=len(hist) or set(ids)!=set(history):raise ValueError('exact_cohort_required')
    if any('answer' not in r for r in hist):raise ValueError('historical_answer_field_missing')
    # Preserve historical null/Unknown predictions and full denominator without fabricating answers.
    mask={r['question_id']:select(r,cards,spec['tools']) for r in inputs}
    arms=['M-S41','M-C41'];rt['arms']={arm:copy.deepcopy(spec) for arm in arms}
    prot.update(experiment_id=a.experiment_id,request_archive='image_base64_content_addressed_v1',main_call_limits={x:6 for x in arms},tool_call_limits={x:4 for x in arms})
    manifest={'schema':'action_r41','mask':mask,'history':history,'inputs_sha256':sha(a.data/'inputs.jsonl'),
              'bank_sha256':sha(a.bank),'historical_sha256':sha(a.historical),'selection_uses_labels':False,'coverage_by_subset':{str(k):{'total':sum(r.get('source',{}).get('subset','unknown')==k for r in inputs),'injected':sum(bool(mask[r['question_id']]['selected_ids']) for r in inputs if r.get('source',{}).get('subset','unknown')==k)} for k in {r.get('source',{}).get('subset','unknown') for r in inputs}}}
    write(a.out/'frozen.json',manifest);write(a.out/'runtime.json',rt);write(a.out/'protocol.json',prot)
    cfg.update(runtime=str((a.out/'runtime.json').resolve()),protocol=str((a.out/'protocol.json').resolve()),action_r41_frozen=str((a.out/'frozen.json').resolve()))
    write(a.out/'config.json',cfg)
    n=sum(bool(x['selected_ids']) for x in mask.values())
    print({'questions':len(ids),'injected':n,'reused_per_arm':len(ids)-n,'max_main_calls_both_arms':12*n,'config':str(a.out/'config.json')})
if __name__=='__main__':main()
