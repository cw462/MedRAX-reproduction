I reviewed the two new files (recovery helper + resume regression), re-confirmed the unchanged reward adapter and the `run_stream` skip-saved branches, and traced the recovery against the actual upstream interfaces. No re-scan of the broad method.

## Verdict: ready — no blocker

**Root cause is correctly isolated.** `run_stream` constructs the trace (and calls `reward_fn` = `released_reward`) only *after* the first question's prediction, prediction-event, and feedback are committed. `released_reward` lazily does `from cxr_author_alignment import extract, choice, m4cxr_normalize`; that module was absent from the R48 inference-only dependency copy, so the process died at exactly the documented point (contexts/steps/prediction/event/feedback for QID committed; no trajectory, no window repo, no second question). `cxr_author_alignment.py` is stdlib-only (`dataclasses, json, re` — no network/ref/label access), so the repair introduces no leakage surface.

**Property-by-property confirmation:**

1. **Preserves first exit 1 / records.** `stage()` copies the original `controller.pid/.started.json/.exitcode/.log`, `chexbench.pid/.exitcode/.log`, `queue_status.json`, `generation.exitcode`, `manifest.json` into `recovery/dependency_1/original/` before any launch; the new attempt writes a new log `chexbench.dependency_1.log` and never overwrites the original `.log`. Original exit 1 remains in `a/original/*.exitcode`.
2. **Never re-executes committed question / re-reads its ref.** `run_stream` resume hits `predpath.exists() → read` (no `service.execute`) and `eventpath.exists() → read` (no `ReferenceVault.after_prediction`). `test_r49_dependency_resume.py` proves this: first run `executed == ['first']`, resume `executed == ['second']`, `ExistingFeedbackVault.after_prediction` raises if called for `first`, and `predictions/ARM/first.json` + `feedback/first.json` are byte-identical after resume.
3. **Does not relax failed-tool / unknown-send rules.** The runner is unchanged (same `tool_failure_reason`, `assert_closed_sends`, `PaidCalls` no-reissue, `Services.embed` unknown-send). The `GUARD` additionally asserts the 2 selections have `tool_failure_reason(...) is None`, the 3 `result.json` have `response_received is True` and `error is None`, and there are 0 META/embedding started records.
4. **Cannot launch duplicates.** `stage()` asserts no prior `a/controller.py`/`a/original`; `launch()` asserts no `a/controller.started.json`; the original `deploy.queue()` is blocked because the recovery rewrites `j/controller.pid`. The `GUARD`'s `/proc/pid` liveness check also fails on any re-run while a recovery attempt is active (fail-closed).
5. **Current status reflects only the new attempt; initial history preserved.** `a/{ds}.exitcode` is written *only* by the new controller (stage writes only `a/original/*`), so `phase()`/`datasets[ds].exit` is the actual new rc; the old `1` lives solely under `initial_attempt` (from `a/original`) and `state()` tags `initial_controller_exit=1`/`initial_chexbench_exit=1` separately. No conflation of the old `1` with a new failure.
6. **Full raw exit 0 before full score.** The recovery controller requires `rc==0` + `complete.json` (status `generation_complete`, `questions==COUNTS[ds]`) per dataset and writes `generation.exitcode`; the unchanged scorer still requires `generation.exitcode == '0'`. Partial recoveries cannot be scored.
7. **No null fill / history fallback.** The only change is adding the missing module; no repeated-stop null-fill, no historical-answer reuse, no policy/model/input/label change.

**Minor non-blocking notes (not deltas required):**
- `status()` `initial_exit` fallback references `a/'jobs'` (should be `j`); dead code in the normal flow since `a/original` is a stage prerequisite.
- `GUARD` checks `cxr_author_alignment.py` existence, not content; content integrity rests on the repairer adding the tracked file plus the reported 0-API/0-ref import smoke. Consistent with the no-byte-check directive.
- The log-tail match is exact (`ModuleNotFoundError: No module named 'cxr_author_alignment'`, appearing once); if the real log differs, `stage()` fails closed rather than proceeding. Correct behavior, but strict.

**Independent rerun limits:** I did not and cannot rerun the new `test_r49_dependency_resume.py` (claimed 0.230s) or the server import smoke; I read the test and confirmed it exercises the exact failure/re-resume properties it claims.

## Memory update
R49 dependency-repair review 002 (narrow): confirmed the one-use `resume_cxr_online_skill_r49.py` (stage/launch/status) + `test_r49_dependency_resume.py` recover the missing `cxr_author_alignment` deployment without touching the committed first question. Guard is exact (exit 1, single committed QID, 3 closed main, 2 healthy tools, no META/embedding/window, dependency present) and fail-closed. Recovery preserves original exit-1 records under `recovery/dependency_1/original`, writes new attempt to `a/{ds}.*` + suffixed logs, keeps `initial_*_exit=1` distinct from the current rc, requires raw exit 0 before scoring, and blocks duplicate stage/launch and the original controller. No blocker; runner/tools/labels/policy unchanged; no null-fill or history fallback. Prior 001 ready/9 remains on record.

SCORE:9, VERDICT:ready, SCOPE_COMPLETE:true
