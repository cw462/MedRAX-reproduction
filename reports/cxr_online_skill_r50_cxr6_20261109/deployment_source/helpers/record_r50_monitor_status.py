"""Persist one already-observed status response; no monitoring/experiment call."""
import json,re,sys
from datetime import datetime,timezone
from pathlib import Path
root=Path(__file__).resolve().parents[1];status=json.loads(sys.argv[1])
assert status['arm']=='M43-IM-GT-S50-CXR6'
p=root/'.aris/IMPROVEMENT_STATE.json';v=json.loads(p.read_text(encoding='utf-8-sig'))
when=datetime.now(timezone.utc).astimezone().isoformat();v['updated_at']=when
ds=(status.get('queue') or {}).get('dataset') or v['R50'].get('current_dataset','chexbench')
d=status['datasets'][ds]
obs={'recorded_at':when,'automation_id':'medrax-r47','controller_pid':status['controller']['pid'],'runner_pid':d['pid'],
 'controller_alive':status['controller']['alive'],'runner_alive':d['alive'],'dataset':ds,
 **{k:d[k] for k in ('saved','contexts','feedback','main_sends','main_responses','meta_sends','windows','complete')},
 'raw_exit':d['exit'],'free_bytes':status['free_bytes'],'status_transport_native_exit':0,
 'snapshot':status,'new_pulls_scores_reviews_or_probes':0}
v['R50']['last_lightweight_actual_status']=obs
v['R50']['formal_main_sends_observed']=sum(x['main_sends'] for x in status['datasets'].values())
v['R50']['formal_main_responses_observed']=sum(x['main_responses'] for x in status['datasets'].values())
counts=v['R50']['cohort'];brief=' / '.join(f"{name}:{x['saved']}/{counts[name]}" for name,x in status['datasets'].items())
v['next_status_note']=brief
v['next']=re.sub(r'^R50 .*?Lightweight statusonly;',f'R50 last actual {brief}; Lightweight statusonly;',v['next'],count=1)
p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
with (root/'local_assets/r50_cxr6_preparation/monitor_observations.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(obs,ensure_ascii=False)+'\n')
print(json.dumps({'recorded':brief,'no_inference_or_score_or_transfer_action':True}))
