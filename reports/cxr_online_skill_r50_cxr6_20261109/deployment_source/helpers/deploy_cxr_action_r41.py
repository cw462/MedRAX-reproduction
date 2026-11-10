"""Private isolated R4.1 transport; credentials only through stdin."""
import argparse,hashlib,json,shlex,tarfile,time
from pathlib import Path
from deploy_v12 import connect,remote_python,ROOT,PYTHON,TRANSPORT_HOME
LOCAL=Path(__file__).resolve().parents[1]
CODE=ROOT+'/code_cxr_action_r41_20261108'
RUN=ROOT+'/runs/action_r41_20261108'
V32=ROOT+'/runs/gain_v32_20261107'
STATE=LOCAL/'local_assets/action_r41_20261108'
DATASETS=['chexbench','slake','vqarad']

def stage(c):
 STATE.mkdir(parents=True,exist_ok=True);archive=STATE/'code.tar.gz'
 with tarfile.open(archive,'w:gz') as tar:
  for p in sorted((LOCAL/'experiments').glob('*.py')):tar.add(p,arcname='experiments/'+p.name)
 remote_python(c,f'''from pathlib import Path
r=Path({RUN!r});code=Path({CODE!r})
if r.exists() and any(r.iterdir()):raise ValueError('new_namespace_required')
r.mkdir(parents=True,exist_ok=True);code.mkdir(parents=True,exist_ok=True)
''')
 with c.open_sftp() as f:f.put(str(archive),CODE+'/code.tar.gz')
 remote_python(c,f'''from pathlib import Path
import tarfile,shutil,json,os
r=Path({RUN!r});code=Path({CODE!r});old=Path({V32!r})
with tarfile.open(code/'code.tar.gz') as tar:
 for m in tar:
  p=Path(m.name)
  if not m.isfile() or p.is_absolute() or '..' in p.parts:raise ValueError('unsafe')
  target=code/p;target.parent.mkdir(parents=True,exist_ok=True)
  with tar.extractfile(m) as a,target.open('xb') as b:shutil.copyfileobj(a,b)
(code/'configs').mkdir(exist_ok=True)
(code/'configs/cxr_vqa_tool_worker_gpu.json').write_text(json.dumps({{'cuda_visible_devices':'0'}}))
(code/'data').mkdir(exist_ok=True)
for ds in ['chexbench','slake_cxr','vqarad_cxr']:(code/'data'/ds).symlink_to(Path({ROOT!r})/'code_cxr_vqa_extension/data'/ds,target_is_directory=True)
shutil.copytree(old/'private_input',r/'private_input',copy_function=os.link)
# Preserve mapping identities/labels while using the new immutable source image aliases.
mapping=json.loads((r/'private_input/image_map.json').read_text())
for images in mapping.values():
 for image in images:image['path']=image['path'].replace(str(old/'private_input'),str(r/'private_input'))
# Hardlinked originals are never edited; replace only this new map inode.
p=r/'private_input/image_map.json';p.unlink();p.write_text(json.dumps(mapping,ensure_ascii=False))
cfg=json.loads((old/'configs/source/config.private.json').read_text())
rt=json.loads(Path(cfg['runtime']).read_text());protocol=json.loads(Path(cfg['protocol']).read_text())
assert protocol['budget']['existing_shared_ledger'] is False and protocol['budget']['enforce_money_cap'] is False
protocol.update(experiment_id='action_r41_source_20261108',main_call_limits={{'M-S':1}})
settings=r/'configs/source';settings.mkdir(parents=True)
for name,value in [('runtime.json',rt),('protocol.json',protocol)]: (settings/name).write_text(json.dumps(value,ensure_ascii=False,indent=2))
cfg.update(runtime=str(settings/'runtime.json'),protocol=str(settings/'protocol.json'))
(settings/'config.private.json').write_text(json.dumps(cfg,ensure_ascii=False,indent=2))
print('R41_STAGED_NO_PAID_CALLS')
''',timeout=60)

