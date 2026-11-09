"""One reviewed post-commit dependency repair; no R49 policy/output rewriting."""
import argparse
import json
from pathlib import Path

from deploy_cxr_online_skill_r49 import (
    CODE, COUNTS, DATASETS, PREP, PYTHON, RUN, TRANSPORT_HOME, connect, program, remote_python,
)

REPAIR = 'dependency_1'
QID = 'chexbench_rad_restruct_0123'
REVIEW = PREP / 'DEPENDENCY_REPAIR_REVIEW_READY.json'


GUARD = r'''
from pathlib import Path
import json
r=Path(RUN);j=r/'jobs';g=r/'generation/chexbench'
def read(p):return json.loads(p.read_text())
def members(folder):return {p.stem for p in folder.glob('*.json')}
for name in ('controller','chexbench'):
 pid=(j/(name+'.pid')).read_text().strip()
 assert pid and not Path('/proc',pid).exists(), 'original_process_still_active'
 assert (j/(name+'.exitcode')).read_text().strip()=='1', 'unexpected_original_exit'
assert (g/'generation.exitcode').read_text().strip()=='1', 'original_generation_exit_required'
tail=(j/'chexbench.log').read_text(errors='replace').rstrip().splitlines()
assert tail[-1]=="ModuleNotFoundError: No module named 'cxr_author_alignment'", 'different_failure_requires_new_diagnosis'
assert sum(line==tail[-1] for line in tail)==1, 'nonunique_dependency_failure'
assert not (g/'complete.json').exists()
for directory in (g/'predictions/M43-IM-GT-S49',g/'contexts',g/'steps',g/'prediction_events',g/'feedback'):
 assert members(directory)=={QID}, 'unexpected_committed_prefix:'+str(directory)
pred=read(g/'predictions/M43-IM-GT-S49'/(QID+'.json'))
event=read(g/'prediction_events'/(QID+'.json'));feedback=read(g/'feedback'/(QID+'.json'))
assert pred['question_id']==QID and pred['ordinal']==1
assert pred['main_calls']==3 and pred['tool_calls']==2
assert event['saved_prediction']==pred and feedback['saved_prediction']==pred, 'changed_postcommit_record'
assert event['question_id']==QID and feedback['question_id']==QID
s=g/'services';starts=list((s/'calls/R49-AGENT').glob('*/*/started.json'))
responses=list((s/'calls/R49-AGENT').glob('*/*/response.json'))
assert len(starts)==len(responses)==3
assert {p.parent.name for p in starts}=={'1','2','3'} and all(p.parent.parent.name==QID for p in starts)
for p in starts:
 assert (p.parent/'response.json').is_file() and (p.parent/'result.json').is_file()
 receipt=read(p.parent/'result.json')
 assert receipt.get('response_received') is True and receipt.get('error') is None
assert not list((s/'calls/R49-META').glob('*/*/started.json'))
assert not list((s/'embeddings').glob('*/started.json'))
assert not list((g/'windows').glob('*/repo.json'))
selections=list((s/'tool_selections/R49-AGENT').glob('*/*.json'))
assert len(selections)==2 and all(p.parent.name==QID for p in selections)
import sys
sys.path.insert(0,str(Path(CODE)/'experiments'))
from cxr_image_memory_r44 import tool_failure_reason
assert all(tool_failure_reason(read(p)) is None for p in selections), 'actual_tool_failure_not_dependency_repair'
for ds in ('slake','vqarad'):
 assert not (j/(ds+'.pid')).exists(), 'subsequent_dataset_already_started'
 other=r/'generation'/ds
 assert not other.exists() or not any(other.rglob('*.json')), 'subsequent_dataset_has_records'
assert (Path(CODE)/'experiments/cxr_author_alignment.py').is_file(), 'missing_dependency_not_repaired'
'''


