I've verified the single-delta fix against the actual on-disk sources (Read only; no execution/network/API/GPU/credentials/clinical data).

## Verdict

**Score: 9 / 10**
**VERDICT: ready**
**SCOPE_COMPLETE: true**

This round is a **pre-write control fix** only; it does not change the reviewed diagnostic semantics, and the scope remains diagnostic-only (not production repair or clinical assurance).

## What I verified

**Root cause**
- `stage()` was the only broken path: its remote prelude was `definitions()+GUARD+…`, and `definitions()` defines only the 8 constants (`RUN`, `CODE`, `ATTEMPT`, `QID`, `TOOL`, `OLD_KEY`, `MODEL_REVISION`, `DIAGNOSTIC_ID`). `GUARD`'s first line `r=Path(RUN)` therefore raised `NameError: name 'Path' is not defined` (and `json` was likewise absent). `launch` and `status` were never affected — `launch` uses `definitions()+shared_source()+GUARD` (and `shared_source()` already begins with `import json\nfrom pathlib import Path\n`), while `status` imports both inside its own body.

**Minimum delta correctness**
- The on-disk `stage` now reads `definitions()+'import json\nfrom pathlib import Path\n'+GUARD+…` (line 225), so `Path` and `json` are bound before the GUARD's first statement. The stage body's remaining uses of `json.dump`/`json.dumps` are also covered. `shutil` is still imported in the stage body. No other path (`launch`, `status`, `RUNNER`, `shared_source`) gained a duplicate or conflicting import.

**No semantic change**
- The GUARD assertions, the archive/`mkdir`/copy logic, and the SFTP writes of `EXECUTION_SCOPE.json`/`REVIEW_READY.json`/`diagnostic_runner.py` are byte-identical to the previously approved version. The `RUNNER` (capture/once-guard/health/network-isolation/no-production-write) is untouched.

**Verification of the fix**
- The new test `test_actual_generated_stage_prelude_reaches_guard_without_writes` execs the *actual generated stage source string* against a temp fake `RUN` (deliberate `controller.exitcode='0'`), and confirms: `Path`/`json` resolve in the namespace, the GUARD reaches and rejects at its first exit-code assertion, the attempt directory is never created, and no files change. This exercises exactly the code path that previously NameError'd.

## Critical blockers

None.

## Memory update
- `run_20261109_49pgd001` round-2 control fix reviewed: **ready / scope_complete=true / score 9**. The only delta — adding `import json\nfrom pathlib import Path\n` to the `stage` remote prelude (`definitions()+imports+GUARD`) — correctly fixes the first-line `NameError: Path undefined` without altering any reviewed diagnostic capture/once-guard/health/network-isolation/no-production-write logic. `launch`/`status` already carried these imports and are unchanged. The new offline generated-stage smoke (actual source string, deliberate exit0) passes and proves the GUARD now rejects before any `mkdir`/archive/write.
- Next step remains the same: `DIAGNOSTIC_EXECUTION_SCOPE.json` + `DIAGNOSTIC_REVIEW_READY.json` (`verdict=ready`, `scope_complete=true`, `trace`) under `local_assets/r49_phrase_grounding_failure_20261109` plus completed DeepSeek metadata; no diagnostic/GPU/API invocation yet; any later q169 production fix still needs its own separately reviewed amendment.
