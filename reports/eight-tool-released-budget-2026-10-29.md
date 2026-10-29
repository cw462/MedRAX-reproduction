# 8-tool validation comparison with the call budget released

Date: 2026-10-29. Status: **single-seed development comparison on the 29 frozen
validation questions; not a paper reproduction and not clinical validation.**

## Protocol

Eight tools available (`chest_xray_classifier`, `chest_xray_report_generator`,
`chest_xray_segmentation`, `chest_xray_expert`, `llava_med_qa`,
`xray_phrase_grounding`, `image_visualizer`, `dicom_processor`), `qwen3-vl-plus`
as the central model, 29 frozen validation questions, 240 s per case.

The paper specifies **only a maximum time** (`t_max`, Algorithm 1) and no tool or
model call cap, so the artificial limits were released:

| parameter | capped run | this run |
|---|---:|---:|
| `max_tool_calls` | 4 | 12 |
| `max_model_calls` | 6 | 16 |
| `recursion_limit` | 12 (hardcoded) | 40 |
| `max_case_seconds` | 240 | 240 |

`recursion_limit` had to be made configurable first: LangGraph spends two
super-steps per tool round, so the hardcoded 12 would have cut the graph off at
six rounds no matter what the call limit said.

## Result

| arm | graded | correct | accuracy (29) | status |
|---|---:|---:|---:|---|
| R0 no memory | 25 | 12 | 41.4% | 25 completed, 3 failed, 1 model_error |
| R1 frozen retriever | 29 | 14 | 48.3% | 29 completed |
| R5 text retriever | 29 | 11 | 37.9% | 29 completed |
| **R5+R7 text + diversity** | 29 | **15** | **51.7%** | 29 completed |

Paired against R0 on the same 29 questions (exact McNemar):

| comparison | shared | both correct | both wrong | R0 only | memory only | p |
|---|---:|---:|---:|---:|---:|---:|
| R0 vs R1 frozen | 29 | 11 | 14 | 1 | 3 | 0.625 |
| R0 vs R5 text | 29 | 10 | 16 | 2 | 1 | 1.000 |
| R0 vs R5+R7 | 29 | 12 | 14 | 0 | 3 | 0.250 |

Ledger after this run: **68.153728 CNY** committed (conservative internal bound,
not the provider bill). This run cost about 12 CNY.

## Finding 1: the earlier eight-tool numbers were measuring the budget

The same four arms with the 4/6 cap, run earlier today:

| arm | capped | released | change |
|---|---:|---:|---:|
| R0 | 24.1% | 41.4% | +17.3 |
| R1 | 31.0% | 48.3% | +17.3 |
| R5 | 13.8% | 37.9% | +24.1 |

Under the cap, 12-16 questions per arm exhausted the call budget; with it
released, the memory arms completed all 29 and only R0 still lost 4 cases (3
failed, 1 model_error, neither of them budget). So **"eight tools made it worse"
was an artefact of a four-call ceiling**, and the seven-tool comparison
(R0 37.9% / R1 48.3% / R2 41.4% / R3 55.2%) should be read as a different protocol,
not a better one.

## Finding 2: text retrieval alone hurts, the diversity filter rescues it

R5 lowers accuracy relative to the frozen retriever (11 vs 14 correct). R7 then
raises it to the best arm in the table (15 correct, 51.7%).

That ordering matches the block-content measurements: the text retriever made
blocks question-specific (7 -> 28 distinct blocks over 29 questions) but also
pulled clusters of near-identical memories, and 32 of 87 slots were
near-duplicates. Removing them costs nothing in coverage (all 29 blocks stay
non-empty) and recovers more than the retrieval change lost.

So the useful contribution in this pair is the **diversity filter**, and the
honest description of R5 is "a retriever that alone does not help".

## The eighth tool is heavily used

```
xray_phrase_grounding         125 calls (111 returned valid, 89%)
chest_xray_report_generator   114
chest_xray_classifier         111
chest_xray_expert             103
llava_med_qa                   13
image_visualizer                6
chest_xray_segmentation         0
dicom_processor                 0
```

Grounding became the **most-called tool** of the eight, which is the strongest
argument for having wired it: without it the agent would have spent those 125
calls elsewhere. Note that segmentation and DICOM were available but never used,
so "eight tools wired" does not mean "eight tools exercised".

## Limitations

* Single seed; 29 questions; no p-value here is significant, and the R5+R7 vs R0
  result is 3 discordant pairs (p = 0.25).
* R0 lost 4 cases to failures rather than budget; those are counted as not correct
  and slightly penalise the baseline. Every memory arm completed 29/29.
* The comparison is against a no-memory arm, not against the authors' reported
  numbers; the central model is Qwen, not GPT-4o.
* Call volume is now driven by the agent, not by a ceiling: 114-124 tool calls and
  122-171 model calls per arm of 29 questions.
* Per-question wall time is 47-54 s per arm average, so heldout (505 questions,
  three arms) is roughly 20-23 h at this configuration.