def launch(c,name,cmd,paid=False):
 remote_python(c,f'''from pathlib import Path
import sys,os,subprocess,fcntl,json
r=Path({RUN!r});jobs=r/'jobs';jobs.mkdir(exist_ok=True)
lock=(jobs/'.launch.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
prefix=jobs/{name!r}
if Path(str(prefix)+'.pid').exists():raise ValueError('existing_job_marker_no_duplicate')
key=sys.stdin.buffer.readline() if {paid!r} else b''
rd,wr=os.pipe()
if key:os.write(wr,key)
os.close(wr)
wrapper={cmd!r}+'; rc=$?; printf "%s\\n" "$rc" > '+str(prefix)+'.exitcode; exit "$rc"'
try:
 with Path(str(prefix)+'.log').open('ab',buffering=0) as log:
  p=subprocess.Popen(['bash','-c',wrapper],cwd={CODE!r},stdin=rd,stdout=log,stderr=subprocess.STDOUT,start_new_session=True,env=dict(os.environ,LANGCHAIN_TRACING_V2='false',LANGSMITH_TRACING='false'))
 Path(str(prefix)+'.pid').write_text(str(p.pid));print(json.dumps({{'job':{name!r},'pid':p.pid}}))
finally:os.close(rd)
''',input_bytes=(TRANSPORT_HOME/'.secrets/token_plan_api.key').read_bytes().strip()+b'\n' if paid else None)

def source(c,execute):
 source_sha=hashlib.sha256((LOCAL/'local_assets/cxr_vqa_extension_source_learning_inputs.json').read_bytes()).hexdigest()
 args=[PYTHON,'-u',CODE+'/experiments/learn_cxr_source_r41.py','--config',RUN+'/configs/source/config.private.json','--source',RUN+'/private_input/source_learning_inputs.json','--image-map',RUN+'/private_input/image_map.json','--source-sha256',source_sha,'--out',RUN+'/source_learning']
 if execute:launch(c,'source',shlex.join(args+['--execute','--api-key-stdin']),True)
 else:remote_python(c,'import subprocess;subprocess.run('+repr(args)+',check=True)',timeout=60)

def status(c):
 remote_python(c,f'''from pathlib import Path
import json,os,shutil,time
r=Path({RUN!r});jobs={{}}
for p in (r/'jobs').glob('*.pid'):
 pid=p.read_text().strip();exitfile=p.with_suffix('.exitcode');log=p.with_suffix('.log')
 jobs[p.stem]={{'pid':pid,'alive':Path('/proc/'+pid).exists(),'exit_code':exitfile.read_text().strip() if exitfile.exists() else None}}
print(json.dumps({{'jobs':jobs,'source_replies':len(list((r/'source_learning/calls/M-S').glob('*/1/response.json'))),'source_candidates_ready':(r/'source_learning/candidate_bank_r41.json').exists(),'bank_reviewed':(r/'bank_review.json').exists(),'free_bytes':shutil.disk_usage(r).free,'targets':{{ds:{{'saved':{{arm:len(list((r/ds/'predictions'/arm).glob('*.json'))) for arm in ['M-S41','M-C41']}},'complete':{{arm:(r/ds/f'complete_{{arm}}.json').exists() for arm in ['M-S41','M-C41']}},'progress':json.loads((r/ds/'progress.json').read_text()) if (r/ds/'progress.json').exists() else None}} for ds in ['chexbench','slake','vqarad']}}}}))
''')

