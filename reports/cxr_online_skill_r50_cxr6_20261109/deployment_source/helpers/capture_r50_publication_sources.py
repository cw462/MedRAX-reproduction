"""Assemble explicit local source/provenance copies after actual completion.

No SSH, inference, scoring, health, tests, Git or checksums. Private credential
loaders/keys/weights are never selected; only outgoing copies may be redacted.
"""
from datetime import datetime,timezone
import json
from pathlib import Path,PurePosixPath
import re

from publish_cxr6_r50 import ROOT,REPORT,SOURCE_NAMES,TEST_NAMES,SECRET,CREDENTIAL_FIELD,text_has_secret
from r50_recovery_evidence import job_completion

PREP=ROOT/'local_assets/r50_cxr6_preparation'
MIRROR=Path('D:/MedRAX_Experiment_Artifacts/online_skill_r50_cxr6_20261109')
RECEIPTS=ROOT/'local_assets/r50_cxr6_collection_receipts'
DEST=REPORT/'deployment_source'
PRIVATE_KEY_BLOCK=re.compile(r'-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----')
PRIVATE_KEY_BEGIN=re.compile(r'-----BEGIN [A-Z ]*PRIVATE KEY-----')
HELPERS=('prepare_r50_cxr6_code.py','deploy_cxr6_r50.py','prepare_r50_execution_review.py','accept_r50_execution_review.py',
 'aris_deepseek_readonly_review.py','prepare_r50_archive_delta_review.py','accept_r50_archive_delta.py',
 'deploy_r50_archive_delta_once.py','prepare_r50_postprocessing.py','collect_and_score_r50_once.py',
 'finalize_r50_report.py','publish_cxr6_r50.py','capture_r50_publication_sources.py',
 'record_current_r50_launch_preparation.py','record_r50_actual_launch.py','record_r50_running_handoff.py',
 'record_r50_publication_code_prep.py','record_r50_final_writer_prep.py','record_r50_publisher_prep.py',
 'record_r50_source_package_prep.py','record_r50_monitor_status.py',
 'inspect_r50_chex_failure_20261110.py','inspect_r50_medvlm_load_failure.py',
 'recover_r50_medvlm_pre_generation_once.py','inspect_r50_retry_outcome.py',
 'record_r50_actual_technical_stop.py','continue_r50_after_known_tool_failure.py',
 'record_r50_actual_technical_continuation.py',
 'inspect_r50_chex_second_failure_once.py','recover_r50_medgemma_load_once.py','record_r50_second_failure.py',
 'inspect_r50_second_retry_outcome_once.py','continue_r50_after_second_load_failure.py',
 'continue_r50_second_load_corrected_once.py','record_r50_second_continuation.py',
 'inspect_r50_chex_third_failure_once.py','capture_r50_third_failure_artifacts_once.py','record_r50_third_stop.py',
 'prepare_r50_paper_failure_amendment.py','launch_r50_paper_failure_amendment_once.py',
 'status_r50_and_strong_skill.py',
 'inspect_r50_intermediate_skill_status_once.py','score_r50_interim_user_requested_once.py',
 'analyze_r50_frozen_skill_effect_once.py',
 'deploy_cxr_action_r41.py','deploy_cxr_online_skill_r49.py','deploy_v12.py')
SKILL_ROOT=Path('C:/Users/cheng/.agents/skills')
SKILLS=('run-experiment/SKILL.md','experiment-bridge/SKILL.md','research-review/SKILL.md','paper-read/SKILL.md',
 'shared-references/compute-env-contract.md','shared-references/reviewer-backends.md','shared-references/review-tracing.md')


