"""Mechanical Q response extraction. NO reference answers or model calls.
Run on the published stage3/D-Q and M-Q calls in the SAME invocation.
The output is a secondary format sensitivity artifact, NOT a rewritten primary score.
"""
import argparse
import json
from pathlib import Path
import re

def unique(pairs):
    result={}
    for k,v in pairs:
        if k in result: raise ValueError('duplicate_json_key')
        result[k]=v
    return result

def normalize(raw, ids):
    if not isinstance(raw,str): raise ValueError('non_text_response')
    text=raw.strip()
    m=re.fullmatch(r'```(?:json)?\s*\n(.*?)\n```',text,re.S|re.I)
    if m: text=m[1]
    obj=json.loads(text,object_pairs_hook=unique)
    if isinstance(obj,dict) and set(obj)=={'answers'}: obj=obj['answers']
    if not isinstance(obj,dict) or set(obj)!=set(ids): raise ValueError('question_id_map_mismatch')
    for v in obj.values():
        if not isinstance(v,dict) or set(v)!={'answer','reason'}: raise ValueError('answer_schema')
        if not all(isinstance(x,str) for x in v.values()) or not v['answer'].strip() or len(v['answer'])>300:
            raise ValueError('answer_type_or_length')
    return obj

def main():
    p=argparse.ArgumentParser();p.add_argument('--published',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args()
    if a.out.exists(): raise ValueError('new_output_required')
    outputs={};audit=[]
    for arm in ('D-Q','M-Q'):
        records=[]
        files=sorted((a.published/'joint_groups'/arm).glob('*.json'))
        if not files: raise ValueError('no_groups:'+arm)
        for f in files:
            group=json.loads(f.read_text(encoding='utf-8'));ids=list(group['answers'])
            calls=json.loads((a.published/'calls'/arm/f.name).read_text(encoding='utf-8'))
            err=None
            try:
                choice=calls[-1]['response']['choices'][0]
                message=choice['message']
                if message.get('tool_calls') or choice.get('finish_reason') not in ('stop',None): raise ValueError('nonfinal_response')
                answers=normalize(message.get('content'),ids)
            except (ValueError,TypeError,KeyError,IndexError) as exc:
                answers={};err=str(exc)
            for qid in ids:
                v=answers.get(qid)
                records.append({'question_id':qid,'group_id':group['group_id'],'arm':arm,
                                'answer':v['answer'] if v else None,'reason':v['reason'] if v else None,
                                'status':'completed' if v else 'missing_mechanical_format'})
            audit.append({'arm':arm,'group_id':group['group_id'],'recovered':len(answers),'error':err})
        outputs[arm]=records
    a.out.mkdir(parents=True)
    for arm,records in outputs.items():
        (a.out/('predictions_'+arm+'.jsonl')).write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in records),encoding='utf-8')
    (a.out/'format_audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({arm:{'total':len(r),'parsed':sum(x['answer'] is not None for x in r)} for arm,r in outputs.items()}))

if __name__=='__main__': main()
