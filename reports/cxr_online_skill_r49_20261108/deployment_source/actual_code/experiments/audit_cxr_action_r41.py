"""Offline completion/reuse audit, never reads reference answers."""
import argparse
from pathlib import Path
from cxr_action_skill_r41 import read

def main():
    p=argparse.ArgumentParser();p.add_argument('--frozen',type=Path,required=True);p.add_argument('--run',type=Path,required=True);a=p.parse_args()
    f=read(a.frozen);changed=0
    for q,item in f['mask'].items():
        result=[read(a.run/'predictions'/arm/(q+'.json')) for arm in ('M-S41','M-C41')]
        if not item['selected_ids']:
            for r in result:
                if r['answer']!=f['history'][q]['answer'] or r['main_calls']!=0 or r['tool_calls']!=0 or not r['reused_historical_M']:raise ValueError('reuse_changed:'+q)
        else:
            for r in result:
                if r['main_calls']>6 or r['tool_calls']>4 or r['reused_historical_M']:raise ValueError('invalid_selected_execution:'+q)
            changed+=result[0]['answer']!=result[1]['answer']
    print({'questions':len(f['mask']),'injected':sum(bool(x['selected_ids']) for x in f['mask'].values()),'selected_answer_disagreements':changed,'reuse_audit':'passed'})
if __name__=='__main__':main()
