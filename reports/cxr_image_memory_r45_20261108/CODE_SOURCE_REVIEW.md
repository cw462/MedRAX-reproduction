# R45 M43-IM execution-readiness review — round 1/3

Run: `run_20261108_45a1b2c3`  
Score: **8/10**  
Verdict: **ready**  
Review completed: **yes**  
Required source/code scope completed: **yes**  
Review independence: **same-family**  
Acceptance status: **provisional**  
Actual underlying reviewer model identity: **unknown; not independently attested**

This is an execution-readiness assessment of the one authorized descriptive M43-IM experiment, not an efficacy score or a paper acceptance assessment. The experiment's scope and comparison limitations are sensible. I found four concrete integration defects in the initial working snapshot. The executor repaired them during this review, and I independently checked the changed source, actual deployed files, saved health assessment, and targeted offline regressions before issuing this final verdict. **No actual execution blocker remains in the reviewed scope.** All original findings and their minimum fixes remain below rather than being erased by the positive final assessment. The initial snapshot would have scored 5.5/not ready; the final verified state scores 8/ready.

## Scope and evidence actually inspected

I read the complete UTF-8 Chinese `local_assets/m43_image_memory_user_package_20261108/CODEX_EXECUTION_PLAN.md`, the package README and upstream manifest, repository `AGENTS.md`, current R45 PLAN and PROTOCOL, all five new source/test files, the private deployment helper, the complete parsed private frozen object, the unchanged M/R41 execution and R43 decision/completion code, the actual tool worker, the paid request/recovery code, and the existing common answer adapter and terminal-source resolver. I also read the published M43 and common-comparison reports and inspected the fixed M43 prediction source without rerunning historical scoring.

I compared all eight pinned upstream files: seven match byte-for-byte; `score_cxr_vqa_extension.py` matches the supplied hash after the existing CRLF-to-LF normalization. I inspected the package-to-working diffs. The frozen M43 source hash matches the actual published M43 JSONL; every frozen baseline answer/reason/status matches its published record. The old upstream files were not changed by the new implementation examined here.

Using the existing connection helper for **read-only SFTP**, I inspected the actual isolated remote code directory, its GPU configuration, and all eight new health selection payloads. I did not start a remote command, tool, model, or paid call. I did not read any new target accuracy, open the unrelated CT project, edit the user's VQA-RAD file, or modify experiment code or historical records. The only permanent authored artifact written by this reviewer is this review response. The reported original 11-test pass is consistent with the test file inspected; I did not redundantly rerun that suite. After the fixes, I independently ran the four added regression tests and checked the actual frozen records with the new predicate; those checks passed.

## Findings, ranked by execution consequence

### 1. Real backend failure payloads passed the new health and memory gates — resolved during review

The new `memory_entry` includes any observation whose outer `status` is `completed` and whose `observation` is not `None`. `BoundTools.call`, the generation completion audit, the new scorer, and the health driver use the same incomplete criterion. The unchanged worker can return an outer `completed` envelope even when the underlying MedRAX tool returned an error as data. This is a current, observed repository behavior, not a hypothetical payload format.

Concrete frozen evidence:

- `chexbench_rad_restruct_0220` has a classifier envelope with outer `status: completed`, but `observation.finding_scores.error` is `CUDA error: device kernel image is invalid...`, and its actual DenseNet inference event has `status: failed`.
- That image has a later scheduled question, `chexbench_openi_0025`, with `previous_ids: [chexbench_rad_restruct_0220]`. Thus the current implementation actually injects this known failed tool item into an upcoming same-image context.
- Three historical MAIRA observations (`chexbench_openi_0066`, `_0167`, `_0246`) have an outer `completed` status, but an observation list containing `{"error":""}` and metadata with `analysis_status: failed`. An empty error message does not make these successful results.

Concrete new health evidence:

