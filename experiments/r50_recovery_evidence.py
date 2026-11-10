"""Explicit evidence for the two actual R50 pre-generation technical recoveries.

No inference, repair, labels or hashes. Unknown failures/registrations are not
accepted. Original nonzero exits remain distinct from final continuation exits.
"""
import inspect
import json
from pathlib import Path

ARM='M43-IM-GT-S50-CXR6'
RECOVERY='001_medvlm_tokenizer_load'
QID='chexbench_rad_restruct_0227'
CACHE='42a5ac09c93a6ac19d79b02eda81d4d4c33048eb56c955ed457f0ce5d6d8c09e'
RECOVERY2='002_medgemma_tokenizer_load'
QID2='chexbench_slake_0068'
CACHE2='90fc56c698e79fe11b01dbef78553feedef1c3f5ea3a92447feca6b700fc86dc'
POLICY003='003_paper_tool_failure_observation'


def amendment_registry(run):
    run=Path(run);path=run/'protocol_amendment.json'
    if not path.exists():return None
    value=json_read(path);ds=run.name
    expected={'schema':'r50_paper_tool_failure_observation_v1','policy_id':POLICY003,'arm':ARM,
      'dataset':ds,'explicit_user_approval':True,'user_reply':'那按照论文中的同样来吧',
      'all_remaining_questions':True,'saved_prefix':316 if ds=='chexbench' else 0,
      'regenerate_failed_output':False,'modify_original_producers':False,'change_model_EOS_or_token_parameters':False,
      'original_exit1_records_retained':True,'held_question':'chexbench_openi_0078',
      'held_cache_key':'65e65ea9f529a7ce811f54147a7c2326bf115aeaf0ddb2960ff9c3437d77626d',
      'new_execution_modules':['r50_failure_observation.py','r50_services_amended.py','r50_run_amended.py']}
    if ds not in ('chexbench','slake','vqarad') or any(value.get(k)!=v for k,v in expected.items()):
        raise ValueError('unknown_or_changed_R50_protocol_amendment')
    return value


def amended_generation_completion(run):
    run=Path(run);policy=amendment_registry(run)
    if policy is None:raise ValueError('explicit_R50_protocol_amendment_required')
    if (run/'generation.amendment003.exitcode').read_text().strip()!='0':
        raise ValueError('actual_amended_generation_zero_required')
    chex=run.name=='chexbench';registries=recovery_registries(run)
    if chex:
        if len(registries)!=2 or any((run/name).read_text().strip()!='1' for name in
            ('generation.exitcode','generation.recovery001.exitcode','generation.recovery002.exitcode')):
            raise ValueError('all_three_actual_prior_generation_ones_required')
    elif registries or (run/'generation.exitcode').exists():
        raise ValueError('unstarted_original_cohort_must_not_be_given_fake_exit')
    return {'original_exit':1 if chex else None,'original_generation_started':chex,'final_exit':0,
      'technical_continuation_used':chex,'recovery_id':RECOVERY2 if chex else None,
      'recovery_ids':[RECOVERY,RECOVERY2] if chex else [],'prior_failed_exits':[1,1,1] if chex else [],
      'protocol_amendment_used':True,'protocol_amendment_id':POLICY003,
      'final_generation_exit_file':'generation.amendment003.exitcode','failed_tool_outputs_retried':False}


