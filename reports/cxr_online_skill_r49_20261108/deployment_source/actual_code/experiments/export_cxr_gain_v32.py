"""Allowlisted v3.2 pair/source evidence, without changing inference artifacts."""
import argparse
from collections import Counter
import json
from pathlib import Path

from export_cxr_vqa_extension import RequestEvidencePublisher, export, restore_images
from export_cxr_vqa_toolsets import CALL_FILES
from export_vote_phase import read


def export_pair(data,run,historical,out):
    export(data,run,run/'offline_score',out,['M-AS','M-A'],historical)
    old=read(out/'publication_manifest.json')
    pub=RequestEvidencePublisher(out,data/'manifest.json')
    pub.copy_json(run/'gain_v3_run.json',out/'frozen_run.json')
    gpu=Path(__file__).resolve().parents[1]/'configs/cxr_vqa_tool_worker_gpu.json'
    if gpu.is_file():pub.copy_json(gpu,out/'tool_worker_gpu.json')
    for path in sorted((run/'offline_analysis').iterdir()):
        if path.suffix in ['.json','.jsonl']:pub.copy_json(path,out/path.name)
    for arm in ['M-AS','M-A']:
        values=[read(p) for p in sorted((run/'retrieval'/arm).glob('*.json'))]
        pub.emit(out/f'retrieval_{arm}.jsonl',values,jsonl=True)
        values=[read(p) for p in sorted((run/'mechanical_format'/arm).glob('*/*.json'))]
        pub.emit(out/f'mechanical_format_{arm}.jsonl',values,jsonl=True)
    pub.emit(out/'publication_manifest.json',{'files':sorted(set(old['files'])|{p.relative_to(out).as_posix() for p in pub.files}),
        'redactions':dict(Counter(old['redactions'])+pub.redactions)})


def export_source(root,out):
    if out.exists():raise FileExistsError(out)
    source=root/'source_learning'
    pub=RequestEvidencePublisher(out,root/'private_input/source_roster.json')
    copies=[(source/'source_v2_manifest.json','source_v2_manifest.json'),
            (source/'bank_M-S-v2.candidate.json','candidate_bank.json'),
            (source/'bank_M-S-v2.reviewed.json','reviewed_bank.json'),
            (root/'private_input/source_content_review.json','source_content_review.json'),
            (root/'private_input/source_learning_inputs.json','source_learning_inputs.json'),
            (root/'private_input/source_roster.json','source_roster.json'),
            (root/'bank_review.json','bank_review.json'),(root/'dev_verified.json','dev_verified.json'),
            (root/'preflight/summary.json','tool_preflight.json'),
            (root/'preflight/summary.initial_failed.json','tool_preflight_initial_failed.json')]
    for original,name in copies:pub.copy_json(original,out/name)
    for path in sorted((source/'calls/M-S').glob('*/*/request.json')):
        call={'case_id':path.parent.parent.name,'ordinal':path.parent.name}
        for name in CALL_FILES:
            p=path.parent/name
            if p.exists():call[p.stem]=restore_images(read(p),source)
        call.get('started',{}).pop('reserved',None)
        call.get('result',{}).pop('ledger_remaining_proxy_cny',None)
        pub.emit(out/'calls'/call['case_id']/(call['ordinal']+'.json'),call)
    pub.emit(out/'image_assets.json',[{k:v for k,v in item.items() if k!='target'}|{'path':pub.rel(item['target'],out/'image_assets.json')} for item in list(pub.assets.values())])
    pub.emit(out/'publication_manifest.json',{'files':sorted(p.relative_to(out).as_posix() for p in pub.files),'redactions':dict(pub.redactions)})


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--data',type=Path);p.add_argument('--run',type=Path);p.add_argument('--historical-url');p.add_argument('--source-root',type=Path);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args()
    if a.source_root:export_source(a.source_root,a.out)
    elif a.data and a.run and a.historical_url:export_pair(a.data,a.run,a.historical_url,a.out)
    else:p.error('Choose source root or complete pair arguments')