CONTROLLER = r'''
from pathlib import Path
import fcntl,json,os,subprocess,sys,time,shutil
r=Path(RUN);j=r/'jobs';a=r/'recovery'/REPAIR
lock=(j/'.controller.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
ready=json.loads((a/'REVIEW_READY.json').read_text())
assert ready['verdict']=='ready' and ready['scope_complete'] is True
assert (a/'original/chexbench.exitcode').read_text().strip()=='1'
main_key=sys.stdin.buffer.readline();embedding_key=sys.stdin.buffer.readline().strip().decode()
assert main_key.strip() and embedding_key
def state(value):
 value.update(recovery=REPAIR,initial_controller_exit=1,initial_chexbench_exit=1)
 p=j/'queue_status.json';tmp=p.with_suffix('.tmp');tmp.write_text(json.dumps(value,indent=2)+'\n');tmp.replace(p)
for ds in DATASETS:
 while True:
  mem=int(subprocess.check_output(['nvidia-smi','--id=1','--query-gpu=memory.used','--format=csv,noheader,nounits'],text=True).strip())
  state({'state':'waiting_gpu1' if mem>=500 else 'starting_dataset','dataset':ds,'gpu1_used_mib':mem,'other_jobs_modified':False})
  if mem<500:break
  time.sleep(60)
 assert shutil.disk_usage(r).free>3*1024**3, 'insufficient_free_disk'
 logfile=j/(ds+'.'+REPAIR+'.log')
 with logfile.open('xb',buffering=0) as log:
  p=subprocess.Popen(PROGRAMS[ds]+['--execute','--api-key-stdin'],stdin=subprocess.PIPE,stdout=log,stderr=subprocess.STDOUT,
   env=dict(os.environ,R49_EMBEDDING_API_KEY=embedding_key,LANGCHAIN_TRACING_V2='false',LANGSMITH_TRACING='false'))
  (a/(ds+'.pid')).write_text(str(p.pid));(j/(ds+'.pid')).write_text(str(p.pid))
  state({'state':'running_dataset','dataset':ds,'pid':p.pid,'current_attempt_exit':None,'log':str(logfile)})
  p.communicate(main_key)
 rc=p.returncode
 (a/(ds+'.exitcode')).write_text(str(rc)+'\n')
 (j/(ds+'.exitcode')).write_text(str(rc)+'\n')
 out=r/'generation'/ds
 if out.is_dir():(out/'generation.exitcode').write_text(str(rc)+'\n')
 if rc:
  state({'state':'dataset_failed_stop_queue','dataset':ds,'exit_code':rc,'pid':p.pid,'log':str(logfile)})
  raise SystemExit(rc)
 complete=json.loads((out/'complete.json').read_text())
 assert complete['status']=='generation_complete' and complete['questions']==COUNTS[ds]
state({'state':'all_three_datasets_exited_zero_after_known_dependency_repair','datasets':DATASETS})
'''


def definitions():
    return '\n'.join(key+'='+repr(value) for key,value in dict(
        RUN=RUN,CODE=CODE,PYTHON=PYTHON,REPAIR=REPAIR,QID=QID,DATASETS=DATASETS,COUNTS=COUNTS,
        PROGRAMS={ds:program(ds) for ds in DATASETS}).items())+'\n'


def stage(client):
    ready=json.loads(REVIEW.read_text(encoding='utf-8'))
    assert ready['verdict']=='ready' and ready['scope_complete'] is True
    remote_python(client,definitions()+GUARD+r'''
import shutil
a=r/'recovery'/REPAIR
assert not (a/'controller.py').exists() and not (a/'original').exists(), 'repair_already_staged_check_state'
(a/'original').mkdir(parents=True)
for name in ('controller.pid','controller.started.json','controller.exitcode','controller.log',
             'chexbench.pid','chexbench.exitcode','chexbench.log','queue_status.json'):
 source=j/name
 assert source.is_file(), 'missing_original_job_record:'+name
 shutil.copyfile(source,a/'original'/name)
shutil.copyfile(g/'generation.exitcode',a/'original/generation.exitcode')
shutil.copyfile(g/'manifest.json',a/'original/manifest.json')
summary={'repair':'missing_deployed_cxr_author_alignment_only','original_controller_exit':1,
 'original_chexbench_exit':1,'committed_question_id':QID,'committed_predictions':1,
 'closed_main_requests':3,'healthy_tool_selections':2,'released_feedback_events':1,
 'prediction_rewrites':0,'new_reference_reads_for_repair':0,'runtime_policy_changed':False,
 'unknown_requests_reissued':False,'automatic_failure_nulls':False}
(a/'diagnosis.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary))
''',timeout=30)
    with client.open_sftp() as sftp:
        sftp.put(str(REVIEW),RUN+'/recovery/'+REPAIR+'/REVIEW_READY.json')
        with sftp.open(RUN+'/recovery/'+REPAIR+'/controller.py','w') as handle:
            handle.write(definitions()+CONTROLLER)


