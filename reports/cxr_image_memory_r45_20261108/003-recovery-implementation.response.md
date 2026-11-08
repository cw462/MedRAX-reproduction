# R45 known technical failure: implementation review

Run: `run_20261108_45a1b2c3`  
Score: **8/10**  
Verdict: **ready**  
Review completed: **yes**  
Requested implementation scope completed: **yes**  
Review independence: **same-family**  
Acceptance status: **provisional**  
Actual underlying reviewer model identity: **unknown**

The implemented recovery is ready for the specifically inspected `chexbench_slake_0046` failure. I found no remaining actual blocker in the new controller, its private invocation, or the corresponding scorer changes. It preserves the failed question as a technical null result, resumes the unchanged frozen runner, and provides a separate effective completion only after the complete cohort and failure-accounting audit. This is not a general permission to convert later failures automatically, nor evidence that the classifier was repaired or that memory improves accuracy.

## Evidence examined and checks performed

I read the full `experiments/recover_cxr_image_memory_r45.py`, `tests/test_cxr_image_memory_r45_recovery.py`, updated `experiments/score_cxr_image_memory_r44.py`, private `local_assets/deploy_cxr_image_memory_r45.py`, and the relevant complete exporter `experiments/export_cxr_image_memory_r45.py`. I compared their behavior with the previously inspected real failure and review 002's accepted design.

I independently ran the two recovery tests. Both passed. Using their temporary fixture, I additionally exercised the actual implementation and confirmed:

- A technical terminal carrying a non-null answer is rejected with `failure_filled_with_answer`.
- A later unhealthy selection without a registered technical stop is rejected with `unregistered_new_tool_failure`.
- A cohort call count over the supplied ceiling is rejected with `cohort_budget_exceeded`.
- None of these rejected finalizations writes an effective exit-0 file.
- `new_terminal` suppresses the technical record's actual last tool-plan response to `raw: None`.
- The resource report accepts an unknown episode duration and reports a known subtotal of zero with one unknown episode, rather than crashing or claiming a measured zero.

The existing tests also demonstrated refusal to terminalize a missing-response send, preservation of only healthy expert evidence, refusal to swallow `frozen_execution_changed`, acceptance only after 618 prediction/context membership, and rejection of a third main call added to the failed question.

Read-only SFTP inspection confirmed that every source file recorded in the actual `generation/run.json` still matches its frozen startup hash. The current remote state remains stopped at index 162 with no prediction for `_0046`; the recovery controller is not yet deployed, and no effective completion exists. This agrees with the stated pre-execution review boundary. The private `record_known_failure` path uploads only the separate new controller when used; it does not re-upload or edit the frozen inference sources.

I did not execute a remote command, record the real technical prediction, launch the controller, call a tool/API, inspect accuracy, load target references, or rerun historical scoring. Test writes were confined to temporary fixtures. This review response is the only permanent authored artifact I wrote.

## Implementation findings

### Known-failure registration is faithful to the actual prefix

`record_known_stop` requires the current stopped progress record to name the explicitly supplied question and tool-health failure. It refuses an existing prediction. `calls_for` requires every recorded send to have its saved response and a healthy received-response receipt. The bad tool records must have definite failed/completed envelopes, no unknown actual-model events, and a saved tool-cache result. The existing frozen branch determines the per-question budgets.

For the actual reviewed state this produces the correct 2-main/2-tool technical terminal, with null answer/reason, `missing_tool_unhealthy_stop`, `technical_failure: true`, and `reused_M43: false`. The failed classifier still counts as a tool selection. Only the already successful expert observation enters the terminal's injectable observations. The failure identity/selection information and original stopped progress go to a separate known-stop receipt. No model answer is inferred from the expert's focused response or last main-model tool plan.

The private helper explicitly registers only `_0046`, checks the initial generation exit is 1, and checks for active matching runner/worker/controller processes before recording. It does not delete the failed cache or retry either request or tool. The unknown episode duration is explicitly represented as unknown.

### Resume preserves the frozen runner and stops on new failures

The separate controller has its own lock and attempt-specific started record, child PID/command record, child log, raw child exit, and complete/incomplete receipt. Attempt files are created exclusively; it does not overwrite the original job's log or exit-1 record. The key goes through stdin and the child's stdin pipe, not the command line or persisted command record.

The child command invokes the original frozen runner with the same frozen configuration and generation directory. The unchanged runner's existing context/prefix verification and saved-prediction skip handle the technical record. No failed-question replay is added by the controller.

There is one child invocation followed by finalization, not a loop that continually turns new failures into missing results. A new tool stop leaves incomplete cohort membership and/or a nonmatching child ending, so it does not receive an effective success. A later failed cached classifier selection is retained and stops again. Further diagnosis/registration would be a separate action; the current transport does not automatically perform it.

### Effective completion is distinct from raw child success