def prepare(c):
 remote_python(c,f"from pathlib import Path\nr=Path({RUN!r})\nfor ds in ['chexbench','slake','vqarad']:(r/'historical_baselines'/ds).mkdir(parents=True,exist_ok=True)\n")
 with c.open_sftp() as ftp:
  for ds in DATASETS:
   original=LOCAL/('reports/cxr_vqa_extension/results/chexbench' if ds=='chexbench' else 'reports/cxr_vqa_toolsets/results/'+ds)
   for name in ['predictions_M.jsonl','complete_M.json','summary.json']:
    target=RUN+'/historical_baselines/'+ds+'/'+name;raw=(original/name).read_bytes()
    try:
     with ftp.file(target,'rb') as f:assert f.read()==raw
    except FileNotFoundError:ftp.put(str(original/name),target)
 remote_python(c,f'''from pathlib import Path
import json,hashlib,subprocess,sys
r=Path({RUN!r});old=Path({V32!r});code=Path({CODE!r});bank=r/'source_learning/bank_r41.reviewed.json'
review=json.loads((r/'bank_review.json').read_text());assert review['status']=='passed' and review['bank_sha256']==hashlib.sha256(bank.read_bytes()).hexdigest()
sys.path.insert(0,str(code/'experiments'))
from cxr_action_skill_r41 import load,select
for ds in ['chexbench','slake','vqarad']:
 base=r/'configs'/('base_'+ds);base.mkdir(exist_ok=True)
 for name in ['runtime.json','protocol.json']:
  value=json.loads((old/'configs'/('base_'+ds)/name).read_text())
  p=base/name
  if p.exists():assert json.loads(p.read_text())==value
  else:p.write_text(json.dumps(value,ensure_ascii=False,indent=2))
 cfg=json.loads((old/'configs'/('base_'+ds)/'config.private.json').read_text());cfg.update(runtime=str(base/'runtime.json'),protocol=str(base/'protocol.json'))
 p=base/'config.private.json'
 if not p.exists():p.write_text(json.dumps(cfg,ensure_ascii=False,indent=2))
 data=code/'data'/('chexbench' if ds=='chexbench' else ds+'_cxr')
 historical=r/'historical_baselines'/ds/'predictions_M.jsonl'
 assert historical.exists()
 out=r/'configs'/ds
 if not (out/'config.json').exists():
  subprocess.run([{PYTHON!r},str(code/'experiments/prepare_cxr_action_r41.py'),'--base-config',str(p),'--data',str(data),'--bank',str(bank),'--historical',str(historical),'--out',str(out),'--experiment-id','action_r41_'+ds+'_20261108'],check=True)
# Choose first source-only question that the frozen bank covers, without reading target labels.
devdata=r/'dev_input';devdata.mkdir(exist_ok=True)
if not (devdata/'inputs.jsonl').exists():
 runtime=json.loads((r/'configs/base_chexbench/runtime.json').read_text());tools=runtime['arms']['M']['tools'];cards=load(bank,tools)
 for line in (r/'private_input/dev_candidates.jsonl').read_text().splitlines():
  row=json.loads(line);trace=select(row,cards,tools)
  if trace['selected_ids']:break
 else:raise ValueError('No_source_development_injection')
 source=json.loads((r/'private_input/source_learning_inputs.json').read_text());sid=row['question_id'].removeprefix('devsource_')
 trajectory=next(t for case in source['cases'] for t in case['source_trajectories'] if t['source_id']==sid)
 history={{'question_id':row['question_id'],'answer':trajectory['previous_answer'],'reason':'Reused released historical source answer, development only.','status':'completed'}}
 (devdata/'source_images').symlink_to(r/'private_input/source_images',target_is_directory=True)
 (devdata/'inputs.jsonl').write_text(json.dumps(row,ensure_ascii=False)+'\\n')
 (devdata/'history.jsonl').write_text(json.dumps(history,ensure_ascii=False)+'\\n')
 (devdata/'selection.json').write_text(json.dumps({{'question_id':row['question_id'],'selected_ids':trace['selected_ids'],'criterion':'First covered isolated source question; no target references or accuracy-based selection.'}},indent=2))
if not (r/'configs/dev/config.json').exists():
 subprocess.run([{PYTHON!r},str(code/'experiments/prepare_cxr_action_r41.py'),'--base-config',str(r/'configs/base_chexbench/config.private.json'),'--data',str(devdata),'--bank',str(bank),'--historical',str(devdata/'history.jsonl'),'--out',str(r/'configs/dev'),'--experiment-id','action_r41_dev_20261108'],check=True)
print('R41_FROZEN_CONFIGS_READY')
''',timeout=60)

def launch_pair(c,ds,job_name=None):
 data=RUN+'/dev_input' if ds=='dev' else CODE+'/data/'+('chexbench' if ds=='chexbench' else ds+'_cxr')
 args=[PYTHON,'-u',CODE+'/experiments/run_cxr_action_r41.py','--config',RUN+'/configs/'+ds+'/config.json','--data',data,'--out',RUN+'/'+ds,'--arms','M-S41','M-C41','--execute','--api-key-stdin']
 launch(c,job_name or ds,shlex.join(args),True)

