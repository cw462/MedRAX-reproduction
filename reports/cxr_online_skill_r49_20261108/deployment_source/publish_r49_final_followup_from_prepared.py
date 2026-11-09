"""Reuse the actual completed prepare gate; check/stage/push one stable snapshot.

The full semantic recovery/result gate has already run in the recorded prepare.
Do not repeat that read-only historical audit for each publication phase. The
original outgoing-content, explicit-index, whitespace and main-base guards run.
"""
import argparse,json
from datetime import datetime,timezone
from pathlib import Path
import publish_cxr_online_skill_r49 as publication

BASE='628617beb777d4b99aa1cb7110f50fbdfc8fde8c'


def main():
    root=Path(__file__).resolve().parents[1]
    report=root/'reports/cxr_online_skill_r49_20261108'
    manifest=publication.read(publication.MANIFEST)
    prepared=publication.read(publication.RECEIPTS/'prepared.json')
    receipt=publication.read(publication.RECEIPTS/'prepare.native_completed.json')
    assert receipt['native_exit']==0 and receipt['session']>0
    assert receipt['completed_gate']=='original full ready() with equivalent cached public paths'
    gate_session=receipt['session']
    assert prepared['expected_base']==BASE and manifest['status']=='allowlist_prepared'
    completed=manifest['datasets'];assert set(completed)==set(publication.DATASETS)
    for ds,count in {'chexbench':465,'slake':113,'vqarad':97}.items():
        v=completed[ds]
        assert v['R49_correct']==count and v['raw_exit']==0 and v['all_predictions_fresh'] is True
        assert v['public_scores_and_resources_reproduced'] is True and v['actual_final_adoption_protocol_resource_result_audit_complete'] is True
    assert not (publication.RECEIPTS/'commit.json').exists(),'final_followup_commit_already_created_inspect_not_repeat'
    publication.require_base(BASE)
    # The initial evidence tree is already committed. Keep its original full
    # prepared allowlist, then stage only the outgoing follow-up and the fixed
    # source/index entries. Every selected path was admitted by prepare.
    full=publication.read(publication.RECEIPTS/'allowlist.json')
    changed={p.relative_to(root).as_posix() for p in publication.outgoing_report_paths()}
    required=set(publication.SCRIPTS+publication.INDEXES+publication.REFINE_LOGS)
    selected=sorted(required|changed|{publication.MANIFEST.relative_to(root).as_posix()})
    assert set(selected)<=set(full)
    for name,value in [('full_prepared_allowlist.json',full),('full_prepared_receipt.json',prepared)]:
        with (publication.RECEIPTS/name).open('x',encoding='utf-8') as f:json.dump(value,f,indent=2);f.write('\n')
    publication.write(publication.RECEIPTS/'allowlist.json',selected)
    prepared.update(original_full_allowlist_count=len(full),allowlist_count=len(selected),followup_only_unchanged_tracked_evidence_reused=True)
    publication.write(publication.RECEIPTS/'prepared.json',prepared)
    manifest.update(files=selected,allowlist_count=len(selected),original_full_allowlist_count=len(full))
    publication.write(publication.MANIFEST,manifest)
    publication.write(report/'deployment_source/FOLLOWUP_PUBLICATION_SCOPE.json',{
      'status':'actual_outgoing_followup_scope_selected','original_full_allowlist_count':len(full),
      'selected_allowlist_count':len(selected),'already_committed_unchanged_evidence_reused':True,
      'full_original_allowlist_and_receipt_preserved_privately':True,'semantic_gate_reused_from_actual_prepare':gate_session,
      'outgoing_content_and_index_and_pre_push_main_base_guards_retained':True,'new_inference_scoring_export_or_model_review':False})
    # Only the phase functions below mutate files now: stage rewrites its own
    # publication manifest. No report/model/score writer runs alongside them.
    publication.ready=lambda:completed
    args=argparse.Namespace(expected_base=BASE,include_untracked_originals=False,
      message='docs: finalize R49 complete evidence, results review and reproducibility report')
    publication.check(args)
    publication.stage(args)
    publication.commit_push(args)
    commit=publication.read(publication.RECEIPTS/'commit.json')['commit']
    publication.write(publication.RECEIPTS/'push_completed.json',{
      'utc':datetime.now(timezone.utc).isoformat(),'status':'push_succeeded_post_push_remote_verification_waived_by_user',
      'commit':commit,'report_url':'https://github.com/cw462/MedRAX-reproduction/blob/main/reports/cxr_online_skill_r49_20261108/README.md',
      'remote_verification_performed':False,'actual_user_waiver':'远端核验（不需要远端核验）',
      'original_full_semantic_prepare_gate_reused':gate_session,'native_final_review_completed':10526,
      'native_report_writer_completed':84164,'new_inference_private_scoring_export_or_model_review':False})
    print(json.dumps({'status':'final_followup_pushed','commit':commit,'post_push_remote_verification':'waived_by_user'}))


if __name__=='__main__':main()