- The DICOM probe on the first PNG returned an error about a missing DICOM header, with nested `analysis_status: failed`, yet the existing health loop accepted it and wrote `complete.json` for eight tools.
- The other seven probes have healthy payloads. In particular, the new MAIRA probe is a legitimate `predictions: []` result with `analysis_status: completed_no_finding`; this must remain acceptable. It is different from `analysis_status: failed`.

This violates the explicit plan requirements that only successful tool text enters memory and that failed/unknown new tool returns stop before further paid reasoning. The currently described “eight successful health checks” is also inaccurate.

**Minimum fix:** Put one narrowly scoped predicate in the new image-memory module for these existing tool structures: require a completed outer envelope and usable observation, reject failed/unknown actual inference events and the observed nested error/failed-analysis envelopes. Use it for memory evidence, `BoundTools`, generation completion, scoring, and health interpretation. Preserve all original model answers/reasons/statuses and original tool archives; exclude only failed tool items from injected evidence. New actual failures must stop. Do not modify the old worker or old published predictions.

No tool rerun is needed to reinterpret the already saved health receipts. Record seven healthy tools and the one expected non-DICOM-input rejection, rather than eight healthy results. Keeping DICOM in the original tool catalog is compatible with the original policy; if the model actually selects it and receives that rejection, the new strict stop rule must apply. Add a small offline regression covering the observed CUDA-error envelope, MAIRA failed envelope with an empty error message, legitimate MAIRA no-finding result, and DICOM rejection. No new framework or expanded paid control is needed.

**Verified resolution:** The new `tool_failure_reason` checks the outer state, actual model events, nested error fields including an empty error string, and nested analysis/status failures; it accepts the legitimate MAIRA no-finding form. `memory_entry`, `BoundTools`, the generation completion audit, and the scoring gate use it. The authoritative health gate is now the separately saved `health/assessment.json`, produced by the helper's offline `sync` assessment of the original probe receipts and required by `launch`; the old probe records are preserved. Read-only SFTP confirmed that assessment records exactly seven healthy results plus the known DICOM input rejection and zero new model calls. The old outer-status-only `complete.json` no longer suffices for launch.

I independently ran the added tool-health regressions. I also applied the predicate to the complete actual frozen baseline: six unhealthy items are excluded (the two already outer-failed items plus the four nested failures identified here), all 618 answer/reason/status triples remain unchanged, and the classifier failure on `rad_restruct_0220` is absent from its memory evidence. The public `OLD_TOOL_HEALTH_FILTER.json` records this technical filter without answer-correctness selection. No historical record was rewritten. Finding closed.

### 2. The actual remote namespace lacked the R43 module and its R42 dependency — resolved during review

The helper clones the old R41 code tree and uploads only `cxr_image_memory_r44.py`, `prepare_cxr_image_memory_r44.py`, and `run_cxr_image_memory_r44.py`. Read-only SFTP inspection of the actual new `code_cxr_image_memory_r45_20261108/experiments` directory confirms that **`cxr_task_completion_r43.py` and `cxr_answer_domain_r42.py` are absent**.

The new runner imports R43 only after its dry-run early return. The R43 module in turn imports R42. Consequently, the successful dry run did not test these imports; `--execute` will stop with `ModuleNotFoundError` before generation. The other examined runtime modules, including base M, R41, the tool worker, and the ledger/client dependencies, match the current local files byte-for-byte, and the new worker config selects GPU 1.

**Minimum fix:** Copy these two unchanged upstream modules into the new isolated code directory and include them in the helper's explicit deployment file list. Do not modify SUPPORT, old runs, or another task's environment. Verify the execute-path imports with the existing interpreter and no API key/network request. There is no need to reinstall a model or environment.

**Verified resolution:** `FILES` now includes the unchanged R42 and R43 modules. A second read-only SFTP inspection confirmed that both are present in the isolated CODE directory and byte-identical to the pinned local upstream files. The three new execution modules also match their updated local versions byte-for-byte. The helper's actual `sync` path imports base/R41/R42/R43 and constructs the existing provider profile before writing the assessment; the saved remote assessment reports `import_and_provider_configuration: passed`. No generation directory or main-send artifacts existed at this verification. Finding closed.

