"""Offline R50 reproduction from public raw evidence and projected raw baselines.

No inference, private run, old R49 scorer invocation or image/file digest gate.
"""
import argparse
import json
import os
from pathlib import Path
from unittest.mock import patch

from cxr_online_primitives_r50 import read
from online_memory_r50 import save_once
from run_online_skill_r50 import ARM
import score_online_skill_r50 as scorer
from score_cxr_author_alignment import adapt


def asset_normalizer(evidence):
    """Normalize document-relative URLs, caching resolved targets and depth maps.

    Every ordinary publisher image is under evidence/assets. For a document
    outside that asset folder, the relative URLs depend only on its depth.
    Nonstandard layouts fall back to a per-parent mapping with the same order.
    """
    evidence=Path(evidence).resolve();asset_root=evidence/'assets';assets=[]
    for index,item in enumerate(read(evidence/'image_assets.json')):
        target=(evidence/item['path']).resolve()
        if not target.is_relative_to(evidence) or not target.is_file():raise ValueError('public_asset_missing_or_outside_evidence')
        assets.append((target,'PUBLIC_ASSET:'+str(index)))
    standard=all(p.is_relative_to(asset_root) for p,_ in assets);mappings_cache={}
    def normalize(value,document):
        parent=Path(document).parent
        depth=len(parent.relative_to(evidence).parts) if parent.is_relative_to(evidence) else None
        key=('depth',depth) if standard and depth is not None and not parent.is_relative_to(asset_root) else ('parent',parent)
        if key not in mappings_cache:
            mappings=sorted([(os.path.relpath(target,parent).replace('\\','/'),canonical) for target,canonical in assets],key=lambda x:-len(x[0]))
            anchor='assets/' if mappings and all('assets/' in old for old,_ in mappings) else None
            mappings_cache[key]=(mappings,anchor)
        mappings,anchor=mappings_cache[key]
        def visit(item):
            if isinstance(item,dict):return {k:visit(v) for k,v in item.items()}
            if isinstance(item,list):return [visit(v) for v in item]
            if isinstance(item,str):
                if anchor and anchor not in item:return item
                for old,new in mappings:item=item.replace(old,new)
            return item
        return visit(value)
    return normalize


def projected_bundle(bundle,inputs,name,names):
    """Only answer/status and actual raw terminal fields are needed by adapt()."""
    if set(bundle)!=set(names):raise ValueError('public_comparator_arm_membership')
    values=bundle[name]
    if set(values)!={row['question_id'] for row in inputs}:raise ValueError('public_comparator_question_membership')
    required={'raw','call_path','ordinal','reuse_chain','evidence_status','technical_stop'}
    for value in values.values():
        if set(value['prediction'])!={'answer','status'} or set(value['source'])!=required:
            raise ValueError('public_comparator_requires_label_free_raw_projection')
    return {row['question_id']:adapt(row,values[row['question_id']]['prediction'],values[row['question_id']]['source']) for row in inputs}


def compare_public(result,details,evidence):
    saved=read(evidence/'scores/summary.json');previous=read(evidence/'scores/per_question.json')
    keys=('dataset','arm','questions','all_questions_fresh','mode','arms','comparisons','skill_hit_questions',
      'same_image_hit_questions','windows','resources','references_read_after_all_arms_adapted',
      'R49_saved_comparator_provenance','R50_combined_changes','R50_uniform_inherited_controls',
      'repeated_no_progress_by_saved_status','descriptive_groups','native_generation_completion')
    for key in keys:
        if saved.get(key)!=result.get(key):raise ValueError('public_R50_score_or_resource_changed:'+key)
    by_id={v['question_id']:v for v in previous}
    if len(previous)!=len(by_id) or set(by_id)!={v['question_id'] for v in details}:raise ValueError('public_scored_membership')
    ignore={'archive_call','reuse_chain'}
    for row in details:
        old=by_id[row['question_id']]
        for key in ('question_id','window','skill_hit','same_image_hit','subset','reference'):
            if row.get(key)!=old.get(key):raise ValueError('public_case_semantics_changed:'+key)
        if set(row['arms'])!=set(old['arms']):raise ValueError('public_case_arm_membership')
        for name,value in row['arms'].items():
            if {k:v for k,v in value.items() if k not in ignore}!={k:v for k,v in old['arms'][name].items() if k not in ignore}:
                raise ValueError('public_answer_adaptation_changed:'+row['question_id']+':'+name)


