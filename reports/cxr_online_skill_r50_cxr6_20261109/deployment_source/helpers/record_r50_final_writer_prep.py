"""Record prepared formatter and metadata contract; no actual final write."""
import json
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[1];PREP=ROOT/'local_assets/r50_cxr6_preparation'
p=PREP/'FINAL_WRITER_PREPARATION.json';assert not p.exists()
when=datetime.now(timezone.utc).astimezone().isoformat()
value={'utc':when,'status':'prepared_not_executed','source':'local_assets/finalize_r50_report.py',
 'new_synthetic_tests_passed':3,'tests_elapsed_s':.0,'checks':'negative claim verdict accepted; missing actual scope/native exit/reused preflight session rejected; negative/zero/positive differences retained',
 'AST_unique_sources_passed':3,'final_writer_single_use_marker_AST':'passed after marker addition',
 'actual_final_writer_scoring_transfer_or_inference_calls':0,'producer_modified':False,'not_yet_model_reviewed':True,
 'review_metadata_contract':{'status':'completed only from actual CLI','native_exit_code':'actual0','fresh':'actualTrue',
  'session_id':'actual new session distinct from preflight53d8f871-7ad7-4c18-b8d6-fc7b623c7a1a',
  'scope_complete':'actualTrue','audit_scope':['online_feedback_and_Skill_protocol','request_resource_accounting','complete_results_and_claims'],
  'publication_blockers':'actual empty list; favorable claim_supported not required','modelUsage':'actual DeepSeek names/usage; duration_ms/turns positive'},
 'expected_inputs':'all3 completed once-score receipts and exact public reproduction/exports, final controller/runner raw0, one source/control capture, actual new3 public health evidence, actual fresh result review and claims',
 'outputs':'848fullcase pages, CASE_INDEX, RESULT_TABLES, RESOURCE_SUMMARY, REPRODUCTION, finalREADME; preserve runningREADME and launchPROTOCOL',
 'source_or_metric_recomputation':'none; uses saved metrics only',
 'collector_timing_change':'final-controls stores already-listed original remote job file mtimes for approximate elapsed durations; no extra probes/hash/billing queries',
 'remaining':'explicit allowlist publisher; actual post-generation pipeline remains gated'}
with p.open('x',encoding='utf-8') as f:json.dump(value,f,ensure_ascii=False,indent=2);f.write('\n')
state=ROOT/'.aris/IMPROVEMENT_STATE.json';v=json.loads(state.read_text(encoding='utf-8-sig'));v['updated_at']=when
v['R50']['postprocessing']['final_writer_preparation']=value
v['R50']['postprocessing']['exporter_public_verifier_report_finalizer_publisher']='exporter/verifier/finalwriter prepared locally, no actual exports/repros/final write; explicitpublisher still needs implementation'
v['next']=v['next'].replace('finalwriter/explicitpublisher still needimplementation;',
 'finalwriter now PREPARED_LOCAL_NOT_EXECUTED (3newsynthetic/3uniqueAST; exact actual-review schema in FINAL_WRITER_PREPARATION), explicitpublisher still needimplementation;')
state.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
header=f'''## R50 FINAL WRITER PREPARED, NOT EXECUTED ({when})

New PRIVATE local_assets/finalize_r50_report.py prepared, no actualfinalwrite/score/transfer/inference/labels. New3synthetic formatter tests passed (negativeclaim-supported:no is publishable, missing actualnative/scope/freshsession rejected, negative/zero/netchange tables preserved),3uniqueASTpassed; finalmarker-only AST also passed. Producer code/predictions unchanged. It reuses saved metrics, creates848fullcasepages+CASE_INDEX/RESULT_TABLES/RESOURCE_SUMMARY/REPRODUCTION/README, preserveslaunchPROTOCOL unchanged and runningREADME as historicalsnapshot. Comparebundle loadedonceperdataset, not repeatedly percase. Single-use final_report.started/completed markers preventblindrepetition.

DoNOTinvoke untilall3once-private scores+all3actualpublicrepro+all3/controlleroriginalraw0+actualsource/controlcapture+publicnew3health+ONE actualfresh fullresultsDeepSeekreview. `RESULT_CLAIM_METADATA.json` must be materialized fromactualCLI, NOT writtenasreadyinadvance: status=completed,native_exit_code=actual0,fresh=actualTrue,session_id=new distinct from initial53d8f871-7ad7-4c18-b8d6-fc7b623c7a1a,scope_complete=actualTrue,audit_scope includes EXACT online_feedback_and_Skill_protocol / request_resource_accounting / complete_results_and_claims, actualDeepSeekmodelUsage/duration_ms/turns, publication_blockers=actualemptylist. claim_supported yes/partial/no allallowed; no favorable-score gate. Also actual RESULT_CLAIM_REVIEW.md/RAW_CLI.json/CLAIMS_FROM_RESULTS.md required. Future actual review prompt must request these scope names and include all newpostprocessing/export/verifier/writer/publisher sources and complete results/resources; no newreviewnow.

Collector final-controls additionally records already-listed remote jobs' original st_mtime in actual_job_file_mtime_seconds (no extraCPU/GPU/hash/billingprobe). Writer uses originalpid/exitmtimes and controller.started.utc to report approximate per-dataset/whole-job durations with explicitsecond precision, separate from exact requestreceipt elapsed/providerbilling. Missing clocks/costs remainunknown. Collector has still notexecutedanypull/score/control/sourcecapture.

Explicit white-list publisher stillneedsimplementation; export/verifier/finalwriter onlyprepared, notactualcompleted. No modelreview ofthesereportingmodulesyet; finalactual complete-resultreview mustinclude them. Do not rerun older tests/reviews/probes or runR49publisher underwrongS50tags. Latestactual progress in.aris takesprecedence overoldercountsbelow.

'''
for rel in ('local_assets/R50_NEW_CHAT_HANDOFF.md','local_assets/cxr_vqa_handoff.md'):
 f=ROOT/rel;f.write_text(header+f.read_text(encoding='utf-8-sig'),encoding='utf-8')
with (ROOT/'reports/cxr_online_skill_r50_cxr6_20261109/TESTS.md').open('a',encoding='utf-8') as f:
 f.write('\n- During generation, three NEW final-formatter synthetic tests passed: negative result-claim support remains publishable; absent real native/scope/fresh review is rejected; negative/zero/positive table differences are retained. Three unique source AST checks and the final single-use-marker AST passed. Actual final writer was not invoked and does not recompute any metric. Original remote job-file mtimes will be captured during the already-planned final-controls transfer for approximate wall durations, not provider billing.\n')
print(json.dumps({'writer_prepared':True,'new_synthetic_tests':3,'actual_final_write':False,'explicit_publisher_still_pending':True}))
