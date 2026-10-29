# One real do/skip pair from a recorded checkpoint

Status: a **feasibility check**, not a method result. It proves the continuation runner
is wired to the real runtime and that a real do/skip contrast lands on disk; one
checkpoint says nothing about whether the action contributed.

Date: 2026-10-29. Artifact: `reports/v4-branch-pair-2026-10-29.json`.

## What was replayed

| item | value |
|---|---|
| checkpoint | `10301_8353800828076#2` from `runs/s0_C` |
| prefix | 2 real observations (`chest_xray_expert`, `xray_phrase_grounding`) |
| target action | `llava_med_qa` with the recorded arguments |
| runtime | the real eight-tool registry, `qwen3-vl-plus`, temperature 0.2 |
| ledger | `api_budget_qwen_100cny_v9.json` |

Both branches were run in **one process** (`branch_probe.py --pair`), so they share the
checkpoint object, the tool registry and the model instance.

## What happened

| | do_action | skip_action |
|---|---|---|
| actions executed | 1 (`llava_med_qa`) | 0 |
| new observations shown | 1 (420 chars of facts) | **0** |
| answer length | 2,424 chars | 2,574 chars |
| stopped reason | answered | answered |

Total: 1 tool call, 2 model calls, 2 ledger settlements, **0.0165 CNY**.

The answers differ in detail — the do branch adds that the mass "compresses and displaces
the esophagus to the left", which only appears in the LLaVA observation — while both
conclude compression rather than infiltration. That is the intended shape of the
contrast: the branch changes the information the model has, not the question.

## Verification

`verify_branch_pair.py` asserts and passes all of:

* both branches come from the same checkpoint;
* the do branch recorded exactly one observation and executed exactly one real tool call;
* the skip branch executed nothing and received **no** observation (nothing fabricated);
* both answers and both settlements are on disk (2 model calls, 2 settlements).

## Fidelity limits, stated rather than hidden

* The semantic trace stores argument strings **truncated at 300 characters**, so the
  replayed `llava_med_qa` call used the recorded (possibly truncated) question text.
* The do branch's observation is a *new* execution, not the observation recorded in the
  trace. That is the point of a replay, but it means the pair measures "this action, run
  now" rather than "this action, as it ran then".
* One checkpoint, one question. No estimate of action contribution follows from it.

## What it changes

D/E are no longer blocked by "the continuation runner is not wired to the real runtime".
Whether to spend on a scaled action-contribution experiment is now a design question,
not an engineering one — and after round 1 the design question is open: neither
representation beat the no-memory baseline on the 60 fixed questions.
