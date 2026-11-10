"""Keep official OSF VQA-RAD questions and image groups without inventing a test split."""
import argparse
import hashlib
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
        if row['phrase_type'] not in ['test_freeform','test_para']:continue
        image=row['image_name'];item=review.get(image,{})
        if item.get('actual_modality')!='CXR' or item.get('review_status')!='confirmed':continue
        record={'question_id':'vqarad_'+str(row['qid']),'question':row['question'],'images':['images/'+image],
                'image_id':image,'source':{'dataset':'VQA-RAD','osf_node':'89kps','original_qid':row['qid'],
                 'phrase_type':row['phrase_type'],
                 'split':'official test_freeform/test_para (OSF Readme section 3)'}}
        if row['answer_type']=='CLOSED':
            selected.append(record);refs.append({'question_id':record['question_id'],'answer':str(row['answer']),'answer_type':'CLOSED','image_id':image})
        else:opened.append(dict(record,answer=str(row['answer']),answer_type=row['answer_type']))
    write_jsonl(out/'inputs.jsonl',selected);write_jsonl(out/'references.jsonl',refs);write_jsonl(out/'open_questions_for_later.jsonl',opened)
    manifest={'name':'VQA-RAD-CXR-Closed','source':'https://osf.io/89kps/','questions':len(selected),'images':len({r['image_id'] for r in selected}),
              'split':'official phrase_type test_freeform/test_para','official_test_claim':True,'run_ready':bool(selected),
              'split_source':'Official OSF Readme.docx section 3 explicitly defines Test_freeform and Test_paraphrase as test data; JSON uses test_para.',
              'note':'The evaluation field describes clinical annotation review, not a split. Original test paraphrase relationships are preserved, and all same-image questions share one bootstrap cluster.',
              'image_review_required':True,'image_review':'107 CHEST originals inspected; confirmed radiographs, not CT',
              'license':'CC0 1.0 Universal (official OSF node license 563c1cf88c5e4a3877f9e96c)',
              'source_json_sha256':hashlib.sha256((source/'vqarad.json').read_bytes()).hexdigest(),
              'question_ids':[x['question_id'] for x in selected],
              'open_test_questions_kept_separate':len(opened)}
    (out/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return manifest


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--out',type=Path,default=Path('data/vqarad_cxr'))
    p.add_argument('--image-review',type=Path);p.add_argument('--verified-split-description');a=p.parse_args()
    print(json.dumps(prepare(a.source,a.out,a.image_review,a.verified_split_description),ensure_ascii=False))
