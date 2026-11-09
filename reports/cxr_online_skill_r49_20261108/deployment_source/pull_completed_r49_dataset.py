"""Read-only once-per-complete-dataset SFTP transfer; never generate or score."""
import argparse
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import stat

from deploy_cxr_online_skill_r49 import COUNTS,DATASETS,RUN,connect

ARCHIVE=Path('D:/MedRAX_Experiment_Artifacts/online_skill_r49_20261108')
ARM='M43-IM-GT-S49'
RECOVERY='adoption_1'
SCORE_RECEIPTS=Path(__file__).resolve().parent/'r49_dataset_score_receipts'


def now():return datetime.now(timezone.utc).isoformat()


def read_remote(sftp,path):
    with sftp.open(path,'r') as handle:
        value=handle.read();return value.decode('utf-8') if isinstance(value,bytes) else value


def json_remote(sftp,path):return json.loads(read_remote(sftp,path))


def optional_remote(sftp,path):
    try:return read_remote(sftp,path).strip()
    except FileNotFoundError:return None


def exists_remote(sftp,path):
    try:sftp.stat(path);return True
    except FileNotFoundError:return False


def json_members(sftp,path):
    return {item.filename[:-5] for item in sftp.listdir_attr(path) if stat.S_ISREG(item.st_mode) and item.filename.endswith('.json')}


def complete_dataset(sftp,dataset):
    """No reference/answer body is opened; check raw exits before completion metadata."""
    if dataset not in DATASETS:raise ValueError('unknown_dataset')
    remote=RUN+'/generation/'+dataset
    exits={key:optional_remote(sftp,path) for key,path in {
      'generation':remote+'/generation.exitcode','jobs':RUN+'/jobs/'+dataset+'.exitcode',
      'actual_runner':RUN+'/recovery/'+RECOVERY+'/'+dataset+'.exitcode'}.items()}
    if any(value!='0' for value in exits.values()):raise ValueError('dataset_original_runner_not_complete_exit_zero:'+dataset)
    if not exists_remote(sftp,remote+'/complete.json'):raise ValueError('original_completion_marker_required:'+dataset)
    # complete.json embeds final_repo/learned content. Only the unchanged scorer
    # opens its body after all compared answers have been reference-free adapted.
    manifest=json_remote(sftp,remote+'/manifest.json')
    ids=[row['question_id'] for row in manifest['inputs']];n=COUNTS[dataset]
    if (len(ids)!=n or len(set(ids))!=n or manifest.get('dataset')!=dataset or manifest.get('arm')!=ARM
        or [row['question_id'] for row in manifest['order']]!=ids):
        raise ValueError('full_original_dataset_completion_required:'+dataset)
    for name in ('predictions/'+ARM,'contexts','steps','prediction_events','feedback'):
        if json_members(sftp,remote+'/'+name)!=set(ids):raise ValueError('complete_dataset_artifact_membership_required:'+dataset+':'+name)
    windows=[item for item in sftp.listdir_attr(remote+'/windows') if stat.S_ISDIR(item.st_mode)]
    if len(windows)!=(n+29)//30 or any(not exists_remote(sftp,remote+'/windows/'+item.filename+'/repo.json') for item in windows):
        raise ValueError('full_dataset_window_repositories_required:'+dataset)
    return {'dataset':dataset,'questions':n,'raw_exits':exits,'windows':len(windows),'remote_run':RUN,'remote_generation':remote}


def controller_snapshot(sftp):
    pid=optional_remote(sftp,RUN+'/recovery/'+RECOVERY+'/controller.pid')
    return {'recovery_id':RECOVERY,'controller_pid':pid,'controller_alive':bool(pid and exists_remote(sftp,'/proc/'+pid)),
      'current_attempt_controller_exit':optional_remote(sftp,RUN+'/recovery/'+RECOVERY+'/controller.exitcode'),
      'queue':json_remote(sftp,RUN+'/jobs/queue_status.json'),'captured_at':now(),'final_controller_completion_claim':False}


def safe_path(path):
    path=Path(path)
    if os.name=='nt' and str(path).startswith('\\\\?\\'):path=Path(str(path)[4:])
    if not path.resolve().is_relative_to(ARCHIVE.resolve()):raise ValueError('transfer_path_outside_explicit_archive')
    return Path('\\\\?\\'+str(path.resolve())) if os.name=='nt' else path


def write_json(path,value):
    path=safe_path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_name(path.name+'.write_part');temporary.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');temporary.replace(path)


