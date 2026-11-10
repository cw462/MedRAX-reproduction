"""Prepare an isolated R50 source variant; no remote/model/API operation."""
import ast
import inspect
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
PREP = ROOT/'local_assets/r50_cxr6_preparation'
CODE = '/home/imss/cw/MedRAX_reproduction_20261027/code_cxr_online_skill_r50_cxr6_20261109'
RUN = '/home/imss/cw/MedRAX_reproduction_20261027/runs/online_skill_r50_cxr6_20261109'
ARM = 'M43-IM-GT-S50-CXR6'
NAMES = ['cxr_online_primitives','online_memory','prepare_feedback','run_online_skill',
         'skill_services','skill_lifecycle','skill_evolve','skill_prompts']


def literal(path, name):
    text=(ROOT/path).read_text(encoding='utf-8-sig')
    for node in ast.parse(text).body:
        if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id==name for t in node.targets):
            return ast.literal_eval(node.value)
    raise ValueError('missing_source_constant:'+name)


def write_new(path,text):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x',encoding='utf-8') as f:f.write(text)


def main():
    if PREP.exists():raise RuntimeError('R50_source_preparation_already_exists_inspect_before_repeating')
    PREP.mkdir()
    fields=literal('local_assets/recover_cxr_online_skill_r49_mutation_fields.py','FIELDS_CLARIFICATION')
    unique=literal('local_assets/recover_cxr_online_skill_r49_adoption.py','ANALYSIS_CLARIFICATION')
    generated=[]
    for stem in NAMES:
        source=ROOT/'experiments'/(stem+'_r49.py')
        text=source.read_text(encoding='utf-8-sig').replace('r49','r50').replace('R49','R50')
        if stem=='run_online_skill':
            text=text.replace("ARM='M43-IM-GT-S49'",'ARM='+repr(ARM))
            old="                    def screen(pool):return service.meta('screen_'+q,PRESCREEN,{'question':row['question'],'options':row.get('options',{}),'candidates':pool})['ids']"
            new="""                    def screen(pool):
                        chosen=service.meta('screen_'+q,PRESCREEN,{'question':row['question'],'options':row.get('options',{}),'candidates':pool})['ids']
                        save_once(out/'prescreen_events'/(q+'.json'),{'question_id':q,'window':wi,
                            'input_pool_ids':[x['id'] for x in pool],'input_pool_count':len(pool),
                            'returned_ids':copy.deepcopy(chosen),'returned_count':len(chosen),
                            'all_rejected':not bool(chosen),'scope':'actual prescreen input after unchanged per-branch top5; no current label'})
                        return chosen"""
            if text.count(old)!=1:raise RuntimeError('prescreen_log_insertion_source_changed')
            text=text.replace(old,new)
            text=text.replace("        service=Services(cfg,protocol,runtime,a.out/'services',key,a.embedding_model,a.embedding_base_url)",
                "        from r50_baseline_controls import validate_runtime\n        validate_runtime(runtime)\n        service=Services(cfg,protocol,runtime,a.out/'services',key,a.embedding_model,a.embedding_base_url)")
            text=text.replace("'initial_repo':'empty'", "'r50_method_changes':['six_model_tool_menu','prescreen_for_any_nonempty_candidate_pool'],\n              'r50_baseline_controls':{'MAIRA_EOS_guard':'uniform_from_start','MUTATE_fields_clarification':True,'ANALYZE_unique_adoption_clarification':True,'old_failure_registrations_imported':False},\n              'initial_repo':'empty'")
        elif stem=='skill_lifecycle':
            old='if len(candidates)>5 and prescreen:'
            if text.count(old)!=1:raise RuntimeError('retrieval_condition_source_changed')
            text=text.replace(old,'if candidates and prescreen:')
        elif stem=='skill_prompts':
            text+='\n# Inherited late-R49 ordinary schema clarifications, uniform from R50 start.\nANALYZE += '+repr(unique)+'\nMUTATE += '+repr(fields)+'\n'
        target=ROOT/'experiments'/(stem+'_r50.py');ast.parse(text);write_new(target,text);generated.append(target.relative_to(ROOT).as_posix())
    baseline='''"""R50 baseline controls inherited uniformly; no old recovery registrations."""
import os
from pathlib import Path
import json
TOOLS=('medgemma','llava_rad','chest_xray_expert','llava_med_qa','xray_phrase_grounding','medvlm_r1')
def validate_runtime(runtime):
    if runtime['arms']['M']['tools']!=list(TOOLS):raise ValueError('exact_six_tool_menu_required')
    if set(runtime['tools'])!=set(TOOLS):raise ValueError('only_six_registered_tools_required')
    if any(v.get('gpu')!='1' for v in runtime['tools'].values()):raise ValueError('GPU1_only')
    device=json.loads((Path(__file__).resolve().parents[1]/'configs/cxr_vqa_tool_worker_gpu.json').read_text())
    if device.get('cuda_visible_devices')!='1':raise ValueError('new_CODE_worker_must_mask_GPU1')
    for name in ('CUDA_LAUNCH_BLOCKING','TORCH_SHOW_CPP_STACKTRACES'):os.environ.pop(name,None)
'''
    write_new(ROOT/'experiments/r50_baseline_controls.py',baseline);generated.append('experiments/r50_baseline_controls.py')
    # Preserve the existing EOS policy and exact token/decode capture implementation.
    sys.path.insert(0,str(ROOT/'local_assets'))
    import recover_cxr_online_skill_r49_phrase_guard as guard
    import diagnose_r49_phrase_grounding_once as capture
    worker=guard.WORKER.replace('from eos_guard_policy import install_eos_guard','from maira_eos_guard_r50 import install_eos_guard')
    old="validate_scope(read(Path(__file__).parent/'SCOPE.json'),read(Path(__file__).parent/'REVIEW_READY.json'))"
    worker=worker.replace(old,"ready=read(Path(RUN)/'EXECUTION_REVIEW_READY.json')\nassert ready['scope_complete'] is True and ready['verdict']=='ready'")
    prelude='import json\nfrom pathlib import Path\nCODE='+repr(CODE)+'\nRUN='+repr(RUN)+"\nTOOL='xray_phrase_grounding'\nPOLICY_ID="+repr(guard.POLICY_ID)+'\n'
    worker=prelude+'\n'.join(inspect.getsource(f) for f in (guard.read,guard.write_once,capture.token_values,capture.capture_tool,capture.capture_state))+'\n'+worker
    ast.parse(worker);write_new(ROOT/'experiments/maira_guard_worker_r50.py',worker);generated.append('experiments/maira_guard_worker_r50.py')
    policy=(ROOT/'local_assets/r49_phrase_grounding_eos_guard_candidate.py').read_text(encoding='utf-8-sig')
    write_new(ROOT/'experiments/maira_eos_guard_r50.py',policy);generated.append('experiments/maira_eos_guard_r50.py')
    # Only this isolated support copy changes: worker selection, device guard, offline/debug env.
    text=(ROOT/'experiments/run_cxr_vqa_toolsets.py').read_text(encoding='utf-8-sig')
    old="command = [spec['python'], str(Path(__file__).with_name('cxr_vqa_tool_worker.py'))]"
    if text.count(old)!=1:raise RuntimeError('worker_selection_source_changed')
    text=text.replace(old,"command = [spec['python'], spec.get('worker_script') or str(Path(__file__).with_name('cxr_vqa_tool_worker.py'))]")
    old="env.update(spec.get('worker_env', {}))"
    text=text.replace(old,old+"\n                env.update(CUDA_VISIBLE_DEVICES='1',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')\n                env.pop('CUDA_LAUNCH_BLOCKING',None);env.pop('TORCH_SHOW_CPP_STACKTRACES',None)")
    ast.parse(text);write_new(PREP/'support/run_cxr_vqa_toolsets.py',text)
    # Freeze evaluation definitions before generation; implementation extends the existing common-answer scorer.
    evaluation={'arm':ARM,'datasets':{'chexbench':618,'slake':114,'vqarad':116},
      'baseline_correct':{'chexbench':{'M43':466,'R47_online_GT':468,'R49_online_GT_Skill':465},'slake':{'M43':108,'R49_online_GT_Skill':113},'vqarad':{'M42':100,'R49_online_GT_Skill':97}},
      'metrics':'unchanged common explicit-answer/author-aligned micro, subset macro, word recall, corrected/harmed/net and paired image/patient-study cluster intervals',
      'all_arms_reference_free_adaptation_before_labels':True,'no_private_R49_score_rerun_or_overwrite':True,
      'not_pooled_independent_848_cases':True,'claim_limits':'two-method-change combination plus uniform inherited controls; no Skill-only causal, clinical, closed-test SOTA claim',
      'score_only_full_dataset_after_original_runner_exit_zero':True,'publish_complete_question_images_requests_feedback_skills_failure_usage_time':True}
    write_new(PREP/'EVALUATION_PROTOCOL.json',json.dumps(evaluation,ensure_ascii=False,indent=2)+'\n')
    write_new(PREP/'SOURCE_PREPARATION.json',json.dumps({'runtime_sources':generated,'isolated_support':'support/run_cxr_vqa_toolsets.py','original_R49_sources_modified':False,'old_failure_registrations_imported':False,'inference_API_GPU_calls':0,'file_or_image_hash_checks':False,'status':'prepared_not_deployed_not_reviewed'},ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'new_runtime_sources':len(generated),'R49_sources_modified':False,'inference_started':False,'arm':ARM}))


if __name__=='__main__':main()
