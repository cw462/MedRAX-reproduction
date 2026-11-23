"""Full-current native/raw membership gate, without opening learned/label bodies."""
import json
from pathlib import Path
from r54_off_resume_evidence import ARM,COUNTS,JOBS,FINAL_EXIT

def require_native_full(out):
    out=Path(out);ds=out.parent.name
    if ds not in COUNTS:raise ValueError('R54_current_dataset_identity')
    for path in (out/FINAL_EXIT,out.parents[2]/'jobs'/(JOBS[ds]+'.exitcode')):
        if not path.is_file() or path.read_text(encoding='utf-8').strip()!='0':
            raise ValueError('R54_current_full_native_zero_before_raw_required')
    manifest=json.loads((out/'manifest.json').read_text(encoding='utf-8'))
    inputs=manifest.get('inputs',[]);ids={row['question_id'] for row in inputs}
    if (manifest.get('dataset')!=ds or manifest.get('arm')!=ARM or manifest.get('skill_enabled') is not False
        or len(inputs)!=len(ids) or len(ids)!=COUNTS[ds]
        or any(set(row)-{'question_id','question','options','images','image_id','source'} for row in inputs)):
        raise ValueError('R54_full_label_free_manifest_required')
    for folder in ('predictions/'+ARM,'prediction_events'):
        if {p.stem for p in (out/folder).glob('*.json')}!=ids:raise ValueError('R54_full_received_raw_membership_required')
    if not (out/'complete.json').is_file():raise ValueError('R54_completion_marker_existence_required')
    return {'dataset':ds,'questions':len(ids),'current_native_exit':0,'learned_or_GT_bodies_opened':False}