### 3. Supported saved-response recovery crashed the new resource report — resolved during review

`run_cxr_vqa_toolsets.PaidCalls.record_saved_response_cost` deliberately reconstructs a missing receipt from an already saved response, with `elapsed_s: None` and `recovered_from_saved_response: True`. This is the unchanged client's supported no-resend recovery path.

The new `resource_report` computes `sum(x.get('elapsed_s',0) for x in receipts)`. When the key exists with `None`, the default is not used. A zero-API temporary fixture using precisely that receipt structure reproduced:

`TypeError: unsupported operand type(s) for +: 'int' and 'NoneType'`

Thus a legitimate resumed generation can finish successfully and then fail before reference loading or scoring.

**Minimum fix:** Sum only known numeric elapsed times and report the number of unknown request durations. Do not substitute a claimed complete elapsed total for missing data. A tiny offline fixture for the real recovered receipt is sufficient; no new recovery mechanism is requested.

**Verified resolution:** The report now emits `model_request_elapsed_seconds_known` from non-null durations and `unknown_request_elapsed_count`. I independently ran the new recovered-response regression with `elapsed_s: None`; it returns a known subtotal of zero and unknown count of one without a scoring crash. The old receipt is not rewritten and no missing duration is fabricated. Finding closed.

### 4. Generation exit-code path disagreed with the scorer — found and resolved during this review

Initially, `PROGRAM --out` targeted `RUN/generation`, while the launch wrapper wrote only `RUN/jobs/generation.exitcode`. The scorer used `a.run/jobs/generation.exitcode`, although `a.run` had to be `RUN/generation` for all other artifact paths. A completed run therefore could not satisfy the scorer's exit gate.

The executor made the minimum repair during review. I reread both changed sites: the scorer now reads `a.run/generation.exitcode`; the wrapper preserves the control receipt in `RUN/jobs` and also writes `RUN/generation/generation.exitcode` when that directory exists. This resolves the identified path mismatch. It is not an unresolved blocker and does not change data, method, or budget.

## Checks that passed

The main experimental design is coherent within its expressly limited interpretation:

- The frozen cohort is 618 unique question IDs with fixed existing order, 488 exact original-image-sequence groups, 130 repeated-image questions, and 488 first/single-image reuses. The repeated policy split is 68 M and 62 C41, yielding the stated 644-main and 384-logical-tool ceilings. Five same-image groups span subsets; this is disclosed rather than mistaken for independent patient generalization.
- Grouping decodes RGB pixels, includes image dimensions, and binds the complete ordered image sequence. It does not merge merely similar images. The existing input/pixel guards are appropriate and were not replaced by a new scheme.
- The original mask determines policy only. C41 invokes the unchanged no-card R41 loop at 6 main/4 tools; M invokes the unchanged 4-main/2-tool loop. R43's unchanged `decision` allows at most one completion within the remaining total of four main calls. There is no current accuracy-based branch selection.
- Memory is constructed serially from already processed results. It does not preload all baseline answers into context, read target reference labels, insert future questions, import other-image entries, or acquire extra patient history. Original answer errors are retained. The record selection is deterministic, at most eight recent records, with whole-record selection and the stated tool-item limit. In the historical-context-only diagnostic, all 130 repeated positions had nonempty context and the maximum included record count was five; this diagnostic is not a prediction of new answers.
- `CapturePaid` and `BoundTools` preserve the M/C41 control flow while directing receipts into the new arm namespace. Main and tool budgets remain bounded by the original branch implementations. Current originals are sent by the original image loader; old derived images are not attached as memory images.
- Resume reconstructs earlier records and checks context/prefix equality. The unchanged paid client verifies the archived request on replay and refuses a started request with no saved response; no blind resend is introduced. A failed tool result is retained rather than silently deleted or retried. Finding 1 concerns recognizing failure, not a demand for a new recovery system.
- The scorer obtains a new answer from the last **actual archived response**, rather than trusting synthetic `terminal_raw`. It excludes native nonfinal tool-call replies and uses the existing reference-free common adapter. Baseline reuse follows the public M43 → M-C41 → original-M source chain. Reference labels are opened only after adaptation. Full membership and completion checks precede scoring; the published 466 baseline is required. I did not rerun that old full score.
- The existing model profile checks the qwen3.7-plus alias or its permitted dated form; actual returned IDs are recorded. The runtime protocol preserves temperature 0.2, top_p 0.95, output 2048, and thinking disabled. The root configuration's older descriptive fields do not override the actual request protocol or reactivate the old shared ledger.
- The private launch transport carries the API key through stdin/pipe, not a command argument or persisted request payload. Examined request artifacts contain model messages, not authorization headers. The new code/GPU directory is isolated; the existing GPU 0 configuration and CT work are outside this task.
- The analysis remains a descriptive single-memory-arm comparison against a historical mixed M43 archive. Exposed development data, cross-subset memory, first-question reuse, rerun/sampling/time confounds, and hardware binding differences are disclosed. No complete same-day no-memory rerun, D-Q, new seed study, official SOTA statement, or causal memory claim is necessary to execute this authorized scope.

