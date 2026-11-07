"""Allowlisted R4.1 source/development evidence export; never runs inference."""
import argparse,json
from pathlib import Path
from export_cxr_vqa_extension import RequestEvidencePublisher,restore_images
from export_cxr_vqa_toolsets import CALL_FILES

def export_source(root,out):
    if out.exists():raise FileExistsError(out)
    source=root/'source_learning'
    if not (source/'bank_r41.reviewed.json').exists():raise ValueError('reviewed_source_bank_required')
    pub=RequestEvidencePublisher(out,root/'private_input/source_roster.json')
    copies=[(source/name,name) for name in ['source_v2_manifest.json','candidate_bank_r41.json','candidate_bank_r41.reviewed_edits.json','reviews.json','source_content_review.json','bank_r41.reviewed.json']]
    copies +=[(root/'private_input/source_learning_inputs.json','source_learning_inputs.json'),(root/'private_input/source_roster.json','source_roster.json'),(root/'bank_review.json','bank_review.json')]
    for path,name in copies:pub.copy_json(path,out/name)
    usage=[];unknown=[]
    for path in sorted((source/'calls/M-S').glob('*/*/request.json')):
        call={'case_id':path.parent.parent.name,'ordinal':path.parent.name}
        for name in CALL_FILES:
            p=path.parent/name
            if p.exists():call[p.stem]=restore_images(json.loads(p.read_text()),source)
        call.get('started',{}).pop('reserved',None)
        call.get('result',{}).pop('ledger_remaining_proxy_cny',None)
        if 'started' in call and 'response' not in call:unknown.append(call['case_id'])
        if call.get('result',{}).get('usage'):usage.append(call['result']['usage'])
        pub.emit(out/'calls'/call['case_id']/(call['ordinal']+'.json'),call)
    metrics={'source_requests':len(usage),'unknown_sent_source_ids':unknown,'known_input_tokens':sum(v.get('prompt_tokens',0) or 0 for v in usage),'known_output_tokens':sum(v.get('completion_tokens',0) or 0 for v in usage)}
    metrics['proxy_cny']=(metrics['known_input_tokens']*4+metrics['known_output_tokens']*12)/1000000
    pub.emit(out/'resources.json',metrics)
    pub.emit(out/'image_assets.json',[{k:v for k,v in item.items() if k!='target'}|{'path':pub.rel(item['target'],out/'image_assets.json')} for item in list(pub.assets.values())])
    pub.emit(out/'publication_manifest.json',{'files':sorted(p.relative_to(out).as_posix() for p in pub.files),'redactions':dict(pub.redactions)})

def export_development(root,out):
    if out.exists():raise FileExistsError(out)
    run=root/'dev'
    for arm in ['M-S41','M-C41']:
        if not (run/f'complete_{arm}.json').exists():raise ValueError('both_source_dev_arms_required')
    if not (root/'dev_verified.json').exists():raise ValueError('actual_dev_request_proof_required')
    pub=RequestEvidencePublisher(out,root/'private_input/source_roster.json')
    for name in ['complete_M-S41.json','complete_M-C41.json','r41_run.json','protocol.json']:
        pub.copy_json(run/name,out/name)
    pub.copy_json(root/'dev_verified.json',out/'dev_verified.json')
    pub.copy_json(root/'dev_input/image_path_recovery.json',out/'image_path_recovery.json')
    pub.copy_json(root/'dev_input/selection.json',out/'selection.json')
    pub.copy_json(run/'runtime_full_M-S41.json',out/'runtime_full_M-S41.json')
    pub.copy_json(run/'runtime_full_M-C41.json',out/'runtime_full_M-C41.json')
    pub.emit(out/'initial_failure.txt',(root/'jobs/dev.log').read_text())
    metrics={}
    for arm in ['M-S41','M-C41']:
        calls=[]
        for path in sorted((run/'calls'/arm).glob('*/*/request.json')):
            call={'question_id':path.parent.parent.name,'ordinal':path.parent.name}
            for name in CALL_FILES:
                p=path.parent/name
                if p.exists():call[p.stem]=restore_images(json.loads(p.read_text()),run)
            call.get('started',{}).pop('reserved',None)
            call.get('result',{}).pop('ledger_remaining_proxy_cny',None)
            calls.append(call);pub.emit(out/'calls'/arm/call['question_id']/(call['ordinal']+'.json'),call)
        usages=[v['result']['usage'] for v in calls if v.get('result',{}).get('usage')]
        metrics[arm]={'main_sends':len(calls),'unknown_sends':sum('response' not in v for v in calls),'input_tokens':sum(v.get('prompt_tokens',0) or 0 for v in usages),'output_tokens':sum(v.get('completion_tokens',0) or 0 for v in usages)}
        metrics[arm]['proxy_cny']=(metrics[arm]['input_tokens']*4+metrics[arm]['output_tokens']*12)/1000000
        pub.emit(out/f'predictions_{arm}.jsonl',[json.loads(p.read_text()) for p in sorted((run/'predictions'/arm).glob('*.json'))],jsonl=True)
        pub.emit(out/f'tool_selections_{arm}.jsonl',[json.loads(p.read_text()) for p in sorted((run/'tool_selections'/arm).glob('*/*.json'))],jsonl=True)
    for path in sorted((run/'tool_cache').glob('*/result.json')):
        pub.copy_json(path,out/'tool_results'/path.parent.name/'result.json')
        raw=path.parent/'artifacts/raw.json'
        if raw.exists():pub.copy_json(raw,out/'tool_results'/path.parent.name/'raw.json')
    pub.emit(out/'resources.json',metrics)
    pub.emit(out/'image_assets.json',[{k:v for k,v in item.items() if k!='target'}|{'path':pub.rel(item['target'],out/'image_assets.json')} for item in list(pub.assets.values())])
    pub.emit(out/'publication_manifest.json',{'files':sorted(p.relative_to(out).as_posix() for p in pub.files),'redactions':dict(pub.redactions)})

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source-root',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--development',action='store_true');a=p.parse_args()
    (export_development if a.development else export_source)(a.source_root,a.out)
