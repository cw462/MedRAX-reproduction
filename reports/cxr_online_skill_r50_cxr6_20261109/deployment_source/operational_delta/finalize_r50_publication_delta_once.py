"""Package the actual same-session Git-ignore delta; reuse the checked whitelist."""
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'local_assets'))
from publish_r50_user_stopped import PREP, REPORT, BASE, phase, put, text, read
from publish_cxr6_r50 import text_has_secret, local_reference
from capture_r50_publication_sources import sanitize


def main():
    trace=PREP/'result_review_publish_delta'
    raw,start,exit_record=read(trace/'stdout.json'),read(trace/'started.json'),read(trace/'exit.json')
    initial=read(REPORT/'RESULT_CLAIM_METADATA.json')
    assert exit_record['exit_code']==0 and start['fresh'] is False and not raw.get('is_error')
    assert raw['session_id']==initial['session_id']==start['session_id']
    assert raw.get('duration_ms',0)>0 and raw.get('num_turns',0)>0
    assert raw.get('modelUsage') and all('deepseek' in name.lower() for name in raw['modelUsage'])
    decoder=json.JSONDecoder();found=[]
    for match in re.finditer(r'\{',raw['result']):
        try:value,_=decoder.raw_decode(raw['result'][match.start():])
        except ValueError:continue
        if isinstance(value,dict) and {'scope_complete','publication_blockers','audit_scope'}<=set(value):found.append(value)
    verdict=found[-1]
    assert verdict['scope_complete'] is True and verdict['publication_blockers']==[]
    assert verdict['audit_scope']==initial['audit_scope']
    metadata=dict(verdict,native_exit_code=0,fresh=False,same_completed_review_session=True,
        session_id=raw['session_id'],modelUsage=raw['modelUsage'],duration_ms=raw['duration_ms'],
        turns=raw['num_turns'],CLI_estimated_USD=raw.get('total_cost_usd'),provider_invoice=False,
        scope='Git add-f only for explicitly allowlisted ignored report logs; ordinary push unchanged')
    documents=[]
    for name,value in [('RESULT_PUBLISH_DELTA_METADATA.json',metadata),('RESULT_PUBLISH_DELTA_RAW_CLI.json',raw)]:
        target=REPORT/name;put(target,value);documents.append(target)
    target=REPORT/'RESULT_PUBLISH_DELTA_REVIEW.md';text(target,raw['result']);documents.append(target)
    delta=REPORT/'deployment_source/operational_delta'
    latest=delta/'publish_r50_user_stopped.py';assert latest.is_file();documents.append(latest)
    helper=delta/'finalize_r50_publication_delta_once.py'
    body,redactions=sanitize(Path(__file__).read_text(encoding='utf-8'));text(helper,body);documents.append(helper)
    note=delta/'PROVENANCE.json'
    put(note,{'reviewed_change':'One git add-f flag for ignored files in the exact validated whitelist; no force-push.',
        'actual_latest_publisher':'publish_r50_user_stopped.py','same_session_review':'../../RESULT_PUBLISH_DELTA_METADATA.json',
        'initial_readiness_snapshot_files':21536,'recheck_scope':'New delta source/document/metadata only; previous complete snapshot reused.',
        'actual_remote_CODE_count_unchanged':264,'scores_or_raw_outputs_changed':False,
        'metadata_packaging_helper_credential_redactions':redactions})
    documents.append(note)
    readme=REPORT/'README.md'
    with readme.open('a',encoding='utf-8') as handle:
        handle.write('\nPublication staging adjustment: repository ignore rules omit some report logs. The same DeepSeek session reviewed the sole executable delta, `git add -f` restricted to the exact literal-NUL allowlist; ordinary push/base/parent/index protections remain. [Delta review](RESULT_PUBLISH_DELTA_REVIEW.md) · [actual delta metadata](RESULT_PUBLISH_DELTA_METADATA.json) · [latest publisher source](deployment_source/operational_delta/publish_r50_user_stopped.py). The prior full readiness snapshot is reused; only these added packaging records are checked separately.\n')
    plan_path=PREP/'publication_allowlist.json';plan=read(plan_path)
    assert plan['base']==BASE and len(plan['files'])==21536
    put(PREP/'publication_allowlist.original_snapshot.json',plan)
    additions=[]
    for path in [*documents,readme]:
        assert path.is_relative_to(REPORT) and not path.is_symlink() and path.stat().st_size<100_000_000
        value=path.read_text(encoding='utf-8-sig');assert '\0' not in value and not text_has_secret(value)
        if path.suffix=='.json':json.loads(value)
        relative=path.relative_to(ROOT).as_posix()
        if relative not in plan['files']:additions.append(relative)
    for match in re.finditer(r'!?\[[^\]]*\]\(([^\s)]+)\)',readme.read_text(encoding='utf-8')):
        local_reference(match.group(1),readme)
    plan['files']=sorted(set(plan['files'])|set(additions))
    plan['bounded_post_prepare_delta']={'source':'publication_allowlist.original_snapshot.json','initial_files':21536,
        'added_files':additions,'only_existing_file_changed':readme.relative_to(ROOT).as_posix(),
        'same_review_session':raw['session_id'],'delta_native_exit':0,'full_score_review_or_readiness_not_repeated':True}
    plan_path.write_text(json.dumps(plan,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return {'files':len(plan['files']),'added_delta_files':len(additions),'native_delta_review_exit':0,
        'same_review_session':raw['session_id'],'previous_readiness_snapshot_reused':True}


if __name__=='__main__':print(json.dumps(phase('publication_delta_accept',main),ensure_ascii=False))
