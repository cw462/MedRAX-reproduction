"""Record local publication-code preparation; never execute export or metrics."""
import json
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[1];PREP=ROOT/'local_assets/r50_cxr6_preparation'
receipt=PREP/'PUBLICATION_CODE_PREPARATION.json';assert not receipt.exists()
when=datetime.now(timezone.utc).astimezone().isoformat()
value={'utc':when,'status':'public_exporter_and_verifier_prepared_not_executed',
 'exporter':'experiments/export_online_skill_r50.py','verifier':'experiments/verify_public_online_skill_r50.py',
 'new_synthetic_tests':3,'elapsed_s':.059,'AST_sources_passed':4,
 'checks':'depth mapping reused for distinct parents; raw terminal outranks cached answer and cached label fields rejected; all3 public bundles adapt before labels',
 'actual_dataset_exports_public_reproductions_private_scores_transfers_or_probes':0,
 'producer_source_or_predictions_modified':False,'not_yet_model_reviewed':True,
 'historical_comparison':'raw answer/status plus raw terminal projection, links to complete already-public R49 case/archive; no old private score CLI or re-download',
 'health_input':'final-controls will copy only the specifically named training_xmlab120.jpg once; old health outputs already local and never re-pulled',
 'ordinary_publisher':'unchanged image storage/sanitizer, existing asset naming only; no new hash validation',
 'remaining':'final report writer and explicit allowlist publisher; complete results review and actual export/reproduction only after full queue/scoring'}
with receipt.open('x',encoding='utf-8') as f:json.dump(value,f,ensure_ascii=False,indent=2);f.write('\n')
p=ROOT/'.aris/IMPROVEMENT_STATE.json';v=json.loads(p.read_text(encoding='utf-8-sig'));v['updated_at']=when
v['R50']['postprocessing']['public_evidence_code_preparation']=value
v['R50']['postprocessing']['exporter_public_verifier_report_finalizer_publisher']='exporter/verifier PREPARED_LOCAL_NOT_EXECUTED with3newsynthetic/4AST; finalwriter/explicitpublisher still need implementation'
v['next']=v['next'].replace('R50 exporter/publicverifier/reportfinalizer/explicitpublisher still needimplementation;',
 'R50 exporter/verify modules now PREPARED_LOCAL_NOT_EXECUTED (3newsynthetic.059s/4AST), finalwriter/explicitpublisher still needimplementation;')
p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
header=f'''## R50 PUBLICATION CODE PREPARED, NO ACTUAL EXPORT ({when})

New local experiments/export_online_skill_r50.py and verify_public_online_skill_r50.py are PREPARED, NOT EXECUTED. They reuse unchanged publisher/commonmetrics, not R49case recovery declarations. Public raw comparison projection contains ONLY answer/status and actual raw terminal fields before labels, plus full_existing_public_archive links to complete already-public R49case/comparison sources. No newR49private score/transfer. Verifier lazily adapts all3bundles; explicit image-link existence/membership only, no byte/hash checks. Depth+target mapping cache avoids priorR49repeated Path.resolve costs. New3synthetic tests passed0.059s and4ASTpassed (the two modules, newtest, updatedcollector); no actualdatasetexport/repro/metrics/transfer/inference/API or real benchmark label read. These post-launch reporting sources are NOT model-reviewed yet; finalactual fullresults/claims review must include them.

Collector final-controls now ALSO downloads one exact new health input training_xmlab120.jpg to Dmirror/health_source once AFTERall3/controllerraw0, so health images can be published; it does NOT re-pullhealthoutputs orR49. Actualhealthoutputs already PREP/health pulled once. Dataset export requires fullprivate scores and originalfinalcontrollerraw0, never early. NewCLI has modes dataset and health. `--reference-dir` may reuse existing R49public evidence/<dataset>/reference_vault; exporter requires exact current feedback answer/answer_text match. Use R49publicevidence source pointer for fullarchive links. PrivateR49rawcomparisons use saved Dmirror GEN; no oldprivate scorer call. Health export uses PREP/health and the once-collected training image, entirely separate from currentproduction resources.

AFTERall3/completed scoring/finalcontrols/source (commands NOT executed):
    python -X utf8 experiments/export_online_skill_r50.py dataset --data <saved_R49_receipt.canonical_data> --run <R50_Dmirror/generation/ds> --scores reports/cxr_online_skill_r50_cxr6_20261109/results/<ds> --references <saved_R49_receipt.references> --reference-dir reports/cxr_online_skill_r49_20261108/evidence/<ds>/reference_vault --out reports/cxr_online_skill_r50_cxr6_20261109/evidence/<ds> --dataset <ds> --r49-run <saved_R49_receipt.run> --r49-public-evidence reports/cxr_online_skill_r49_20261108/evidence/<ds> --jobs <R50_Dmirror/jobs> [CheXrequires --r47-frozen and --r47-run from saved receipt]
    python -X utf8 experiments/verify_public_online_skill_r50.py --evidence reports/cxr_online_skill_r50_cxr6_20261109/evidence/<ds> --out reports/cxr_online_skill_r50_cxr6_20261109/public_reproduction/<ds>
    python -X utf8 experiments/export_online_skill_r50.py health --health local_assets/r50_cxr6_preparation/health --image D:/MedRAX_Experiment_Artifacts/online_skill_r50_cxr6_20261109/health_source/training_xmlab120.jpg --out reports/cxr_online_skill_r50_cxr6_20261109/evidence/health
Eachonce whengatesactuallymet; preserveany failure/source/native exit, no blindretries. Finalreportwriter/explicitpublisher still needimplementation; do not claimthispreparation actual results/publicrepro/GitHubrelease. No productioncodechanges, probes, extraarms, modelreviews, pulls orscores thisheartbeat. Existingactualstatsin.aris takeprecedence overolder countsbelow.

'''
for rel in ('local_assets/R50_NEW_CHAT_HANDOFF.md','local_assets/cxr_vqa_handoff.md'):
 p=ROOT/rel;p.write_text(header+p.read_text(encoding='utf-8-sig'),encoding='utf-8')
with (ROOT/'reports/cxr_online_skill_r50_cxr6_20261109/TESTS.md').open('a',encoding='utf-8') as f:
 f.write('\n- During generation, three NEW public-evidence synthetic tests passed0.059s: distinct document parents reuse the correct depth mapping; raw terminal extraction takes precedence over cached strict answer and rejects cached label fields; all three public historical bundles adapt before any labels. Four publication-source AST parses passed. No actual export/public reproduction/private scoring/transfer/probe or benchmark label read was executed; final result review still must include these reporting modules.\n')
print(json.dumps({'public_modules_prepared':2,'new_synthetic_tests_passed':3,'actual_exports_or_scores':0,'producer_modified':False}))
