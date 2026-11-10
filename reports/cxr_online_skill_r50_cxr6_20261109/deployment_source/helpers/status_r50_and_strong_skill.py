"""One lightweight actual snapshot of the two authorized queues, no transfers."""
import contextlib
import io
import json
import subprocess
import sys
from datetime import datetime,timezone
from pathlib import Path
from deploy_cxr6_r50 import connect,remote_python,script,status as r50_status,RUN as R50_RUN
RUN='/home/imss/cw/MedRAX_reproduction_20261027/runs/strong_skill_qwen38max_20261110'
PREP=Path(__file__).resolve().parents[1]/'local_assets/strong_model_skill_comparison_20261110'


def main():
    root=Path(__file__).resolve().parents[1]
    current=json.loads((root/'.aris/IMPROVEMENT_STATE.json').read_text(encoding='utf-8'))
    selected=current['strong_model_skill_comparison_20261110'].get('active_comparison',{})
    actual_run=selected.get('run',RUN) if selected.get('staged') else RUN
    actual_prep=root/selected['preparation'] if selected.get('staged') else PREP
    arms={'direct':selected.get('direct_arm','M-STRONG-DIRECT'),
          'skill':selected.get('skill_arm','M-STRONG-IM-GT-SKILL')} if selected.get('staged') else {'direct':'M-STRONG-DIRECT','skill':'M-STRONG-IM-GT-SKILL'}
    seen=current['R50'].get('observed_failure_delivery_ids',{'chexbench':['chexbench_openi_0078/1'],'slake':[],'vqarad':[]})
    strong_seen=current['strong_model_skill_comparison_20261110'].get('observed_failure_delivery_ids',{})
    first=io.StringIO();second=io.StringIO()
    with connect() as client:
        with contextlib.redirect_stdout(first):r50_status(client)
        source=script(r'''
from pathlib import Path
import json
r=Path(RUN);j=r/'jobs'
def phase(name):
 p=j/(name+'.pid');e=j/(name+'.exitcode');pid=p.read_text().strip() if p.is_file() else None
 return {'pid':pid,'alive':bool(pid and Path('/proc',pid).exists()),'exit':e.read_text().strip() if e.is_file() else None}
v={'controller':phase('controller'),'queue':json.loads((j/'queue_status.json').read_text()) if (j/'queue_status.json').is_file() else None,'datasets':{}}
def delivered(root,known):
 paths={str(p.relative_to(root).with_suffix('')).replace('\\','/'):p for p in root.glob('*/*.json')}
 fresh=[];pending=[]
 for identity in sorted(set(paths)-set(known)):
  try:value=json.loads(paths[identity].read_text())
  except (FileNotFoundError,json.JSONDecodeError):pending.append(identity);continue
  raw=value.get('raw_selection',{})
  fresh.append({'delivery_id':identity,'question_id':value.get('question_id'),'question_ordinal':value.get('question_ordinal'),
    'selection_ordinal':value.get('selection_ordinal'),'tool':raw.get('tool'),'cache_key':value.get('cache_key'),
    'failure_reason':value.get('delivered_observation',{}).get('failure_observation',{}).get('failure_reason'),
    'status':raw.get('status'),'error_type':raw.get('error_type'),'error':str(raw.get('error',''))[:600],
    'backend_regenerated':value.get('backend_regenerated'),'output_repaired':value.get('output_repaired')})
 return {'ids':sorted(set(paths)-set(pending)),'new':fresh,'pending_receipt_flush':pending}
v['R50_tool_failure_deliveries']={ds:delivered(Path(R50_RUN)/'generation'/ds/'failure_observations',SEEN.get(ds,[])) for ds in ('chexbench','slake','vqarad')}
if (j/'USER_MODEL_SELECTION_HOLD.json').is_file():
 v['intentional_user_model_selection_hold']=json.loads((j/'USER_MODEL_SELECTION_HOLD.json').read_text())
 v['reconciled_state']='held_before_inference_for_DeepSeek_input_choice'
if (j/'USER_SKILL_PROTOCOL_HOLD.json').is_file():
 v['intentional_user_skill_protocol_hold']=json.loads((j/'USER_SKILL_PROTOCOL_HOLD.json').read_text())
 v['reconciled_state']='held_before_inference_for_Skill_method_decision'
for ds in ('chexbench','slake','vqarad'):
 v['datasets'][ds]={}
 for mode,arm in ARMS.items():
  g=r/'generation'/mode/ds
  item=dict(phase(ds+'_'+mode),saved=len(list((g/'predictions'/arm).glob('*.json'))),
    main_sends=len(list((g/'services/calls').glob('*/*/*/started.json'))),
    main_responses=len(list((g/'services/calls').glob('*/*/*/response.json'))),complete=(g/'complete.json').is_file())
  if mode=='skill':item['tool_failure_deliveries']=delivered(g/'failure_observations',STRONG_SEEN.get(ds,[]))
  if item['exit'] not in (None,'0') and (j/(ds+'_'+mode+'.log')).is_file():item['failure_tail']=(j/(ds+'_'+mode+'.log')).read_text(errors='replace').splitlines()[-18:]
  v['datasets'][ds][mode]=item
if v['controller']['exit'] not in (None,'0') and not any(name in v for name in ('intentional_user_model_selection_hold','intentional_user_skill_protocol_hold')):v['controller_failure_tail']=(j/'controller.log').read_text(errors='replace').splitlines()[-18:]
print(json.dumps(v))
''',RUN=actual_run,ARMS=arms,R50_RUN=R50_RUN,SEEN=seen,STRONG_SEEN=strong_seen)
        with contextlib.redirect_stdout(second):remote_python(client,source,timeout=30)
    original=json.loads(first.getvalue());strong=json.loads(second.getvalue())
    deliveries=strong.pop('R50_tool_failure_deliveries')
    for ds,value in deliveries.items():original['datasets'][ds]['tool_failure_deliveries']=value
    subprocess.run([sys.executable,'-X','utf8',str(root/'local_assets/record_r50_monitor_status.py'),json.dumps(original)],check=True,capture_output=True)
    p=root/'.aris/IMPROVEMENT_STATE.json';state=json.loads(p.read_text(encoding='utf-8'));record={'recorded_at':datetime.now(timezone.utc).isoformat(),'actual_status_native_exit':0,'snapshot':strong,'new_model_or_transfer_calls':0}
    state['strong_model_skill_comparison_20261110']['last_actual_status']=record
    state['strong_model_skill_comparison_20261110']['new_inference_started']=any(v['main_sends'] for modes in strong['datasets'].values() for v in modes.values())
    state['R50']['observed_failure_delivery_ids']={ds:v['ids'] for ds,v in deliveries.items()}
    state['R50'].setdefault('new_terminal_tool_failure_notifications',[]).extend(dict(v,dataset=ds,notice_status='pending') for ds,item in deliveries.items() for v in item['new'])
    state['strong_model_skill_comparison_20261110']['observed_failure_delivery_ids']={ds:modes['skill']['tool_failure_deliveries']['ids'] for ds,modes in strong['datasets'].items()}
    state['strong_model_skill_comparison_20261110'].setdefault('new_terminal_tool_failure_notifications',[]).extend(dict(v,dataset=ds,notice_status='pending') for ds,modes in strong['datasets'].items() for v in modes['skill']['tool_failure_deliveries']['new'])
    p.write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    with (actual_prep/'status_observations.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(record,ensure_ascii=False)+'\n')
    print(json.dumps({'R50':original,'strong_model_comparison':strong}))


if __name__=='__main__':main()
