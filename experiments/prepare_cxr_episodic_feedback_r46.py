"""Copy a fixed legal source/development cohort, separating per-source feedback."""
import argparse
import json
from pathlib import Path
import shutil
from cxr_episodic_feedback_r46 import public_row,rows,make_protocol


def main():
    p=argparse.ArgumentParser();p.add_argument('--from-data',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    assert not a.out.exists(),'new_data_directory_required'
    source=sorted(rows(a.from_data/'source_examples.jsonl'),key=lambda x:x['source']['original_qid'])
    development=rows(a.from_data/'inputs.jsonl');assert len(source)==12 and len(development)==27
    a.out.mkdir(parents=True);(a.out/'source_labels').mkdir()
    def jsonl(path,values):path.write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in values),encoding='utf-8')
    for name,values in [('source_inputs.jsonl',[public_row(x) for x in source]),('inputs.jsonl',development)]:jsonl(a.out/name,values)
    for x in source:
        label={k:x[k] for k in ['question_id','image_id','answer','content_type']}
        (a.out/'source_labels'/(x['question_id']+'.json')).write_text(json.dumps(label,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    # This developer reference file remains local and is not on the deployment allowlist.
    shutil.copyfile(a.from_data/'references.jsonl',a.out/'references.jsonl')
    for name in sorted({x['images'][0] for x in source+development}):
        target=a.out/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(a.from_data/name,target)
    spec=make_protocol(rows(a.out/'source_inputs.jsonl'),rows(a.out/'inputs.jsonl'),a.out)
    a.report.mkdir(parents=True,exist_ok=True)
    (a.report/'PROTOCOL.json').write_text(json.dumps(spec,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    provenance={'upstream_cohort':'data/slake_skill_probe_r44','upstream_manifest':json.loads((a.from_data/'manifest.json').read_text(encoding='utf-8')),
       'new_selection':False,'source_split':'official train,12questions/12distinctimages','development_split':'official validation,27questions/8images',
       'source_annotations':'only current source label opened after corresponding source prediction is saved',
       'development_references_uploaded_to_server':False,'development_previously_exposed':True,
       'patient_independence':'official split + origin/pixel exclusions, no verified patient identities',
       'labels_are_dataset_annotations_not_full_clinical_adjudication':True}
    (a.out/'manifest.json').write_text(json.dumps(provenance,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'prepared_source':12,'development':27,'source_calls':24,'development_calls':54,'total':78,'tools':0}))


if __name__=='__main__':main()
