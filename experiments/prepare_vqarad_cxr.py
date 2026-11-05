"""Keep official OSF VQA-RAD questions and image groups without inventing a test split."""
import argparse
import json
from pathlib import Path
from prepare_slake_cxr import write_jsonl


def prepare(source,out,review=None,split=None):
    rows=json.loads((source/'vqarad.json').read_text(encoding='utf-8-sig'))
    out.mkdir(parents=True,exist_ok=True)
    write_jsonl(out/'all_questions.jsonl',rows)
    review=json.loads(review.read_text(encoding='utf-8')) if review else {}
    selected=[];refs=[];opened=[]
    for row in rows:
        # CHEST is a candidate label, never sufficient evidence of radiography.
        if row['image_organ']!='CHEST':continue
        image=row['image_name'];item=review.get(image,{})
        if item.get('actual_modality')!='CXR' or item.get('review_status')!='confirmed':continue
        record={'question_id':'vqarad_'+str(row['qid']),'question':row['question'],'images':['images/'+image],
                'image_id':image,'source':{'dataset':'VQA-RAD','osf_node':'89kps','original_qid':row['qid'],
                 'evaluation_annotation':row['evaluation'],'split':split or 'unassigned'}}
        if row['answer_type']=='CLOSED':
            selected.append(record);refs.append({'question_id':record['question_id'],'answer':str(row['answer']),'answer_type':'CLOSED','image_id':image})
        else:opened.append(dict(record,answer=str(row['answer']),answer_type=row['answer_type']))
    write_jsonl(out/'inputs.jsonl',selected);write_jsonl(out/'references.jsonl',refs);write_jsonl(out/'open_questions_for_later.jsonl',opened)
    manifest={'name':'VQA-RAD-CXR-Closed','source':'https://osf.io/89kps/','questions':len(selected),'images':len({r['image_id'] for r in selected}),
              'split':split or 'not established','official_test_claim':bool(split),'run_ready':bool(split) and bool(selected),
              'note':'The official evaluation field describes annotation evaluation, not a train/test split. No official test set is inferred from it.',
              'image_review_required':True,'license':'verify official OSF registration metadata and Readme before publication'}
    (out/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return manifest


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--out',type=Path,default=Path('data/vqarad_cxr'))
    p.add_argument('--image-review',type=Path);p.add_argument('--verified-split-description');a=p.parse_args()
    print(json.dumps(prepare(a.source,a.out,a.image_review,a.verified_split_description),ensure_ascii=False))