`finalize_known_failures` requires child exit 1 and the exact final exception line `ValueError: unhealthy_tool_selection`. An unrelated final error is not accepted. It then checks the 618 distinct frozen IDs and exact prediction/context membership; verifies all actual main receipts; applies each question's original 6/4 or 4/2 cap; and independently enforces the 644/384 cohort ceilings that the original child cannot reach after the unhealthy-selection audit raises.

Every unhealthy selection must belong to a registered technical-null terminal. For the registered question it requires the explicit technical status/flag, null answer and reason, unchanged actual call/selection counts, and the same failed cache-key sequence. Retained prediction observations must be healthy. Missing registered failure evidence or an unregistered failure is rejected. This addresses the actual risk of concealing an extra call or an unresolved later failure.

Only after those checks does it create `complete_M43-IM.json` with `generation_complete_with_known_technical_missing`, the explicit completion mode, raw child exit 1, known missing IDs, actual main/tool totals, and references-read false. The independent `generation.effective.exitcode` is then written as 0. The original `generation.exitcode` remains 1. This is an alternate complete-denominator accounting result, not a false claim that the original runner completed its all-tools-healthy gate.

### Scoring and resource handling keep the missing result missing

The scorer's explicit `--completion-exit` allows use of the independently produced effective marker while retaining full membership, actual send/response counts, per-response receipts, and unhealthy-selection accounting against the completion receipt. I also reread the last supplementary scorer changes before finalizing this review: known technical IDs must belong to the cohort; their receipt must name independent finalization and raw child exit 1; each known terminal is checked against the actual main/tool counts, failed cache keys, and null answer/reason/status using the explicit or default recovery directory. Actual per-question and cohort caps and the total logical-tool count are verified before reference loading. These are consistent with the approved recovery boundary.

The scorer does not fill a technical answer with the baseline. The existing `new_terminal` technical flag/status suppression ensures this record produces no answer for the common reference-free adapter, even though its last actual response is preserved. Reference labels are still loaded only after all answer adaptation and these completion checks.

Known request and tool costs remain counted from their original artifacts. The previously identified episode-duration issue is fixed: `new_episode_elapsed_seconds_known` and `unknown_episode_elapsed_count` separate observed timing from the interrupted episode's missing measurement. The zero-paid fixture verified this behavior. The finalizer additionally records its actual UTC completion time, and the scorer reports wall time from the earliest actual main send to that completion with interruptions explicitly included; this does not relabel the unknown episode measurement as known.

The complete receipt is issued by the inspected finalizer; the scorer consumes that receipt rather than pretending the raw generation exit was zero. In this cooperating-operator, fixed-run workflow I do not require a second generic recovery validator or new digest machinery.

### Export keeps the raw/effective distinction

The exporter chooses the effective marker only for the explicit independent-finalization completion mode. It preserves the original plain-text exit marker and the separate effective marker, completion receipt, recovery records, and job logs/JSON/exit records, in addition to predictions, memory contexts, requests, tool selections, and cached results. The private pull path includes the recovery directory. These changes do not run new inference and do not overwrite old experiment records.

The actual completed export and publication have not happened and are not claimed validated here. Their normal allowlisted outgoing-content checks remain part of the eventual publication work, not a reason to rerun predictions.

## Final judgment

**Ready for this bounded known-failure record and resume. No additional code fix is required by this review.** The implementation satisfies the minimum conditions in review 002 and the user package's explicit technical-missing allowance. The recovered full-denominator result must disclose the original native worker crash, unknown root cause, null answer, no retry, and separate effective completion; it must not be described as a successful answer recovery or classifier repair.

If the unchanged runner encounters a new failure, unknown send, budget violation, or context mismatch, preserve that stop and diagnose it separately. The current ready verdict does not waive those gates. Accuracy and the fixed baseline comparison remain unavailable until complete generation/accounting and offline scoring.

## Memory update

- Recovery implementation review completed: **8/10, ready**, same-family provisional, actual underlying reviewer identity unknown.
- Inspected the actual record/resume/finalize controller, private transport, scorer and exporter changes. The original frozen runtime code still matches the actual startup marker; current remote state remains stopped with no technical prediction or new controller execution yet.
- Two implementation tests passed independently. Additional temporary probes confirmed rejection of non-null technical answers, unregistered failures, and cohort-budget excess; technical raw suppression and unknown episode-duration reporting also passed.
- No failed-question retry/cache deletion, no automatic later-failure loop, no raw exit-1 overwrite, no historical-answer fill, and no reference read were found in the reviewed recovery path.
- All real issues from review 002 are handled, including independent budget checks and unknown interrupted-episode timing. Supplementary before-label scorer checks and explicit interruption-inclusive wall timing were reread and are consistent. No further required fix or paid test is requested.
- Keep the score/claim boundary: complete with technical missing is not all-healthy generation, and this readiness review says nothing about efficacy or backend repair.
