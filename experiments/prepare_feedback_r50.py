"""Convert label JSONL to separate feedback files. Run before the inference process."""
import argparse
from pathlib import Path
from cxr_online_primitives_r50 import rows
from online_memory_r50 import safe_qid,save_once

def main():
 p=argparse.ArgumentParser();p.add_argument('--references',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
 records=rows(a.references);ids=[safe_qid(x['question_id']) for x in records]
 if len(set(ids))!=len(ids):raise ValueError('duplicate_reference_id')
 for r in records:
  if not isinstance(r.get('answer'),str) or not r['answer'].strip():raise ValueError('answer_must_be_canonical_string')
  save_once(a.out/(r['question_id']+'.json'),{k:r[k] for k in ('question_id','answer','answer_text') if k in r})
 print({'reference_files':len(records),'model_calls':0})
if __name__=='__main__':main()
