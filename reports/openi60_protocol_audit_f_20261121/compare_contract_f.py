"""Compare the F contract with historical raw replies without counterfactual inference."""
import argparse
from collections import Counter
import csv
import json
from pathlib import Path
import sys
from audit_protocol import message_from_response


def compare(root,native,out):
    sys.path[:0]=[str(native),str(native/'code/M5/experiments'),str(native/'code/M5')]
    import toolsets_r54 as base
    sys.path.insert(0,str(Path(__file__).resolve().parent/'repair'))
    from action_protocol_f import decision,ProtocolError
    output=[];summary={}
    for arm in ('B0','L1'):
        manifest=json.loads((root/arm/'manifest.json').read_text(encoding='utf-8'))
        rows={row['question_id']:row for row in manifest['inputs']};counts=Counter()
        for path in sorted((root/arm/'services/calls/R49-AGENT').glob('*/*/response.json')):
            raw,_=message_from_response(json.loads(path.read_text(encoding='utf-8')))
            qid=path.parent.parent.name
            result={'arm':arm,'question_id':qid,'call':int(path.parent.name),'accepted':False,
                    'kind':'','error_stage':'','error':'','proposed_calls_accepted':0}
            try:
                kind,value=decision(raw['content'],rows[qid],base,manifest['runtime'])
                result.update(accepted=True,kind=kind,proposed_calls_accepted=len(value) if kind=='calls' else 0)
                counts['accepted_'+kind]+=1
                if kind=='calls':counts['accepted_call_items']+=len(value)
            except ProtocolError as error:
                result.update(error_stage=error.stage,error=error.code)
                counts['rejected_'+error.stage]+=1
            output.append(result)
        summary[arm]=dict(counts)
    out.mkdir(parents=True,exist_ok=True)
    with (out/'contract_f_historical_replies.csv').open('w',encoding='utf-8-sig',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(output[0]));writer.writeheader();writer.writerows(output)
    report={'coverage':summary,'responses':len(output),'model_calls':0,'tool_calls':0,
            'interpretation':'Contract classification only. Historical follow-up replies are not F predictions or repaired outcomes.'}
    (out/'contract_f_summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,required=True);parser.add_argument('--native',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args();compare(args.root,args.native,args.out)
