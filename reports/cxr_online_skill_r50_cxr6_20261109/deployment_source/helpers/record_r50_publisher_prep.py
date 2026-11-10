"""Record prepared publication code, never invoke a Git/publication phase."""
import json
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];PREP=ROOT/'local_assets/r50_cxr6_preparation'
receipt=PREP/'PUBLISHER_PREPARATION.json';assert not receipt.exists()
when=datetime.now(timezone.utc).astimezone().isoformat()
value={'utc':when,'status':'prepared_not_executed','source':'local_assets/publish_cxr6_r50.py',
 'new_synthetic_tests_passed':3,'checks':'own R50 source/report scope including r50_baseline_controls admitted; user open_questions/oldR49/private/weights rejected; secret patterns checked; unrelated index text preserved',
 'AST_unique_sources_passed':3,'final_copy_map_gate_AST':'passed after completed source-map requirements',
 'actual_Git_prepare_check_stage_commit_push_calls':0,'actual_inference_score_export_review_or_transfer_calls':0,
 'producer_or_root_indexes_modified':False,'not_yet_model_reviewed':True,
 'phases':['prepare','check','stage','commit-push'],'expected_main_base':'3ab0a927526e0910328b8db2503ac0fdc0e10036',
 'source_scope':'explicit14newR50modules+6ownedtests+4R50marker-only indexes+newreport tree; no whole private data/run staging',
 'readiness':'actual fresh resultreview/full finalwriter/all848casepages/3nativeonce scores+publicrepro/finalraw0/sourcecontrol captures/new3health/publicsource map',
 'reused_readiness_gate':'prepare once; sequential check/stage/commit reuse the prepared stable report snapshot, no re-running old recovery audits',
 'checks_only':'outgoing credentials/JSON/links/image-link existence/file sizes, explicit literal-NUL index membership, parent/pre-push main guards',
 'post_push_remote_verification':'waived by user; no extra final remote check, no fake verified label',
 'source_map_contract':{'shape':'COPY_MAP.json object with files list; every entry has kind/source_relative/published',
  'actual_CODE':'one mapping per exact source.completed.files entry/count, required11producer modules+base worker/extended backend/GPU config present',
  'control':'RUN queue_controller.py, health_controller.py, EXECUTION_REVIEW_READY.json, EVALUATION_PROTOCOL.json; all6 configs incl order; jobs/controller.started.json and controller+3dataset.exitcode',
  'published':'safe path relative to REPORT/deployment_source; all listed source copies actually present'},
 'still_needed':'source/receipt/proposal/skill provenance package assembler before actual full-result review; all real post-generation phases remain gated'}
with receipt.open('x',encoding='utf-8') as f:json.dump(value,f,ensure_ascii=False,indent=2);f.write('\n')
p=ROOT/'.aris/IMPROVEMENT_STATE.json';v=json.loads(p.read_text(encoding='utf-8-sig'));v['updated_at']=when
post=v['R50']['postprocessing'];post['publisher_preparation']=value
post['exporter_public_verifier_report_finalizer_publisher']='all4modules PREPARED_LOCAL_NOT_EXECUTED; actual source/provenance package assembler still needed, actual phases await real completion'
v['next']=v['next'].replace('explicitpublisher still needimplementation;',
 'explicitpublisher now PREPARED_LOCAL_NOT_EXECUTED (3newsynthetic/3uniqueAST; strict COPY_MAP/source-control contract in PUBLISHER_PREPARATION), source/provenance package assembler still needed;')
