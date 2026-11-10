"""One completed-dataset transfer/score; final controls/source collected separately.

Never invokes inference, health, old private scorers or any checksum gate.
Native failures/partial inventories remain for explicit diagnosis, not auto-retry.
"""
import argparse
from contextlib import contextmanager
from datetime import datetime,timezone
import json
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import io
from contextlib import redirect_stdout

from deploy_cxr6_r50 import connect,remote_python,ROOT,LOCAL,PREP,RUN,CODE,ARM,DATASETS,COUNTS,HEALTH_IMAGE,read,write_new

MIRROR=Path('D:/MedRAX_Experiment_Artifacts/online_skill_r50_cxr6_20261109')
RECEIPTS=LOCAL/'local_assets/r50_cxr6_collection_receipts'
REPORT=LOCAL/'reports/cxr_online_skill_r50_cxr6_20261109'
sys.path.insert(0,str(LOCAL/'experiments'))
from r50_recovery_evidence import REMOTE_GATE_SOURCE,job_completion,generation_completion


def now():return datetime.now(timezone.utc).isoformat()


@contextmanager
def collection_lock():
    import msvcrt
    MIRROR.mkdir(parents=True,exist_ok=True)
    with (MIRROR/'.collection.lock').open('a+b') as f:
        if f.seek(0,2)==0:f.write(b'0');f.flush()
        f.seek(0);msvcrt.locking(f.fileno(),msvcrt.LK_NBLCK,1)
        try:yield
        finally:f.seek(0);msvcrt.locking(f.fileno(),msvcrt.LK_UNLCK,1)


def remote_gate(c,datasets,final=False):
    # Setup/transfer gate does not open feedback, refs, final Skill contents or
    # completed predictions. The private scorer itself adapts all raw arms first.
    output=io.StringIO()
    source=REMOTE_GATE_SOURCE+'\nRUN='+repr(RUN)+'\nARM='+repr(ARM)+'\nCOUNTS='+repr(COUNTS)+'\nDATASETS='+repr(datasets)+'\nFINAL='+repr(final)+'\n'+r'''
from pathlib import Path
import json
r=Path(RUN);native={}
for ds in DATASETS:
 g=r/'generation'/ds
 native[ds]=job_completion(r/'jobs',ds)
 generation=generation_completion(g)
 assert generation['original_exit']==native[ds]['original_exit'] and generation['final_exit']==0
 assert (g/'complete.json').is_file() and (g/'final_repo.json').is_file()
 manifest=json.loads((g/'manifest.json').read_text());ids=[v['question_id'] for v in manifest['inputs']]
 assert manifest['arm']==ARM and manifest['dataset']==ds and len(ids)==len(set(ids))==COUNTS[ds]
 for name in ('predictions','contexts','steps','prediction_events','feedback'):
  folder=g/name/ARM if name=='predictions' else g/name
  assert {p.stem for p in folder.glob('*.json')}==set(ids)
if FINAL:
 controller=job_completion(r/'jobs')
else:controller=None
print(json.dumps({'completed_dataset_transfer_gate':'passed','datasets':DATASETS,'native_datasets':native,'native_controller':controller,'reference_or_feedback_bodies_read':0,'new_model_or_API_calls':0}))
'''
    with redirect_stdout(output):remote_python(c,source,timeout=30)
    result=json.loads(output.getvalue());print(json.dumps(result),flush=True);return result


def transfer(c,pairs):
    """One serialized SFTP walk, normal transfer inventory only, no hashes."""
    inventory=MIRROR/'download_inventory.json'
    marks=read(inventory) if inventory.exists() else {};count=0
    with c.open_sftp() as s:
        def walk(remote,local,relative):
            nonlocal count
            local.mkdir(parents=True,exist_ok=True)
            for entry in s.listdir_attr(remote):
                if entry.filename.startswith('.') or entry.filename in ('__pycache__','hf_modules'):continue
                src=remote+'/'+entry.filename;dest=local/entry.filename;key=relative+'/'+entry.filename
                if stat.S_ISDIR(entry.st_mode):walk(src,dest,key)
                elif stat.S_ISREG(entry.st_mode):
                    if dest.suffix.lower() in ('.safetensors','.pt','.pth'):raise RuntimeError('unexpected_weight_in_results_namespace')
                    mark=[entry.st_size,entry.st_mtime]
                    if marks.get(key)==mark and dest.is_file():continue
                    assert not dest.exists(),'existing_uninventoried_result_inspect_before_overwrite:'+key
                    part=dest.with_name(dest.name+'.download_part');s.get(src,str(part),prefetch=False);part.replace(dest)
                    marks[key]=mark;count+=1
                    if count%50==0:
                        inventory.write_text(json.dumps(marks),encoding='utf-8');print(json.dumps({'new_streamed_files':count}),flush=True)
        try:
            for remote,local,relative in pairs:walk(remote,local,relative)
        finally:inventory.write_text(json.dumps(marks,indent=2)+'\n',encoding='utf-8')
    return count


