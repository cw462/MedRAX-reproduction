# R45 first technical failure: scoped recovery-design review

Run: `run_20261108_45a1b2c3`  
Review artifact: `002-recovery-review.response.md`  
Score: **8/10 for the concrete recovery design**  
Verdict: **ready to implement this bounded recovery**  
Review completed: **yes**  
Review scope completed: **yes — actual failed prefix, frozen runner/metric behavior, and proposed recovery logic**  
Review independence: **same-family**  
Acceptance status: **provisional**  
Actual underlying reviewer model identity: **unknown**

The proposed handling is faithful to the user package's explicit allowance to preserve a technical missing result after diagnosing a stopped tool call. It does not require retrying the classifier, repeating a paid call, filling with the historical answer, changing the frozen memory algorithm, or weakening the common answer metric. I support implementing the narrow controller/receipt and then resuming the unchanged runner. This is a review of the recovery design before its implementation, not a claim that an as-yet-unwritten controller has been tested, and not permission to convert arbitrary later failures into success.

There are two material implementation details to retain: the finalizer must independently execute the budget checks that the unchanged runner cannot reach after its unhealthy-selection audit fails, and the resource report must represent this technical terminal's unknown episode duration without crashing or inventing a zero. Both are small changes, described below. No new paid control experiment or model/backend repair is necessary for this missing-result recovery.

## Actual failure evidence checked

I reread the package's complete generation/recovery paragraph, the current frozen runner's resume and final audit code, and the scorer's terminal suppression and resource logic. Via the existing connection helper and **read-only SFTP**, I inspected the affected context, both request receipts and responses, both tool selections, the classifier cache's started/result/stderr files, the generation exit receipts, progress and log tail, and artifact counts. I did not start a process, tool, or API request, modify code or run records, inspect target accuracy, or open reference labels.

The observed state agrees with the executor's report:

- The stop is at frozen index 162, `chexbench_slake_0046`, a **C41** question. There are 161 prediction files and 162 memory-context files. There are exactly 62 started requests, 62 responses, 62 result receipts, and 62 archived requests.
- Both original exit files are `1`. The stopped progress record reports `tool_unhealthy_stop:outer_status_not_completed`. No prediction was saved for this question.
- The affected question has exactly **two main calls and two logical tool selections**. Call 1 requests the expert, which returned a healthy observation and completed generation event. Call 2 requests the classifier to cross-check that evidence. Its actual last response is a tool plan, not a final answer. There is no third main-call directory and no post-classifier paid response for this question.
- Selection 2 and its preserved cache result (`0de4f4b6f921677bcb502045bd9e299f9fa8bfe07cce7d0dccf329a57db9ef4d`) are explicitly `status: failed`, `observation: null`, `error: backend_exit_-11`. Its stderr contains only the native-resolution resize warning. The subprocess's signal-11 termination is established; a root cause is **not** established by that warning. Do not claim that the resize warning proves causation or that the backend has been repaired.
- The failure was not passed onward as negative evidence. `BoundTools` stopped the episode before another main call.
- The current memory prefix contains only earlier `chexbench_slake_0028`. Later frozen same-image questions include `_0049`, `_0072`, and `_0074`; the proposed technical terminal will therefore be part of their processed history, with its null answer, technical status, and only its healthy expert evidence.

The package says: “工具返回失败/未知时停止，不把失败当阴性。先查明已发送状态；必要时另存技术缺失并披露，不删缓存绕过。” The observed stop has happened; the actual sends and failure are now identified. Preserving a technical missing prediction is directly within that instruction. The root cause of a native worker crash need not be invented before recording that its answer is missing.

## Accepted minimum recovery semantics

1. **Preserve the original failure.** Keep both initial exit-1 receipts, original log, all requests/responses, the healthy expert result, failed classifier selection/cache, and started evidence. Use separate resume/controller logs and effective completion receipts. Do not overwrite the original exit-1 evidence, delete the failed cache, rerun the classifier, or add an additional main call for `_0046`.

2. **Write only the missing terminal record for the inspected question.** It should be a new explicit technical terminal with `answer: null`, `reason: null`, `status: missing_tool_unhealthy_stop`, `technical_failure: true`, `reused_M43: false`, and the actual counts `main_calls: 2`, `tool_calls: 2`, `new_main_calls: 2`, `new_tool_calls: 2`. The two tool calls include the failed attempt; counting only the healthy expert would understate use. Preserve only the already returned healthy expert in the injectable `observations` list. Link the failure receipt/selection separately. Do not turn the expert's answer to its focused tool question into the main answer, copy the historical M43 answer, or supply a synthetic final model reason. This technical record is an operator adjudication of missing output, not a successful model completion.

3. **Resume the frozen runner without altering its code, memory rules, configuration, or input order.** Its current loop reconstructs prior memory, verifies saved context/prefix equality, reads an existing prediction without another call, and then appends its memory record. Thus `_0046` will be skipped as a terminal missing result and later questions can continue in their original order. The saved `_0046` context need not and must not be rewritten. Passing the null answer, technical status, and healthy expert text to a later same-image question is consistent with the declared memory design; it does not assert that the failed classifier was negative. The failed tool item remains excluded by the same predicate.

4. **Keep this recovery bounded to the diagnosed terminal.** The current receipt should explicitly name `_0046` and selection 2. If a later question selects the same failed cache, the unchanged tool gate will stop again. Do not silently retry or delete the cache, and do not make the controller an automatic “mark every exception missing and keep paying” loop. A new failure must remain stopped until its actual send/tool state is diagnosed and separately documented. This matters here because the schedule contains three later questions on the same image, rather than being a purely hypothetical recurrence.

