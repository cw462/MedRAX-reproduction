"""User-requested intermediate card/usage inventory; no scoring or model calls."""
import contextlib
import io
import json
from datetime import datetime, timezone
from pathlib import Path
from deploy_cxr6_r50 import connect, remote_python, script, RUN, ARM, LOCAL

PREP = LOCAL / 'local_assets/r50_cxr6_preparation'


def main():
    with (PREP / 'intermediate_skill_inventory.started.json').open('x', encoding='utf-8') as f:
        json.dump({'utc': datetime.now(timezone.utc).isoformat(),
                   'user_request': '目前看一下中间状态，这个skill有建好之类的吗？没建好感觉跑的希望也不大了',
                   'scope': 'Read current completed window card metadata and saved injection/adoption records only; no accuracy/GT scoring.'}, f, ensure_ascii=False, indent=2)
    source = script(r'''
from pathlib import Path
from collections import Counter
import json
r=Path(RUN);result={}
for ds in ('chexbench','slake','vqarad'):
 g=r/'generation'/ds
 repos=sorted((g/'windows').glob('*/repo.json'))
 repo=json.loads(repos[-1].read_text()) if repos else {'skills':{},'window':0}
 skills=repo['skills'];statuses=Counter(v['status'] for v in skills.values());branches=Counter(v['c']['branch'] for v in skills.values())
 windows=[];operations=Counter();rejections=0;adoptions=Counter();credits=0
 for p in repos:
  e=json.loads((p.parent/'events.json').read_text())
  writes=Counter(v['operation'] for v in e['write'] if v.get('operation'))
  rejected=sum('rejected' in v for v in e['write']);operations.update(writes);rejections+=rejected
  adoptions.update(v['status'] for v in e['credit']);credits+=len(e['credit'])
  snapshot=json.loads(p.read_text());windows.append({'window':int(p.parent.name)+1,'accepted_operations':dict(writes),'rejections':rejected,
   'active_after_window':sum(v['status'] in ('active','mature') for v in snapshot['skills'].values())})
 predictions=[]
 for p in (g/'predictions'/ARM).glob('*.json'):
  v=json.loads(p.read_text());predictions.append({'ordinal':v['ordinal'],'injected':v.get('selected_skill_ids',[]),'same_image_hit':bool(v.get('same_image_ids'))})
 use=Counter(sid for v in predictions for sid in v['injected'])
 used=[v['ordinal'] for v in predictions if v['injected']]
 item={'saved_predictions':len(predictions),'completed_learning_windows':len(repos),'latest_repo_window':repo.get('window'),
  'total_cards_in_repo':len(skills),'card_statuses':dict(statuses),'card_branches':dict(branches),
  'active_or_mature_cards':sum(statuses[k] for k in ('active','mature')),
  'questions_with_skill_injection':len(used),'skill_injection_slots':sum(use.values()),
  'distinct_injected_skill_ids':len(use),'first_injected_question_ordinal':min(used) if used else None,
  'same_image_hit_questions':sum(v['same_image_hit'] for v in predictions),
  'accepted_operations':dict(operations),'rejected_candidate_writes':rejections,
  'provisional_same_model_attributions':dict(adoptions),'credit_events':credits,'windows':windows,
  'card_examples':[{'id':sid,'name':v['c']['name'],'branch':v['c']['branch'],'status':v['status'],
    'source_count':len(v['source_ids']),'recorded_usage':v.get('usage'),'injection_slots':use.get(sid,0)}
    for sid,v in sorted(skills.items(),key=lambda kv:(-use.get(kv[0],0),kv[0]))[:8]],
  'accuracy_or_score_computed':False,'current_question_GT_opened':False,'new_model_calls':0}
 result[ds]=item
print(json.dumps(result,ensure_ascii=False))
''', RUN=RUN, ARM=ARM)
    output = io.StringIO()
    try:
        with connect() as client, contextlib.redirect_stdout(output):
            remote_python(client, source, timeout=30)
        value = json.loads(output.getvalue())
    except Exception as error:
        with (PREP / 'intermediate_skill_inventory.failure.json').open('x', encoding='utf-8') as f:
            json.dump({'utc': datetime.now(timezone.utc).isoformat(), 'error': repr(error),
                       'automatic_retry': False, 'native_stderr': 'original exec transcript'}, f, indent=2)
        print(output.getvalue())
        raise
    record = {'utc': datetime.now(timezone.utc).isoformat(), 'user_requested_partial_status': True,
              'native_exit': 0, 'datasets': value, 'private_accuracy_score_computed': False,
              'model_or_tool_calls': 0, 'producer_or_completed_predictions_modified': False}
    with (PREP / 'intermediate_skill_inventory.completed.json').open('x', encoding='utf-8') as f:
        json.dump(record, f, ensure_ascii=False, indent=2)
    statepath = LOCAL / '.aris/IMPROVEMENT_STATE.json'
    state = json.loads(statepath.read_text(encoding='utf-8'))
    state['R50']['user_requested_intermediate_skill_inventory'] = record
    statepath.write_text(json.dumps(state, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(record, ensure_ascii=False))


if __name__ == '__main__':
    main()