def snapshot(c):
 code=f'''from pathlib import Path
import json
r=Path({RUN!r});jobs={{}}
for p in (r/'jobs').glob('*.pid'):
 pid=p.read_text().strip();exitfile=p.with_suffix('.exitcode')
 jobs[p.stem]={{'alive':Path('/proc/'+pid).exists(),'exit':exitfile.read_text().strip() if exitfile.exists() else None}}
if 'dev_recovery_1' in jobs:
 jobs['dev_initial']=jobs.get('dev');jobs['dev']=jobs['dev_recovery_1']
print(json.dumps({{'jobs':jobs,'reviewed':(r/'bank_review.json').exists(),'dev_verified':(r/'dev_verified.json').exists(),'complete':{{ds:all((r/ds/('complete_'+a+'.json')).exists() for a in ['M-S41','M-C41']) for ds in ['dev','chexbench','slake','vqarad']}}}}))
'''
 _,stdout,stderr=c.exec_command(shlex.quote(PYTHON)+' -c '+shlex.quote(code));raw=stdout.read();err=stderr.read();rc=stdout.channel.recv_exit_status()
 if rc:raise RuntimeError(err.decode()[:1000])
 return json.loads(raw)

def verify_dev(c):
 remote_python(c,f'''from pathlib import Path
import json
r=Path({RUN!r});run=r/'dev';exitfile=r/'jobs/dev_recovery_1.exitcode' if (r/'jobs/dev_recovery_1.pid').exists() else r/'jobs/dev.exitcode';assert exitfile.read_text().strip()=='0'
frozen=json.loads((r/'configs/dev/frozen.json').read_text());assert len(frozen['mask'])==1
qid,item=next(iter(frozen['mask'].items()));assert item['selected_ids']
statuses={{}}
for arm in ['M-S41','M-C41']:
 assert (run/('complete_'+arm+'.json')).exists()
 pred=json.loads((run/'predictions'/arm/(qid+'.json')).read_text());statuses[arm]=pred['status']
 assert 1<=pred['main_calls']<=6 and pred['tool_calls']<=4
 assert all(v.get('status')=='completed' and v.get('observation') is not None for v in pred.get('observations',[]))
 assert all((p.parent/'response.json').exists() for p in (run/'calls'/arm/qid).glob('*/started.json'))
 requests=[json.loads(p.read_text()) for p in (run/'calls'/arm/qid).glob('*/request.json')]
 contains=any(item['conditioning'] in [m.get('content') for m in req['messages'] if isinstance(m.get('content'),str)] for req in requests)
 assert contains==(arm=='M-S41')
proof={{'status':'passed','source_question_id':qid,'selected_ids':item['selected_ids'],'M_S41_actual_request_contains_skill':True,'M_C41_actual_requests_contain_no_skill':True,'target_reference_answers_read':False,'prediction_statuses':statuses,'scope':'Request injection and healthy process integration only, not correctness, format success or temporal-binding validation. Source development images retain explicit original index but source Figure labels are not mapped into the old runner prompt; do not infer development clinical validity.','format_failure_preserved_no_rerun':True}}
p=r/'dev_verified.json'
if not p.exists():p.write_text(json.dumps(proof,indent=2))
print(json.dumps(proof))
''')

def queue():
 last=None
 while True:
  try:
   with connect() as c:
    state=snapshot(c)
    if state!=last:print(json.dumps(state),flush=True);last=state
    if state['reviewed']:
     if 'dev' not in state['jobs']:prepare(c);launch_pair(c,'dev')
     elif state['complete']['dev'] and not state['jobs']['dev']['alive']:
      if state['jobs']['dev']['exit']!='0':raise RuntimeError('Development_nonzero_exit')
      if not state['dev_verified']:verify_dev(c)
      for ds in DATASETS:
       job=state['jobs'].get(ds)
       if job is None:launch_pair(c,ds);break
       if not state['complete'][ds] or job['alive']:break
       if job['exit']!='0':raise RuntimeError('Completed_pair_nonzero_exit')
      else:print('ALL_R41_PAIRS_GENERATED',flush=True);return
  except Exception as exc:print('QUEUE_DIAGNOSTIC '+type(exc).__name__+': '+str(exc)[:500],flush=True)
  time.sleep(60)

def main():
 p=argparse.ArgumentParser();p.add_argument('mode',choices=['stage','source-check','source-launch','status','prepare','queue']);a=p.parse_args()
 if a.mode=='queue':queue();return
 with connect() as c:
  if a.mode=='stage':stage(c)
  elif a.mode.startswith('source'):source(c,a.mode=='source-launch')
  elif a.mode=='prepare':prepare(c)
  else:status(c)
if __name__=='__main__':main()