def inventory():
    path=safe_path(ARCHIVE/'download_inventory.json')
    return json.loads(path.read_text(encoding='utf-8')) if path.is_file() else {}


def transfer_file(sftp,remote,relative,inv):
    """Same size/mtime resume inventory as the existing pull; no content/hash checks."""
    path=safe_path(ARCHIVE/relative);attributes=sftp.stat(remote);mark=[attributes.st_size,attributes.st_mtime]
    if inv.get(relative)==mark and path.is_file():return 0
    path.parent.mkdir(parents=True,exist_ok=True)
    part=path.with_name(path.name+'.download_part');sftp.get(remote,str(part),prefetch=False);part.replace(path)
    inv[relative]=mark
    if len(inv)%100==0:
        write_json(ARCHIVE/'download_inventory.json',inv)
        print(json.dumps({'streamed_inventory_entries':len(inv)}),flush=True)
    return 1


def transfer_tree(sftp,remote,relative,inv):
    count=0;safe_path(ARCHIVE/relative).mkdir(parents=True,exist_ok=True)
    for item in sftp.listdir_attr(remote):
        name=item.filename
        if name.startswith('.') or name in ('__pycache__','hf_modules') or '/' in name or '\\' in name:continue
        if Path(name).suffix.lower() in ('.key','.pem','.safetensors','.pth','.pt'):continue
        source=remote+'/'+name;target=relative+'/'+name
        if stat.S_ISDIR(item.st_mode):count+=transfer_tree(sftp,source,target,inv)
        elif stat.S_ISREG(item.st_mode):count+=transfer_file(sftp,source,target,inv)
    return count


def receipt_path(dataset):return ARCHIVE/'dataset_completion'/dataset/'PULL_RECEIPT.json'


def reused_dataset(dataset):
    path=safe_path(receipt_path(dataset))
    if not path.is_file():return None
    receipt=json.loads(path.read_text(encoding='utf-8'))
    if (receipt.get('status')!='complete_immutable_dataset_pulled' or receipt.get('dataset')!=dataset or receipt.get('remote_run')!=RUN
        or receipt.get('archive')!=str(ARCHIVE) or receipt.get('questions')!=COUNTS[dataset]):raise ValueError('completed_dataset_pull_receipt_changed')
    for relative in ('generation/'+dataset+'/complete.json','generation/'+dataset+'/generation.exitcode',
                     'jobs/'+dataset+'.exitcode','recovery/'+RECOVERY+'/'+dataset+'.exitcode'):
        if not safe_path(ARCHIVE/relative).is_file():raise ValueError('completed_immutable_mirror_missing_no_automatic_repull')
    return receipt


def pull_dataset(client,dataset,resume_transfer=False):
    old=reused_dataset(dataset)
    if old is not None:return {'dataset':dataset,'reused_existing_complete_pull':True,'new_transfers':0,'receipt':str(receipt_path(dataset))}
    started=ARCHIVE/'dataset_completion'/dataset/'PULL_STARTED.json';started_path=safe_path(started)
    expected={'dataset':dataset,'remote_run':RUN,'archive':str(ARCHIVE),'questions':COUNTS[dataset]}
    if started_path.is_file():
        prior=json.loads(started_path.read_text(encoding='utf-8'))
        if not resume_transfer or any(prior.get(key)!=value for key,value in expected.items()):raise ValueError('partial_pull_requires_explicit_same_transfer_resume')
        if (SCORE_RECEIPTS/(dataset+'.json')).exists() or (SCORE_RECEIPTS/(dataset+'.started.json')).exists():
            raise ValueError('scored_or_started_scoring_dataset_may_not_be_repulled')
    elif safe_path(ARCHIVE/'generation'/dataset).exists():raise ValueError('existing_unreceipted_dataset_mirror_must_be_inspected')
    with client.open_sftp() as sftp:
        completion=complete_dataset(sftp,dataset)
        if not started_path.is_file():write_json(started,{**expected,'started_at':now(),'remote_generation_writes':False,'model_api_calls':0})
        inv=inventory();count=0
        try:
            count+=transfer_tree(sftp,RUN+'/generation/'+dataset,'generation/'+dataset,inv)
            for relative in ('jobs/'+dataset+'.exitcode','jobs/'+dataset+'.pid','jobs/'+dataset+'.'+RECOVERY+'.log',
                             'recovery/'+RECOVERY+'/'+dataset+'.exitcode','recovery/'+RECOVERY+'/'+dataset+'.pid'):
                count+=transfer_file(sftp,RUN+'/'+relative,relative,inv)
            # Complete GEN/failure_events supplies the scorer's repair proof.
            # Do not copy a whole recovery tree or the active controller log.
            write_json(ARCHIVE/'dataset_completion'/dataset/'control_snapshot.json',controller_snapshot(sftp))
        finally:write_json(ARCHIVE/'download_inventory.json',inv)
    receipt={**expected,**completion,'status':'complete_immutable_dataset_pulled','completed_at':now(),'files_transferred':count,
      'score_invoked':False,'references_parsed':False,'completion_marker_body_parsed':False,'other_dataset_predictions_pulled':False,'controller_may_still_run':True,
      'final_pull_must_preserve_this_generation_directory':True,'transfer_inventory_scope':'existing_size_mtime_resume_metadata_only_no_hashes'}
    write_json(receipt_path(dataset),receipt)
    return {'dataset':dataset,'reused_existing_complete_pull':False,'new_transfers':count,'questions':COUNTS[dataset],'receipt':str(receipt_path(dataset))}


