# CXR VQA toolsets — frozen first-round protocol

Main model: `qwen3.7-plus` (actual returned identifier retained). Temperature 0.2,
top_p 0.95, enable_thinking=false, 2048 output tokens per call. D uses one call;
adapted M/C use at most four and two selectable tool invocations. Adapted X uses
two turns and at most two selectable actions; automatic view/measurement work
is counted separately. No cross-case skills, dynamic memory, sibling questions,
extra history or new model training. Technical failures remain in the denominator.
No paid retries and no resending uncertain sends. Completed records are immutable.

## Data

`SLAKE-English-CXR-Closed`: official `BoKelvin/SLAKE` revision
`a9083ce6c34ac3ffb17671a605962924d8a8f9e9`, official test.json, English,
X-Ray, CLOSED, Lung: **114 questions / 30 original images**. All 30 originals were
visually inspected as chest radiographs. Original questions and short answers are
unchanged; no answer options added. The independent paper subset list was not
located in the official MedRAX tree or X-Ragent paper links. A matching count does
not establish identical question IDs, so this is not claimed as strict replication
of the paper's 114-item subset. SLAKE 1.0's authors warn of cleaned data changes.

Inputs, references and exact IDs: [data manifest](../../data/slake_cxr/manifest.json),
[inputs](../../data/slake_cxr/inputs.jsonl), [offline references](../../data/slake_cxr/references.jsonl).
Only input fields and bound original images enter inference; answers, semantic
labels, segmentation references and knowledge annotations are withheld.
Attribution: [official project](https://www.med-vqa.com/slake/),
[official author release, CC-BY-4.0](https://huggingface.co/datasets/BoKelvin/SLAKE).

VQA-RAD's official OSF Readme section 3 defines test_freeform/test_paraphrase;
the JSON uses test_freeform/test_para. Restricting these official test questions
to CLOSED and visually confirmed radiographs yields **116 questions / 58 images**.
All 107 CHEST originals were checked as actual radiographs before filtering.
`evaluation` is annotation-review status, never the split. Open test questions
are kept separately. The official OSF node declares CC0 1.0 Universal.
[VQA-RAD manifest](../../data/vqarad_cxr/manifest.json).
CheXbench remains gated and does not delay SLAKE.

## Workflows and deployment

* D: original image + current question -> final JSON, one call.
* M: bounded MedRAX-style image/tool reasoning loop with early stopping. Existing
  registry exposes classifier, report, segmentation, CheXagent, LLaVA-Med,
  MAIRA-2 grounding, image visualizer and DICOM processor. These eight entries
  are not nine deployed models. RoentGen generation (the upstream ninth optional
  entry) is absent. Actual loading/inference status must be reported separately.
* C: pinned CXRAgent source `0514b4897fd040ae2c32cf2f2cdc163a1144a06c`;
  optional director-selected tools -> EDV original-image validation -> optional
  focused expert -> director answer, all within four main calls. Six intended
  models are MedGemma-4B, LLaVA-Rad, CheXagent, LLaVA-Med, MAIRA-2 and MedVLM-R1.
  Missing services/weights are unresolved, and no full-six deployment is claimed.
  Any runnable subset receives its actual subset label before its first prediction.
* X: mechanism migration, not the paper's SFT/GRPO policy: optional region parsing,
  coordinate-preserving crop and local Qwen3.5-27B knowledge -> independent
  OpenCXR PA gate -> valid CXAS geometry -> second-turn answer. Failed/non-PA
  gates withhold values, never zero-fill. Missing backends block a full-X claim.
  Unsourced knowledge is explicitly model knowledge.

All tool observations are unverified model output. Classifier scores are not
severity. Single-image report claims cannot establish interval change. C and M
may reuse the same model services and cached outputs; differences include
scheduling, prompts, EDV and collaboration, not just tool identities.

Current resource constraint: 2 x RTX3090 24GB; about 12GB persistent disk initially
free. User authorized cleanup only of CT/segmentation data with local backups or
reproducible recovery. No unrelated data, unique originals, checkpoints, prior
experiment evidence or ledger is deleted to make room.

## Frozen evaluation

Answer format: `{"answer":"short direct answer","reason":"one short sentence"}`.
Only answer is scored. Unicode NFKC, lowercase, punctuation to whitespace,
whitespace collapse, exact entire-answer comparison; true/false map to yes/no.
No substring yes/no logic, semantic judging or explanation-based correction.
This custom evaluator is disclosed because an applicable official standalone
scorer was not located in the official data release. All four groups must finish
generation before any SLAKE scoring. Paired image-cluster percentile bootstrap:
10,000 replicates, seed 20261105, 95% intervals. No patient/exam IDs were supplied.
Report accuracy, complete counts, missing, corrections, harms, net gain, percentage
point difference, actual calls/cache/backend usage, tokens, elapsed time and costs.
Dataset scores stay separate. Small changes are not stable generalization claims.

## Reproduction entry points

```bash
python experiments/prepare_slake_cxr.py --source /path/to/official/download --out data/slake_cxr
python experiments/prepare_vqarad_cxr.py --source /path/to/official/osf/files --out data/vqarad_cxr
python experiments/run_cxr_vqa_toolsets.py --config /path/to/private/runtime.json --data data/slake_cxr --out /path/to/run --arms D
# Add --execute --api-key-stdin only for the already-authorized real execution.
# M/C/X are launched only after their actual frozen backend configuration is ready.
python experiments/score_cxr_vqa_toolsets.py --data data/slake_cxr --out /path/to/run --dest reports/cxr_vqa_toolsets/slake/analysis
```

Python dependencies for the shared runner: existing openai, numpy, Pillow and the
repository's existing client/profile/V12ProviderLedger. Tool-specific interpreters
are reused to avoid Transformers version conflicts. No credentials are published.
Existing shared money cap, inherited balance and request counter are reused;
request-count ceilings remain canceled. Token rates 4/12 CNY per million are only
a bookkeeping proxy; Credits and actual charges remain unknown. No credits bought
and no second-round skill experiment automatically authorized.

Status: initial D and M generation completed. No accuracy was read. M's initial
system prompt was found to conflict with intermediate planning; its 114 original
records are retained as an initial-controller run, and are not represented as a
validated repaired M comparison. See [controller repair](controller_amendment.md).
C/X deployment continues. Repaired M requires an explicit exception to the
first-request/no-repeat rule; D does not require any new paid calls.