5. **Treat the finalizer as an honest alternate completion audit.** The unchanged runner will eventually reject the preserved bad selection even if every question has an explicit terminal record. Its raw child exit remains 1. After a fully enumerated audit, a distinct effective receipt/exit may declare **complete with technical missing results**. It must not claim that the unchanged child exited successfully or that all 618 questions received model answers. The full denominator is 618; the technically missing question remains missing/incorrect under the common metric.

## Required finalizer and scoring checks

These are the minimum consequences of using a separate finalizer for this actual run, not a request for a general recovery framework:

- Require all 618 distinct prediction and context IDs from the frozen cohort. All sent main requests must have their actual response and healthy receipt; any unknown send or bad main receipt remains a stop. The finalized technical record's actual main count must still be 2, with no additional request on `_0046` after the failed tool.
- Require every unhealthy tool selection to match an explicit, documented technical-null terminal and its actual failure selection; reject an unaccounted bad selection. All tool evidence retained in prediction memory must pass the existing `tool_failure_reason` predicate. Do not accept a technical label on a non-null model answer as an excuse to bypass the gate.
- Accept the unchanged child's final nonzero status only for the **expected end-of-run `unhealthy_tool_selection` audit caused by the documented selection(s)** after full terminal membership. Do not turn `frozen_execution_changed`, `memory_prefix_changed`, an incomplete later episode, an unknown send, or another exception into an effective success.
- **Independently enforce the actual 644-main / 384-logical-tool cohort ceilings and the frozen per-question M 4/2 or C41 6/4 ceilings, including the failed calls.** In the unchanged code, the unhealthy-selection loop precedes the cohort-budget test. Consequently, that raw child exit does not certify that its budget test ran. A finalizer that bypasses the former must execute the latter itself. Count actual send/selection artifacts, not just the hand-authored technical terminal's claimed counts.
- The scorer may take an explicit effective completion/exit path, but should validate the effective receipt's full membership, accounted failures, counts, and receipt conditions before loading references. Merely passing a path containing the character `0` must not disable the existing receipt and health requirements. This needs only the narrow current receipt schema and checks, not new hashes or a migration layer.
- Continue using `new_terminal` and the existing common adapter. Its `technical_failure`/status handling already forces `raw: null` for this record. It therefore cannot score the last tool plan or the successful expert answer as a final answer. Baseline source adaptation and the 466 check remain unchanged. No references or target scores are needed for this recovery.

The existing request and tool resource paths already contain the affected calls and their usage. They must remain included in new cost/time/tool totals. **One real resource edge needs a small correction:** the technical terminal was never returned by the episode, so the runner did not persist its measured `elapsed_s`. The current `resource_report` still sums `x.get('elapsed_s',0)` for new predictions. Filling `elapsed_s: null` would raise a `TypeError`; omitting it would silently claim zero elapsed time. As already done for unknown request durations, report a known episode-duration subtotal plus an unknown-episode-duration count. Alternatively retain an explicitly identified trace-derived estimate separately, but do not label it as the missing original measurement. No timing reconstruction is required to continue.

Before resumed calls, verify the small implementation with offline fixtures for: the accepted explicit technical-null record; a non-null “technical” answer rejection; an unaccounted bad selection or extra call on the failed question; and an unknown episode duration. This verifies the actual altered gate without rerunning historical scores or paying for a failure reproduction. The implementation can use one small controller/finalizer and one receipt. There is no requirement to modify the frozen runner, introduce a generic recovery framework, create another digest scheme, or request additional paid controls.

## Reporting and interpretation

Record that this is a post-failure operational amendment implementing an allowance already present in the user plan. Preserve the initial stop and the separate effective completion. Report the failed question, actual 2-main/2-tool prefix, SIGSEGV symptom, unknown root cause, null final answer, zero retry, all costs, and any downstream same-image use of its healthy expert text. Do not describe it as a recovered medical answer or a backend repair. The complete-denominator comparison will include this technical loss and its possible memory consequences, as well as the pre-existing sampling/time confounds.

This preserves the authorized single-arm experiment and the user's stop/no-blind-retry requirement. There is no actual blocker that requires abandoning the remaining cohort. The next action is the minimal implementation and its zero-paid gate verification, followed by the unchanged runner's bounded continuation. A later unknown send, unaccounted tool failure, budget violation, or context mismatch would be a new stop, not grounds for automatic success.

## Memory update

- Reviewed first actual failure without target labels/scores: index 162 `_0046`, C41, 2 main/2 tools; expert healthy; classifier SIGSEGV `backend_exit_-11`; no final answer or subsequent main call; 161 saved predictions/162 contexts and 62 matched send/response/receipt artifacts.
- Proposed explicit null technical terminal is faithful to the original Chinese plan's technical-missing allowance. Preserve original failure/cache/log/exit evidence; no failed-question retry, no baseline fill, no frozen runner/memory edits.
- Ready for this bounded recovery design, 8/10, same-family provisional. Implementation is not yet reviewed or claimed tested by this design review.
- Finalizer must account only diagnosed failures, require the specific expected final audit failure, and independently enforce actual per-question/cohort budgets because the unchanged child stops before its budget audit.
- Same-image later questions exist; failed cached selection may recur and must stop again rather than be silently retried or auto-converted. Healthy prior expert evidence may remain in memory with the explicit null technical answer/status.
- Small necessary resource correction: technical episode duration is unknown; use a known-duration subtotal plus unknown count, avoiding `None` summation and fabricated zero.
- No new paid control, score inspection, backend retest, extra hash scheme, or general recovery framework is requested.
