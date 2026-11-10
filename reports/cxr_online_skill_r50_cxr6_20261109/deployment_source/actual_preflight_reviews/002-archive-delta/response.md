Delta reviewed against the supplied exact diff, the complete changed `observe` method, and the new synthetic test source. I did not reread unchanged helpers.

## Findings

**Archival goal is met.** The exact tool `request.json` is now persisted before the send-intent marker, raw `backend.stdout.log` is saved alongside the existing `backend.stderr.log` (both written before the returncode/parse checks, so exit-7 and parse failures still retain raw stdout), and `TimeoutExpired` partial stdout/stderr are recovered via the exception's `.stdout`/`.stderr` attributes with a bytes/str branch. This closes the concrete gap (un-persisted request + missing raw stdout) without altering command/env/timeout/cache-key/result logic.

**No behavior drift on the primary paths.** `started.json` keeps `identity`+`utc` and only *adds* `automatic_retry:False` and, for `xray_phrase_grounding`, the `maira_unclosed_tag_eos_guard_v1`/`generation_policy_changed:True` declaration. That policy metadata is accurate (that tool runs `maira_guard_worker_r50.py`, whose `POLICY_ID` matches) and is declaration-only — the actual guard remains authoritative in the worker. The `started_unknown` branch, cache-hit branch, and `result.json` write are untouched. No new model calls.

**Test namespace fix is sound.** Providing `__file__` in the exec namespace is required because `observe` references `Path(__file__).with_name('cxr_vqa_tool_worker.py')` when `worker_script` is absent; without it the AST-isolated method would fail before any mocked `subprocess.run`. With it, the three tests exercise the exact success/exit7/timeout paths with a single mocked `subprocess.run` each (call_count==1, idempotent second-call cache hit). Test-only change, no production impact.

## Nonblocking limitation (one edge worth knowing)

`save(folder/'request.json', request)` now precedes `save(folder/'started.json', ...)`, and `save` is the strict `os.link` publisher (no idempotency, raises `FileExistsError`). If the process dies in the microsecond window *after* `request.json` lands but *before* `started.json` lands, a resume re-enters the `else` branch (started absent) and the second `save(request.json)` raises `FileExistsError`, hard-stopping rather than resuming. This window did not exist when `started.json` was the first write. The request content is deterministic for the same cache key, so the failure is loud, non-silent, and preserves the exact request as evidence — consistent with the no-auto-retry policy — but it is a slight crash-resume regression versus the original ordering. (A "skip-if-identical" write would remove it; not required for readiness.)

---

```json
{
  "scope_complete": true,
  "verdict": "ready",
  "audit_scope": ["tool_request_and_stdout_archiving_delta"],
  "blockers": [],
  "nonblocking_limitations": [
    "request.json is now saved before started.json using the strict os.link save(); a crash in the narrow window between the two writes makes a resume raise FileExistsError instead of resuming (loud, no silent retry, exact request preserved as evidence).",
    "The MAIRA policy entries in started.json are declaration-only metadata; actual generation policy remains authoritative in maira_guard_worker_r50.py (policy_id matches maira_unclosed_tag_eos_guard_v1).",
    "The synthetic timeout test covers only the bytes partial-log branch of the TimeoutExpired recovery; the str branch is exercised indirectly and is trivial."
  ]
}
```