def launch(client):
    remote_python(client,definitions()+GUARD+r'''
import fcntl,os,shlex,subprocess,sys
a=r/'recovery'/REPAIR
lock=(j/'.queue_launch.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
assert not (a/'controller.started.json').exists(), 'repair_launch_already_claimed'
ready=read(a/'REVIEW_READY.json');assert ready['verdict']=='ready' and ready['scope_complete'] is True
assert (a/'original/controller.exitcode').read_text().strip()=='1'
assert (a/'original/generation.exitcode').read_text().strip()=='1'
key=sys.stdin.buffer.readline()+sys.stdin.buffer.readline();assert len(key.splitlines())==2
rd,wr=os.pipe();os.write(wr,key);os.close(wr)
controller=a/'controller.py'
wrapper=shlex.join([PYTHON,'-u',str(controller)])+'; rc=$?; printf "%s\n" "$rc" > '+str(a/'controller.exitcode')+'; printf "%s\n" "$rc" > '+str(j/'controller.exitcode')+'; exit "$rc"'
try:
 with (a/'controller.log').open('xb',buffering=0) as log:
  p=subprocess.Popen(['bash','-c',wrapper],stdin=rd,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
 record={'pid':p.pid,'recovery':REPAIR,'serial_datasets':list(DATASETS),'initial_exit':1,
  'resume_existing_committed_prefix':True,'runtime_changed':False,'automatic_retry':False}
 (a/'controller.pid').write_text(str(p.pid))
 (a/'controller.started.json').write_text(json.dumps(record,indent=2)+'\n')
 (j/'controller.pid').write_text(str(p.pid))
 print(json.dumps(record))
finally:os.close(rd)
''',timeout=30,
        input_bytes=(TRANSPORT_HOME/'.secrets/token_plan_api.key').read_bytes().strip()+b'\n'
        +(TRANSPORT_HOME/'.secrets/qwen_api.key').read_bytes().strip()+b'\n')


def status(client):
    remote_python(client,definitions()+r'''
from pathlib import Path
import json,shutil
r=Path(RUN);j=r/'jobs';a=r/'recovery'/REPAIR
def text(path):return path.read_text().strip() if path.is_file() else None
def phase(name):
 pid=text(a/(name+'.pid'))
 return {'pid':pid,'alive':bool(pid and Path('/proc',pid).exists()),'exit':text(a/(name+'.exitcode'))}
def initial_exit(name):
 value=text(a/'original'/(name+'.exitcode'))
 return value if value is not None else text(a/'jobs'/(name+'.exitcode'))
value={'recovery':REPAIR,'controller':phase('controller'),
 'initial_attempt':{'controller_exit':initial_exit('controller'),'chexbench_exit':initial_exit('chexbench'),
                    'generation_exit':text(a/'original/generation.exitcode') or text(a/'generation/chexbench/generation.exitcode')},
 'queue':json.loads((j/'queue_status.json').read_text()) if (j/'queue_status.json').is_file() else None,
 'datasets':{},'free_bytes':shutil.disk_usage(r).free}
for ds in DATASETS:
 g=r/'generation'/ds;s=g/'services'
 item=dict(phase(ds),saved=len(list((g/'predictions/M43-IM-GT-S49').glob('*.json'))),
  contexts=len(list((g/'contexts').glob('*.json'))),prediction_events=len(list((g/'prediction_events').glob('*.json'))),
  feedback=len(list((g/'feedback').glob('*.json'))),main_sends=len(list((s/'calls/R49-AGENT').glob('*/*/started.json'))),
  main_responses=len(list((s/'calls/R49-AGENT').glob('*/*/response.json'))),
  meta_sends=len(list((s/'calls/R49-META').glob('*/*/started.json'))),
  meta_responses=len(list((s/'calls/R49-META').glob('*/*/response.json'))),
  embeddings_sent=len(list((s/'embeddings').glob('*/started.json'))),
  embeddings_received=len(list((s/'embeddings').glob('*/response.json'))),
  tools=len(list((s/'tool_selections/R49-AGENT').glob('*/*.json'))),
  windows=len(list((g/'windows').glob('*/repo.json'))),complete=(g/'complete.json').exists())
 logfile=j/(ds+'.'+REPAIR+'.log')
 item['current_attempt_log']=str(logfile) if logfile.is_file() else None
 if item['exit'] not in (None,'0') and logfile.is_file():
  item['failure_tail']=logfile.read_text(errors='replace').splitlines()[-16:]
 value['datasets'][ds]=item
if value['controller']['exit'] not in (None,'0') and (a/'controller.log').is_file():
 value['controller_failure_tail']=(a/'controller.log').read_text(errors='replace').splitlines()[-16:]
print(json.dumps(value))
''',timeout=30)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=('stage','launch','status'))
    args=parser.parse_args()
    with connect() as client:globals()[args.mode](client)
