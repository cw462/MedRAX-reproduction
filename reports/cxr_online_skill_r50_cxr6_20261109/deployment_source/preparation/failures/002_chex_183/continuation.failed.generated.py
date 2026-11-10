RUN='/home/imss/cw/MedRAX_reproduction_20261027/runs/online_skill_r50_cxr6_20261109'
CODE='/home/imss/cw/MedRAX_reproduction_20261027/code_cxr_online_skill_r50_cxr6_20261109'
PYTHON='/home/imss/cw/MedRAX_reproduction_20261027/.venv/bin/python'
ARM='M43-IM-GT-S50-CXR6'
Q='chexbench_slake_0068'
KEY='90fc56c698e79fe11b01dbef78553feedef1c3f5ea3a92447feca6b700fc86dc'
NAME='002_medgemma_tokenizer_load'
CONTROLLER="RUN='/home/imss/cw/MedRAX_reproduction_20261027/runs/online_skill_r50_cxr6_20261109'\nARM='M43-IM-GT-S50-CXR6'\nDATASETS=('chexbench', 'slake', 'vqarad')\nCOUNTS={'chexbench': 618, 'slake': 114, 'vqarad': 116}\nNAME='002_medgemma_tokenizer_load'\nPROGRAMS={'chexbench': ['/home/imss/cw/MedRAX_reproduction_20261027/.venv/bin/python', '-u', '/home/imss/cw/MedRAX_reproduction_20261027/code_cxr_online_skill_r50_cxr6_20261109/experiments/run_online_skill_r50.py', '--config', '/home/imss/cw/MedRAX_reproduction_20261027/runs/online_skill_r50_cxr6_20261109/configs/chexbench.json', '--data', '/home/imss/cw/MedRAX_reproduction_20261027/code_cxr_vqa_extension/data/chexbench', '--reference-dir', '/home/imss/cw/MedRAX_reproduction_20261027/runs/image_memory_gt_r47_20261108/reference_vault', '--out', '/home/imss/cw/MedRAX_reproduction_20261027/runs/online_skill_r50_cxr6_20261109/generation/chexbench', '--dataset', 'chexbench', '--expect-questions', '618', '--embedding-model', 'text-embedding-v4', '--embedding-base-url', 'https://dashscope.aliyuncs.com/compatible-mode/v1', '--order-manifest', '/home/imss/cw/MedRAX_reproduction_20261027/runs/online_skill_r50_cxr6_20261109/configs/chexbench_order.json'], 'slake': ['/home/imss/cw/MedRAX_reproduction_20261027/.venv/bin/python', '-u', '/home/imss/cw/MedRAX_reproduction_20261027/code_cxr_online_skill_r50_cxr6_20261109/experiments/run_online_skill_r50.py', '--config', '/home/imss/cw/MedRAX_reproduction_20261027/runs/online_skill_r50_cxr6_20261109/configs/slake.json', '--data', '/home/imss/cw/MedRAX_reproduction_20261027/code_cxr_action_r41_20261108/data/slake_cxr', '--reference-dir', '/home/imss/cw/MedRAX_reproduction_20261027/runs/image_memory_gt_r48_20261108/reference_vault/slake', '--out', '/home/imss/cw/MedRAX_reproduction_20261027/runs/online_skill_r50_cxr6_20261109/generation/slake', '--dataset', 'slake', '--expect-questions', '114', '--embedding-model', 'text-embedding-v4', '--embedding-base-url', 'https://dashscope.aliyuncs.com/compatible-mode/v1'], 'vqarad': ['/home/imss/cw/MedRAX_reproduction_20261027/.venv/bin/python', '-u', '/home/imss/cw/MedRAX_reproduction_20261027/code_cxr_online_skill_r50_cxr6_20261109/experiments/run_online_skill_r50.py', '--config', '/home/imss/cw/MedRAX_reproduction_20261027/runs/online_skill_r50_cxr6_20261109/configs/vqarad.json', '--data', '/home/imss/cw/MedRAX_reproduction_20261027/code_cxr_action_r41_20261108/data/vqarad_cxr', '--reference-dir', '/home/imss/cw/MedRAX_reproduction_20261027/runs/image_memory_gt_r48_20261108/reference_vault/vqarad', '--out', '/home/imss/cw/MedRAX_reproduction_20261027/runs/online_skill_r50_cxr6_20261109/generation/vqarad', '--dataset', 'vqarad', '--expect-questions', '116', '--embedding-model', 'text-embedding-v4', '--embedding-base-url', 'https://dashscope.aliyuncs.com/compatible-mode/v1']}\n\nfrom pathlib import Path\nimport fcntl,json,os,subprocess,sys,time,shutil\nr=Path(RUN);jobs=r/'jobs';tag='recovery002'\nlock=(jobs/'.controller.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)\nassert (jobs/'controller.exitcode').read_text().strip()=='1'\nassert json.loads((r/'generation/chexbench/technical_recovery002.json').read_text())['adopted_retry_id']==NAME\nmain_key=sys.stdin.buffer.readline();embedding_key=sys.stdin.buffer.readline().strip().decode()\nassert main_key.strip() and embedding_key\ndef state(v):\n v.update(technical_continuation=tag,original_controller_exit=1,original_chexbench_exit=1,prior_continuation_exit=1)\n path=jobs/'queue_status.recovery002.json';temporary=path.with_suffix('.tmp')\n temporary.write_text(json.dumps(v,indent=2)+'\\n');temporary.replace(path)\nfor ds in DATASETS:\n job=ds+'_recovery002' if ds=='chexbench' else ds\n assert not (jobs/(job+'.pid')).exists(),'continuation_dataset_already_invoked'\n while True:\n  mem=int(subprocess.check_output(['nvidia-smi','--id=1','--query-gpu=memory.used','--format=csv,noheader,nounits'],text=True).strip())\n  state({'state':'waiting_gpu1' if mem>=500 else 'starting_dataset','dataset':ds,'gpu1_used_mib':mem,'other_jobs_modified':False})\n  if mem<500:break\n  time.sleep(60)\n assert shutil.disk_usage(r).free>3*1024**3,'insufficient_free_disk'\n env=dict(os.environ,R50_EMBEDDING_API_KEY=embedding_key,LANGCHAIN_TRACING_V2='false',LANGSMITH_TRACING='false')\n for flag in ('CUDA_LAUNCH_BLOCKING','TORCH_SHOW_CPP_STACKTRACES'):env.pop(flag,None)\n with (jobs/(job+'.log')).open('xb',buffering=0) as log:\n  p=subprocess.Popen(PROGRAMS[ds]+['--execute','--api-key-stdin'],stdin=subprocess.PIPE,stdout=log,stderr=subprocess.STDOUT,env=env)\n  (jobs/(job+'.pid')).write_text(str(p.pid));state({'state':'running_dataset','dataset':ds,'pid':p.pid})\n  p.communicate(main_key)\n rc=p.returncode\n with (jobs/(job+'.exitcode')).open('x') as f:f.write(str(rc)+'\\n')\n out=r/'generation'/ds;name='generation.recovery002.exitcode' if ds=='chexbench' else 'generation.exitcode'\n if out.is_dir():\n  with (out/name).open('x') as f:f.write(str(rc)+'\\n')\n if rc:\n  state({'state':'dataset_failed_stop_queue','dataset':ds,'exit_code':rc,'pid':p.pid});raise SystemExit(rc)\n complete=json.loads((out/'complete.json').read_text())\n assert complete['status']=='generation_complete' and complete['questions']==COUNTS[ds] and complete['arm']==ARM\nstate({'state':'all_three_datasets_exited_zero','datasets':DATASETS,'arm':ARM})\n"