def pull_final_controls(client,resume_transfer=False):
    receipt=ARCHIVE/'dataset_completion/FINAL_CONTROL_PULL_RECEIPT.json'
    if safe_path(receipt).is_file():return {'reused_existing_final_controls':True,'new_transfers':0}
    for dataset in DATASETS:
        if reused_dataset(dataset) is None:raise ValueError('pull_each_completed_dataset_before_final_controls:'+dataset)
    started=ARCHIVE/'dataset_completion/FINAL_CONTROL_PULL_STARTED.json'
    if safe_path(started).exists() and not resume_transfer:raise ValueError('partial_final_control_pull_requires_explicit_resume')
    with client.open_sftp() as sftp:
        if optional_remote(sftp,RUN+'/recovery/'+RECOVERY+'/controller.exitcode')!='0' or optional_remote(sftp,RUN+'/jobs/controller.exitcode')!='0':
            raise ValueError('final_control_pull_requires_actual_controller_exit_zero')
        queue=json_remote(sftp,RUN+'/jobs/queue_status.json')
        if (queue.get('state')!='all_three_datasets_exited_zero_after_adoption_recovery' or queue.get('recovery')!=RECOVERY
            or list(queue.get('datasets',[]))!=list(DATASETS) or queue.get('prior_production_attempts_include_exit1') is not True):
            raise ValueError('final_control_pull_requires_all_three_final_queue')
        for dataset in DATASETS:
            if optional_remote(sftp,RUN+'/jobs/'+dataset+'.exitcode')!='0' or optional_remote(sftp,RUN+'/recovery/'+RECOVERY+'/'+dataset+'.exitcode')!='0':
                raise ValueError('final_control_pull_requires_three_actual_child_exit_zero')
        if not safe_path(started).is_file():write_json(started,{'remote_run':RUN,'archive':str(ARCHIVE),'started_at':now(),'generation_directories_skipped':list(DATASETS)})
        inv=inventory();count=0
        try:
            for name in ('jobs','configs','recovery'):count+=transfer_tree(sftp,RUN+'/'+name,name,inv)
            for name in ('PROTOCOL.json','EXECUTION_REVIEW_READY.json','queue_controller.py'):
                if exists_remote(sftp,RUN+'/'+name):count+=transfer_file(sftp,RUN+'/'+name,name,inv)
        finally:write_json(ARCHIVE/'download_inventory.json',inv)
    write_json(receipt,{'status':'final_controls_pulled','remote_run':RUN,'archive':str(ARCHIVE),'completed_at':now(),'files_transferred':count,
      'generation_directories_skipped':list(DATASETS),'scores_invoked':False,'result_files_overwritten':False})
    return {'reused_existing_final_controls':False,'new_transfers':count,'generation_directories_skipped':list(DATASETS)}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('mode',choices=('dataset','final-controls'))
    parser.add_argument('--dataset',choices=DATASETS);parser.add_argument('--resume-transfer',action='store_true');args=parser.parse_args()
    if args.mode=='dataset' and args.dataset is None:parser.error('--dataset is required')
    reused=reused_dataset(args.dataset) if args.mode=='dataset' else None
    if reused is not None:print(json.dumps({'dataset':args.dataset,'reused_existing_complete_pull':True,'new_transfers':0}))
    else:
        with connect() as client:
            result=pull_dataset(client,args.dataset,args.resume_transfer) if args.mode=='dataset' else pull_final_controls(client,args.resume_transfer)
        print(json.dumps(result,ensure_ascii=False))
