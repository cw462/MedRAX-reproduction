"""Private R49 serial controller; independent from stopped R48 and other GPU jobs."""
import argparse
import json
from pathlib import Path
from deploy_cxr_action_r41 import connect, remote_python, ROOT, PYTHON, TRANSPORT_HOME

LOCAL=Path(__file__).resolve().parents[1]
RUN=ROOT+'/runs/online_skill_r49_20261108'
CODE=ROOT+'/code_cxr_online_skill_r49_20261108'
OLD_CODE=ROOT+'/code_cxr_image_memory_gt_r48_20261108'
PREP=LOCAL/'local_assets/online_skill_r49_preparation'
DATASETS=('chexbench','slake','vqarad')
COUNTS={'chexbench':618,'slake':114,'vqarad':116}
DATA={'chexbench':ROOT+'/code_cxr_vqa_extension/data/chexbench',
      'slake':ROOT+'/code_cxr_action_r41_20261108/data/slake_cxr',
      'vqarad':ROOT+'/code_cxr_action_r41_20261108/data/vqarad_cxr'}
REFS={'chexbench':ROOT+'/runs/image_memory_gt_r47_20261108/reference_vault',
      'slake':ROOT+'/runs/image_memory_gt_r48_20261108/reference_vault/slake',
      'vqarad':ROOT+'/runs/image_memory_gt_r48_20261108/reference_vault/vqarad'}
FILES=['cxr_online_primitives_r49.py','online_memory_r49.py','prepare_feedback_r49.py',
       'run_online_skill_r49.py','skill_services_r49.py','skill_lifecycle_r49.py',
       'skill_evolve_r49.py','skill_prompts_r49.py']
EMBED_BASE='https://dashscope.aliyuncs.com/compatible-mode/v1'
EMBED_MODEL='text-embedding-v4'

def program(ds):
    p=[PYTHON,'-u',CODE+'/experiments/run_online_skill_r49.py',
       '--config',RUN+'/configs/'+ds+'.json','--data',DATA[ds],
       '--reference-dir',REFS[ds],'--out',RUN+'/generation/'+ds,
       '--dataset',ds,'--expect-questions',str(COUNTS[ds]),
       '--embedding-model',EMBED_MODEL,'--embedding-base-url',EMBED_BASE]
    if ds=='chexbench':p+=['--order-manifest',RUN+'/configs/chexbench_order.json']
    return p

CONTROLLER=r'''
from pathlib import Path
import fcntl,json,os,subprocess,sys,time,shutil
r=Path(RUN);jobs=r/'jobs'
lock=(jobs/'.controller.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
ready=json.loads((r/'EXECUTION_REVIEW_READY.json').read_text())
assert ready['verdict']=='ready' and ready['scope_complete'] is True
assert not any((jobs/(ds+'.pid')).exists() for ds in DATASETS)
main_key=sys.stdin.buffer.readline();embedding_key=sys.stdin.buffer.readline().strip().decode()
assert main_key.strip() and embedding_key
def state(v):
 p=jobs/'queue_status.json';t=p.with_suffix('.tmp');t.write_text(json.dumps(v,indent=2)+'\n');t.replace(p)
for ds in DATASETS:
 while True:
  mem=int(subprocess.check_output(['nvidia-smi','--id=1','--query-gpu=memory.used','--format=csv,noheader,nounits'],text=True).strip())
  state({'state':'waiting_gpu1' if mem>=500 else 'starting_dataset','dataset':ds,'gpu1_used_mib':mem,'other_jobs_modified':False})
  if mem<500:break
  time.sleep(60)
 assert shutil.disk_usage(r).free>3*1024**3,'insufficient_free_disk'
 with (jobs/(ds+'.log')).open('xb',buffering=0) as log:
  p=subprocess.Popen(PROGRAMS[ds]+['--execute','--api-key-stdin'],stdin=subprocess.PIPE,stdout=log,stderr=subprocess.STDOUT,
   env=dict(os.environ,R49_EMBEDDING_API_KEY=embedding_key,LANGCHAIN_TRACING_V2='false',LANGSMITH_TRACING='false'))
  (jobs/(ds+'.pid')).write_text(str(p.pid));state({'state':'running_dataset','dataset':ds,'pid':p.pid})
  p.communicate(main_key)
 rc=p.returncode
 (jobs/(ds+'.exitcode')).write_text(str(rc)+'\n')
 out=r/'generation'/ds
 if out.is_dir():(out/'generation.exitcode').write_text(str(rc)+'\n')
 if rc:
  state({'state':'dataset_failed_stop_queue','dataset':ds,'exit_code':rc,'pid':p.pid});raise SystemExit(rc)
 complete=json.loads((out/'complete.json').read_text())
 assert complete['status']=='generation_complete' and complete['questions']==COUNTS[ds]
state({'state':'all_three_datasets_exited_zero','datasets':DATASETS})
'''

