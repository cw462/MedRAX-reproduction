"""Narrow source/capture preservation only; no remote execution, scoring, or inference."""
import argparse
from datetime import datetime,timezone
import json
import os
from pathlib import Path,PurePosixPath
import shutil
import stat

from deploy_cxr_online_skill_r49 import CODE,ROOT,RUN,FILES,connect

LOCAL=Path(__file__).resolve().parents[1]
ARCHIVE=Path('D:/MedRAX_Experiment_Artifacts/online_skill_r49_20261108')
ACTUAL_CODE=ARCHIVE/'actual_code_source'
RECEIPTS=ARCHIVE/'supplemental_receipts'
CUDA=LOCAL/'local_assets/r49_cuda_failure_20261108/isolated_diagnostic_attempt_1'
CUDA_REMOTE=ROOT+'/runs/online_skill_r49_cuda_diagnostic_20261108/attempt_1'
ADOPTION=LOCAL/'local_assets/r49_adoption_failure_20261109'
PHRASE_TOKEN_MAP=LOCAL/'local_assets/r49_phrase_grounding_diagnostic_20261109/attempt_1/TOKEN_FORMAT_MAPPING.json'
HELPERS=('deploy_cxr_online_skill_r49.py','resume_cxr_online_skill_r49.py','recover_cxr_online_skill_r49_cuda.py',
 'recover_cxr_online_skill_r49_meta_schema.py','recover_cxr_online_skill_r49_mutation_fields.py',
 'recover_cxr_online_skill_r49_embedding_arrearage.py','recover_cxr_online_skill_r49_phrase_guard.py',
 'r49_phrase_grounding_eos_guard_candidate.py','recover_cxr_online_skill_r49_adoption.py',
 'diagnose_r49_chexagent_cuda_once.py','diagnose_r49_embedding_400_once.py','diagnose_r49_phrase_grounding_once.py',
 'pull_completed_r49_dataset.py','score_completed_r49_dataset_once.py','capture_r49_supplemental_sources.py')


def now():return datetime.now(timezone.utc).isoformat()


def normal(path):
    value=str(path)
    return Path(value[4:] if os.name=='nt' and value.startswith('\\\\?\\') else value)


def long(path):
    path=normal(path).resolve()
    return Path('\\\\?\\'+str(path)) if os.name=='nt' else path


def child(root,relative):
    relative=PurePosixPath(relative)
    if relative.is_absolute() or '..' in relative.parts or '\\' in str(relative) or any(':' in part for part in relative.parts):
        raise ValueError('unsafe_capture_relative_path')
    root=normal(root).resolve();path=root.joinpath(*relative.parts).resolve()
    if not path.is_relative_to(root):raise ValueError('capture_path_outside_explicit_root')
    return long(path)


def read(path):return json.loads(long(path).read_text(encoding='utf-8-sig'))


