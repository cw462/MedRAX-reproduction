# V4 Skill method validation — progress

Plan: `MedRAX_Skill_Method_Validation_Plan_v4.md`. Base commit at start: `65da316`.
This file records only what actually ran. Anything not executed is listed as not executed.

## Naming correction carried over from the plan

| old module | what it actually did | not |
|---|---|---|
| `memory_credit.py` | removed *retrieved memory entries* and measured the answer flip | not tool-step credit |
| `memory_rerank.py` | changed retrieval ranking | not next-action selection |
| `memory_capacity.py` | de-duplicated the injected block | not a capacity-limited pool update |

This work uses **A/B/C/D/E**, and the new modules carry the plan's names.

## Modules

| module | verification level |
|---|---|
| `semantic_trace.py` | **real run**: 2 questions, 4 tool kinds, 0 unparseable |
| `skill_distill.py` | **real run**: 18 traces -> 17 skills, 0 rejected, no answer/option leakage |
| `skill_render.py` | **real run**: C's logged blocks rebuild identically (5/5 in S0) |
| `skill_policy.py` | **unit tests** + on-topic filter measured on 29 questions (mismatch 5 -> 1) |
| `roi_reinspect.py` | **local check**: real crop, inverted/un-normalised boxes rejected |
| `tool_step_replay.py` | **6 unit tests** |
| `tool_step_credit.py` | **6 unit tests** |
| `skill_branch_runner.py` | **real run**: one do/skip pair from a real checkpoint |
| `branch_probe.py` | **real run**: do/skip from a real checkpoint on the eight-tool runtime |
| `run_skill_validation.py` | **real run**: S0 and S2 round 1 driven end to end, resumable |
| `analyze_skill_s2.py`, `make_s2_report.py` | **real run**: produced the round-1 tables and report |

## What has actually run

* **S1 collection**: 60 of 60 training questions; 18 usable traces distilled.
* **Skill v0**: 17 skills from 18 traces, 0 rejected.
* **Retrieval relevance**: without the on-topic filter 5 of 29 injections were about a
  different finding; with it, **1 of 29**, with no question left without an injection.
* **Dataset**: `figures.zip` (822,949,819 bytes, 20,713 members, CRC clean) extracted to
  6,267 images; all 2,500 benchmark questions have every referenced image on disk.
* **S2 fixed validation set**: 60 questions from 82 never-used validation cases, one per
  case, round-robin over the official `categories` label (12 per type). Rule and excluded
  case ids in `runs/v4_validation60/manifest.json`.
* **S0 pilot (18:56–19:07)**: A/B/C on 5 questions, 5/5 terminals each, C's skill
  injection verified 5/5 by rebuilding it. **Not a method result**:
  `reports/v4-s0-audit-2026-10-29.md`.
* **S2 round 1 (complete, the only round that ran)** — A/B/C on the 60 fixed questions:

  | arm | correct | accuracy | Wilson 95% | CNY / q |
  |---|---:|---:|---|---:|
  | A no memory | 39/60 | 0.650 | 0.524–0.758 | 0.128 |
  | B structural memory | 38/60 | 0.633 | 0.507–0.744 | 0.119 |
  | C semantic skill | 33/60 | 0.550 | 0.425–0.669 | 0.134 |

  Paired (exact test, bootstrap over cases):
  A→B **−1.7pp** [−15.0, +11.7] p=1.00; B→C **−6.8pp** [−20.3, +6.8] p=0.45;
  A→C **−8.5pp** [−23.7, +6.8] p=0.38. **No arm separates from no-memory, and the two
  representations cost 0.119–0.134 CNY/question without buying accuracy.** C also had one
  `case_budget_exceeded` (graded 33/59 = 55.9%). Report:
  `reports/v4-s2-round1-2026-10-29.md`, full tables `reports/s2_round1_table.md`.
* **One real do/skip pair (S3/S4 feasibility)**: checkpoint `10301_...#2` from `runs/s0_C`,
  one process, real eight-tool runtime. Do: 1 tool call (`llava_med_qa`), 1 new
  observation (420 chars). Skip: 0 actions, 0 observations. Both answered, both settled,
  0.0165 CNY total. `reports/v4-branch-pair-2026-10-29.md`.

## Not run, and why

1. **S2 rounds 2–3** — cancelled at 19:35 before they started, and stay cancelled: per the
   rule agreed beforehand, C not clearly beating B means redesigning the representation
   and injection, not repeating this design.
2. **S3 (D_branch / D_roi) and S4 (E step credit) at scale** — the runner is now wired to
   the real runtime (one pair proved it), but a scaled action-contribution experiment is a
   design decision that waits on the redesign above.
3. **S5 heldout** — deliberately disabled in the config until the user authorises it.

## Cost

Ledger `api_budget_qwen_100cny_v9.json`: **95.64 CNY** committed (v9 inherits v8's 79.90;
a conservative internal bound at assumed prices, not the provider bill). Round 1 of S2
cost 22.86 CNY for 180 question-runs plus 0.0165 for the branch pair.

## Honest summary

The pipeline works end to end: A/B/C run on fresh questions, C injects exactly the
filtered skill block the log says it does, observations/answers/cost land on disk, and a
do/skip continuation can be run from a recorded checkpoint on the real runtime.

What the data say is less flattering: **on 60 never-used questions neither representation
beat having no memory at all.** The earlier 29-question read (B 48.3 > A 41.4) did not
survive. The intervals are wide (~±13pp), so a small effect is not excluded, but the
point estimates are at or below zero for both A→B and B→C, and the C−B interval rules out
a C gain larger than 7 points.

The known confound stands: C's block is at its 1400-char cap while B's is 554–1137, so
even that comparison mixes representation with length until `B_length_control` runs.
