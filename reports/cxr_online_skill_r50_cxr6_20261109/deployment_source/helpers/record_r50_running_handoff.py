"""Store current lightweight progress and exact unexecuted next-stage commands."""
import json
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];PREP=ROOT/'local_assets/r50_cxr6_preparation';REPORT=ROOT/'reports/cxr_online_skill_r50_cxr6_20261109'
when=datetime.now(timezone.utc).astimezone().isoformat()
path=ROOT/'.aris/IMPROVEMENT_STATE.json';v=json.loads(path.read_text(encoding='utf-8-sig'))
v['updated_at']=when;v['status']='R50_formal_generation_running_R49_final_pushed'
v['R50']['last_lightweight_actual_status']={'recorded_at':when,'controller_pid':3167009,'runner_pid':3167015,
 'controller_alive':True,'runner_alive':True,'dataset':'chexbench','saved':5,'contexts':6,'feedback':5,
 'main_sends':19,'main_responses':19,'meta_sends':0,'windows':0,'SLAKE_or_VQA_started':False,
 'raw_exit':None,'complete':False,'free_bytes':6447026176,'status_transport_native_exit':0}
v['R50']['postprocessing']={'status':'prepared_locally_not_executed','scorer':'experiments/score_online_skill_r50.py',
 'once_helper':'local_assets/collect_and_score_r50_once.py','mirror':'D:/MedRAX_Experiment_Artifacts/online_skill_r50_cxr6_20261109',
 'receipts':'local_assets/r50_cxr6_collection_receipts','report':'reports/cxr_online_skill_r50_cxr6_20261109',
 'new_composition_synthetic_tests':3,'new_composition_tests_elapsed_s':.041,'AST_sources_passed':3,
 'actual_transfers_private_scores_or_evaluation_reference_reads':0,'old_R49_private_score_cli_called':False,
 'note':'copy common functions/metric formulas unchanged; current+M43/M42+R47+saved R49 raw adapters before labels; no old recovery registrations imported',
 'not_yet_model_reviewed':True,'final_complete_result_review_must_include_new_postprocessing':True,
 'exporter_public_verifier_report_finalizer_publisher':'not yet implemented for R50; do not run R49 versions with misleading tags'}
v['next']='R50 running CheX5/618,lastmain19/19,controller3167009/runner3167015alive; SLAKE/VQAqueued. Lightweight statusonly; no additional probes/reviews/stage/queue/producer edits. Allpreflight and health sessionsDONE/consumed. New local R50scorer+oncepull/scorehelperprepared,3newcompositiontests.041s+3ASTpassed; no actual pull/score/reference reads. When eachwhole dataset complete+originalraw0, helper pull --dataset ONCE then score --dataset ONCE; serialize transfers, record live native IDs, use original failures if necessary/no automatic repeat. Final-controls/actual-source afterall3/controller0 only. R50 exporter/publicverifier/reportfinalizer/explicitpublisher still needimplementation; must reflect actualR50six/gate/uniformcontrols and extra savedR49comparator without oldR49failed-case registrations. One actual complete-result/claims review after evidence. Publishall truthfulnegatives/requests/images/resources; no Skillcausal/SOTAclaim. R49fullypushed3ab0a9 and userfinalremoteverifywaived; do not repeatanything.'
path.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
score=PREP/'SCORE_PREPARATION.json';s=json.loads(score.read_text(encoding='utf-8'))
s.update(new_synthetic_composition_tests_passed=3,new_synthetic_elapsed_s=.041,new_postprocessing_sources_AST_passed=3,
 actual_target_reference_reads_or_dataset_scoring_runs=0)
