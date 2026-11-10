"""Format completed R50 saved results after public reproduction/fresh review.

No scoring, inference, transfers, Git or hash validation. Negative results are
publishable; only actual completion/evidence/review gates are required.
"""
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import re
import sys

ROOT=Path(__file__).resolve().parents[1]
REPORT=ROOT/'reports/cxr_online_skill_r50_cxr6_20261109'
PREP=ROOT/'local_assets/r50_cxr6_preparation'
RECEIPTS=ROOT/'local_assets/r50_cxr6_collection_receipts'
MIRROR=Path('D:/MedRAX_Experiment_Artifacts/online_skill_r50_cxr6_20261109')
sys.path.insert(0,str(ROOT/'experiments'))
from r50_recovery_evidence import job_completion,generation_completion,QID,RECOVERY,QID2,RECOVERY2
ARM='M43-IM-GT-S50-CXR6'
DATASETS={'chexbench':(618,'M43',466,465),'slake':(114,'M43',108,113),'vqarad':(116,'M42',100,97)}
REVIEW_SCOPE={'online_feedback_and_Skill_protocol','request_resource_accounting','complete_results_and_claims'}
METRIC_FIELDS=('dataset','arm','questions','all_questions_fresh','mode','arms','comparisons','skill_hit_questions',
 'same_image_hit_questions','windows','resources','references_read_after_all_arms_adapted','R49_saved_comparator_provenance',
 'R50_combined_changes','R50_uniform_inherited_controls','repeated_no_progress_by_saved_status','descriptive_groups','native_generation_completion')
INDEXES=('README.md','findings.md','MANIFEST.md','reports/cxr_author_alignment_20261108/TABLES.md')
INDEX_START='<!-- R50_CXR6_START -->'
INDEX_END='<!-- R50_CXR6_END -->'


