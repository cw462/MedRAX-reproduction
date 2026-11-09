RUN='[REDACTED]'
CODE='[REDACTED]'
PYTHON='[REDACTED]'
REPAIR='dependency_1'
QID='chexbench_rad_restruct_0123'
DATASETS=('chexbench', 'slake', 'vqarad')
COUNTS={'chexbench': 618, 'slake': 114, 'vqarad': 116}
PROGRAMS={'chexbench': ['[REDACTED]', '-u', '[REDACTED]', '--config', '[REDACTED]', '--data', '[REDACTED]', '--reference-dir', '[REDACTED]', '--out', '[REDACTED]', '--dataset', 'chexbench', '--expect-questions', '618', '--embedding-model', 'text-embedding-v4', '--embedding-base-url', 'https://dashscope.aliyuncs.com/compatible-mode/v1', '--order-manifest', '[REDACTED]'], 'slake': ['[REDACTED]', '-u', '[REDACTED]', '--config', '[REDACTED]', '--data', '[REDACTED]', '--reference-dir', '[REDACTED]', '--out', '[REDACTED]', '--dataset', 'slake', '--expect-questions', '114', '--embedding-model', 'text-embedding-v4', '--embedding-base-url', 'https://dashscope.aliyuncs.com/compatible-mode/v1'], 'vqarad': ['[REDACTED]', '-u', '[REDACTED]', '--config', '[REDACTED]', '--data', '[REDACTED]', '--reference-dir', '[REDACTED]', '--out', '[REDACTED]', '--dataset', 'vqarad', '--expect-questions', '116', '--embedding-model', 'text-embedding-v4', '--embedding-base-url', 'https://dashscope.aliyuncs.com/compatible-mode/v1']}

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
