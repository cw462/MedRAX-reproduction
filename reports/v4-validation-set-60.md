# V4 fixed validation set (S2)

> **Historical exposure correction (2026-10-31):** Later retained-run comparison found that `13238_8353800603808` had already triggered model calls in `val30_r0_v1` and two early R1 attempts, all ending without a legal answer. It was absent from the later exclusion subset but included here. Thus any statement below that all selected inputs had never been used in development is too strong. The selection and original predictions remain unchanged; see [the source-linked historical review](history/early-experiments.md) and [this question's retained records](history/early/cases/13238_8353800603808.json).

Status: built and verified on 2026-10-29. This is the case list the A/B/C/D/E
comparison will use; it is fixed before any method result is produced.

## Where it came from

The public benchmark archive was fetched from the authors' dataset repository
`wanglab/chest-agent-bench` through the mirror `hf-mirror.com` (huggingface.co is
unreachable from this network; eurorad.org returns 403 to this server). The
download matches the project's own frozen audit exactly:

| item | downloaded | frozen audit (`data/audit_v3/summary.json`) |
|---|---|---|
| archive bytes | 822,949,819 | `archive_bytes: 822949819` |
| archive members | 20,713 | `archive_members: 20713` |
| zip integrity | `testzip() == None` | `all_member_crc_checked: true` |
| metadata rows | 2,500 | `total_questions: 2500` |
| metadata cases | 609 | `total_cases: 609` |

6,267 images were extracted into `data/memory_v1/images/`, and every referenced
image for all three frozen splits now exists:

```
memory_train   questions=1500  with_missing_images=0
validation     questions= 490  with_missing_images=0
heldout_test   questions= 510  with_missing_images=0
```

## How the 60 cases were chosen

* 121 validation cases exist; **82** remain after excluding every case already used
  in development (29 validation + 60 training = 39 distinct cases).
* A case qualifies only if every image it references exists.
* Per case, the question with the fewest images is used, so the set does not
  silently prefer single-image questions: 18 questions have 1 image, 32 have 2,
  6 have 3, 3 have 4 and 1 has 5.
* Selection is round-robin over the official `categories` labels from the
  benchmark metadata, giving an exactly balanced set:

| official type | questions |
|---|---:|
| detection, localization, characterization, reasoning | 12 |
| localization, comparison, relationship, reasoning | 12 |
| classification, comparison, diagnosis, reasoning | 12 |
| detection, classification, relationship, reasoning | 12 |
| classification, characterization, diagnosis, reasoning | 12 |

* Ties are broken by case id, seed 20261029. The rule is recorded in
  `runs/v4_validation60/manifest.json` on the server, together with the excluded
  case ids and the image-count distribution.

## Why this matters for the comparison

The previous 29 questions had been used repeatedly during development. The plan
explicitly forbids presenting them as final evidence, and any method choice made
on them would bias a later test. This 60-case set is drawn only from cases never
used before, so A/B/C results on it are a genuine held-out-within-validation
comparison rather than a re-read of the development set.

Labels for these questions live in `data/prepared_v2/validation.labels.jsonl` and
are used only by the scorer.
