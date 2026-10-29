# V4 skill validation — results so far

Only measured results appear here. Anything still running or not started is marked
as such, and no number below is treated as a method conclusion.

## S0 — five-question functional pilot (complete)

Five questions from the frozen development subset, one round, arms A/B/C, eight
tools, released budget (12 tool / 16 model calls, 240 s per case).

| arm | graded | correct | accuracy |
|---|---:|---:|---:|
| A no memory | 5 | 4 | 80% |
| B memory + question-text retrieval + diversity filter | 5 | 3 | 60% |
| C semantic skill v0 | 5 | 3 | 60% |

**What this establishes.** The pipeline runs end to end and the three arms are
actually distinct:

```
v4_A_r1: retrieval rows=0, rows_with_skills=0
v4_B_r1: retrieval rows=5, rows_with_skills=0     (memory ids, not skills)
v4_C_r1: retrieval rows=5, rows_with_skills=5, skill_chars=[1400,1400,1400,1400,1400]
```

C injected a skill block on every one of its five questions, at the full 1400
character budget. A silent empty injection would have looked identical to a
failure, so this was the point of the pilot.

**What this does not establish.** Anything about method quality. With five
questions one answer moves accuracy by 20 points, and the ordering here
(A > B = C) is the opposite of the earlier 29-question read (B 48.3% > A 41.4%),
which is exactly what a five-question sample does. Per the plan this run is a
functional check only.

## S2 — 60 fresh cases, three arms, three rounds (running)

Input is the fixed 60-case set documented in `reports/v4-validation-set-60.md`:
cases never used in development, balanced 12/12/12/12/12 across the five official
question-type groups, image counts reported rather than filtered away.

Launched at about 19:10. Expected about 7 hours for 9 arm-runs. **No result from
this stage exists yet**, so no comparison table is printed here.

## S3 / S4 — not started

`skill_policy.decide` (state-driven action choice), `roi_reinspect` (full image
plus region sent to the vision model) and `skill_branch_runner` (do/skip/alternate
continuation from a checkpoint) are implemented and unit-tested against fakes,
but none of them is wired to the real eight-tool runtime yet. The stages refuse
rather than approximating.

## Operational constraints learned the hard way

1. **Paid stages must be strictly serialised.** The provider ledger refuses a
   second writer, so a stage that starts while the previous one is still exiting
   dies with `LedgerLocked`. This killed the first S2 launch.
2. **Run directory names must not collide across stages.** The resumable
   orchestrator skips an arm whose `summary.json` exists, so reusing a name made
   S2 silently skip its whole first round. S0's directories were renamed `s0_*`.
3. **A tooling note that mattered twice:** an unquoted empty positional argument
   collapses when the command is assembled for `bash -lc`, shifting `$6/$7` in
   `run_arm.sh`. The memory arm survived it, the no-memory arms did not, which is
   why a two-arm smoke test would have missed it.

## Cost

Ledger `api_budget_qwen_100cny_v8.json`: **72.43 CNY** committed (conservative
internal bound, not the provider bill). S2 is still spending.
