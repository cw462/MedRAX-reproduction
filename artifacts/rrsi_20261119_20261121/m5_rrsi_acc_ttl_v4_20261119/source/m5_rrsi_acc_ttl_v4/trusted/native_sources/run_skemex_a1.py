"""One A1 answer per target question with the other source fold frozen; no labels."""
import argparse
from pathlib import Path
import sys
from run_direct_vlm import read,write,now
from skemex_adapter.transport import PaidTransport,Halt,ID
from skemex_adapter.official import components
from skemex_adapter.embedding import LocalEmbeddings
from skemex_adapter.episode import episode


def run(root,fold,key):
    root=Path(root);base=root/'runs'/ID;cfg=read(base/'config.json');source='B' if fold=='A' else 'A'
    freeze=read(base/'evolution'/source/'complete.json')
    if freeze['target_feedback_used']:raise Halt('unfrozen_target_feedback')
    rows=[r for r in read(base/'inputs/rows.json') if read(base/'inputs/folds.json')[r['case_id']]==fold]
    transport=PaidTransport(cfg,key,base);emb=LocalEmbeddings(root,base/'embedding_cache'/('target_'+fold+'.json'))
    runtime=components(base/'evolution'/source/'current',source,emb,transport.factory,read_only=True,model=cfg['model'])
    source_map=freeze['source_trajectory_to_case']
    if cfg.get('tool_agent'):
        from skemex_adapter.tool_episode import RealTools,episode as tool_episode
        tools=RealTools(cfg,base)
        if any(tools.eligible(row) for row in rows):tools.initialize()
    for i,row in enumerate(rows):
        target=base/'predictions'/(row['question_id']+'.json')
        if target.exists():continue
        transport.set_context('t'+fold+'q'+row['question_id'],row)
        if cfg.get('tool_agent'):tool_episode(runtime,transport,row,cfg,target,freeze['window_count'],source_map,tools)
        else:episode(runtime,transport,row,cfg,target,freeze['window_count'],source_map)
        write(base/'progress.json',{'phase':'target_A1','target_fold':fold,'completed_in_fold':i+1,'planned_in_fold':len(rows),'updated_utc':now()})
    emb.flush()


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--target-fold',choices=['A','B'],required=True);a=p.parse_args();run(a.root,a.target_fold,sys.stdin.readline().strip())
