RUN='/home/imss/cw/MedRAX_reproduction_20261027/runs/online_skill_r50_cxr6_20261109'
ARM='M43-IM-GT-S50-CXR6'
DATASETS=('chexbench', 'slake', 'vqarad')
COUNTS={'chexbench': 618, 'slake': 114, 'vqarad': 116}
PROGRAMS={'chexbench': ['/home/imss/cw/MedRAX_reproduction_20261027/.venv/bin/python', '-u', '/home/imss/cw/MedRAX_reproduction_20261027/code_cxr_online_skill_r50_cxr6_20261109/experiments/run_online_skill_r50.py', '--config', '/home/imss/cw/MedRAX_reproduction_20261027/runs/online_skill_r50_cxr6_20261109/configs/chexbench.json', '--data', '/home/imss/cw/MedRAX_reproduction_20261027/code_cxr_vqa_extension/data/chexbench', '--reference-dir', '/home/imss/cw/MedRAX_reproduction_20261027/runs/image_memory_gt_r47_20261108/reference_vault', '--out', '/home/imss/cw/MedRAX_reproduction_20261027/runs/online_skill_r50_cxr6_20261109/generation/chexbench', '--dataset', 'chexbench', '--expect-questions', '618', '--embedding-model', 'text-embedding-v4', '--embedding-base-url', 'https://dashscope.aliyuncs.com/compatible-mode/v1', '--order-manifest', '/home/imss/cw/MedRAX_reproduction_20261027/runs/online_skill_r50_cxr6_20261109/configs/chexbench_order.json'], 'slake': ['/home/imss/cw/MedRAX_reproduction_20261027/.venv/bin/python', '-u', '/home/imss/cw/MedRAX_reproduction_20261027/code_cxr_online_skill_r50_cxr6_20261109/experiments/run_online_skill_r50.py', '--config', '/home/imss/cw/MedRAX_reproduction_20261027/runs/online_skill_r50_cxr6_20261109/configs/slake.json', '--data', '/home/imss/cw/MedRAX_reproduction_20261027/code_cxr_action_r41_20261108/data/slake_cxr', '--reference-dir', '/home/imss/cw/MedRAX_reproduction_20261027/runs/image_memory_gt_r48_20261108/reference_vault/slake', '--out', '/home/imss/cw/MedRAX_reproduction_20261027/runs/online_skill_r50_cxr6_20261109/generation/slake', '--dataset', 'slake', '--expect-questions', '114', '--embedding-model', 'text-embedding-v4', '--embedding-base-url', 'https://dashscope.aliyuncs.com/compatible-mode/v1'], 'vqarad': ['/home/imss/cw/MedRAX_reproduction_20261027/.venv/bin/python', '-u', '/home/imss/cw/MedRAX_reproduction_20261027/code_cxr_online_skill_r50_cxr6_20261109/experiments/run_online_skill_r50.py', '--config', '/home/imss/cw/MedRAX_reproduction_20261027/runs/online_skill_r50_cxr6_20261109/configs/vqarad.json', '--data', '/home/imss/cw/MedRAX_reproduction_20261027/code_cxr_action_r41_20261108/data/vqarad_cxr', '--reference-dir', '/home/imss/cw/MedRAX_reproduction_20261027/runs/image_memory_gt_r48_20261108/reference_vault/vqarad', '--out', '/home/imss/cw/MedRAX_reproduction_20261027/runs/online_skill_r50_cxr6_20261109/generation/vqarad', '--dataset', 'vqarad', '--expect-questions', '116', '--embedding-model', 'text-embedding-v4', '--embedding-base-url', 'https://dashscope.aliyuncs.com/compatible-mode/v1']}

from pathlib import Path
import fcntl,json,os,subprocess,sys,time,shutil
r=Path(RUN);jobs=r/'jobs'
lock=(jobs/'.controller.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
ready=json.loads((r/'EXECUTION_REVIEW_READY.json').read_text())
assert ready['verdict']=='ready' and ready['scope_complete'] is True
health=json.loads((r/'health/complete.json').read_text());assert health['status']=='three_new_tools_healthy'
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
 env=dict(os.environ,R50_EMBEDDING_API_KEY=embedding_key,LANGCHAIN_TRACING_V2='false',LANGSMITH_TRACING='false')
 for flag in ('CUDA_LAUNCH_BLOCKING','TORCH_SHOW_CPP_STACKTRACES'):env.pop(flag,None)
 with (jobs/(ds+'.log')).open('xb',buffering=0) as log:
  p=subprocess.Popen(PROGRAMS[ds]+['--execute','--api-key-stdin'],stdin=subprocess.PIPE,stdout=log,stderr=subprocess.STDOUT,env=env)
  (jobs/(ds+'.pid')).write_text(str(p.pid));state({'state':'running_dataset','dataset':ds,'pid':p.pid})
  p.communicate(main_key)
 rc=p.returncode;(jobs/(ds+'.exitcode')).write_text(str(rc)+'\n')
 out=r/'generation'/ds
 if out.is_dir():(out/'generation.exitcode').write_text(str(rc)+'\n')
 if rc:
  state({'state':'dataset_failed_stop_queue','dataset':ds,'exit_code':rc,'pid':p.pid});raise SystemExit(rc)
 complete=json.loads((out/'complete.json').read_text())
 assert complete['status']=='generation_complete' and complete['questions']==COUNTS[ds] and complete['arm']==ARM
state({'state':'all_three_datasets_exited_zero','datasets':DATASETS,'arm':ARM})
