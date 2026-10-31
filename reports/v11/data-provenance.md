# Case and image provenance

This package accompanies the completed V10/V11 fixed sixty-question experiments.
It contains the benchmark question text and image inputs used by those runs,
together with saved model/tool observations needed to inspect the failures.
The user explicitly requested this case-level publication. Exporting the package
did not run a new model request, alter a prediction, or open a new evaluation.

## Upstream sources and rights

- Dataset: [wanglab/chest-agent-bench](https://huggingface.co/datasets/wanglab/chest-agent-bench).
- Pinned source revision: [`921e60440927f9893228d843c0206b755744252a`](https://huggingface.co/datasets/wanglab/chest-agent-bench/tree/921e60440927f9893228d843c0206b755744252a).
- [README at that revision](https://huggingface.co/datasets/wanglab/chest-agent-bench/raw/921e60440927f9893228d843c0206b755744252a/README.md).
- The upstream README identifies Eurorad as the source of the clinical cases.
  Each case page links to its corresponding `https://www.eurorad.org/case/<id>`
  page using the original case/figure directory identifier.

The pinned dataset README did not provide an explicit dataset license declaration.
These are **third-party benchmark questions and images**; the repository's code
license does not relicense them. Original source attribution and figure filenames
are preserved. No additional Eurorad article text was copied into this package.

## Included artifacts

| Material | Count | Export location |
|---|---:|---|
| Fixed benchmark questions with full options | 60 | `cases/<question_id>.md` and `.json` |
| Original benchmark images | 117 | `images/originals/figures/<case_id>/` |
| Cached local/tool comparison images | 21 | `images/evidence/<question_id>/` |
| S2 targeted original-pixel crops | 9 | `images/followup/<question_id>/` |
| Cases with anonymous X/Y comparison packets | 21 | Case `cached_comparison` field |
| Cached tool request/return observations | 140 | Case `cached_comparison.tool_observations` field |
| Cases with S2 action/reader records | 19 | Case `s2_followup` field |
| Cases with S3 blind-reader observations | 21 | Case `v11.S3.blind_observation` field |

The 147 exported images total **12,557,105 bytes**. Original image paths are
deduplicated, and each original is stored once. A comparison packet points back to
the same public original file rather than creating another copy. Cached and S2
images retain the bytes generated during the completed experiments; no images
were recreated or rescaled for publication.

The original 60 questions are copied from the frozen V10 selection, in the same
order and with the same figure list. Per-image SHA-256 values, sizes and byte counts
are available in [cases.json](cases.json) for artifact identification. The complete
package is navigable through the [case index](cases/README.md).

Case JSON preserves the question strings exactly. Markdown display removes trailing
line whitespace only; it does not change the wording, options or experiment input.

## Interpretation and publication transformations

- Cached comparison observations are the values actually passed into S1. Their
  neutral image/observation IDs and anonymous X/Y mapping are exposed after the
  experiment to make evidence tracing possible.
- Tool observations may include erroneous classifier predictions, generated
  reports or reader interpretations. They are **not clinically validated facts**.
- S2 action plans, resulting pixels and reader reports are linked together. S3
  blind-reader reports are stored alongside the subsequent selector outputs.
- Parsed V10 candidate/gate and V11 selector outputs are included. The historical
  supplement now also preserves all saved observable V11 conversation messages
  in [180 stage/question trace archives](traces/README.md), from 563 JSON checkpoints.
  Embedded images are replaced with byte-identical file references. No hidden
  model reasoning is requested, reconstructed, or added.
- Reference answers and correctness records are published after completed
  generation/scoring; they were not input to inference. See
  [per-question outcomes](per-question-outcomes.json) for the scoring provenance.
- Image files replace embedded base64 image payloads. Local/remote filesystem
  paths are replaced with public image paths or `[private_path_omitted]`.
- Four cached error-string fields already contain `http[private_path_omitted]`
  in their PyTorch memory-management documentation references. That text was
  produced by the original comparison-packet sanitizer and is retained as a
  recorded preprocessing artifact; it is not a working citation. The separate
  dataset and Eurorad provenance links in this export remain intact.
- Credentials, host authentication data, model weights, ledger files, full
  retrieved guideline texts and private contact sheets are excluded.

## Visual privacy inspection and limits

All 117 original images were reviewed in eight private contact sheets, and all
30 additional images were reviewed in two further sheets. Images with visible
corner text were inspected at original resolution. No clear patient name or
address was identified in that visual review.

Upstream burn-ins remain intact: Eurorad case **9308**, `figure_1.jpg` and
`figure_2.jpg`, includes a date/time and an unexplained numeric string; case
**3397**, `figure_1.jpg`, includes truncated date/time text. These annotations
were already present in the public benchmark images used by the experiment.
They were preserved with the source pixels at the user's request. The numeric
string's meaning was not established, and no identity inference was performed.

This visual review is not a certification of de-identification and does not
establish clinical validity. Source anatomy, orientation markers, annotations and
image limitations must be considered when interpreting the recorded outputs.

## Offline exporter

[experiments/export_v11_cases.py](../../experiments/export_v11_cases.py) reads the
frozen local run outputs plus a private cache of the selected remote image files
and comparison metadata. It emits only the selected publication fields and copies
image bytes. The private cache is not committed.

```powershell
python experiments/export_v11_cases.py --references reports/v11/per-question-outcomes.json
```

The exporter does not access an API, launch inference, recalculate experiment
scores, or read a cost ledger. The source cache must already be available locally.
