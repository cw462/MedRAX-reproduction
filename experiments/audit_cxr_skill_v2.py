"""Preview every retrieval without API calls or target references."""
import argparse
from collections import Counter
import json
from pathlib import Path
from cxr_skill_v2 import load_bank,select

def main():
    p=argparse.ArgumentParser();p.add_argument('--config',type=Path,required=True);p.add_argument('--data',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();cfg=json.loads(a.config.read_text());rt=json.loads(Path(cfg['runtime']).read_text())
    spec=rt['arms']['M-S'];tools=rt['arms']['M']['tools'];cards=load_bank(spec['bank_path'],spec['bank_sha256'],tools)
    traces=[]
    for line in (a.data/'inputs.jsonl').read_text().splitlines():
        row=json.loads(line)
        _,trace=select(row,cards,tools,**spec['retrieval']);traces.append(trace)
    if a.out.exists():raise ValueError('new_audit_output_required')
    a.out.mkdir(parents=True)
    (a.out/'retrieval.jsonl').write_text(''.join(json.dumps(t,ensure_ascii=False)+'\n' for t in traces),encoding='utf-8')
    summary={'questions':len(traces),'injected':sum(bool(t['selected_ids']) for t in traces),
             'selected_frequency':dict(Counter(x for t in traces for x in t['selected_ids'])),
             'paid_calls':0,'references_read':False}
    (a.out/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8');print(json.dumps(summary))

if __name__=='__main__':main()
