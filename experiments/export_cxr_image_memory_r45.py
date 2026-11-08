"""Publish completed M43-IM evidence using the existing privacy/image exporter."""
import argparse
from pathlib import Path

from cxr_image_memory_r44 import read,rows
from export_cxr_vqa_extension import RequestEvidencePublisher,restore_images,emit_tool_results
from export_cxr_vqa_toolsets import CALL_FILES


def export(frozen_path,run,scores,data,out,health=None):
    if out.exists():raise FileExistsError(out)
    frozen=read(frozen_path);inputs=frozen['inputs'];expected={r['question_id'] for r in inputs}
    if len(inputs)!=618 or read(scores/'summary.json')['n']!=618:raise ValueError('full618_scored_required')
    completion=read(run/'complete_M43-IM.json')
    exitpath=run/('generation.effective.exitcode' if completion.get('completion_mode')=='independent_known_failure_finalization' else 'generation.exitcode')
    if exitpath.read_text().strip()!='0':raise ValueError('successful_effective_generation_exit_required')
    if completion['questions']!=618:raise ValueError('complete_receipt_required')
    if {p.stem for p in (run/'predictions/M43-IM').glob('*.json')}!=expected:raise ValueError('prediction_membership')
    originals=rows(data/'inputs.jsonl');canonical={r['question_id']:r for r in originals}
    if set(canonical)!=expected:raise ValueError('canonical_input_membership')
    # Reuse already-published original files instead of copying the old cohort.
    public_map={name:name for row in originals for name in row['images']}
    pub=RequestEvidencePublisher(out,data/'data_manifest.json',public_map=public_map,image_roots=(data,))
    for row in inputs:
        original=canonical[row['question_id']]
        if any(row.get(k)!=original.get(k) for k in ['question','options','image_id']):raise ValueError('canonical_input_changed')
        if len(row['images'])!=len(original['images']):raise ValueError('original_image_sequence_count_changed')
        for remote_name,name in zip(row['images'],original['images']):
            pub.source_image(name);digest=pub.sources[name]
            pub.alias(frozen['data'].rstrip('/')+'/'+remote_name,digest)
    marker=read(run/'run.json')
    tools={};selections=[]
    for path in sorted((run/'tool_selections/M43-IM').glob('*/*.json')):
        value=read(path);selections.append(dict(question_id=path.parent.name,ordinal=path.stem,**value))
        key=value['cache_key']
        if key in tools:continue
        folder=run/'tool_cache'/key
        for remote in value.get('derived_images',[]):
            suffix=remote.split('/tool_cache/',1)[-1]
            local=(run/'tool_cache'/suffix).resolve()
            if not local.is_relative_to((run/'tool_cache').resolve()):raise ValueError('derived_image_outside_run')
            pub.alias(remote,pub.put_image(pub.read_image(local)))
        raw=folder/'artifacts/raw.json';stderr=folder/'backend.stderr.log'
        tools[key]={'cache_key':key,'result':value,'raw_result':read(raw) if raw.is_file() else None,
                    'backend_stderr':stderr.read_text(errors='replace') if stderr.is_file() else None}
    for name in ['summary.json','per_question.json']:
        pub.copy_json(scores/name,out/'scores'/name)
    for name in ['inputs.jsonl','references.jsonl']:
        values=rows(data/name)
        for row in values:
            if 'images' in row:row['images']=[pub.rel(pub.source_image(image),out/name) for image in row['images']]
        pub.emit(out/name,values,jsonl=True)
    pub.emit(out/'frozen.public.json',frozen)
    pub.emit(out/'run.json',marker)
    pub.copy_json(run/'complete_M43-IM.json',out/'complete_M43-IM.json')
    raw_exit=(run/'generation.exitcode').read_text().strip()
    pub.emit(out/'generation.exitcode',raw_exit)
    # The exit marker must be plain text, as the offline scorer reads it.
    (out/'generation.exitcode').write_text(raw_exit+'\n',encoding='utf-8')
    if exitpath.name=='generation.effective.exitcode':
        pub.emit(out/exitpath.name,'0');(out/exitpath.name).write_text('0\n',encoding='utf-8')
    recovery=run.parent/'recovery'
    for path in recovery.rglob('*.json'):
        pub.copy_json(path,out/'recovery'/path.relative_to(recovery))
    for path in (run.parent/'jobs').glob('*'):
        if path.is_file() and path.suffix in ['.json','.log','.exitcode']:
            if path.suffix=='.json':pub.copy_json(path,out/'job_records'/path.name)
            else:pub.emit(out/'job_records'/path.name,path.read_text(errors='replace'))
    pub.emit(out/'tool_selections_M43-IM.jsonl',selections,jsonl=True)
    for row in inputs:
        q=row['question_id']
        pub.copy_json(run/'predictions/M43-IM'/(q+'.json'),out/'predictions/M43-IM'/(q+'.json'))
        pub.copy_json(run/'memory_context'/(q+'.json'),out/'memory_context'/(q+'.json'))
        for request in sorted((run/'calls/M43-IM'/q).glob('*/request.json')):
            target=out/'calls/M43-IM'/q/request.parent.name
            for name in CALL_FILES:
                source=request.parent/name
                if source.is_file():pub.emit(target/name,restore_images(read(source),run))
    # Preserve per-selection records in addition to the readable combined table.
    for path in (run/'tool_selections/M43-IM').glob('*/*.json'):
        pub.copy_json(path,out/'tool_selections/M43-IM'/path.parent.name/path.name)
    emit_tool_results(pub,out,tools.values())
    for path in (run/'tool_cache').glob('*/result.json'):
        pub.copy_json(path,out/'tool_cache'/path.parent.name/'result.json')
    if health is not None:
        probes=[read(p) for p in sorted((health/'tool_selections/HEALTH').glob('*/*.json'))]
        health_raw=[]
        for probe in probes:
            for remote in probe.get('derived_images',[]):
                suffix=remote.split('/tool_cache/',1)[-1];local=(health/'tool_cache'/suffix).resolve()
                if not local.is_relative_to((health/'tool_cache').resolve()):raise ValueError('health_image_outside_run')
                pub.alias(remote,pub.put_image(pub.read_image(local)))
            raw=health/'tool_cache'/probe['cache_key']/'artifacts/raw.json'
            health_raw.append({'tool':probe['tool'],'result':probe,'raw_result':read(raw) if raw.exists() else None})
        for name in ['assessment.json','kernel_witness.json','complete.json']:
            if (health/name).exists():pub.copy_json(health/name,out/'health'/name)
        pub.emit(out/'health/probes.jsonl',health_raw,jsonl=True)
    pub.emit(out/'reuse.json',{'baseline_M43':'../../cxr_task_completion_r43_20261108/README.md',
        'M_C41':'../../cxr_action_r41_20261108/FINAL_REPORT.md',
        'old_original_inputs_and_evidence':'../../cxr_vqa_extension/results/chexbench',
        'privacy_note':'Saved request parameters and memory/tool metadata undergo the existing path/credential transformations; image bytes preserved. Not a byte-identical private metadata replay.'})
    pub.emit(out/'image_assets.json',[{k:v for k,v in x.items() if k!='target'}|
        {'path':pub.rel(x['target'],out/'image_assets.json')} for x in pub.assets.values()])
    pub.emit(out/'publication_manifest.json',{'files':sorted(p.relative_to(out).as_posix() for p in pub.files),
        'redactions':dict(pub.redactions),'raw_backend_arrays':'preserved in private streamed mirror; published model-visible tool structures and all relevant derived images are retained'})
    return {'files':len(pub.files),'images':len(pub.assets),'new_inference_calls':0}


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for name in ['frozen','run','scores','data','out']:p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--health',type=Path)
    a=p.parse_args();print(export(a.frozen,a.run,a.scores,a.data,a.out,a.health))