p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
header=f'''## R50 EXPLICIT PUBLISHER PREPARED, NO ACTUAL GIT ACTION ({when})

PRIVATE local_assets/publish_cxr6_r50.py nowprepared. New3synthetic tests passed: ownR50source/report-only allowlist (including prefix-named r50_baseline_controls.py); excludeuseropen_questions/oldR49/private/weights; credentialliteralpattern catches whileusage/REDACTED kept; R50index replacement preservesalloutsideusertext.3uniqueASTpassed plusfinalCOPY_MAPgate AST. NO actualprepare/check/stage/commit/push/Git or model/metric/export/transfer/review called. Producer/predictions and rootindexfiles unchanged. Newfinalwriter can now insert/replaceonly R50_CXR6 markerblocks into4rootindexes AFTERallactualgates; testdidnotwriteactualindexes.

PublisherCLI actualfuturephases: prepare (defaultknownownbase3ab0a927526e0910328b8db2503ac0fdc0e10036), check, stage, commit-push. Prepare requiresactual finalwriter marker/848casepages/fresh complete-resultreview/3realprivateonce/publicrepro/finalnative0/actualsource+controls+new3publichealth/sourcePROVENANCE+COPY_MAP. Reuses savedgate on same stable snapshot for laterphases; no repeatedfullrecoveryaudits. One literal-NUL git add, exactindexmembership, source/index whitespace and pre-pushmainbase checks. No force/reset/merge. Userpost-push remoteverificationwaived; nofinalverify method, do notclaimindependentremoteverified. UnexpectedmainchangeSTOP. OutsideR50indexedits causeSTOP; preserveuserwork, useconcrete isolation only ifthisactuallyoccurs. No broadprivateRUN/datastaging. FreezeR50report between contentcheck/stage/commit.

REMAINING source-package assembler mustbe prepared/actually runAFTERall3native0 and final-controls/actual-source collection, BEFOREonefresh complete-resultreview. `REPORT/deployment_source/PROVENANCE.md`+COPY_MAP.json areNOTyetcreated, do notfake/skipgates. ExactCOPY_MAPcontract: objectwith fileslist entries kind/source_relative/published. actual_CODE entries source_relative set/count MUSTexactlymatch actual_source.completed.json files (11producer modules+base/worker/extendedbackend/GPUconfig required, post3modules arelocalreportcode notremotedeployed). publishedsafe pathrelative todeployment_source. control entries mustinclude queue_controller.py,health_controller.py,EXECUTION_REVIEW_READY.json,EVALUATION_PROTOCOL.json, configs/runtime.json,protocol.json,chexbench/slake/vqarad.json,chexbench_order.json, jobs/controller.started.json/controller.exitcode/3dataset.exitcode. Alltargetfilespresent. Otherexplicit helpers/proposal/metadata/reviews/skill-source/credential-redaction receipts canbeadditional kinds. Preserveactual code/cfg/time/CLI/failure sources, excludecredentials/weights/unrelated/useropen_questions. Snapshotprovenance isafterexecution, no byte/hash/weightintegrityattestation. Already-public R49archives shouldbe linked/reused ratherthan re-pulled/re-scored. Privatecredentialloader/envkeys mustnotbe copied; publishinterface/provenance only. Ifcopiedoldfixture sources triggeroutgoingcredential gate, redactonlyoutgoingcopies andrecordscope, never editoldexperiment source/predictions or blindly sanitizer-break code.

Do notexecuteanynew phaseearly orrepeatoldertests/reviews/probes. Newpublisher/index code waspreparedafterinitialcodereview; finalactual complete-results reviewmustinclude ALLreportingsources. Later single-report/allowlist publication only fromactual savedresults, negative/zeroSkill valid. Latest.aris actualprogress supersedesoldercountsbelow.

'''
for rel in ('local_assets/R50_NEW_CHAT_HANDOFF.md','local_assets/cxr_vqa_handoff.md'):
 f=ROOT/rel;f.write_text(header+f.read_text(encoding='utf-8-sig'),encoding='utf-8')
with (ROOT/'reports/cxr_online_skill_r50_cxr6_20261109/TESTS.md').open('a',encoding='utf-8') as f:
 f.write('\n- During generation, three NEW publication/index synthetic tests passed: explicit R50 scope includes the prefix-named controls module and excludes user open_questions/private/oldR49/weights; outgoing secret patterns detect literals while preserving usage/redaction markers; replacing the R50 index block preserves all outside text. Three unique source AST checks plus final COPY_MAP gate AST passed. No actual Git/publication/finalwriter/model/scoring action or root index edit occurred. Actual source/controls/provenance package must still be assembled after native completion and included in the final result review.\n')
print(json.dumps({'publisher_prepared':True,'actual_Git_or_writer_calls':0,'new_synthetic_tests':3,'source_package_assembler_still_pending':True}))
