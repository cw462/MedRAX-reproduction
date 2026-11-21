"""Stage an isolated B0-F/L1-F runtime from the historical cohort; no inference."""
from __future__ import annotations
import argparse
import copy
import json
from pathlib import Path
import shutil


def selected_template(history, count):
    frozen=json.loads((history/'frozen.json').read_text(encoding='utf-8'))
    manifest=json.loads((history/'B0/manifest.json').read_text(encoding='utf-8'))
    if count not in (8,60) or len(frozen['cohort']['selected_ids'])!=60:
        raise ValueError('Use the original first 8 or the full original 60 questions')
    ids=frozen['cohort']['selected_ids'][:count]
    if [row['question_id'] for row in manifest['inputs']]!=frozen['cohort']['selected_ids']:
        raise ValueError('Historical manifest/cohort order mismatch')
    template=copy.deepcopy(manifest)
    template['inputs']=template['inputs'][:count]
    template['order']=template['order'][:count]
    template['reference_files']={qid:template['reference_files'][qid] for qid in ids}
    return frozen,template,ids


def stage(base_package, history, out, count):
    base_package,history,out=base_package.resolve(),history.resolve(),out.resolve()
    if out.exists() or out.is_relative_to(base_package) or out.is_relative_to(history):
        raise ValueError('Output must be a new separate directory outside the historical runtime')
    frozen,template,ids=selected_template(history,count)
    cfg=copy.deepcopy(frozen['config'])
    original_native=Path(cfg['native_root'])
    if not original_native.is_dir():
        raise ValueError('Run staging on the original server with its existing native and memory runtimes')
    repair=Path(__file__).resolve().parent/'repair'
    out.mkdir(parents=True)
    shutil.copytree(base_package/'openi60',out/'openi60',ignore=shutil.ignore_patterns('__pycache__'))
    shutil.copytree(base_package/'prompts',out/'prompts')
    for name in ('openi60_cli.py','native_worker.py'):
        shutil.copy2(base_package/name,out/name)
    native=out/'native';native.mkdir()
    for path in original_native.glob('*.py'):
        shutil.copy2(path,native/path.name)
    shutil.copytree(original_native/'code',native/'code',ignore=shutil.ignore_patterns('__pycache__','.git','.venv','venv'))
    (native/'jobs').mkdir()
    # The standard worker imports its lease helper even for CPU ROI cropping.
    original_helpers=original_native/'jobs/lab-resident-tools'
    helpers=native/'jobs/lab-resident-tools'
    helpers.mkdir()
    for name in ('r55_lab_resident_tools.py', 'r55_resident_tools.py'):
        shutil.copy2(original_helpers/name, helpers/name)
    marker=original_native/'jobs/memory-writer-token-plan.json'
    if marker.is_file():shutil.copy2(marker,native/'jobs'/marker.name)
    code=native/'code/M5/experiments'
    for name in ('skill_services_r54.py','action_protocol_f.py'):
        shutil.copy2(repair/name,code/name)
    template_path=native/'manifests/M5/chexbench.json'
    template_path.parent.mkdir(parents=True)
    # Existing prepare selects all rows from this fixed manifest, preserving stream order.
    template_path.write_text(json.dumps(template,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    cfg.update(native_root=str(native),code_root=str(native/'code/M5'),
               template_manifest=str(template_path),data_root=str(history/'data'),
               prompt_file=str(out/'prompts/L1_zh.txt'),work_dir=str(out/'runs/evaluation'),
               n=count,expected_pool=count)
    cfg['protocol_f']={'version':'F','historical_work':str(history),
                       'selection':'original_cohort_prefix_8' if count==8 else 'original_full_cohort_60',
                       'question_ids':ids,'memory_initialization':'fresh_native_seven_seed_patterns_per_arm'}
    config_path=out/'config.F.json'
    config_path.write_text(json.dumps(cfg,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return {'phase':'staged_only','config':str(config_path),'work':cfg['work_dir'],
            'questions_per_arm':count,'question_ids':ids,'model_calls':0,'tool_calls':0,
            'memory_writes':0,'note':'Run existing prepare separately; generation requires explicit run --execute'}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-package',type=Path,required=True)
    parser.add_argument('--history',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--count',type=int,choices=(8,60),required=True)
    args=parser.parse_args()
    print(json.dumps(stage(args.base_package,args.history,args.out,args.count),ensure_ascii=False,indent=2))