def exclusive_json(path,value):
    path=long(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x',encoding='utf-8') as handle:json.dump(value,handle,ensure_ascii=False,indent=2);handle.write('\n')


def binding():
    if CODE!=ROOT+'/code_cxr_online_skill_r49_20261108' or RUN!=ROOT+'/runs/online_skill_r49_20261108':
        raise ValueError('fixed_R49_ROOT_CODE_RUN_binding_required')
    return {'remote_root':ROOT,'remote_code':CODE,'remote_run':RUN,'archive':str(ARCHIVE)}


def copy_missing(source,destination):
    source=long(source);destination=long(destination)
    if destination.exists():
        if not destination.is_file():raise ValueError('existing_capture_target_is_not_a_file')
        return False
    if not source.is_file():raise FileNotFoundError(str(source))
    if not normal(destination).resolve().is_relative_to(ARCHIVE.resolve()):raise ValueError('local_capture_destination_outside_archive')
    destination.parent.mkdir(parents=True,exist_ok=True)
    temporary=destination.with_name(destination.name+'.capture_part')
    try:
        with source.open('rb') as incoming,temporary.open('xb') as outgoing:shutil.copyfileobj(incoming,outgoing,1024*1024)
        os.link(temporary,destination)  # Exclusive commit; never overwrite an existing source record.
    finally:
        if temporary.exists():temporary.unlink()
    return True


def capture_source(client):
    fixed=binding();done=ACTUAL_CODE/'source_completed.json';started=ACTUAL_CODE/'source_started.json'
    if long(done).is_file():
        value=read(done)
        if value.get('binding')!=fixed or value.get('status')!='actual_code_source_copied':raise ValueError('source_capture_receipt_changed')
        return {'reused_completed_source_capture':True,'files_transferred':0}
    if long(started).exists() or long(ACTUAL_CODE).exists():raise ValueError('source_capture_started_or_unreceipted_inspect_without_automatic_repeat')
    with client.open_sftp() as sftp:
        remote=[]
        for entry in sftp.listdir_attr(CODE+'/experiments'):
            name=entry.filename
            if name.startswith('.') or '/' in name or '\\' in name or not name.endswith('.py') or not stat.S_ISREG(entry.st_mode):continue
            remote.append((CODE+'/experiments/'+name,'experiments/'+name))
        required=set(FILES)|{'cxr_author_alignment.py'}
        if not required <= {PurePosixPath(relative).name for _,relative in remote}:
            raise ValueError('actual_frozen_R49_modules_or_added_dependency_missing')
        config=CODE+'/configs/cxr_vqa_tool_worker_gpu.json'
        if not stat.S_ISREG(sftp.stat(config).st_mode):raise ValueError('actual_worker_gpu_config_not_regular')
        remote.append((config,'configs/cxr_vqa_tool_worker_gpu.json'))
        exclusive_json(started,{'binding':fixed,'started_at':now(),'scope':'immediate_python_sources_and_one_known_config_only',
          'remote_execution':False,'model_api_calls':0,'hash_validation':False,'shared_download_inventory_used':False})
        records=[]
        for source,relative in sorted(remote):
            target=child(ACTUAL_CODE,relative)
            if target.exists():raise ValueError('actual_source_target_already_exists_no_overwrite')
            target.parent.mkdir(parents=True,exist_ok=True);part=target.with_name(target.name+'.download_part')
            sftp.get(source,str(part),prefetch=False)
            os.link(part,target);part.unlink()
            records.append({'remote':source,'local':relative})
    exclusive_json(done,{'binding':fixed,'status':'actual_code_source_copied','completed_at':now(),'files':records,
      'remote_execution':False,'model_api_calls':0,'byte_or_pixel_or_hash_checks':False,'shared_download_inventory_used':False,
      'scope':'actual deployed Python source snapshot, no source byte attestation'})
    return {'reused_completed_source_capture':False,'files_transferred':len(records),'receipt':str(done)}


def local_capture_map():
    fixed=binding();inventory=read(CUDA/'download_inventory.json')
    files=inventory.get('files')
    if (inventory.get('remote')!=CUDA_REMOTE or inventory.get('streamed') is not True or inventory.get('byte_hash_validation') is not False
        or not isinstance(files,list) or len(files)!=17 or len(set(files))!=17):raise ValueError('known_seventeen_file_CUDA_capture_inventory_required')
    records=[]
    for relative in files:
        records.append((child(CUDA,relative),child(ARCHIVE,'recovery/cuda_1/diagnostic_evidence/'+relative)))
    records.append((CUDA/'download_inventory.json',ARCHIVE/'recovery/cuda_1/diagnostic_evidence/LOCAL_CAPTURE_INVENTORY.json'))
    adoption=read(ADOPTION/'INVENTORY.json')
    if not isinstance(adoption,list) or len(adoption)!=25:raise ValueError('known_twentyfive_file_adoption_capture_required')
    seen=set()
    for item in adoption:
        relative=item['local'];remote=item['remote']
        if (relative in seen or remote!=ROOT+'/'+relative or not (remote.startswith(CODE+'/experiments/') or remote.startswith(RUN+'/'))):
            raise ValueError('known_adoption_capture_source_binding_changed')
        seen.add(relative)
        records.append((child(ADOPTION,relative),child(ARCHIVE,'recovery/adoption_1/failure_boundary_capture/'+relative)))
    for name in ('INVENTORY.json','FAILURE_METADATA.json'):
        records.append((ADOPTION/name,ARCHIVE/'recovery/adoption_1/failure_boundary_capture'/name))
    records.append((PHRASE_TOKEN_MAP,ARCHIVE/'recovery/phrase_guard_1/diagnostic_evidence/TOKEN_FORMAT_MAPPING.json'))
    return fixed,records


def preserve_local_captures():
    fixed=binding();done=RECEIPTS/'local_captures_completed.json';started=RECEIPTS/'local_captures_started.json'
    if long(done).is_file():
        value=read(done)
        if value.get('binding')!=fixed or value.get('status')!='known_local_captures_preserved':raise ValueError('local_capture_receipt_changed')
        return {'reused_completed_local_capture':True,'files_copied':0}
    if long(started).exists():raise ValueError('local_capture_started_inspect_without_automatic_repeat')
    final_path=ARCHIVE/'dataset_completion/FINAL_CONTROL_PULL_RECEIPT.json'
    if not long(final_path).is_file():raise ValueError('actual_final_controls_receipt_required_before_local_supplement')
    final=read(final_path)
    if final.get('status')!='final_controls_pulled' or final.get('remote_run')!=RUN or final.get('archive')!=str(ARCHIVE):
        raise ValueError('actual_final_controls_receipt_required_before_local_supplement')
    fixed,records=local_capture_map()
    if any(not long(source).is_file() for source,_ in records):raise ValueError('known_local_capture_file_missing_no_remote_recapture')
    exclusive_json(started,{'binding':fixed,'started_at':now(),'scope':'known_local_inventory_records_missing_only','remote_requests':0,
      'generation_writes':False,'existing_files_overwritten':False})
    copied=[];preserved=[]
    for source,target in records:
        item={'source':str(normal(source)),'destination':str(normal(target).relative_to(ARCHIVE.resolve()))}
        (copied if copy_missing(source,target) else preserved).append(item)
    exclusive_json(done,{'binding':fixed,'status':'known_local_captures_preserved','completed_at':now(),'copied_missing':copied,
      'existing_preserved_without_reading_or_overwriting':preserved,'remote_requests':0,'generation_writes':False,
      'capture_or_diagnostic_reexecuted':False,'hashes_computed':False})
    return {'reused_completed_local_capture':False,'files_copied':len(copied),'existing_preserved':len(preserved),'receipt':str(done)}


def source_plan():
    root=LOCAL/'local_assets';report='reports/cxr_online_skill_r49_20261108'
    return {'binding':binding(),'actual_code_capture':{'remote_python':CODE+'/experiments/*.py (immediate regular files only)',
      'remote_config':CODE+'/configs/cxr_vqa_tool_worker_gpu.json','private_destination':str(ACTUAL_CODE),
      'future_public_destination':report+'/deployment_source/actual_code'},
      'run_records_already_in_final_controls':[{'source':str(ARCHIVE/name),'future_public':report+'/deployment_source/'+target} for name,target in
        [('queue_controller.py','queue_controller.py'),('PROTOCOL.json','PROTOCOL.executed.json'),('EXECUTION_REVIEW_READY.json','EXECUTION_REVIEW_READY.json')]],
      'existing_private_helper_source_map':[{'source':str(root/name),'future_public':report+'/deployment_source/'+name,'exists':(root/name).is_file()} for name in HELPERS],
      'original_deployed_controllers_and_wrappers':{'source':str(ARCHIVE/'recovery'),'export_once_with':'--recovery-root '+str(ARCHIVE/'recovery'),
        'future_public':report+'/evidence/recovery'},
      'postrun_audit_input_controls':{'dataset_pull_receipts':str(ARCHIVE/'dataset_completion'),
        'score_receipts_directory':str(root/'r49_dataset_score_receipts'),
        'preserve_initial_failed_started':str(root/'r49_dataset_score_receipts/chexbench.started.json'),
        'preserve_pre_adaptation_failure':str(root/'r49_dataset_score_receipts/chexbench.pre_adaptation_failure_001.json'),
        'preserve_explicit_resume_started':str(root/'r49_dataset_score_receipts/chexbench.pre_adaptation_resume_001.started.json'),
        'canonical_input_source_receipt':str(ARCHIVE/'dataset_completion/chexbench/SOURCE_INPUT_PULL_RECEIPT.json'),
        'native_scorer_changed':False,'final_review_must_cover_reporting_and_source_path_resume':True},
      'publication_requires':report+'/deployment_source/PROVENANCE.md plus an actual final RESULT_CLAIM review; no hashes, API calls or audit claims made by this plan'}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('mode',choices=('plan','source','local-captures'));args=parser.parse_args()
    if args.mode=='plan':result=source_plan()
    elif args.mode=='local-captures':result=preserve_local_captures()
    else:
        with connect() as client:result=capture_source(client)
    print(json.dumps(result,ensure_ascii=False,indent=2))