def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def put(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


def relative_path(value):
    p=PurePosixPath(value)
    if p.is_absolute() or '..' in p.parts or '\\' in value or ':' in value:raise ValueError('unsafe_source_copy_relative_path')
    return p


def sanitize(text):
    """Selected outgoing source only, preserving quoted field names and syntax."""
    text,blocks=PRIVATE_KEY_BLOCK.subn('[REDACTED PRIVATE KEY]',text)
    if PRIVATE_KEY_BEGIN.search(text):raise ValueError('incomplete_private_key_block_requires_explicit_exclusion')
    text,tokens=SECRET.subn('[REDACTED]',text);fields=0
    def quoted(match):
        nonlocal fields
        value=match.group(1)
        if value.startswith(('[REDACTED]','<','YOUR_','os.environ','getenv(')):return match.group(0)
        fields+=1;a,b=match.start(1)-match.start(),match.end(1)-match.start()
        return match.group(0)[:a]+'[REDACTED]'+match.group(0)[b:]
    text=CREDENTIAL_FIELD.sub(quoted,text)
    if text_has_secret(text):raise ValueError('credential_literal_remains_after_outgoing_redaction')
    return text,{'private_key_blocks':blocks,'credential_tokens':tokens,'quoted_credential_fields':fields}


def complete_gate():
    source=read(RECEIPTS/'actual_source.completed.json');controls=read(RECEIPTS/'final_controls.completed.json')
    if source.get('status')!='completed' or controls.get('status')!='completed':raise ValueError('actual_source_and_controls_required')
    job_completion(MIRROR/'jobs')
    for ds in ('chexbench','slake','vqarad'):
        if read(RECEIPTS/(ds+'.score.completed.json')).get('status')!='completed':raise ValueError('completed_once_score_required:'+ds)
        public=read(REPORT/'public_reproduction'/ds/'summary.json')
        if public.get('matches_published_primary_scores_and_extractions') is not True or public.get('matches_published_resources') is not True:
            raise ValueError('actual_public_reproduction_required:'+ds)
    return source


def main():
    if DEST.exists() or (PREP/'source_package.started.json').exists():raise ValueError('source_package_already_invoked_inspect')
    source=complete_gate();when=datetime.now(timezone.utc).isoformat()
    put(PREP/'source_package.started.json',{'utc':when,'source_capture':str(RECEIPTS/'actual_source.completed.json'),
      'scope':'explicit source/control/helper/proposal/skill/receipt copies; no model/data/credential directories'})
    DEST.mkdir();entries=[];redactions=[]
    def copy(src,published,kind,source_relative):
        relative_path(published);relative_path(source_relative)
        if not src.is_file() or src.is_symlink():raise ValueError('explicit_source_missing_or_symlink:'+source_relative)
        body=src.read_text(encoding='utf-8-sig');cleaned,counts=sanitize(body)
        if src.suffix=='.json':json.loads(cleaned)
        elif src.suffix=='.jsonl':
            for line in cleaned.splitlines():
                if line.strip():json.loads(line)
        target=DEST/published;target.parent.mkdir(parents=True,exist_ok=True)
        with target.open('x',encoding='utf-8') as f:f.write(cleaned)
        entry={'kind':kind,'source_relative':source_relative,'published':published,
          'source_capture_time':'post_execution_or_local_preparation_snapshot_not_hash_attested',
          'credential_redactions':counts}
        entries.append(entry)
        if any(counts.values()):redactions.append({'published':published,'counts':counts,'original_preserved_privately':True})
    for relative in source['files']:
        relative_path(relative);copy(MIRROR/'actual_code_source'/relative,'actual_CODE/'+relative,'actual_CODE',relative)
    control_names=['queue_controller.py','health_controller.py','EXECUTION_REVIEW_READY.json','EVALUATION_PROTOCOL.json']
    if (MIRROR/'jobs/technical_continuation001.json').exists():control_names+=['queue_controller_recovery001.py']
    if (MIRROR/'jobs/technical_continuation002.json').exists():control_names+=['queue_controller_recovery002.py']
    if (MIRROR/'jobs/protocol_amendment003.json').exists():control_names+=['queue_controller_amendment003.py','protocol_amendment003.json','amendment003_user_approval.json']
    for name in control_names:
        copy(MIRROR/name,'controls/'+name,'control',name)
    for folder in ('configs','jobs'):
        for path in sorted((MIRROR/folder).iterdir()):
            if path.is_file() and not path.name.startswith('.') and path.suffix in ('.json','.py','.log','.pid','.exitcode'):
                relative=folder+'/'+path.name;copy(path,'controls/'+relative,'control',relative)
    for name in SOURCE_NAMES:copy(ROOT/'experiments'/name,'local_reporting_and_runtime/experiments/'+name,'local_source','experiments/'+name)
    for name in TEST_NAMES:copy(ROOT/'tests'/name,'local_reporting_and_runtime/tests/'+name,'local_test','tests/'+name)
    for name in HELPERS:copy(ROOT/'local_assets'/name,'helpers/'+name,'helper',name)
    for path in sorted(PREP.iterdir()):
        if path.is_file() and path.suffix in ('.json','.jsonl','.md','.txt','.log'):
            copy(path,'preparation/'+path.name,'preparation_record',path.name)
    for path in sorted((PREP/'support').glob('*.py')):copy(path,'preparation/support/'+path.name,'support_history','support/'+path.name)
    for path in sorted((PREP/'failures').rglob('*')):
        if path.is_file() and path.suffix in ('.json','.jsonl','.md','.txt','.log','.py','.pid','.exitcode'):
            relative=path.relative_to(PREP).as_posix()
            copy(path,'preparation/'+relative,'actual_R50_failure_history',relative)
    for path in sorted((PREP/'amendment003').rglob('*')):
        if path.is_file() and path.suffix in ('.json','.jsonl','.md','.txt','.log','.py'):
            relative=path.relative_to(PREP).as_posix()
            copy(path,'preparation/'+relative,'actual_R50_protocol_amendment',relative)
    for path in sorted((PREP/'user_requested_interim_accuracy_20261110').rglob('*')):
        if path.is_file() and path.suffix in ('.json','.jsonl','.md','.txt','.log','.py'):
            relative=path.relative_to(PREP).as_posix()
            copy(path,'preparation/'+relative,'explicit_user_requested_interim_score_history',relative)
    for path in sorted(RECEIPTS.iterdir()):
        if path.is_file() and path.suffix in ('.json','.log','.txt'):
            copy(path,'collection_receipts/'+path.name,'collection_receipt',path.name)
    proposal=ROOT/'local_assets/r50_cxr6_user_package_20261109/R50_CXR6'
    for path in sorted(proposal.iterdir()):
        if path.is_file() and path.suffix in ('.md','.py','.json','.patch'):
            copy(path,'user_proposal/'+path.name,'user_proposal',path.name)
    for relative in SKILLS:
        # Plain-text original documentation preserves its relative references
        # without pretending the entire installed ARIS package is vendored.
        copy(SKILL_ROOT/relative,'skill_sources/'+relative+'.txt','skill_document',relative)
    for relative in ('001-code','002-archive-delta'):
        trace=ROOT/'.aris/traces/experiment-bridge/run_20261109_r50_cxr6_001'/relative
        for path in sorted(trace.iterdir()):
            if path.is_file() and path.suffix in ('.json','.md','.txt','.log'):
                copy(path,'actual_preflight_reviews/'+relative+'/'+path.name,'actual_review_record',relative+'/'+path.name)
    put(DEST/'CREDENTIAL_REDACTION_RECEIPT.json',{'scope':'selected outgoing source copies only','files':redactions,
      'private_originals_or_predictions_modified':False,'redacted_values_not_recorded':True,'new_model_or_hash_validation':False})
    put(DEST/'COPY_MAP.json',{'utc':when,'files':entries,'count':len(entries),
      'actual_CODE_count':sum(v['kind']=='actual_CODE' for v in entries),
      'credentials_weights_unrelated_user_files_excluded':True,'byte_or_weight_integrity_attestation':False})
    (DEST/'PROVENANCE.md').write_text('''# Actual R50 sources and provenance

The map lists actual NEW CODE source/config files captured once after execution,
actual RUN controllers/config/job records, local owned runtime/reporting modules,
preparation/support history, native review records and once-collection receipts.
This is a post-execution snapshot, without code/image/file/weight hash validation
or independent model identity attestation. It is not a pre-launch integrity seal.

Selected outgoing credential literals alone are redacted with a receipt; private
originals and completed predictions remain unchanged. Private credential loaders,
SSH configuration, keys, settings, model weights, unrelated files and user
open_questions are not selected. The omitted credential interface is
user_supplied_key(), returning the user's own key; SSH connect/ROOT come from the
operator's private transport. Actual keys travel via stdin/environment and are
not part of publication.

The user_proposal directory is the attachment, not proof of approval/readiness.
Its apply_fix.py targets the archived R49 file and was NOT used on that file;
actual R50 uses isolated modules. Its old claimed tests are not this run's checks.
The skill_sources plain-text files preserve installed guidance and attribution;
relative references describe that installation, not a complete vendored ARIS
package. User instructions override their generic hash/rebuild/extra-run defaults.
Actual R50 reused warm environments and tested only the three added tools once.

Preparation documents retain their creation-time pending flags. Actual readiness,
health, launch, exits and results are in the corresponding later receipts. Only
the native code-review and bounded archive-delta sessions are copied here; the
fresh complete-results review is stored separately at the report root after its
actual execution. This assembler never runs a model, test, scorer, transfer or Git.

Actual R50 later stopped after104 saved CheX questions when MedVLM-R1 tokenizer
loading failed with no generate event. The masked protobuf error, original
controller/CheX exit1, unchanged single successful tool retry (including poor
text), and explicit attributed continuation are retained. Original producer
modules and completed predictions were not edited. The native loader's
intermittency cause remains unknown; no model/environment installation or
rebuild was performed. Both physical attempts count in resource accounting.
The postprocessing-only r50_recovery_evidence module describes this actual
failure; it was not part of the originally deployed11 producer modules.

A second, distinct MedGemma tokenizer JSON-load failure later stopped the first
continuation after183 saved questions, again before generate. Its one explicit
unchanged retry generated once and was retained without clinical/quality checks.
Original and recovery001 native1 files remain; recovery002 has separate native
records. The first recovery002 helper failed a wrong old filename guard before
adoption/launch, then an explicit corrected helper reused the saved tool result.
Both helper sources and the nonzero launch receipt are retained; no claim of a
separate raw-byte stderr file where only the original tool transcript was saved.

Recovery002 subsequently stopped after316 saved questions: MAIRA actually
generated300tokens without EOS and its original parser rejected an unclosed
object. This third failed generation was never regenerated, repaired or made
into a successful cache. Its original output, parser exception and physical
resource use remain failed. A further artifact-copy helper failed after11files
when it treated a directory as a file; source/partial receipt/files remain.

After the paper's explicit appendix A.4 error-message mechanism was explained,
the user approved adopting it. New r50_failure_observation.py,
r50_services_amended.py and r50_run_amended.py extend actual execution, while the
original11producer files remain. They deliver terminal errors as failed tool
observations uniformly from CheX317 and from SLAKE/VQA1, without changing EOS,
300token/model/environment settings or saved predictions. Separate receipts,
native amended jobs and final exit files preserve every original/intermediate1.
The resulting stream is amendedR50 with code/protocol/time/order confounds,
not an unchanged producer or exact original-paper experiment reproduction.

The local reporting copy of r50_failure_observation.py subsequently gained an
optional reader hook so public reproduction uses the same image-path
normalization as the common scorer. This pure postprocessing compatibility
change was not uploaded to running CODE; the separately captured actual_CODE
copy remains the authority for the executed three-module amendment. Default
failure-delivery behavior and physical production outputs were not changed.

Some early local preparation fixes (the pre-deployment ARM residual and the
__file__ omission in an AST-only synthetic test fixture) are recorded in the chat
tool transcript/review notes, not claimed as retained byte-attested pre-fix files.
No real model request or prediction resulted from either fixture/preparation error.
The synthetic fixture's first native failure and subsequent corrected test success
remain explicit in TESTS.md and actual archive-delta reviewer request/reply.
''',encoding='utf-8')
    put(PREP/'source_package.completed.json',{'status':'completed','utc':datetime.now(timezone.utc).isoformat(),
      'files':len(entries),'actual_CODE_count':sum(v['kind']=='actual_CODE' for v in entries),
      'redacted_outgoing_files':len(redactions),'new_models_metrics_transfers_or_Git_calls':0})
    print(json.dumps({'source_package_copied':len(entries),'outgoing_redacted_files':len(redactions),'new_model_or_score_calls':0}))


if __name__=='__main__':
    try:main()
    except Exception as exc:
        failure=PREP/'source_package.failure.json'
        if (PREP/'source_package.started.json').exists() and not (PREP/'source_package.completed.json').exists() and not failure.exists():
            put(failure,{'status':'failed','utc':datetime.now(timezone.utc).isoformat(),
              'exception_type':type(exc).__name__,'error':str(exc),'automatic_retry':False,
              'partial_outgoing_source_and_originals_preserved':True})
        raise