score.write_text(json.dumps(s,indent=2)+'\n',encoding='utf-8')
header=f'''## R50 LATEST RUNNING / POSTPROCESSING PREPARED ({when})

Actual lightweight status: controller3167009alive, CheXrunner3167015alive,5/618saved,6contexts,5feedback,main19sends/19responses,META0,windows0,no exits yet;SLAKE/VQAqueued. ALL848isNOTcomplete. No privateR50scores/pulls have occurred. Stop ordinary progress reports except meaningful completion/failure; monitor may advance local non-producer reporting work while generation runs.

LOCAL ONLY new experiments/score_online_skill_r50.py prepared from unchanged common functions/metrics, no copied old failed-case registrations. Current/directhistorical/R47/savedR49raw adaptation BEFORE label-bearing checks; savedR49usesold adapt_current ONLY, neverold private score CLI. Additional resource/PRESCREEN/Skill/repeated-stop/descriptivegroups. New3synthetic compositiontests passed0.041s (ordering/zero-tools/no-old-score-invocation) and3ASTpassed. R50producerremoteCODEwasNOTmodified orrestarted. These postprocessing sources were prepared after the full initial code review; do not pretend pre-reviewed. Final actual complete-result/claims review must include them. Score preparation receipt recordsno actualscore/referencecalls. Existing actual execution/deployment controls/health remain complete, no more model reviews/probes now.

Ready private once-helper (ROOT READ fullsource, ASTonly, notyetexecuted): local_assets/collect_and_score_r50_once.py. Dmirrornew D:/MedRAX_Experiment_Artifacts/online_skill_r50_cxr6_20261109; receipts local_assets/r50_cxr6_collection_receipts; REPORT reports/cxr_online_skill_r50_cxr6_20261109 (running README/PROTOCOL/INITIAL_ACTUAL_LAUNCH only). It gates remote original ds.exitcode0/generation.exitcode0/fullmembership/manifest fixedcohort, serializes SFTP inventory, no hashes, refusesexisting started/completed markers, preserves failures/partialinventory/noautoretry. Reuses R49 receipt CANONICAL input/ref/R47 paths without old transfers. Do not repeat completedR49inference/private score/transfers/reviews.

AFTER actualwhole dataset generation+runnerraw0, each command ONCE (doNOTexecuteearly):
    python -X utf8 local_assets/collect_and_score_r50_once.py pull --dataset chexbench
    python -X utf8 local_assets/collect_and_score_r50_once.py score --dataset chexbench
Use slake/vqarad similarly aftertheirownraw0. Consume/saveactualnative session IDs; serialize alltransfers. If nativefails, inspectoriginalstderr/receipt/exactstage andpreserveit; no automatic rescore/overwrites/unknownsend retries. Root must inspect any needed exact technical continuation before use, never treat legitimate wronganswers as technicalfails. Dataset score result notify once.

AFTERall3/controlleroriginalraw0:
    python -X utf8 local_assets/collect_and_score_r50_once.py final-controls
    python -X utf8 local_assets/collect_and_score_r50_once.py actual-source
These skip allGEN/healthre-pulls; healthalreadylocalPREP/health once, exactsourcecapturedfrom NEWCODE onlyonce(no models/data). Producerfrozen11runtimefiles+supportarchive; localpostprocesssource isseparate, notinremoteimplementation_files. All keys remain stdin/env, no balance probes.

Still needed WHILE waiting/AFTER completion: R50-specific public exporter/verifier/finalwriter/publisher. Do not blindly runR49versions or mislabelR50asS49. Reuse alreadypublicR49comparators by stablepublicsources/explicitmetadataaliases wherepossible, no repeatdownload/privateR49score. ActualR50rawfull0+one scores+publicreproduction then ONE actual complete-results/claims DeepSeek review, final report and explicit allowlist ordinarypush, stop onexternal mainchanges. Latest known ownmain3ab0a927526e0910328b8db2503ac0fdc0e10036. User doesnotwant post-push remoteverification; neverclaimperformed. Publishcomplete question/options/original/derived images/requests/replies/tools/feedbackSkillsource/allfailures/feesandtime unknowns. Retainnegative outcomes/onlineGT/budget/prompt/EOS/overlap confounds, no Skill-onlycausal/clinical/SOTAclaims. Do nottouch/stageuseropen_questions. Existingmedrax-r47continuescurrentchat, do notduplicateorpausenow.

'''
for rel in ('local_assets/R50_NEW_CHAT_HANDOFF.md','local_assets/cxr_vqa_handoff.md'):
 p=ROOT/rel;p.write_text(header+p.read_text(encoding='utf-8-sig'),encoding='utf-8')
tests='''# Actual R50 checks

- Four new retrieval/arm synthetic unittest methods passed before deployment;
  14 runtime/support/helper AST parses passed. No benchmark/model calls.
- Actual full selected DeepSeek execution review: native99479 exit0,
  scope_complete and ready,40turns; CLI1174294ms, estimatedUSD3.398147,
  not a provider invoice or independent weight identity attestation.
- Three remote label/network-blind cohort/config dryruns passed:618/114/116;
  groups488/30/58, same-image followups130/84/58. No reference files opened,
  model/API calls or tool probes occurred in these dryruns.
- Fresh doc-following agent ran exactly one real health invocation per new
  tool. MedGemma29.55s/LLaVA-Rad123.30s/MedVLM-R115.36s, native0 each,
  one completed generate event, expected revision/nonempty answer/GPU1.
  Old3 were not re-probed; health does not enter production caches/Skill/scores.
- Three new tool archive synthetic tests passed0.143s. First test fixture
  attempt failed before any mocked/real backend call because its AST exec
  namespace omitted __file__; only the fixture was corrected. The actual
  request/stdout/partial-timeout logging delta then received one bounded
  same-reviewer continuation25880, native0/ready/scope_complete/1turn,
  118332ms/CLIestimatedUSD1.023265(notinvoice). Original source retained.
  The reviewer recorded a nonblocking request-before-start crash-resume limit;
  it remains explicit, with hard stop/no automatic resend.
- During generation, three NEW local postprocessing composition tests passed
  0.041s: all raw arms adapt before label-bearing checks; unused tools remain
  zero and health separate; saved R49 comparator invokes raw adaptation only,
  never the old private scorer. Three postprocessing source AST parses passed.
  No actual dataset transfer/private score/evaluation reference read occurred.

Actual full results/public reproduction/claims review are not yet complete.
No previous R49 tests, private scores, pulls or model reviews were repeated.
'''
with (REPORT/'TESTS.md').open('x',encoding='utf-8') as f:f.write(tests)
print(json.dumps({'running_saved':5,'formal_scores_or_pulls':0,'postprocessing_prepared':True,'monitor_must_remain_active':True}))