def amended_job_completion(jobs,dataset=None):
    jobs=Path(jobs);mapping=json_read(jobs/'protocol_amendment003.json')
    expected={'schema':'r50_explicit_protocol_amendment_v1','arm':ARM,'amendment_id':POLICY003,
      'active_controller':'controller_amendment003','active_queue_status':'queue_status.amendment003.json',
      'dataset_jobs':{ds:ds+'_amendment003' for ds in ('chexbench','slake','vqarad')},
      'generation_exit_files':{ds:'generation.amendment003.exitcode' for ds in ('chexbench','slake','vqarad')},
      'prior_mappings':['technical_continuation001.json','technical_continuation002.json'],
      'prior_controller_jobs':['controller','controller_recovery001','controller_recovery002'],
      'prior_chexbench_jobs':['chexbench','chexbench_recovery001','chexbench_recovery002'],
      'all_prior_native_exits':1,'original_11_producer_modules_modified':False,
      'execution_code_extended':True,'saved_predictions_modified':False,'failed_tool_regenerated':False,
      'new_execution_modules':['r50_failure_observation.py','r50_services_amended.py','r50_run_amended.py']}
    if any(mapping.get(k)!=v for k,v in expected.items()):raise ValueError('unknown_R50_amended_job_map')
    for name in expected['prior_controller_jobs']+expected['prior_chexbench_jobs']:
        if (jobs/(name+'.exitcode')).read_text().strip()!='1':raise ValueError('amendment_must_preserve_all_prior_native_ones')
    for tag,recovery in (('001',RECOVERY),('002',RECOVERY2)):
        prior=json_read(jobs/('technical_continuation'+tag+'.json'))
        if prior.get('recovery_id')!=recovery or prior.get('arm')!=ARM:
            raise ValueError('prior_technical_continuation_mapping_changed')
    if dataset is not None and dataset not in expected['dataset_jobs']:raise ValueError('unknown_dataset')
    prefix=expected['dataset_jobs'][dataset] if dataset else expected['active_controller']
    if (jobs/(prefix+'.exitcode')).read_text().strip()!='0':raise ValueError('amended_final_native_zero_required')
    if dataset not in (None,'chexbench') and (jobs/(dataset+'.exitcode')).exists():
        raise ValueError('unstarted_original_cohort_must_not_be_given_fake_exit')
    if dataset is None:
        queue=json_read(jobs/expected['active_queue_status'])
        if queue.get('state')!='all_three_datasets_exited_zero' or queue.get('policy_id')!=POLICY003:
            raise ValueError('whole_amended_queue_completion_required')
    prior_used=dataset in (None,'chexbench')
    return {'original_exit':1 if prior_used else None,'original_generation_started':prior_used,
      'final_exit':0,'job_prefix':prefix,'technical_continuation_used':prior_used,
      'recovery_id':RECOVERY2 if prior_used else None,'recovery_ids':[RECOVERY,RECOVERY2] if prior_used else [],
      'prior_failed_exits':[1,1,1] if prior_used else [],'protocol_amendment_used':True,
      'protocol_amendment_id':POLICY003,'job_map':'protocol_amendment003.json',
      'final_generation_exit_file':'generation.amendment003.exitcode' if dataset else None}