def pull_dataset(ds):
    completed=RECEIPTS/(ds+'.pull.completed.json');started=RECEIPTS/(ds+'.pull.started.json')
    assert not completed.exists() and not started.exists(),'pull_already_invoked_inspect_original_receipts'
    with collection_lock():
        with connect() as c:
            gate=remote_gate(c,[ds]);native=gate['native_datasets'][ds]
            write_new(started,{'utc':now(),'dataset':ds,'remote':RUN+'/generation/'+ds,'local':str(MIRROR/'generation'/ds),'native_completion':native})
            try:
                files=transfer(c,[(RUN+'/generation/'+ds,MIRROR/'generation'/ds,'generation/'+ds)])
                with c.open_sftp() as s:
                    jobs=MIRROR/'jobs';jobs.mkdir(exist_ok=True)
                    names={native['job_prefix']+suffix for suffix in ('.pid','.log','.exitcode')}
                    if native.get('original_generation_started',True):names|={ds+suffix for suffix in ('.pid','.log','.exitcode')}
                    if native['technical_continuation_used']:
                        names|={'technical_continuation001.json','controller.pid','controller.log','controller.exitcode'}
                        if len(native['recovery_ids'])==2:
                            names|={'technical_continuation002.json'}|{prefix+suffix for prefix in ('controller_recovery001','chexbench_recovery001') for suffix in ('.pid','.log','.exitcode')}
                    if native.get('protocol_amendment_used'):
                        names|={'protocol_amendment003.json'}
                        if ds=='chexbench':names|={prefix+suffix for prefix in ('controller_recovery002','chexbench_recovery002') for suffix in ('.pid','.log','.exitcode')}
                    for name in sorted(names):
                        dest=jobs/name
                        if dest.exists():continue
                        s.get(RUN+'/jobs/'+name,str(dest),prefetch=False)
            except Exception as e:
                write_new(RECEIPTS/(ds+'.pull.failure.json'),{'utc':now(),'error_type':type(e).__name__,'partial_inventory_preserved':True,'automatic_retry':False});raise
        write_new(completed,{'status':'completed','utc':now(),'dataset':ds,'new_streamed_files':files,'original_runner_exit':native['original_exit'],
          'final_runner_exit':native['final_exit'],'native_completion':native,
          'generation':str(MIRROR/'generation'/ds),'old_R49_transfers_repeated':False,'hash_checks':False})
    print(json.dumps({'dataset_pull_completed':ds,'files':files,'private_score_not_started':True}))


def score_dataset(ds):
    assert read(RECEIPTS/(ds+'.pull.completed.json'))['status']=='completed'
    native=job_completion(MIRROR/'jobs',ds);generation_completion(MIRROR/'generation'/ds)
    started=RECEIPTS/(ds+'.score.started.json');completed=RECEIPTS/(ds+'.score.completed.json')
    assert not started.exists() and not completed.exists(),'score_already_invoked_inspect_do_not_repeat'
    # Completed R49 receipt supplies already-saved canonical input/ref/R47 paths.
    # Neither old references nor old result score bodies are read by this wrapper.
    old=read(LOCAL/'local_assets/r49_dataset_score_receipts'/(ds+'.json'))['identity']
    out=REPORT/'results'/ds;assert not out.exists()
    command=[sys.executable,'-X','utf8',str(LOCAL/'experiments/score_online_skill_r50.py'),
      '--data',old['data'],'--run',str(MIRROR/'generation'/ds),'--references',old['references'],
      '--dataset',ds,'--out',str(out),'--r49-run',old['run']]
    if ds=='chexbench':command+=['--r47-frozen',old['r47_frozen'],'--r47-run',old['r47_run']]
    write_new(started,{'utc':now(),'dataset':ds,'command':command,'original_runner_exit':native['original_exit'],
      'final_runner_exit':native['final_exit'],'native_completion':native,
      'old_R49_private_scorer_invoked':False,'automatic_retry':False})
    with (RECEIPTS/(ds+'.score.stdout.log')).open('x',encoding='utf-8') as stdout, (RECEIPTS/(ds+'.score.stderr.log')).open('x',encoding='utf-8') as stderr:
        p=subprocess.run(command,cwd=LOCAL,stdout=stdout,stderr=stderr)
    if p.returncode:
        write_new(RECEIPTS/(ds+'.score.failure.json'),{'utc':now(),'native_exit':p.returncode,'completed_metric_claim':False,
          'internal_failure_stage_requires_original_traceback_inspection':True,'automatic_retry':False})
        raise RuntimeError('R50_score_native_failure_preserved_'+str(p.returncode))
    summary=read(out/'summary.json');assert summary['questions']==COUNTS[ds] and summary['arm']==ARM
    write_new(completed,{'status':'completed','utc':now(),'dataset':ds,'native_exit':0,'summary':str(out/'summary.json'),
      'per_question':str(out/'per_question.json'),'n':COUNTS[ds],'correct':summary['arms'][ARM]['correct'],
      'old_R49_private_score_invoked':False,'raw_R49_historical_comparison_with_common_adapter':True,'new_inference_or_hash_checks':0})
    print(json.dumps({'dataset_score_completed':ds,'correct':summary['arms'][ARM]['correct'],'n':COUNTS[ds],'summary':str(out/'summary.json')}))


