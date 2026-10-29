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
| `skill_distill.py` | compiles; **not run end-to-end yet** (blocked below) |
| `skill_render.py` | **local check**: 671 chars, all sections, capability mapped to a real tool |
| `skill_policy.py` | **12 unit tests** |
| `roi_reinspect.py` | **local check**: real crop (325x250), inverted/un-normalised boxes rejected |
| `tool_step_replay.py` | **6 unit tests** (a test caught the "always pick the classifier" bug) |
| `tool_step_credit.py` | **6 unit tests** |
| `run_skill_validation.py` | **local smoke**: parses 29 config keys, refuses unready stages |
| `configs/skill_validation_v4.yaml` | `heldout_enabled: false` |

## What has actually run

* S1 collection started 18:13:27: **13 of 60** questions done, no errors, ~60 s/question.
  Partial scoring: 8/13 correct (Wilson 95% CI 35.5%-82.3%). These are **training**
  questions, not validation, so this is not a method result.
* One semantic-capture smoke (2 questions) verified the four tool kinds parse.

## Not run, and why

1. **Skill v0 distillation** — blocked by the provider ledger lock: the collection process
   holds it and `ProviderLedger` correctly refuses a second writer. Distillation must
   follow the collection, not overlap it. The same applies to S4's 120 replays.
2. **S0 pilot (5 cases A/B/C)** — needs skill v0, so it follows distillation.
3. **S2 fixed 60-case validation — blocked by missing images.** The server has exactly
   **100 images / 100 case dirs** (the frozen 60-train + 40-validation subset) and no
   benchmark archive. `data/prepared_v2/validation.inputs.jsonl` lists 490 questions over
   121 cases but their images are not on this machine; only 39 image-backed validation
   questions exist and 29 of them were already used for development. The plan forbids
   presenting those as final evidence. Options are with the user: transfer
   `figures.921e604.zip` (823 MB; 13 GB free), or accept a development-only comparison
   labelled as such.
4. **S3 (D_branch / D_roi) and S4 execution** — `skill_policy.decide` and
   `roi_reinspect.review_region` are written, but wiring them into the agent loop needs a
   continuation runner: start from an explicit prefix (question, prior observations, active
   skill, remaining budget), take a policy-chosen action, continue. That runner does not
   exist, so the stages refuse rather than approximating.
5. **S5 heldout** — deliberately disabled in the config until the user authorises it.

## Cost

Ledger `api_budget_qwen_100cny_v8.json`: about **68.9 CNY** committed across the session
(conservative internal bound, not the provider bill). V4 itself has cost roughly 1 CNY.

## Honest summary

The infrastructure is complete and tested wherever pure logic can be tested, and semantic
capture is proven on real runs. **No A/B/C/D/E comparison in the plan's terms exists yet.**
The two obstacles are not code quality: (a) the collection is still running, and (b) the
image archive needed for a genuinely new validation set is not on this machine.
