RUN='/home/imss/cw/MedRAX_reproduction_20261027/runs/online_skill_r50_cxr6_20261109'
CODE='/home/imss/cw/MedRAX_reproduction_20261027/code_cxr_online_skill_r50_cxr6_20261109'
ARM='M43-IM-GT-S50-CXR6'
STRONG_RUN='/home/imss/cw/MedRAX_reproduction_20261027/runs/deepseek_flash_skill_formation_v2_20261110'
REQUEST='这个实验先停一下吧，把结果上传这个github'

from pathlib import Path
import json,os,signal,time
r=Path(RUN);jobs=r/'jobs';s=Path(STRONG_RUN);sj=s/'jobs'
def load(p):return json.loads(p.read_text())
def write(p,v):
 with p.open('x') as f:json.dump(v,f,ensure_ascii=False,indent=2)
def proc(pid):
 p=Path('/proc')/str(pid)
 if not p.exists():return None
 stat=(p/'stat').read_text().split(') ',1)[1].split()
 return {'pid':pid,'state':stat[0],'ppid':int(stat[1]),'start_ticks':stat[19],
   'command':(p/'cmdline').read_bytes().replace(b'\0',b' ').decode('utf-8','replace')}
def children(pid):
 p=Path('/proc')/str(pid)/'task'/str(pid)/'children'
 return [int(x) for x in p.read_text().split()] if p.exists() else []
def descendants(pid):
 result=[]
 for c in children(pid):result.extend(descendants(c));result.append(proc(c))
 return [x for x in result if x]
controller=int((jobs/'controller_amendment003.pid').read_text())
assert controller==3517457 and not (jobs/'controller_amendment003.exitcode').exists()
queue=load(jobs/'queue_status.amendment003.json');assert queue['state']=='running_dataset'
ds=queue['dataset'];runner=int((jobs/(ds+'_amendment003.pid')).read_text())
assert ds=='chexbench' and runner==int(queue['pid'])
rp=proc(runner);assert rp and CODE+'/experiments/r50_run_amended.py' in rp['command'] and str(r/'generation'/ds) in rp['command']
strong=int((sj/'controller.pid').read_text());assert strong==3584627
sq=load(sj/'queue_status.json');assert sq['state']=='waiting_R50_actual_complete' and sq['new_inference_started'] is False
assert not list((s/'generation').glob('*/*/services/calls/*/*/*/started.json'))
assert not list(sj.glob('*_direct.pid')) and not list(sj.glob('*_skill.pid'))
sc=children(strong);assert len(sc)==1
sp=proc(sc[0]);assert sp and str(s/'queue_controller.py') in sp['command'] and 'python' in sp['command']
owned=descendants(runner)
record={'utc':time.time(),'user_request':REQUEST,'R50_controller':controller,'R50_runner':rp,
 'R50_descendants':owned,'comparison_controller':strong,'comparison_idle_child':sp,
 'comparison_requests':0,'no_automatic_resume':True,'completed_predictions_modified':False,
 'GPU0_CT_unrelated_processes_selected':False,'inflight_outcomes_may_be_unknown_and_must_not_be_resent':True}
write(jobs/'USER_STOP_REQUEST_20261110.json',record)
write(sj/'USER_STOP_REQUEST_20261110.json',record)
# Stop submissions immediately, then terminate only the verified private process tree.
os.kill(runner,signal.SIGSTOP)
os.kill(sp['pid'],signal.SIGTERM)
signals=[]
for item in owned:
 current=proc(item['pid'])
 if current and current['start_ticks']==item['start_ticks'] and current['state']!='Z':
  os.kill(item['pid'],signal.SIGTERM);signals.append({'pid':item['pid'],'signal':'SIGTERM'})
os.kill(runner,signal.SIGTERM);os.kill(runner,signal.SIGCONT)
signals.append({'pid':runner,'signals':['SIGSTOP','SIGTERM','SIGCONT']})
for _ in range(100):
 if (jobs/'controller_amendment003.exitcode').is_file() and (sj/'controller.exitcode').is_file():break
 time.sleep(.1)
remaining=[]
for item in [rp,*owned]:
 current=proc(item['pid'])
 if current and current['start_ticks']==item['start_ticks'] and current['state']!='Z':remaining.append(current)
assert not remaining,remaining
assert (jobs/(ds+'_amendment003.exitcode')).is_file() and (jobs/'controller_amendment003.exitcode').is_file()
assert (r/'generation'/ds/'generation.amendment003.exitcode').is_file() and (sj/'controller.exitcode').is_file()
assert (sj/'controller.exitcode').read_text().strip()=='143'
g=r/'generation'/ds
counts={name:len(list((g/name/ARM if name=='predictions' else g/name).glob('*.json'))) for name in ('predictions','prediction_events','contexts','feedback','steps')}
exits={name:(jobs/(name+'.exitcode')).read_text().strip() for name in ('controller','controller_recovery001','controller_recovery002','chexbench','chexbench_recovery001','chexbench_recovery002','controller_amendment003',ds+'_amendment003')}
assert all(exits[name]=='1' for name in ('controller','controller_recovery001','controller_recovery002','chexbench','chexbench_recovery001','chexbench_recovery002'))
assert exits['controller_amendment003']!='0' and exits[ds+'_amendment003']!='0'
result={'utc':time.time(),'status':'USER_STOPPED_INCOMPLETE','user_request':REQUEST,'dataset':ds,
 'counts':counts,'R50_native_exits':exits,'GEN_amendment003_exit':(g/'generation.amendment003.exitcode').read_text().strip(),
 'comparison_idle_controller_exit':(sj/'controller.exitcode').read_text().strip(),'comparison_new_requests':0,
 'signals':signals,'no_live_attributed_runner_descendants':True,'saved_predictions_or_original_exits_modified':False,
 'unstarted_datasets':['slake','vqarad'],'automatic_resume':False,'publish_as_incomplete':True,
 'inflight_started_records_preserved_do_not_resend':True}
write(jobs/'USER_STOP_COMPLETED_20261110.json',result)
write(sj/'USER_STOP_COMPLETED_20261110.json',result)
print(json.dumps(result,ensure_ascii=False))
