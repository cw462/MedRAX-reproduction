## Operational delta finding

Reviewed only `deployment_source/operational_delta/publish_r50_user_stopped.py` against the previously reviewed source.

**The delta is exactly as stated.** The sole executable change is in `push()` at line 592:

```python
git(['--literal-pathspecs','add','-f','--pathspec-from-file=-','--pathspec-file-nul'], literal)
```

- `-f` is a **force-add**, not a force-push. It only overrides gitignore for the explicitly enumerated pathspec (`--pathspec-from-file=-` + `--pathspec-file-nul`, literal-NUL retained), permitting the already-validated ignored report log files (e.g. `backend.stderr.log`) to be staged.
- The safety net is retained: line 594 still asserts `staged == set(plan['files'])`, so `-f` cannot stage anything outside the validated allowlist.
- Push remains ordinary: line 598 `subprocess.run(['git','push','origin','HEAD:main'])` — no `--force`.
- Base/HEAD/parent/remote-main guards unchanged (lines 586-590, 597): local HEAD == `3ab0a9275…`, remote main == BASE, no pre-staged files, `HEAD^ == BASE`.
- Scope is not expanded: `prepare()` (lines 467-502) is byte-identical to the reviewed version — same allowlist (report + 18 `SOURCE_NAMES` + 9 `TEST_NAMES` + stopped scorer + 4 `INDEXES`), same `open_questions_for_later`/`.secrets`/`__pycache__`/`hf_modules` exclusions, same per-file secret/NUL/JSON/JSONL validation (which now also covers the force-added `.log` files). `DATA/` and `open_questions` remain excluded.

No integrity or publication blocker. The scientific result, scores, and raw artifacts are unchanged; only the staging mechanics for approved ignored logs were adjusted, with the exact-staged-equality assertion preserving the allowlist boundary.

```json
{"scope_complete":true,"audit_scope":["online_feedback_and_Skill_protocol","request_resource_accounting","complete_results_and_claims"],"publication_blockers":[],"claim_supported":"yes","nonblocking_limitations":["git add -f overrides ignore rules for the allowlisted report logs; it is safe only because the staged == allowlist assertion is retained, not because ignore rules were removed.","Reviewer could not independently run git check-ignore or prepare natively (read-only); the -f necessity and 21536-file allowlist rest on the retained staged-equality assertion and the unchanged prepare() validation."]}
```
