# First real classifier + report Agent run

This completed P1.3 execution check makes two original tools available to the real upstream Agent. It is a restricted-tool development run, not the six-tool paper reproduction or a memory result. All earlier runs are retained.

The predeclared sample is the first five questions in the original 50-question memory-training input, in its original order. These are five distinct cases, all with one image. Selection uses neither correctness nor truncation. Each question has a fresh direct and Agent conversation; the original per-question arm ordering is retained. Both arms use the same APIYi model request `gpt-4o-2024-11-20`, temperature 0.2, top-p 0.95, 1024 output-token cap, two-stage answer protocol, at most four model calls and two total tool calls. The original classifier description and report decoding parameters are retained. Registered tools are not forced to execute.

The run lasted **22:46:27–22:51:11 Asia/Shanghai on 2026-10-27**, or **284.16 seconds**. All ten planned arm outcomes have durable terminal records, including one failed outcome.

| Measurement | Direct | Classifier + report Agent |
|---|---:|---:|
| Predeclared questions | 5 | 5 |
| Correct / full denominator | 1/5 | 0/5 |
| Valid final options | 4/5 | 5/5 |
| Wrong valid options | 3 | 5 |
| API timeout outcomes | 1 | 0 |
| Observed output-length stops | 0 | 0 |
| Actual API requests | 9 | 15 |
| Actual classifier calls / valid returns | 0 / 0 | 5 / 5 |
| Actual report calls / valid returns | 0 / 0 | 5 / 5 |
| Reported input tokens | 6,524* | 21,894 |
| Reported output tokens | 2,100* | 3,090 |

`*` One direct request timed out at approximately 60.27 seconds and returned no usage. Reported token totals therefore exclude its unknown usage. There was no automatic retry. The error class was `APITimeoutError`; no HTTP status or provider bill was available.

Both tools actually returned valid output structures on all five Agent questions. Original tool results were passed to the Agent; safe traces contain version, argument/image fingerprints, output-contract checks, output hashes/lengths, status and elapsed time. This establishes execution and observation delivery, not correctness of the medical observations. Clinical evidence remains `unknown` and step credit remains `null`.

There were zero direct-wrong-to-Agent-correct changes and one direct-correct-to-Agent-wrong change. This tiny development sample cannot establish a general deterioration or attribute an error to the report tool. The exploratory paired case-cluster bootstrap interval for Agent minus direct accuracy was [-60, 0] percentage points (five cases, 10,000 resamples, seed 20261027). It is not a heldout efficacy result. No successful Agent trajectory is available from this batch for a success-memory pool; the five wrong answers must not be relabeled as successful experiences merely because their tools executed.

## Accounting and limits

The original shared CNY 100 ledger increased from **13.85858 to 20.04406**, leaving **79.95594**. Incremental conservative occupancy is **6.18548**: **0.98356** for known usage and **5.20192** retained for the unknown timeout request. These are accounting values, not actual provider charges. There were 24 actual requests; reservation blocks are not requests.

This batch lacks full-run CUDA peak measurement. One external sample showed 1,029 MiB on the active RTX 3090, which is only a point sample and must not be reported as a peak. A separate process-profile wrapper is prepared for subsequent runs. No actual multi-image case, segmentation call, VQA, grounding, clinical evidence validation, failure recovery or memory intervention was established by this run. Report text and model reasoning are not recoverable from hash-only logs; subsequent memory processing can use only the recorded structured execution facts.

## Reproducibility

`experiments/multi_tool_eval.py` loads verified local original classifier and report assets and the pinned upstream Agent. It validates the completed baseline, source files, package versions, original input/image hashes, prompts and shared ledger policy before issuing any request. `--segmentation-checkpoint` creates a separately identified three-tool configuration; that variant is not part of the results above.

```bash
python experiments/multi_tool_eval.py \
  --baseline-run /private/completed-diagnostic50 \
  --input /private/diagnostic50/inference.jsonl \
  --output /private/new-multi-tool-run \
  --ledger /private/existing-api-budget-100cny.json \
  --classifier-checkpoint /private/fixed-classifier.pt \
  --report-cache /private/verified-report-cache \
  --api-key-stdin
```

The classifier file must retain its validated original filename; paths above are placeholders. Use secure runtime stdin for the API key. Labels are opened only afterward by the separate offline scorer, on a derived five-question scoring manifest checked against the frozen run. This is process separation, not a claim of operating-system access isolation.

| Durable artifact | SHA256 |
|---|---|
| Run manifest | `d5b3ecec43fa706c38db94fb7ef19c2154990fadc5a31ab291547ef1239c8d6d` |
| Result journal | `bb7548a79464515dc2dbec49951a6464e973170829dcd59c2b9050d968c2c90e` |
| Final summary | `804e8c187d2588262f1ad745bc334d3eeadbc5f82d46a16f5790a3626b225956` |

The public repository contains code and aggregate results. Credentials, raw inputs, labels, images, private reports, original traces and full model weights remain outside Git.