from pathlib import Path
import json,os,subprocess,shlex,shutil,fcntl,datetime
r=Path(RUN);jobs=r/'jobs';g=r/'generation/chexbench';retry=r/'technical_recovery'/NAME
lock=(jobs/'.continuation001.launch.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
assert not Path('/proc/3240536').exists() and not Path('/proc/3240544').exists()
assert (jobs/'controller.exitcode').read_text().strip()=='1' and (jobs/'chexbench.exitcode').read_text().strip()=='1'
assert (g/'generation.exitcode').read_text().strip()=='1'
assert (g/'generation.recovery001.exitcode').read_text().strip()=='1'
assert (jobs/'controller_recovery001.exitcode').read_text().strip()=='1' and (jobs/'chexbench_recovery001.exitcode').read_text().strip()=='1'
assert not (jobs/'controller_recovery002.pid').exists() and not (jobs/'technical_continuation001.json').exists()
assert len(list((g/'predictions'/ARM).glob('*.json')))==183
assert not (g/'predictions'/ARM/(Q+'.json')).exists() and not (g/'feedback'/(Q+'.json')).exists()
cache=g/'services/tool_cache'/KEY;selection=g/'services/tool_selections/R50-AGENT'/Q/'1.json'
failed=json.loads((cache/'result.json').read_text());old_selection=json.loads(selection.read_text())
result=json.loads((retry/'result.json').read_text());request=json.loads((retry/'request.json').read_text())
original_request=json.loads((cache/'request.json').read_text());done=json.loads((retry/'completed.json').read_text())
assert failed['status']=='failed' and failed.get('actual_model_events')==[] and old_selection['cache_key']==KEY
assert done['status']=='completed_healthy' and (retry/'attempt.exitcode').read_text().strip()=='0'
assert result['status']=='completed' and result['identity']==failed['identity']
assert request==dict(original_request,artifact_dir=str(retry/'artifacts'))
assert len(result['actual_model_events'])==1 and result['actual_model_events'][0]['status']=='completed'
assert not result['derived_images'],'this bounded recovery does not reinterpret derived assets'
archive=g/'technical_failures'/NAME;archive.mkdir(parents=True,exist_ok=False)
# Preserve originals by same-filesystem rename; no completed prediction touched.
cache.rename(archive/'tool_cache');selection.rename(archive/'selection.json')
shutil.copytree(retry,g/'technical_recovery'/NAME)
cache.mkdir()
for name in ('request.json','result.json','backend.stdout.log','backend.stderr.log'):
 shutil.copyfile(retry/name,cache/name)
shutil.copytree(retry/'artifacts',cache/'artifacts')
actual_start=json.loads((retry/'started.json').read_text())
started={'identity':result['identity'],'utc':datetime.datetime.fromtimestamp(actual_start['utc'],datetime.timezone.utc).isoformat(),
 'automatic_retry':False,'explicit_known_technical_retry':NAME,
 'materialized_from_actual_retry_started':'technical_recovery/'+NAME+'/started.json'}
with (cache/'started.json').open('x') as f:json.dump(started,f,indent=2)
registry={'schema':'r50_known_medgemma_pre_generate_recovery_v2','adopted_retry_id':NAME,
 'question_id':Q,'ordinal':184,'selection_ordinal':1,'cache_key':KEY,'tool':'medgemma',
 'failed_archive':'technical_failures/'+NAME,'successful_attempt':'technical_recovery/'+NAME,
 'original_generation_exit':1,'prior_generation_exit_file':'generation.recovery001.exitcode','prior_continuation_exit':1,'parent_recovery_id':'001_medvlm_tokenizer_load','final_generation_exit_file':'generation.recovery002.exitcode',
 'original_controller_exit':1,'original_runner_exit':1,'original_saved_prefix':183,
 'failed_attempt_model_events':[],'exact_image_args_revision_unchanged':True,
 'completed_predictions_modified':False,'unknown_sends_reissued':False,'own_GT_read_before_adoption':False,
 'model_environment_or_generation_parameters_changed':False,'underlying_loader_intermittency_cause':'unknown',
 'adoption_is_technical_not_answer_quality_selection':True,'successful_attempt_mirrored_for_publication':True}
with (g/'technical_recovery002.json').open('x') as f:json.dump(registry,f,indent=2)
mapping={'schema':'r50_explicit_technical_continuation_v2','arm':ARM,'recovery_id':NAME,
 'original_controller':'controller','active_controller':'controller_recovery002',
 'active_queue_status':'queue_status.recovery002.json',
 'dataset_jobs':{'chexbench':'chexbench_recovery002','slake':'slake','vqarad':'vqarad'},
 'generation_exit_files':{'chexbench':'generation.recovery002.exitcode','slake':'generation.exitcode','vqarad':'generation.exitcode'},
 'original_controller_exit':1,'original_chexbench_exit':1,'prior_controller_exit':1,'prior_chexbench_exit':1,'parent_recovery_id':'001_medvlm_tokenizer_load','original_failed_records_retained':True,
 'original_producer_modules_modified':False,'saved_predictions_modified':False,'automatic_retry':False}
with (jobs/'technical_continuation001.json').open('x') as f:json.dump(mapping,f,indent=2)
with (r/'queue_controller_recovery002.py').open('x') as f:f.write(CONTROLLER)
main_key=__import__('sys').stdin.buffer.readline();embed_key=__import__('sys').stdin.buffer.readline()
assert main_key.strip() and embed_key.strip()
rd,wr=os.pipe();os.write(wr,main_key+embed_key);os.close(wr)
cmd=shlex.join([PYTHON,'-u',str(r/'queue_controller_recovery002.py')])+'; rc=$?; printf "%s\\n" "$rc" > '+shlex.quote(str(jobs/'controller_recovery002.exitcode'))+'; exit "$rc"'
try:
 with (jobs/'controller_recovery002.log').open('xb',buffering=0) as out:
  p=subprocess.Popen(['bash','-c',cmd],stdin=rd,stdout=out,stderr=subprocess.STDOUT,start_new_session=True)
 (jobs/'controller_recovery002.pid').write_text(str(p.pid))
 with (jobs/'controller_recovery002.started.json').open('x') as f:json.dump({'utc':datetime.datetime.now(datetime.timezone.utc).timestamp(),
  'pid':p.pid,'arm':ARM,'original_controller_exit':1,'technical_recovery_id':NAME},f,indent=2)
 print(json.dumps({'explicit_continuation_launched':True,'controller_pid':p.pid,'original_controller_exit':1,
  'original_chexbench_exit':1,'saved_predictions_modified':False,'producer_modules_modified':False,
  'recovery_id':NAME,'mapping':mapping}))
finally:os.close(rd)