def stage(client):
    assert all((LOCAL/'experiments'/name).is_file() for name in FILES)
    shared=PREP/'configs';assert not shared.exists(),'R49_configs_exist_inspect_before_repeating'
    shared.mkdir()
    original=json.loads((LOCAL/'local_assets/image_memory_gt_r48_preparation/shared/config.json').read_text(encoding='utf-8'))
    runtime=json.loads((LOCAL/'local_assets/image_memory_gt_r48_preparation/shared/runtime.json').read_text(encoding='utf-8'))
    assert all(x.get('gpu')=='1' for x in runtime['tools'].values())
    protocol={'experiment_id':'online_skill_r49_20261108','model':'qwen3.7-plus','temperature':.2,'top_p':.95,
       'max_output_tokens':2048,'enable_thinking':False,'main_call_limits':{},'tool_call_limits':{},
       'request_archive':'inline_original_images_semantic_restart_r49',
       'budget':{'existing_shared_ledger':False,'enforce_money_cap':False}}
    for name,value in [('runtime',runtime),('protocol',protocol)]:
        (shared/(name+'.json')).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    for ds in DATASETS:
        cfg={k:original[k] for k in ('model','profile','credential_slot','prompt_variant','temperature','top_p','max_output_tokens','request_timeout_seconds','extra_body')}
        cfg.update(experiment_id='online_skill_r49_'+ds+'_20261108',root=ROOT,protocol=RUN+'/configs/protocol.json',runtime=RUN+'/configs/runtime.json')
        (shared/(ds+'.json')).write_text(json.dumps(cfg,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    remote_python(client,'RUN='+repr(RUN)+'\nCODE='+repr(CODE)+'\nOLD_CODE='+repr(OLD_CODE)+'\n'+r'''
from pathlib import Path
import json,shutil
r=Path(RUN);c=Path(CODE)
assert not r.exists() and not c.exists(),'R49_already_staged'
assert shutil.disk_usage(r.parent).free>3*1024**3
(r/'configs').mkdir(parents=True);(r/'jobs').mkdir();(c/'experiments').mkdir(parents=True);(c/'configs').mkdir()
for p in (Path(OLD_CODE)/'experiments').glob('*.py'):shutil.copyfile(p,c/'experiments'/p.name)
shutil.copyfile(Path(OLD_CODE)/'configs/cxr_vqa_tool_worker_gpu.json',c/'configs/cxr_vqa_tool_worker_gpu.json')
print(json.dumps({'independent_R49_support_created':True,'warm_environment':'same_original_tool_interpreters_and_versions','new_inference_calls':0}))
''',timeout=30)
    driver='\n'.join(k+'='+repr(v) for k,v in dict(RUN=RUN,DATASETS=DATASETS,COUNTS=COUNTS,PROGRAMS={d:program(d) for d in DATASETS}).items())+'\n'+CONTROLLER
    with client.open_sftp() as sftp:
        for name in FILES:sftp.put(str(LOCAL/'experiments'/name),CODE+'/experiments/'+name)
        for p in shared.glob('*.json'):sftp.put(str(p),RUN+'/configs/'+p.name)
        sftp.put(str(PREP/'chexbench_order.json'),RUN+'/configs/chexbench_order.json')
        sftp.put(str(LOCAL/'reports/cxr_online_skill_r49_20261108/PROTOCOL.json'),RUN+'/PROTOCOL.json')
        with sftp.open(RUN+'/queue_controller.py','w') as h:h.write(driver)
    dryrun(client)

def dryrun(client):
    remote_python(client,'PROGRAMS='+repr({d:program(d) for d in DATASETS})+'\nREFS='+repr(REFS)+'\n'+r'''
import subprocess,json
for ds,command in PROGRAMS.items():
 wrapper="import pathlib,runpy,sys,socket\nreference=pathlib.Path(sys.argv[1]).resolve()\nold=pathlib.Path.open\ndef guarded(self,*a,**kw):\n if self.resolve().is_relative_to(reference):raise RuntimeError('dryrun_reference_open_forbidden')\n return old(self,*a,**kw)\npathlib.Path.open=guarded\ndef deny(*a,**kw):raise RuntimeError('dryrun_network_forbidden')\nsocket.socket.connect=deny\nsys.argv=sys.argv[2:]\nsys.path.insert(0,str(pathlib.Path(sys.argv[0]).parent))\nrunpy.run_path(sys.argv[0],run_name='__main__')\n"
 subprocess.run(command[:1]+['-c',wrapper,REFS[ds]]+command[2:],check=True)
print(json.dumps({'three_semantic_dryruns':'passed','new_main_calls':0,'reference_files_read':0,'new_tool_probes':0,'byte_checks':False}))
''',timeout=60)

def queue(client):
    ready=PREP/'EXECUTION_REVIEW_READY.json';assert ready.is_file()
    with client.open_sftp() as s:s.put(str(ready),RUN+'/EXECUTION_REVIEW_READY.json')
    remote_python(client,'RUN='+repr(RUN)+'\nPYTHON='+repr(PYTHON)+'\n'+r'''
from pathlib import Path
import fcntl,json,os,shlex,subprocess,sys
r=Path(RUN);j=r/'jobs';lock=(j/'.queue_launch.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
assert not (j/'controller.pid').exists() and not (j/'controller.started.json').exists()
ready=json.loads((r/'EXECUTION_REVIEW_READY.json').read_text());assert ready['verdict']=='ready' and ready['scope_complete'] is True
key=sys.stdin.buffer.readline()+sys.stdin.buffer.readline();assert len(key.splitlines())==2
rd,wr=os.pipe();os.write(wr,key);os.close(wr)
wrapper=shlex.join([PYTHON,'-u',str(r/'queue_controller.py')])+'; rc=$?; printf "%s\n" "$rc" > '+str(j/'controller.exitcode')+'; exit "$rc"'
try:
 with (j/'controller.log').open('xb',buffering=0) as log:p=subprocess.Popen(['bash','-c',wrapper],stdin=rd,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
 (j/'controller.pid').write_text(str(p.pid));(j/'controller.started.json').write_text(json.dumps({'pid':p.pid,'datasets':['chexbench','slake','vqarad'],'questions':848,'fixed_main_cap':None,'fixed_tool_cap':None,'serial':True,'gpu':'1'}))
 print(json.dumps({'controller_pid':p.pid,'serial_datasets':['chexbench','slake','vqarad'],'questions':848,'fixed_call_caps':None}))
finally:os.close(rd)
''',timeout=30,input_bytes=(TRANSPORT_HOME/'.secrets/token_plan_api.key').read_bytes().strip()+b'\n'+(TRANSPORT_HOME/'.secrets/qwen_api.key').read_bytes().strip()+b'\n')

def status(client):
    remote_python(client,'RUN='+repr(RUN)+'\nDATASETS='+repr(DATASETS)+'\n'+r'''
from pathlib import Path
import json,shutil
r=Path(RUN);j=r/'jobs'
def text(p):return p.read_text().strip() if p.exists() else None
def phase(n):
 pid=text(j/(n+'.pid'));return {'pid':pid,'alive':bool(pid and Path('/proc',pid).exists()),'exit':text(j/(n+'.exitcode'))}
v={'controller':phase('controller'),'queue':json.loads((j/'queue_status.json').read_text()) if (j/'queue_status.json').exists() else None,'datasets':{},'free_bytes':shutil.disk_usage(r).free}
for ds in DATASETS:
 g=r/'generation'/ds;s=g/'services';d=dict(phase(ds),saved=len(list((g/'predictions/M43-IM-GT-S49').glob('*.json'))),contexts=len(list((g/'contexts').glob('*.json'))),prediction_events=len(list((g/'prediction_events').glob('*.json'))),feedback=len(list((g/'feedback').glob('*.json'))),main_sends=len(list((s/'calls/R49-AGENT').glob('*/*/started.json'))),main_responses=len(list((s/'calls/R49-AGENT').glob('*/*/response.json'))),meta_sends=len(list((s/'calls/R49-META').glob('*/*/started.json'))),meta_responses=len(list((s/'calls/R49-META').glob('*/*/response.json'))),embeddings_sent=len(list((s/'embeddings').glob('*/started.json'))),embeddings_received=len(list((s/'embeddings').glob('*/response.json'))),tools=len(list((s/'tool_selections/R49-AGENT').glob('*/*.json'))),windows=len(list((g/'windows').glob('*/repo.json'))),complete=(g/'complete.json').exists())
 if d['exit'] not in (None,'0') and (j/(ds+'.log')).exists():d['failure_tail']=(j/(ds+'.log')).read_text(errors='replace').splitlines()[-16:]
 v['datasets'][ds]=d
print(json.dumps(v))
''',timeout=30)

def pull(client):
    import stat
    dest=Path('D:/MedRAX_Experiment_Artifacts/online_skill_r49_20261108')
    with client.open_sftp() as s:
        for ds in DATASETS:
            with s.open(RUN+'/jobs/'+ds+'.exitcode') as h:assert h.read().decode().strip()=='0'
        dest.mkdir(parents=True,exist_ok=True);ip=dest/'download_inventory.json';inv=json.loads(ip.read_text()) if ip.exists() else {};count=0
        def walk(remote,local,relative):
            nonlocal count
            local.mkdir(parents=True,exist_ok=True)
            for it in s.listdir_attr(remote):
                if it.filename.startswith('.') or it.filename in ['__pycache__','hf_modules']:continue
                src=remote+'/'+it.filename;target=local/it.filename;key=relative+'/'+it.filename
                if stat.S_ISDIR(it.st_mode):walk(src,target,key)
                elif stat.S_ISREG(it.st_mode):
                    mark=[it.st_size,it.st_mtime]
                    if inv.get(key)==mark and target.is_file():continue
                    part=target.with_name(target.name+'.download_part');s.get(src,str(part),prefetch=False);part.replace(target);inv[key]=mark;count+=1
                    if count%50==0:ip.write_text(json.dumps(inv));print(json.dumps({'streamed_files':count}),flush=True)
        try:
            for name in ['generation','jobs','configs']:walk(RUN+'/'+name,dest/name,name)
        finally:ip.write_text(json.dumps(inv,indent=2)+'\n')
    print(json.dumps({'streamed_complete':True,'files':count,'root':str(dest)}))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['stage','dryrun','queue','status','pull']);a=p.parse_args()
    with connect() as c:globals()[a.mode](c)
