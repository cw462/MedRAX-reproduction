# V4 Skill method validation — progress

Plan: `MedRAX_Skill_Method_Validation_Plan_v4.md`. Base commit at start: `65da316`.
This file records only what actually ran; anything not executed is marked as such.

## Naming correction carried over from the plan

The plan is right that the previous module names do not describe what they did:

| module | what it actually did | not |
|---|---|---|
| `memory_credit.py` | removes *retrieved memory entries* and measures the answer flip | not tool-step credit |
| `memory_rerank.py` | changes retrieval ranking | not next-action selection |
| `memory_capacity.py` | de-duplicates the injected block | not a capacity-limited pool update |

So this work uses **A/B/C/D/E** and the new modules carry the plan's names.

## Status: S0 in progress — semantic capture is working

S0 asks for A/B/C on five development cases. The prerequisite is that a real run
can record *semantic* observations, because the existing traces keep only tool
names, output lengths and hashes, from which no skill can be distilled.

That prerequisite is now implemented and verified on real runs.

### Implemented

`experiments/semantic_trace.py` derives, per tool call, the compact content a
summariser can use, and never invents a finding when the output cannot be parsed.
`memory_agent_eval.TrackedTool` writes one record per call to
`runs/<run>/semantic_trace.jsonl`.

### Verified on a real 2-question run (arm A, no memory)

```
semantic_trace.jsonl: 6 lines, 4 tool kinds, 0 unparseable

chest_xray_expert      completed  {"answer_text": "COP"}
chest_xray_classifier  completed  {"top_findings": [{"finding": "Lung Opacity", "score": 0.6325},
                                                    {"finding": "Mass", "score": 0.6149}, ...]}
chest_xray_report_generator completed {"report_text": "CHEST X-RAY REPORT FINDINGS: ..."}
xray_phrase_grounding  completed  {"grounded_regions": [{"phrase": "Consolidation in the right
                                     lower lung.", "box_xyxy_normalised": [0.154, 0.454, 0.433, 0.704]}]}
```

Each record keeps `execution_status`, `evidence_status="tool_statement_unverified"`,
`clinical_evidence="unknown"` and `step_credit=null`, so a tool's claim is never
promoted to a medical fact by being recorded.

### Two defects found while wiring this

1. The classifier returns a bare mapping of pathology to `numpy.float32` scores,
   not a wrapper with a `scores` key. A plain `isinstance(x, float)` test rejected
   every value, so the first smoke recorded "not parseable". Fixed with a numeric
   coercion and re-verified (local check with `np.float32`, plus the real run above).
2. (Earlier in this session) the grounding proxy returned a JSON string where the
   runner's `observe()` contract requires `(output, metadata)`; every grounding
   return was therefore counted invalid. Fixed and verified with `observe()`.
   See `reports/eight-tool-validation-2026-10-29.md`.

## Not yet done

* S0 itself: the A/B/C pilot on five development cases.
* S1: 60-case semantic collection and Skill v0 (`skill_distill.py`,
  `skill_render.py` do not exist yet).
* S2–S6: validation set, D branches, credit replay, heldout.
* No A/B/C/D/E comparison numbers exist yet in this plan's terms, so the 29-question
  history (12/14/11/15 correct) remains the only data and is *not* an independent
  test - the plan explicitly forbids treating it as final evidence.

## Cost so far

Ledger `api_budget_qwen_100cny_v8.json`: 68.56 CNY committed (conservative internal
bound, not the provider bill). The two smoke runs cost about 0.4 CNY.
