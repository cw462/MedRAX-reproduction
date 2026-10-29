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

## Modules: all eight exist

| module | verification level |
|---|---|
| `semantic_trace.py` | **real run**: 2 questions, 4 tool kinds, 0 unparseable |
| `skill_distill.py` | **real run**: 18 traces -> 17 skills, 0 rejected, no answer/option leakage |
| `skill_render.py` | **real run**: C's logged blocks rebuild byte-for-byte (5/5 in S0) |
| `skill_policy.py` | **unit tests** + on-topic filter measured on 29 questions (mismatch 5 -> 1) |
| `roi_reinspect.py` | **local check**: real crop (325x250), inverted/un-normalised boxes rejected |
| `tool_step_replay.py` | **6 unit tests** (a test caught the "always pick the classifier" bug) |
| `tool_step_credit.py` | **6 unit tests** |
| `run_skill_validation.py` | **real run**: S0 A/B/C completed, resumable, refuses unimplemented stages |
| `analyze_skill_s2.py` | **synthetic test**: pooling, pairing, per-type split, bootstrap CI |

## What has actually run

* **S1 collection**: 60 of 60 training questions; 18 usable traces selected for distillation.
* **Skill v0**: 17 skills distilled from 18 traces, 0 rejected; every skill maps its
  capability to a real tool.
* **Retrieval relevance test** (29 frozen validation questions): without the on-topic
  filter 5 of 29 injections were about a different finding; with it, **1 of 29**, with no
  question left without an injection.
* **Dataset**: `figures.zip` (822,949,819 bytes, 20,713 members, CRC clean) extracted to
  6,267 images; all 2,500 benchmark questions now have every referenced image on disk.
* **S2 fixed validation set**: 60 questions from 82 never-used validation cases, one per
  case, round-robin over the official `categories` label (12 per type). Rule and excluded
  case ids in `runs/v4_validation60/manifest.json`.
* **S0 pilot (2026-10-29 18:56–19:07)**: A/B/C on 5 questions, 5/5 terminals each, skill
  injection verified 5/5 by rebuild. Details and caveats:
  `reports/v4-s0-pilot-2026-10-29.md`. **Not a method result.**
* **S2 (2026-10-29 19:09:47, running)**: 3 rounds x arms A/B/C x 60 questions = 9 arm-runs,
  detached from the session. Input `runs/v4_validation60/inputs.jsonl`.
  **Scope change at 19:35: only round 1 runs for now** (A/B/C on the fixed 60), so the
  table can be reviewed before spending on repeats. The running orchestrator was armed
  with `--rounds 3`, so a stop watch took it down after round 1.
* **S2 round 1 (only round that will run for now)**: B finished 60/60 at **38 correct
  (63.3%, Wilson 50.7–74.4%)**, all 60 `completed`, mean 4.83 tool and 4.90 model calls,
  7.14 CNY charged (0.119 CNY/question). By official type: 10/12, 8/12, 7/12, 6/12, 7/12.
  A and C are running on the fresh ledger `v9` under a supervisor that resumes after the
  intermittent ledger fault; each fault costs at most one question.
* **Ledger faults**: B died at question 39 and A at question 6 with
  `monetary_guard_error`; the ledger path tore between two byte streams under load while
  reading consistently when idle. The guard was left alone; the mitigation is a fresh
  inherited ledger plus a supervised resume. Evidence:
  `reports/v4-ledger-incident-2026-10-29.md`.

## Not run, and why

1. **S2 results** — the nine arm-runs are in progress; each is 60 questions at roughly
   65 s/question, about 10 hours for all nine. The comparison table is produced by
   `analyze_skill_s2.py` from the nine `*_scored/score.json` sidecars.
2. **S3 (D_branch / D_roi) and S4 (E step credit)** — `skill_policy.decide`,
   `roi_reinspect.review_region` and `skill_branch_runner` exist and are unit-tested, but
   the runner is still only wired to fake tools and a fake model. Whether it is worth
   wiring to the real runtime is a decision S2 is supposed to inform: if C is not better
   than B, the semantic representation itself needs rethinking before more experiments.
3. **S5 heldout** — deliberately disabled in the config until the user authorises it.

## Cost

Ledger `api_budget_qwen_100cny_v8.json`: **73.35 CNY** committed at 19:18 CST (a
conservative internal bound at assumed prices, not the provider bill). S0 cost about
1.55 CNY for 15 question-runs. At the observed 0.12–0.13 CNY per question, the nine S2
arm-runs are projected to add roughly 65–70 CNY, taking the ledger to about 140 CNY.

## Honest summary

S0 proves the pipeline: the arms run, C injects the filtered skill block that the log
says it does, and observations/answers/cost land on disk. It says nothing about which
arm is better, because n=5.

The one methodological caveat already visible: C's block is at its 1400-char cap while
B's block is 554–1126 chars, so a B→C difference in S2 would mix representation with
prompt length until the `B_length_control` ablation runs.

The S0 raw run directories are intact under `runs/s0_A`, `runs/s0_B`, `runs/s0_C`
(renamed before S2 needed the `v4_*` names), and `reports/v4_s0_recovered.json` holds a
compact extract of the same run from the orchestrator log.
