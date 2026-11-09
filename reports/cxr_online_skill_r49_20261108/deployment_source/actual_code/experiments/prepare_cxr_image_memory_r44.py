"""Freeze full618 ordering and M43 provenance. Reads no references or correctness fields."""
import argparse
from pathlib import Path
from cxr_image_memory_r44 import *

def project(r):
    return {k:r[k] for k in ('question_id','answer','reason','status','observations','inherited_observations','technical_failure') if k in r}
def main():
    p=argparse.ArgumentParser()
    for k in ('data','m43','original-m','r41-frozen','config','out'):p.add_argument('--'+k,type=Path,required=True)
    a=p.parse_args();inputs=rows(a.data/'inputs.jsonl');ids=[r['question_id'] for r in inputs]
    if len(inputs)!=618 or len(set(ids))!=618:raise ValueError('full_CheXbench618_required')
    allowed={'question_id','question','images','image_id','source','options'}
    if any(set(r)-allowed for r in inputs):raise ValueError('unexpected_inference_fields')
    best={r['question_id']:r for r in rows(a.m43)};original={r['question_id']:r for r in rows(a.original_m)}
    frozen=read(a.r41_frozen)
    if set(best)!=set(ids) or set(original)!=set(ids) or set(frozen['mask'])!=set(ids):raise ValueError('cohort_mismatch')
    # Use original R41 mask only for reconstructing which policy generated the fixed M43 predecessor.
    plan=schedule(inputs,a.data);policy={q:('C41' if frozen['mask'][q]['selected_ids'] else 'M') for q in ids}
    baseline={}
    for q in ids:
        r=project(best[q]);r['question_id']=q
        # R41's reused rows dropped historical observations; restore exact SAME-question evidence only.
        if policy[q]=='M' and not (r.get('observations') or r.get('inherited_observations')):
            r['inherited_observations']=original[q].get('observations',[])
        baseline[q]=r
    cfg=read(a.config);rt=read(cfg['runtime']);protocol=read(cfg['protocol'])
    for k in ('model','temperature','top_p','enable_thinking','max_output_tokens'):
        if k not in protocol:raise ValueError('missing_protocol:'+k)
    if protocol['enable_thinking']:raise ValueError('M43_used_thinking_false')
    repeats=[x for x in plan if x['previous_ids']]
    repeated_policy={name:sum(policy[x['question_id']]==name for x in repeats) for name in ('M','C41')}
    result={'schema':'M43_same_image_memory_r45_20261108','data':str(a.data.resolve()),'inputs_sha256':sha(a.data/'inputs.jsonl'),
            'order':plan,'policy':policy,'baseline':baseline,'inputs':inputs,'config':cfg,'runtime':rt,'protocol':protocol,
            'source_hashes':{'m43':sha(a.m43),'original_m':sha(a.original_m),'r41_frozen':sha(a.r41_frozen)},
            'memory_max_chars':12000,'memory_max_entries':8,'reference_read':False,
            'repeated_policy_counts':repeated_policy,
            'new_main_ceiling':repeated_policy['M']*4+repeated_policy['C41']*6,
            'new_tool_ceiling':repeated_policy['M']*2+repeated_policy['C41']*4,
            'run_scope':'One sequential memory arm on exposed CheXbench618; no new D-Q or complete no-memory rerun.'}
    write(a.out/'frozen.json',result)
    repeats=sum(bool(x['previous_ids']) for x in plan)
    print({'questions':618,'repeated_image_questions':repeats,'reused_first_or_single':618-repeats,'image_groups':len({x['image_key'] for x in plan}),'prepared':str(a.out/'frozen.json')})
if __name__=='__main__':main()
