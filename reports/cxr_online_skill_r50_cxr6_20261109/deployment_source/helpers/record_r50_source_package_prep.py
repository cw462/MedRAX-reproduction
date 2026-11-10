"""Record local source-package preparation; never invoke the actual assembler."""
import json
from datetime import datetime,timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
PREP=ROOT/'local_assets/r50_cxr6_preparation'
receipt=PREP/'SOURCE_PACKAGE_PREPARATION.json'
assert not receipt.exists(),'preparation_receipt_already_recorded'
when=datetime.now(timezone.utc).astimezone().isoformat()
value={
 'utc':when,'status':'prepared_locally_not_executed',
 'source':'local_assets/capture_r50_publication_sources.py',
 'new_synthetic_tests_passed':3,'tests_elapsed_s':0.000,
 'checks':'quoted credential value-only redaction preserves JSON fields and usage; complete private-key blocks removed and truncated blocks refused; traversal/absolute/backslash source mappings refused',
 'AST_unique_sources_passed':3,'final_single_use_failure_receipt_AST':'passed',
 'publisher_owned_tests':7,'outgoing_test_source_credential_literal':False,
 'actual_source_package_copies_or_Git_or_model_or_metric_or_transfer_calls':0,
 'producer_predictions_or_root_indexes_modified':False,
 'not_yet_model_reviewed':True,
 'actual_command_after_gates':'python -X utf8 local_assets/capture_r50_publication_sources.py',
 'gates':'all3 original dataset/controller raw0, completed once private scores and public reproductions, final-controls and actual-source receipts',
 'outputs':'REPORT/deployment_source/PROVENANCE.md, COPY_MAP.json, explicit actual_CODE/control/helper/preparation/review/proposal/skill copies and outgoing-only credential redaction receipt',
 'single_use':'started/completed/failure receipts; inspect retained partial sources/native stderr on failure, no automatic retry',
 'scope':'exact actual_source files/count; all queue/health/review/protocol configs and job exits; 14 local modules,7 owned tests, explicit helpers, actual native preflight reviews, user proposal and actually-used skill guidance',
 'excluded':'private credential loader, keys, settings, weights, unrelated files, user open_questions; no new image/file/weight hashes',
 'redaction':'only outgoing copies, original producer/predictions/preparation sources retained; field names and source syntax preserved; redacted values never recorded',
 'provenance_limit':'post-execution snapshot, not byte/weight integrity attestation; attachment is proposal, historical pending flags retained; early preparation/fixture failures disclosed without inventing pre-fix byte copies',
 'remaining':'actual once pulls/scores after native completion, final controls/source, public export/reproduction/health, actual source assembly, ONE fresh complete-result DeepSeek review, final writer and explicit normal push',
}
with receipt.open('x',encoding='utf-8') as f:
 json.dump(value,f,ensure_ascii=False,indent=2);f.write('\n')
p=ROOT/'.aris/IMPROVEMENT_STATE.json'
state=json.loads(p.read_text(encoding='utf-8-sig'));state['updated_at']=when
post=state['R50']['postprocessing'];post['source_package_preparation']=value
post['exporter_public_verifier_report_finalizer_publisher']='all4modules and explicit source/provenance assembler PREPARED_LOCAL_NOT_EXECUTED; all actual phases await real completion'
post['publisher_owned_scope_latest']='explicit14newR50modules+7ownedtests+4R50marker-only indexes+newreport tree; initial publisher receipt retained as creation-time6tests snapshot'
state['next']=state['next'].replace('source/provenance package assembler still needed;',
 'source/provenance assembler now PREPARED_LOCAL_NOT_EXECUTED (3newsynthetic+3uniqueAST, actual command/gates in SOURCE_PACKAGE_PREPARATION);')
p.write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
header=f'''## R50 SOURCE/PROVENANCE ASSEMBLER PREPARED, NO ACTUAL COPY ({when})

PRIVATE local_assets/capture_r50_publication_sources.py is now prepared; actual command is `python -X utf8 local_assets/capture_r50_publication_sources.py` ONLY after all3 original dataset/controller raw0, all3 once-private scores/public reproductions, final-controls and actual-source completed receipts. No source package, COPY_MAP or PROVENANCE has been assembled yet. No actual transfers, scores, export/repro, model review or Git action in this preparation. Producer/predictions/root indexes unchanged.

New3 synthetic tests passed0.000s: quoted credential value-only redaction preserves JSON fields/usage; complete private-key blocks are removed and truncated blocks refused; unsafe source mapping paths rejected.3uniqueAST passed plus final single-use failure-receipt AST. Publisher now explicitly owns7tests (new source-package test added),14modules,4R50-only root marker blocks and newreport; original publisher preparation receipt remains historical6tests snapshot. Proposal .patch is an explicit text artifact. No old tests/probes/reviews repeated.

Assembler selects exact actual_CODE receipt filelist/count; controls/controllers/gates/6configs/jobs/raw exits; local modules/tests/helpers, preflight/delta CLI traces, preparation/collection receipts, proposal and actually used Skill documentation. Private credential loader/settings/keys/weights/user open_questions excluded. Sanitizes ONLY outgoing source copies, records redaction counts without values, preserves original experiment/preparation files. Raw Skill docs are .txt copies with attribution; attachment is proposal, historical pending flags and real early local preparation/fixture failures remain disclosed. Post-execution source snapshot, no code/weight/hash attestation. Source package started/completed/failure are single-use; any actual failure leaves partial sources and original native stderr, inspect before bounded technical continuation.

SOURCE_PACKAGE_PREPARATION.json records exact future gates/scope. This code, all post-launch scorer/export/verifier/writer/publisher code and actual resources/failures still require ONE actual fresh complete-results DeepSeek review AFTER848/results/public evidence. No model review now and no fabricated ready markers. All actual post-generation phases remain pending; latest .aris observations override older counts below. Continue existing sole-owner monitor quietly on routine increments.

'''
for relative in ('local_assets/R50_NEW_CHAT_HANDOFF.md','local_assets/cxr_vqa_handoff.md'):
 p=ROOT/relative;p.write_text(header+p.read_text(encoding='utf-8-sig'),encoding='utf-8')
with (ROOT/'reports/cxr_online_skill_r50_cxr6_20261109/TESTS.md').open('a',encoding='utf-8') as f:
 f.write('\n- During generation, three NEW source-package synthetic tests passed0.000s: outgoing value-only credential redaction preserves JSON fields and usage; complete private-key blocks are removed and truncated blocks refused; unsafe source mapping paths rejected. Three unique source AST checks and final single-use failure-receipt AST passed. Explicit publisher scope now includes this seventh owned test. No actual source assembly, transfer, score, export/reproduction, review, Git action or producer/prediction/root-index edit occurred. All new reporting sources still await the final actual complete-result review.\n')
print(json.dumps({'source_package_prepared':True,'actual_copy_model_score_transfer_or_Git_calls':0,'new_synthetic_tests':3,'owned_public_tests':7}))