def verify(evidence,out):
    evidence,out=Path(evidence).resolve(),Path(out).resolve()
    if out.exists() or out.is_relative_to(evidence) or evidence.is_relative_to(out):raise ValueError('new_separate_public_reproduction_output_required')
    publication=read(evidence/'publication_manifest.json');dataset=publication['dataset']
    n,baseline,_=scorer.EXPECTED[dataset]
    names={baseline,'R49_online_GT_Skill'}|({'R47_online_GT'} if dataset=='chexbench' else set())
    if (publication.get('schema')!='r50_semantic_public_evidence_v1' or publication.get('scope')!='complete_scored_online_stream'
        or publication.get('arm')!=ARM or publication.get('questions')!=n or publication.get('final_generation_exit')!=0
        or set(publication.get('comparisons',[]))!=names):raise ValueError('complete_R50_publication_required')
    from r50_recovery_evidence import generation_completion,job_completion
    native=generation_completion(evidence)
    if publication.get('native_generation_completion')!=native or publication.get('raw_generation_exit')!=native['original_exit']:
        raise ValueError('original_failure_and_final_zero_must_be_publicly_reproducible')
    if publication.get('native_dataset_completion')!=job_completion(evidence/'job_records',dataset) or publication.get('native_controller_completion')!=job_completion(evidence/'job_records'):
        raise ValueError('public_actual_native_job_history_changed')
    normalize=asset_normalizer(evidence);raw_read,raw_rows=scorer.read,scorer.rows
    targets={(evidence/v['path']).resolve() for v in read(evidence/'image_assets.json')}
    for row in raw_rows(evidence/'inputs.jsonl'):
        for name in row['images']:
            target=(evidence/name).resolve()
            if target not in targets or not target.is_relative_to(evidence) or not target.is_file():
                raise ValueError('cohort_original_image_not_in_public_asset_store')
    def public_read(path):return normalize(raw_read(path),Path(path))
    def public_rows(path):return [normalize(v,Path(path)) for v in raw_rows(path)]
    bundle_cache={}
    def bundle(inputs,name):
        if not bundle_cache:bundle_cache['raw']=public_read(evidence/'comparison_sources.json')
        return projected_bundle(bundle_cache['raw'],inputs,name,names)
    def baseline_adapter(inputs,ds,name):
        if ds!=dataset or name!=baseline:raise ValueError('public_baseline_identity')
        return bundle(inputs,name)
    def r47_adapter(inputs,old,frozen,run):return bundle(inputs,'R47_online_GT')
    def r49_adapter(inputs,run):
        result=bundle(inputs,'R49_online_GT_Skill');values=bundle_cache['raw']['R49_online_GT_Skill']
        stops={q:v['prediction']['status'] for q,v in values.items() if str(v['prediction']['status']).startswith('repeated_')}
        return result,{'raw_archive_only':True,'private_R49_score_invoked':False,'repeated_no_progress_by_saved_status':stops}
    # No reference/score-body is opened until all raw answer bundles adapt.
    with patch.object(scorer,'read',side_effect=public_read),patch.object(scorer,'rows',side_effect=public_rows), \
         patch.object(scorer,'adapt_historical',side_effect=baseline_adapter),patch.object(scorer,'adapt_r47',side_effect=r47_adapter), \
         patch.object(scorer,'adapt_saved_r49',side_effect=r49_adapter):
        result,details=scorer.score(evidence,evidence,evidence/'references.jsonl',dataset,
          r47_frozen=evidence/'comparison_sources.json' if dataset=='chexbench' else None,
          r47_run=evidence if dataset=='chexbench' else None,r49_run=evidence)
    for row in details:
        q=row['question_id'];event=read(evidence/'feedback'/(q+'.json'));vault=read(evidence/'reference_vault'/(q+'.json'))
        if vault.get('question_id')!=q or {k:vault[k] for k in ('answer','answer_text') if k in vault}!=event['reference_annotation']:
            raise ValueError('public_vault_feedback_binding_changed')
    compare_public(result,details,evidence)
    result.update(scope='Offline public R50 common-answer and resource reproduction, not clinical/causal verification.',
      matches_published_primary_scores_and_extractions=True,matches_published_resources=True,
      private_run_paths_required=False,image_or_file_digests_checked=False,new_inference_calls=0,
      old_R49_private_score_invoked=False,clinical_or_causal_verification=False)
    save_once(out/'summary.json',result);save_once(out/'per_question.json',details)
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--evidence',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();print(json.dumps(verify(a.evidence,a.out),ensure_ascii=False))
