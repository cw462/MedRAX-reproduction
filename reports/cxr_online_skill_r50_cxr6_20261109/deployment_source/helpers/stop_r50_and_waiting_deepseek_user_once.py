"""Explicit user stop: terminate only attributed current R50 children and idle pair queue."""
import contextlib
import io
import json
from datetime import datetime, timezone
from pathlib import Path

from deploy_cxr6_r50 import LOCAL, RUN, CODE, ARM, connect, remote_python, script

DEST = LOCAL / 'local_assets/r50_user_stop_publication_20261110'
STRONG_RUN = '/home/imss/cw/MedRAX_reproduction_20261027/runs/deepseek_flash_skill_formation_v2_20261110'
REQUEST = '这个实验先停一下吧，把结果上传这个github'


def once(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)
        handle.write('\n')


def main():
    DEST.mkdir()
    once(DEST / 'stop.started.json', {'utc': datetime.now(timezone.utc).isoformat(),
        'user_request': REQUEST, 'scope': 'Stop attributed R50 runner and its descendants, hold the zero-request waiting comparison; publish honestly incomplete results.',
        'resume_or_restart_authorized': False, 'new_inference_authorized': False})
    source = script(r'''
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
''', RUN=RUN, CODE=CODE, ARM=ARM, STRONG_RUN=STRONG_RUN, REQUEST=REQUEST)
    (DEST / 'stop.remote.py').write_text(source, encoding='utf-8')
    output = io.StringIO()
    try:
        with connect() as client, contextlib.redirect_stdout(output):
            remote_python(client, source, timeout=35)
        result = json.loads(output.getvalue())
    except Exception as error:
        once(DEST / 'stop.failure.json', {'utc': datetime.now(timezone.utc).isoformat(),
            'error': repr(error), 'automatic_retry': False, 'native_stderr': 'original exec transcript'})
        print(output.getvalue())
        raise
    once(DEST / 'stop.completed.json', result)
    statepath = LOCAL / '.aris/IMPROVEMENT_STATE.json'
    state = json.loads(statepath.read_text(encoding='utf-8'))
    state['R50'].update(status='USER_STOPPED_INCOMPLETE_PENDING_PUBLICATION',
        user_stop=result, resume_authorized=False, user_stop_publication=str(DEST))
    strong = state['strong_model_skill_comparison_20261110']
    strong.update(status='USER_STOPPED_WAITING_COMPARISON_ZERO_REQUESTS',
        user_stop=result, resume_authorized=False, new_inference_started=False)
    strong['active_comparison']['user_stopped'] = True
    state['latest_user_focus'] = REQUEST
    state['next_status_note'] = 'Stop inference and automatic queue resumption; publish incomplete R50 evidence per explicit user request.'
    statepath.write_text(json.dumps(state, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