def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def rows(p):return [json.loads(x) for x in Path(p).read_text(encoding='utf-8-sig').splitlines() if x.strip()]
def put(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def text(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(v.rstrip()+'\n',encoding='utf-8')
def cell(v):return str(v).replace('|','\\|').replace('\r','').replace('\n','<br>')
def link(target,document):return os.path.relpath(target,document.parent).replace('\\','/')


def replace_index_block(original,block):
    if original.count(INDEX_START)!=original.count(INDEX_END) or original.count(INDEX_START)>1:
        raise ValueError('ambiguous_R50_index_block')
    pattern=re.compile(re.escape(INDEX_START)+r'.*?'+re.escape(INDEX_END),re.S)
    return pattern.sub(lambda _:block,original) if INDEX_START in original else original.rstrip()+'\n\n'+block+'\n'


def write_root_indexes(loaded):
    for relative in INDEXES:
        path=ROOT/relative
        block=INDEX_START+'\n## R50 CXR6: complete single-arm results\n\n'+result_table(loaded)+'\n\n'
        block+=f"[Complete report]({link(REPORT/'README.md',path)}) · [all cases]({link(REPORT/'CASE_INDEX.md',path)}) · [resources]({link(REPORT/'RESOURCE_SUMMARY.json',path)})\n\n"
        block+='Six-model menu plus applicability gate with onlineGT and inherited uniform controls; no Skill-only causal, clinical or official SOTA claim.\n'+INDEX_END
        text(path,replace_index_block(path.read_text(encoding='utf-8-sig'),block))


def validate_review(meta,initial_session):
    if (meta.get('status')!='completed' or meta.get('native_exit_code')!=0 or meta.get('is_error')
        or meta.get('scope_complete') is not True or not REVIEW_SCOPE<=set(meta.get('audit_scope',[]))
        or not meta.get('session_id') or meta['session_id']==initial_session
        or meta.get('fresh') is not True or not meta.get('modelUsage')
        or not all('deepseek' in name.lower() for name in meta['modelUsage'])
        or (meta.get('duration_ms') or 0)<=0 or (meta.get('turns') or 0)<=0
        or meta.get('publication_blockers')!=[]):
        raise ValueError('actual_fresh_complete_scope_DeepSeek_result_review_required')
    # claim_supported may be yes, partial or no. A favorable score is not a gate.
    return meta


def complete_gate():
    initial=read(PREP/'CODE_REVIEW_METADATA.json')
    review=validate_review(read(REPORT/'RESULT_CLAIM_METADATA.json'),initial['session_id'])
    for name in ('RESULT_CLAIM_REVIEW.md','RESULT_CLAIM_RAW_CLI.json','CLAIMS_FROM_RESULTS.md'):
        if not (REPORT/name).is_file() or not (REPORT/name).stat().st_size:raise ValueError('actual_result_review_artifact_required:'+name)
    controls=read(RECEIPTS/'final_controls.completed.json');source=read(RECEIPTS/'actual_source.completed.json')
    if controls.get('status')!='completed' or source.get('status')!='completed':raise ValueError('actual_final_controls_and_source_required')
    jobs=MIRROR/'jobs'
    job_completion(jobs)
    loaded={}
    for ds,(n,baseline,expected,old49) in DATASETS.items():
        receipt=read(RECEIPTS/(ds+'.score.completed.json'));s=read(REPORT/'results'/ds/'summary.json')
        p=read(REPORT/'public_reproduction'/ds/'summary.json');e=REPORT/'evidence'/ds;exported=read(e/'scores/summary.json')
        names={baseline,'R49_online_GT_Skill'}|({'R47_online_GT'} if ds=='chexbench' else set())
        if (receipt.get('status')!='completed' or receipt.get('native_exit')!=0 or receipt.get('n')!=n
            or receipt.get('correct')!=s['arms'][ARM]['correct'] or s.get('arm')!=ARM or s.get('questions')!=n
            or s.get('all_questions_fresh') is not True or set(s['comparisons'])!=names
            or s['arms'][baseline]['correct']!=expected or s['arms']['R49_online_GT_Skill']['correct']!=old49
            or any(s.get(k)!=p.get(k) or s.get(k)!=exported.get(k) for k in METRIC_FIELDS)
            or p.get('matches_published_primary_scores_and_extractions') is not True or p.get('matches_published_resources') is not True
            or p.get('new_inference_calls')!=0 or p.get('private_run_paths_required') is not False):
            raise ValueError('completed_once_scored_publicly_reproduced_fixed_dataset_required:'+ds)
        if ds=='chexbench' and s['arms']['R47_online_GT']['correct']!=468:raise ValueError('fixed_R47_count')
        native=job_completion(jobs,ds);generation_native=generation_completion(e)
        if native['original_exit']!=generation_native['original_exit'] or s.get('native_generation_completion')!=generation_native:
            raise ValueError('actual_original_and_continuation_native_history_required:'+ds)
        inputs=rows(e/'inputs.jsonl');details=read(REPORT/'results'/ds/'per_question.json')
        if len(details)!=n or [r['question_id'] for r in details]!=[r['question_id'] for r in inputs]:raise ValueError('whole_question_index_required:'+ds)
        publication=read(e/'publication_manifest.json')
        if publication.get('scope')!='complete_scored_online_stream' or publication.get('arm')!=ARM:raise ValueError('complete_public_evidence_required:'+ds)
        loaded[ds]={'summary':s,'inputs':inputs,'details':details,'evidence':e}
    health=read(REPORT/'evidence/health/publication_manifest.json')
    if health.get('scope')!='current_new3_health_evidence_only' or health.get('new_inference_calls')!=0:
        raise ValueError('actual_new3_health_public_evidence_required')
    return loaded,review,controls,source


def result_table(loaded):
    lines=['| Dataset | R50 correct/N | Micro % | Macro % | Historical direct | vs direct corrected/harmed/net | vs R49 corrected/harmed/net |',
      '|---|---:|---:|---:|---|---|---|']
    for ds,(_,baseline,_,_) in DATASETS.items():
        s=loaded[ds]['summary'];arm=s['arms'][ARM];a=s['comparisons'][baseline];b=s['comparisons']['R49_online_GT_Skill']
        lines.append(f"| {ds} | {arm['correct']}/{arm['n']} | {arm['micro_pct']:.6f} | {arm['macro_pct']:.6f} | {baseline} {s['arms'][baseline]['correct']}/{arm['n']} | {a['corrected']}/{a['harmed']}/{a['net']:+d} | {b['corrected']}/{b['harmed']}/{b['net']:+d} |")
    return '\n'.join(lines)


def case_page(ds,row,detail,evidence,document,bundle):
    q=row['question_id'];ctxpath=evidence/'contexts'/(q+'.json');ctx=read(ctxpath);predpath=evidence/'predictions'/ARM/(q+'.json');pred=read(predpath)
    eventpath=evidence/'feedback'/(q+'.json');feedback=read(eventpath)
    lines=[f'# {q}',f"Dataset: {ds}; ordinal {pred['ordinal']}; window {ctx['window']}.",'','## Original question','',row['question'],'']
    if row.get('options'):
        lines+=['## Complete options','']+[f'- **{k}**: {v}' for k,v in row['options'].items()]+['']
    lines+=['## Original images','']
    for i,name in enumerate(row['images'],1):lines.append(f'![original {i}]({link(evidence/name,document)})')
    lines+=['','## Answers through the common reference-free adapter','',
      '| Arm | Explicit answer | Strict saved answer | Correct | Archive |','|---|---|---|---|---|']
    for name,value in detail['arms'].items():
        archive=evidence/'services/calls/R50-AGENT'/q if name==ARM else (evidence/bundle[name][q]['full_existing_public_archive']).resolve()
        lines.append(f"| {name} | {cell(value.get('explicit_answer'))} | {cell(value.get('strict_answer'))} | {value['aligned_correct']} | [raw]({link(archive,document)}) |")
    lines+=['',f"Released dataset annotation: **{cell(detail['reference'])}**.",
      f"Saved terminal status: `{pred['status']}`; main calls {pred['main_calls']}; logical tool calls {pred['tool_calls']}.",
      f"Prediction saved {pred['prediction_saved_at']}; own feedback released {feedback['released_at']}.",
      f"[Prediction]({link(predpath,document)}) · [prediction event]({link(evidence/'prediction_events'/(q+'.json'),document)}) · [own feedback]({link(eventpath,document)}) · [full context and exact injected Skill versions]({link(ctxpath,document)})",'','## Actual tool choices and outputs','']
    selections=sorted((evidence/'services/tool_selections/R50-AGENT'/q).glob('*.json'),key=lambda p:int(p.stem))
    if not selections:lines.append('No tool selected.')
    for path in selections:
        value=read(path);key=value['cache_key'];cache=evidence/'services/tool_cache'/key
        lines.append(f"- {path.stem}: **{value['tool']}**, cache_hit={value.get('cache_hit')}, status={value['status']}; [selection]({link(path,document)}), [exact request]({link(cache/'request.json',document)}), [result]({link(cache/'result.json',document)}), [raw stdout]({link(cache/'backend.stdout.log',document)}), [stderr]({link(cache/'backend.stderr.log',document)}).")
        for original in value.get('derived_images',[]):
            target=(path.parent/original).resolve();lines.append(f'![derived]({link(target,document)})')
        delivery=evidence/'failure_observations'/q/path.name
        if delivery.is_file():
            lines.append(f"  Tool remains failed; [actual failed-observation delivery receipt]({link(delivery,document)}). The main model continued without regenerating or repairing this tool output.")
    if (evidence/'protocol_amendment.json').is_file():
        lines+=['',f"[Explicit paper-A.4 protocol amendment and boundary]({link(evidence/'protocol_amendment.json',document)}). Original and intermediate nonzero exits remain preserved; new amended execution has separate attribution."]
    if ds=='chexbench' and q in (QID,QID2) and (evidence/'technical_recovery.json').exists():
        name=RECOVERY if q==QID else RECOVERY2
        mapping=evidence/('technical_recovery.json' if q==QID else 'technical_recovery002.json')
        failed=evidence/'technical_failures'/name;retry=evidence/'technical_recovery'/name
        lines+=['','## Actual technical failure and explicit continuation','',
          ('The fifth tool selection failed loading MedVLM-R1 tokenizer after104 saved questions. Its poor but technically successful retry text was retained.' if q==QID else 'The first tool selection failed loading MedGemma tokenizer after183 saved questions. The first continuation also exited1; the original failed attempt remains preserved.'),
          'Both failures preceded any generate event or current prediction/own feedback. Each had one explicit unchanged image/args/model/environment tool retry and one successful generate, without answer-quality filtering. Original successful predictions were preserved; paid responses were replayed locally. The underlying intermittent native tokenizer-load cause remains unknown.',
          f"[Original failed selection]({link(failed/'selection.json',document)}) · [original stderr]({link(failed/'tool_cache/backend.stderr.log',document)}) · [actual retry request]({link(retry/'request.json',document)}) · [actual retry stdout]({link(retry/'backend.stdout.log',document)}) · [retry completion]({link(retry/'completed.json',document)}) · [explicit adoption mapping]({link(mapping,document)})",'']
    lines+=['','## Injected Skill sources and prior same-image feedback','']
    if not ctx['selected_skills']:lines.append('No Skill injected.')
    for value in ctx['selected_skills']:
        skill=ctx['skill_snapshot']['skills'][value['id']]
        sources=', '.join(f'[{source}]({source}.md)' for source in skill['source_ids'])
        lines.append(f"- `{value['id']}` ({value['c']['branch']}): {value['c']['name']}; source cases: {sources}.")
    if ctx['same_image_ids']:lines.append('Prior released same-image cases: '+', '.join(f'[{source}]({source}.md)' for source in ctx['same_image_ids'])+'.')
    else:lines.append('No prior same-image feedback injected.')
    screen=evidence/'prescreen_events'/(q+'.json')
    if screen.is_file():lines.append(f'[Actual prescreen pool/returned IDs, including all-rejected result]({link(screen,document)})')
    window=evidence/'windows'/f"{ctx['window']:04d}"
    lines+=['',f"[Window read snapshot]({link(window/'read_snapshot.json',document)}) · [write/credit/govern events]({link(window/'events.json',document)})",'',
      'Scores, model narratives, tool claims and same-model adoption are descriptive records, not clinical or causal verification.']
    return '\n'.join(lines)


def timing_record(controls):
    mtimes=controls.get('actual_job_file_mtime_seconds',{})
    result={'source':'actual remote job-file mtime, second precision; not provider billing time','per_dataset':{}}
    for ds in DATASETS:
        prefix=controls['native_datasets'][ds]['job_prefix']
        begin,end=mtimes.get(ds+'.pid',mtimes.get(prefix+'.pid')),mtimes.get(prefix+'.exitcode')
        result['per_dataset'][ds]={'start_unix_seconds':begin,'end_unix_seconds':end,
          'approx_elapsed_s_including_any_failure_gap':end-begin if begin is not None and end is not None else None,
          'original_attempt':{'start':mtimes.get(ds+'.pid'),'end':mtimes.get(ds+'.exitcode'),
            'exit':controls['native_datasets'][ds]['original_exit']},
          'final_job_prefix':prefix,'final_attempt_start':mtimes.get(prefix+'.pid'),
          'final_exit':controls['native_datasets'][ds]['final_exit']}
    marker=MIRROR/'jobs/controller.started.json'
    started=read(marker).get('utc') if marker.is_file() else None
    final_prefix=controls['native_controller']['job_prefix'];ended=mtimes.get(final_prefix+'.exitcode')
    result['controller']={'start_unix_seconds':started,'end_unix_seconds':ended,
      'approx_elapsed_s_including_failure_and_recovery_gap':ended-started if started is not None and ended is not None else None,
      'original_exit':controls['native_controller']['original_exit'],'original_attempt_end':mtimes.get('controller.exitcode'),
      'final_job_prefix':final_prefix,'final_attempt_start':mtimes.get(final_prefix+'.pid'),
      'final_exit':controls['native_controller']['final_exit']}
    return result


def main():
    marker=PREP/'final_report.completed.json'
    started=PREP/'final_report.started.json'
    if marker.exists() or started.exists():raise ValueError('report_already_invoked_inspect_do_not_repeat')
    loaded,review,controls,source=complete_gate();when=datetime.now(timezone.utc).isoformat()
    with started.open('x',encoding='utf-8') as f:json.dump({'utc':when,'actual_result_review_session':review['session_id'],'status':'report_write_started'},f)
    running=REPORT/'README.running.md'
    if running.exists():raise ValueError('running_report_snapshot_already_exists_inspect')
    with running.open('x',encoding='utf-8') as f:f.write((REPORT/'README.md').read_text(encoding='utf-8'))
    resources={'status':'complete','arm':ARM,'report_written_utc':when,
      'original_controller_exit':controls['native_controller']['original_exit'],
      'final_controller_exit':controls['native_controller']['final_exit'],
      'original_dataset_exits':{k:controls['native_datasets'][k]['original_exit'] for k in DATASETS},
      'final_dataset_exits':{k:controls['native_datasets'][k]['final_exit'] for k in DATASETS},
      'native_controller_completion':controls['native_controller'],'native_dataset_completions':controls['native_datasets'],
      'datasets':{k:v['summary']['resources'] for k,v in loaded.items()},
      'dataset_scores_once_receipts':{k:read(RECEIPTS/(k+'.score.completed.json')) for k in DATASETS},
      'native_job_timing':timing_record(controls),'new3_health':read(PREP/'health/complete.json'),
      'code_review':read(PREP/'CODE_REVIEW_METADATA.json'),'archive_delta_review':read(PREP/'ARCHIVE_DELTA_METADATA.json'),
      'complete_results_review':review,'actual_source_capture':source,'provider_invoice':False,
      'review_CLI_USD_and_generation_CNY_proxies_not_combined':True,'embedding_or_hardware_unknown_costs_not_zero':True,
      'Skill_only_causality_clinical_or_official_SOTA_claim':False,'independent_848_case_pool_claim':False}
    # Result documents are formatted from saved metrics, never recomputed here.
    put(REPORT/'RESOURCE_SUMMARY.json',resources)
    index=['# All R50 questions','',result_table(loaded),'',
      '| Dataset | Case | R50 correct | vs direct delta | vs R49 delta | Skill injected | Same-image prior |','|---|---|---|---:|---:|---|---|']
    for ds,data in loaded.items():
        baseline=DATASETS[ds][1]
        bundle=read(data['evidence']/'comparison_sources.json')
        for row,detail in zip(data['inputs'],data['details']):
            q=row['question_id'];document=REPORT/'cases'/ds/(q+'.md')
            text(document,case_page(ds,row,detail,data['evidence'],document,bundle))
            current=int(detail['arms'][ARM]['aligned_correct']);direct=int(detail['arms'][baseline]['aligned_correct']);old49=int(detail['arms']['R49_online_GT_Skill']['aligned_correct'])
            index.append(f"| {ds} | [{q}](cases/{ds}/{q}.md) | {bool(current)} | {current-direct:+d} | {current-old49:+d} | {detail['skill_hit']} | {detail['same_image_hit']} |")
    text(REPORT/'CASE_INDEX.md','\n'.join(index))
    tables=['# Complete denominator and paired comparisons','',result_table(loaded),'']
    for ds,data in loaded.items():
        s=data['summary'];tables+=['## '+ds,'','```json',json.dumps({'arms':s['arms'],'comparisons':s['comparisons'],
          'descriptive_groups':s['descriptive_groups'],'repeated_no_progress':s['repeated_no_progress_by_saved_status'],
          'saved_R49_repeated_no_progress':s['R49_saved_comparator_provenance']['repeated_no_progress_by_saved_status']},ensure_ascii=False,indent=2),'```','']
    text(REPORT/'RESULT_TABLES.md','\n'.join(tables))
    text(REPORT/'README.md',f'''# Amended R50 CXR6 — complete results

The single arm `{ARM}` completed CheXbench618 → SLAKE114 → VQA-RAD116,
each from empty Skill and same-image state. All final attributed jobs exited0;
the original, recovery001 and recovery002 controller/CheX exit1 and final amended jobs are
retained separately in [resource history](RESOURCE_SUMMARY.json). Saved private
scores were reused for public reproduction.

{result_table(loaded)}

CheX also compares against saved R47 onlineGT468/618; VQA's direct historical
100/116 arm is M42, not an independently run M43 arm. Complete denominators,
micro/macro/subsets, corrected/harmed/net and clustered intervals remain in
[all tables](RESULT_TABLES.md). No positive result is required for this report.

The two method changes are the dynamic six-model menu and applying existing
applicability prescreen to every nonempty eligible Skill pool, allowing all
rejection. Late-R49 ordinary MUTATE/ANALYZE schema and MAIRA EOS controls apply
uniformly from R50 start; old failure registrations and Skill libraries were
not imported. Main/META Qwen3.7plus sampling, embedding, window30/buffer20/topk6,
post-prediction own feedback, prior same-image memory and unbounded total call
counts with existing no-progress stops are retained. MAIRA remains a phrase
grounding interface; this is not a full CXRAgent architecture reproduction.

OnlineGT, executor/tool budgets, prompt/EOS policy, sampling/time and dataset
overlap confound causal attribution. Injected versus uninjected and first versus
repeat-image groups are descriptive. No Skill-only causality, clinical ability,
closed-test/official SOTA or independent pooled848-case claim is made. SLAKE
overlap and VQA image-clustered paraphrases remain visible. Negative results,
legal no-progress stops, technical histories, zero-Skill outcomes and unknown
costs are preserved.

An actual MedVLM-R1 tokenizer-load failure stopped CheX after104 saved questions,
before that worker generated any output. The original exit1 and raw error remain.
One explicit unchanged tool retry succeeded; its poor text was retained. The
same original producer then continued with saved predictions and cached API
responses. The loader intermittency's underlying cause is unknown. Both physical
attempts and their elapsed time count in resources; no completed wrong answer
was redone. A second pre-generation MedGemma tokenizer JSON-load failure stopped
the first continuation after183 saved questions; its one unchanged retry used
24.0387727s/254outputtokens. Both original and first-continuation failures remain,
with recovery002's later nonzero stop and final amendment003 attributed separately. The first recovery002 launch helper
also exited1 on an incorrect old mapping filename guard before adoption/launch;
its source and failure record remain, and the corrected launch reused the saved
tool result without additional generation. See the affected
[MedVLM case](cases/chexbench/chexbench_rad_restruct_0227.md) and
[MedGemma case](cases/chexbench/chexbench_slake_0068.md).

Recovery002 stopped after316 saved questions when MAIRA actually completed one
300-token generation without EOS and the original parser rejected its unclosed
object. That output remains failed and was never regenerated, repaired or made
into a successful cache. After the paper's appendix A.4 was explained, the user
explicitly approved returning failed tool observations to the main model.
Three new actual execution modules implement this uniformly from CheX317 and
SLAKE/VQA1; original11producer files and316predictions remain. The main model
continues with the honest error; unknown sends still stop, and failed tool
trajectories follow existing Skill eligibility exclusions. All native ones stay
distinct from generation.amendment003.exitcode and amended job zeros. This is
amendedR50 with a protocol/time/order boundary, not unchanged executed code or
an exact original-paper reproduction. See the [affected MAIRA case](cases/chexbench/chexbench_openi_0078.md)
and [approval/implementation record](deployment_source/preparation/amendment003/PROTOCOL_AMENDMENT003.md).
The supplementary archive helper's directory-as-file failure after11 copied
files and retained partial evidence are also preserved, with no false claim of
a separately saved raw-byte stderr file.

All [case pages](CASE_INDEX.md) provide full questions/options/original and
available derived images, answers and changes, actual requests/replies/tools,
exact context/Skill sources and feedback timing. [Resources](RESOURCE_SUMMARY.json)
separate Agent/META/embedding/tool/health/reviewer usage and timing. CNY token
proxies and CLI-estimated reviewer USD are not invoices or converted into a
single total; missing embedding/hardware cost is unknown. New3 health was one
actual invocation each on a training image, separate from production; old3
were warm-reused without re-probing. Actual model/weight identity is not
independently attested.

[Protocol](PROTOCOL.json) is the preserved launch-time record; its historical
running status is not retroactively changed into an earlier completion or
approval. [Public reproduction](REPRODUCTION.md), [actual result review](RESULT_CLAIM_REVIEW.md)
and [claim limits](CLAIMS_FROM_RESULTS.md) describe final evidence and limits.
All actual source/control copies and failures must accompany publication.
The user waived extra post-push remote verification; a successful push must
not be mislabeled as independently remotely verified.

Report formatted from saved results at {when}.
''')
    reproduction=['# Public R50 reproduction','',
      'Use this repository checkout, including its unchanged earlier published R49 evidence. No private run, model inference, API credential, weight or digest gate is required for offline scoring.','',
      'For each dataset, run once into a new output directory:','',
      '```powershell']
    for ds in DATASETS:reproduction.append(f'python -X utf8 experiments/verify_public_online_skill_r50.py --evidence reports/cxr_online_skill_r50_cxr6_20261109/evidence/{ds} --out /path/to/new/{ds}')
    reproduction+=['```','',
      'The verifier first adapts every current and historical raw answer before label-bearing checks. Historical bundles contain answer/status and actual raw terminals, with links to complete already-published archives; cached correctness labels are excluded. Image URLs are normalized by document depth and asset metadata without reading image pixels or checking file/image digests. Metrics/resources/extractions must match the saved publication. Public reproduction is a separate offline metric recomputation, not a second private score or independent clinical audit.','',
      'Generation is not claimed bitwise reproducible: the API alias and stochastic sampling, backend/runtime differences and online annotation feedback remain part of the recorded protocol. Health outputs never enter scored answers or Skill caches.']
    text(REPORT/'REPRODUCTION.md','\n'.join(reproduction))
    write_root_indexes(loaded)
    put(marker,{'status':'completed','utc':when,'case_pages':sum(x[0] for x in DATASETS.values()),
      'saved_scores_reused':True,'new_private_scoring_inference_transfer_or_hash_checks':0,
      'actual_result_review_session':review['session_id'],'publication_push_not_claimed_by_writer':True})
    print(json.dumps({'report_formatted':True,'case_pages':848,'new_scoring_or_inference':0,'pushed':False}))


if __name__=='__main__':main()