def json_read(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def recovery_registry(run,reader=json_read,*,second=False):
    path=Path(run)/('technical_recovery002.json' if second else 'technical_recovery.json')
    if not path.exists():return None
    value=reader(path)
    expected={'schema':'r50_known_medvlm_pre_generate_recovery_v1','adopted_retry_id':RECOVERY,
      'question_id':QID,'ordinal':105,'selection_ordinal':5,'cache_key':CACHE,'tool':'medvlm_r1',
      'failed_archive':'technical_failures/'+RECOVERY,'successful_attempt':'technical_recovery/'+RECOVERY,
      'original_generation_exit':1,'final_generation_exit_file':'generation.recovery001.exitcode',
      'original_controller_exit':1,'original_runner_exit':1,'original_saved_prefix':104,
      'failed_attempt_model_events':[],'exact_image_args_revision_unchanged':True,
      'completed_predictions_modified':False,'unknown_sends_reissued':False,'own_GT_read_before_adoption':False,
      'model_environment_or_generation_parameters_changed':False,
      'adoption_is_technical_not_answer_quality_selection':True,'successful_attempt_mirrored_for_publication':True}
    if second:
        expected.update(schema='r50_known_medgemma_pre_generate_recovery_v2',adopted_retry_id=RECOVERY2,
          question_id=QID2,ordinal=184,selection_ordinal=1,cache_key=CACHE2,tool='medgemma',
          failed_archive='technical_failures/'+RECOVERY2,successful_attempt='technical_recovery/'+RECOVERY2,
          original_saved_prefix=183,final_generation_exit_file='generation.recovery002.exitcode',
          prior_generation_exit_file='generation.recovery001.exitcode',prior_continuation_exit=1,parent_recovery_id=RECOVERY)
    if any(value.get(k)!=v for k,v in expected.items()):raise ValueError('unknown_or_changed_R50_technical_recovery')
    return value


def recovery_registries(run,reader=json_read):
    first=recovery_registry(run,reader);second=recovery_registry(run,reader,second=True)
    if second and not first:raise ValueError('second_recovery_requires_preserved_first_registry')
    return ([first] if first else [])+([second] if second else [])


def generation_completion(run):
    run=Path(run)
    if (run/'protocol_amendment.json').is_file():return amended_generation_completion(run)
    original=int((run/'generation.exitcode').read_text().strip())
    registries=recovery_registries(run)
    if not registries:
        if original!=0:raise ValueError('unrecovered_original_generation_exit')
        return {'original_exit':0,'final_exit':0,'technical_continuation_used':False,'recovery_id':None,'recovery_ids':[],'prior_failed_exits':[]}
    registry=registries[-1]
    if len(registries)==2 and (run/'generation.recovery001.exitcode').read_text().strip()!='1':
        raise ValueError('actual_failed_first_continuation_must_be_retained')
    if original!=1 or (run/registry['final_generation_exit_file']).read_text().strip()!='0':
        raise ValueError('original1_and_actual_continuation0_required')
    return {'original_exit':1,'final_exit':0,'technical_continuation_used':True,'recovery_id':registry['adopted_retry_id'],
      'recovery_ids':[v['adopted_retry_id'] for v in registries],'prior_failed_exits':[1]*len(registries)}


def job_completion(jobs,dataset=None):
    jobs=Path(jobs)
    if (jobs/'protocol_amendment003.json').is_file():return amended_job_completion(jobs,dataset)
    second=(jobs/'technical_continuation002.json').exists()
    path=jobs/('technical_continuation002.json' if second else 'technical_continuation001.json')
    mapping=json_read(path) if path.exists() else None
    if mapping:
        expected={'schema':'r50_explicit_technical_continuation_v1','arm':ARM,'recovery_id':RECOVERY,
          'original_controller':'controller','active_controller':'controller_recovery001',
          'active_queue_status':'queue_status.recovery001.json',
          'dataset_jobs':{'chexbench':'chexbench_recovery001','slake':'slake','vqarad':'vqarad'},
          'generation_exit_files':{'chexbench':'generation.recovery001.exitcode','slake':'generation.exitcode','vqarad':'generation.exitcode'},
          'original_controller_exit':1,'original_chexbench_exit':1,'original_failed_records_retained':True,
          'original_producer_modules_modified':False,'saved_predictions_modified':False,'automatic_retry':False}
        if second:
            expected.update(schema='r50_explicit_technical_continuation_v2',recovery_id=RECOVERY2,
              active_controller='controller_recovery002',active_queue_status='queue_status.recovery002.json',
              dataset_jobs={'chexbench':'chexbench_recovery002','slake':'slake','vqarad':'vqarad'},
              generation_exit_files={'chexbench':'generation.recovery002.exitcode','slake':'generation.exitcode','vqarad':'generation.exitcode'},
              prior_controller_exit=1,prior_chexbench_exit=1,parent_recovery_id=RECOVERY)
            if (not (jobs/'technical_continuation001.json').is_file()
                or any((jobs/(v+'.exitcode')).read_text().strip()!='1' for v in ('controller_recovery001','chexbench_recovery001'))):
                raise ValueError('first_failed_continuation_native_history_required')
        if any(mapping.get(k)!=v for k,v in expected.items()):raise ValueError('unknown_R50_continuation_job_map')
        if (jobs/'controller.exitcode').read_text().strip()!='1' or (jobs/'chexbench.exitcode').read_text().strip()!='1':
            raise ValueError('original_failed_native_exits_must_be_retained')
    if dataset is not None:
        if dataset not in ('chexbench','slake','vqarad'):raise ValueError('unknown_dataset')
        prefix=mapping['dataset_jobs'][dataset] if mapping else dataset
        original=int((jobs/(dataset+'.exitcode')).read_text().strip())
        final=int((jobs/(prefix+'.exitcode')).read_text().strip())
        if final!=0 or original!=(1 if mapping and dataset=='chexbench' else 0):raise ValueError('dataset_final_native_zero_required')
        return {'original_exit':original,'final_exit':final,'job_prefix':prefix,
          'technical_continuation_used':bool(mapping and dataset=='chexbench'),
          'recovery_id':mapping['recovery_id'] if mapping and dataset=='chexbench' else None,
          'recovery_ids':([RECOVERY,RECOVERY2] if second else [RECOVERY]) if mapping and dataset=='chexbench' else [],
          'prior_failed_exits':([1,1] if second else [1]) if mapping and dataset=='chexbench' else []}
    prefix=mapping['active_controller'] if mapping else 'controller'
    original=int((jobs/'controller.exitcode').read_text().strip())
    final=int((jobs/(prefix+'.exitcode')).read_text().strip())
    queue=json_read(jobs/(mapping['active_queue_status'] if mapping else 'queue_status.json'))
    if final!=0 or original!=(1 if mapping else 0) or queue.get('state')!='all_three_datasets_exited_zero':
        raise ValueError('whole_actual_queue_final_native_zero_required')
    return {'original_exit':original,'final_exit':final,'job_prefix':prefix,
      'technical_continuation_used':bool(mapping),'recovery_id':mapping['recovery_id'] if mapping else None,
      'recovery_ids':([RECOVERY,RECOVERY2] if second else [RECOVERY]) if mapping else [],
      'prior_failed_exits':([1,1] if second else [1]) if mapping else []}


def tool_recovery_attempts(run,reader=json_read):
    run=Path(run);registries=recovery_registries(run,reader)
    if not registries:
        if any((run/v).exists() for v in ('technical_failures','technical_recovery')):
            raise ValueError('unregistered_R50_failure_or_recovery_directory')
        return [],[]
    for folder in ('technical_failures','technical_recovery'):
        if {p.name for p in (run/folder).iterdir()}!={v['adopted_retry_id'] for v in registries}:raise ValueError('unknown_extra_R50_recovery_attempt')
    failed_values=[];histories=[]
    for registry in registries:
        failed,history=one_tool_recovery(run,registry,reader)
        failed_values.append(failed);histories.append(history)
    return failed_values,histories


def one_tool_recovery(run,registry,reader):
    failed_root=run/registry['failed_archive'];success_root=run/registry['successful_attempt']
    failed=reader(failed_root/'tool_cache/result.json');selection=reader(failed_root/'selection.json')
    old_request=reader(failed_root/'tool_cache/request.json');request=reader(success_root/'request.json')
    result=reader(success_root/'result.json');completed=reader(success_root/'completed.json')
    active=run/'services/tool_cache'/registry['cache_key']
    error_type='ImportError' if registry['adopted_retry_id']==RECOVERY else 'Exception'
    if (failed.get('status')!='failed' or failed.get('error_type')!=error_type or failed.get('actual_model_events')!=[]
        or selection.get('status')!='failed' or selection.get('cache_key')!=registry['cache_key'] or selection.get('tool')!=registry['tool']
        or failed.get('identity')!=result.get('identity') or result.get('status')!='completed'
        or {k:v for k,v in request.items() if k!='artifact_dir'}!={k:v for k,v in old_request.items() if k!='artifact_dir'}
        or reader(active/'result.json')!=result or reader(active/'request.json')!=request
        or completed.get('status')!='completed_healthy' or completed.get('native_worker_exit_code')!=0):
        raise ValueError('actual_R50_failed_and_successful_attempt_binding_changed')
    if any((success_root/v).read_text().strip()!='0' for v in ('worker.exitcode','attempt.exitcode')):
        raise ValueError('actual_explicit_tool_retry_native_zero_required')
    events=result.get('actual_model_events',[])
    if len(events)!=1 or events[0].get('kind')!='generate' or events[0].get('status')!='completed':
        raise ValueError('one_actual_recovery_generate_required')
    history={'recovery_id':registry['adopted_retry_id'],'question_id':registry['question_id'],'selection_ordinal':registry['selection_ordinal'],
      'failed_pre_generation_attempts':1,'successful_explicit_tool_retries':1,
      'original_error_type':failed['error_type'],'failed_elapsed_s':failed.get('elapsed_s'),
      'successful_retry_elapsed_s':result.get('elapsed_s'),'unknown_sends_reissued':False,
      'completed_predictions_modified':False,'underlying_loader_intermittency_cause':'unknown',
      'successful_tool_text_retained_without_quality_filter':True,
      'failed_archive':registry['failed_archive'],'successful_attempt':registry['successful_attempt']}
    return failed,history


# Used only for remote completion receipts; no producer module upload/execution.
REMOTE_GATE_SOURCE='\n'.join(['import json','from pathlib import Path',
    'ARM='+repr(ARM),'RECOVERY='+repr(RECOVERY),'QID='+repr(QID),'CACHE='+repr(CACHE),
    'RECOVERY2='+repr(RECOVERY2),'QID2='+repr(QID2),'CACHE2='+repr(CACHE2),'POLICY003='+repr(POLICY003),
    inspect.getsource(json_read),inspect.getsource(recovery_registry),
    inspect.getsource(recovery_registries),
    inspect.getsource(amendment_registry),inspect.getsource(amended_generation_completion),inspect.getsource(amended_job_completion),
    inspect.getsource(generation_completion),inspect.getsource(job_completion)])