## Final readiness judgment and limits

All four concrete findings are resolved in the source and deployment state checked at the end of this round. The independent four-test regression run passed, the complete frozen-record technical filter preserved all model answers/reasons/statuses, and the actual new remote namespace contains the needed unchanged dependencies and updated execution modules. The corrected health assessment is truthful about the DICOM rejection. There are **no remaining required code fixes or additional paid experiments** before the authorized M43-IM execution.

The runner must still honor its normal stop conditions if an actual future request or tool fails; this review does not guarantee future service availability. The DICOM probe was an expected rejection and does not demonstrate successful DICOM processing. The new run has not produced an accuracy result, and no result was read during review. Scoring and interpretation must remain after full completion, use the common answer metric and fixed 466 baseline, retain the full denominator, and disclose the already stated historical/sampling/exposure confounds. This ready verdict establishes neither an accuracy gain nor independent medical/causal validation.

## Memory update

- Round 1 final score **8/10**, verdict **`ready`**; review complete and source/code scope complete, same-family provisional, actual underlying model unknown. The initial working snapshot would have scored 5.5/not ready; all four actual defects were repaired and verified during this round before the final verdict.
- Confirmed and fixed real nested tool-failure envelopes: historical classifier CUDA failure has an actual later same-image recipient; three MAIRA failed-analysis payloads have empty error messages; current DICOM health probe is a non-DICOM-input rejection. The new common predicate filters these from memory and stops new inference. Legitimate MAIRA `completed_no_finding` passes. The saved authoritative health assessment truthfully records seven healthy probes plus one expected input rejection.
- Confirmed and fixed the missing `cxr_task_completion_r43.py` and `cxr_answer_domain_r42.py` deployment. Both unchanged dependencies and all three updated execution modules match local bytes in the actual remote CODE directory; saved zero-API import/provider validation passed.
- Reproduced and fixed the resource report's `elapsed_s=None` crash using the unchanged client's real saved-response recovery receipt shape. Known durations and unknown-duration count are now separate. Four targeted regressions independently passed.
- The exit-code path mismatch was fixed during this review and independently reread; it is resolved.
- Exact frozen cohort/order, original M/C41/R43 policy dispatch and caps, published baseline source, actual-response common scoring, reference separation, isolated GPU/runtime namespace, and secret transport are otherwise consistent with the intended limited experiment.
- No unresolved execution blockers remain in this scope. Do not escalate historical/sampling confounds into a demand for unauthorized paid controls. Do not add new digest machinery. Positive readiness is not positive efficacy or cross-family acceptance.