def final_controls():
    started=RECEIPTS/'final_controls.started.json';assert not started.exists()
    with collection_lock():
        with connect() as c:
            gate=remote_gate(c,DATASETS,final=True);write_new(started,{'utc':now(),'scope':'final RUN controls, excluding all already-pulled generation/health','native_completion':gate})
            files=transfer(c,[(RUN+'/configs',MIRROR/'configs','configs')])
            job_mtimes={}
            with c.open_sftp() as s:
                for entry in s.listdir_attr(RUN+'/jobs'):
                    if not stat.S_ISREG(entry.st_mode) or entry.filename.startswith('.'):continue
                    job_mtimes[entry.filename]=entry.st_mtime
                    dest=MIRROR/'jobs'/entry.filename
                    if dest.exists():continue  # dataset job records already copied once after original exit0.
                    s.get(RUN+'/jobs/'+entry.filename,str(dest),prefetch=False);files+=1
                names=['queue_controller.py','health_controller.py','EXECUTION_REVIEW_READY.json','EVALUATION_PROTOCOL.json']
                names+=['queue_controller_recovery'+str(i).zfill(3)+'.py' for i,_ in enumerate(gate['native_controller']['recovery_ids'],1)]
                if gate['native_controller'].get('protocol_amendment_used'):
                    names+=['queue_controller_amendment003.py','protocol_amendment003.json','amendment003_user_approval.json']
                for name in names:
                    dest=MIRROR/name;assert not dest.exists();s.get(RUN+'/'+name,str(dest),prefetch=False);files+=1
                # New health input was not part of its earlier evidence pull.
                # Collect this one explicitly named training image once, without
                # re-probing or re-downloading any R49 or new health outputs.
                health_source=MIRROR/'health_source';health_source.mkdir()
                s.get(HEALTH_IMAGE,str(health_source/'training_xmlab120.jpg'),prefetch=False);files+=1
        write_new(RECEIPTS/'final_controls.completed.json',{'status':'completed','utc':now(),'new_files':files,
          'native_datasets':gate['native_datasets'],'native_controller':gate['native_controller'],
          'all_three_final_runner_and_controller_exits':0,'initial_nonzero_exits_retained':gate['native_controller']['technical_continuation_used'],
          'generation_or_health_repeated':False,
          'health_evidence_reuse':'local_assets/r50_cxr6_preparation/health already pulled once',
          'health_input_image_collected_once':str(MIRROR/'health_source/training_xmlab120.jpg'),
          'actual_job_file_mtime_seconds':job_mtimes,'filesystem_mtime_is_not_provider_billing_time':True})
    print(json.dumps({'final_controls_completed':True,'new_files':files}))


def actual_source():
    started=RECEIPTS/'actual_source.started.json';assert not started.exists()
    with collection_lock():
        with connect() as c:
            remote_gate(c,DATASETS,final=True);write_new(started,{'utc':now(),'code':CODE,'scope':'actual source and device config only; no weights/data'})
            target=MIRROR/'actual_code_source';target.mkdir()
            files=[]
            with c.open_sftp() as s:
                for folder,suffix in (('experiments','.py'),('configs','.json')):
                    dest=target/folder;dest.mkdir()
                    for e in s.listdir_attr(CODE+'/'+folder):
                        if not stat.S_ISREG(e.st_mode) or not e.filename.endswith(suffix):continue
                        s.get(CODE+'/'+folder+'/'+e.filename,str(dest/e.filename),prefetch=False);files.append(folder+'/'+e.filename)
        write_new(RECEIPTS/'actual_source.completed.json',{'status':'completed','utc':now(),'files':files,
          'count':len(files),'actual_deployed_CODE':CODE,'postexecution_source_capture_not_weight_or_integrity_attestation':True,'hash_checks':False})
    print(json.dumps({'actual_source_collected':len(files)}))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['pull','score','final-controls','actual-source']);p.add_argument('--dataset',choices=DATASETS);a=p.parse_args()
    if a.mode in ('pull','score'):
        if not a.dataset:p.error('--dataset required')
        (pull_dataset if a.mode=='pull' else score_dataset)(a.dataset)
    elif a.mode=='final-controls':final_controls()
    else:actual_source()
