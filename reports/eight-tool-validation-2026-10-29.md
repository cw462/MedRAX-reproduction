# 8-tool validation run, 2026-10-29 — results are INVALID, do not use

This run finished (11:30 → 12:55) but its numbers must not be read as a method
comparison. The eighth tool never returned a valid observation, and every failed
call still consumed the per-case tool budget.

## What was run

Four arms, 29 frozen validation questions, **all eight tools**, the unchanged
4 tool-call / 6 model-call budget, 240 s per case.

| arm | graded | correct | accuracy (all 29) | status counts |
|---|---:|---:|---:|---|
| R0 no memory | 14 | 7 | 24.1% | completed 14, budget_exceeded 15 |
| R1 frozen retriever | 16 | 9 | 31.0% | completed 16, budget_exceeded 13 |
| R5 text retriever | 13 | 4 | 13.8% | completed 13, budget_exceeded 16 |
| R5+R7 text+diverse | 17 | 9 | 31.0% | completed 17, budget_exceeded 12 |

Ledger after the run: **56.156024 CNY** committed (conservative internal bound).

## Why these numbers are not usable

Every arm called grounding, and **every grounding return failed validation**:

```
R0             called 19/29, validated_returns 0
R1             called 21/29, validated_returns 0
R5             called 21/29, validated_returns 0
R5+R7          called 11/29, validated_returns 0

issue tags: tool_failed_or_invalid 19, case_call_or_time_limit 15, tool_arguments_rejected 5
failed tool returns in R0: 21
```

The agent therefore spent tool calls on a tool that always answered with something
the runner rejected, and then ran out of budget. `case_budget_exceeded` rose from 9
(seven-tool run) to 15, which is the mechanical consequence.

## Root cause

`memory_agent_eval.observe()` validates tool returns against the official shape:

```python
output, meta = (result if isinstance(result, tuple) and len(result) == 2 else (result, {}))
status = meta.get('analysis_status')          # -> None for a bare string
ok = status == 'completed' and not failed and text is not None   # -> False
```

The registry proxy returned `json.dumps({...})`, a plain string, so `meta` was `{}`
and `valid` was always false. The official tool returns `(output, metadata)`; the
proxy must do the same.

## Fix and verification

`tool_registry_ext._ground` now returns `(output, metadata)` with
`metadata["analysis_status"]`, and was checked with the runner's own validator:

```
return type: tuple | len: 2
observe -> {"kind": "grounding", "valid": true, "tool_analysis_status": "completed",
            "response_chars": 468}
VALID: True
second call (different phrase): VALID: True
```

## Consequences for the seven-tool comparison

The seven-tool run (R0 37.9%, R1 48.3%, R2 41.4%, R3 55.2%) was **not** affected:
that pool's `available_tool_names` never contained `xray_phrase_grounding`, and the
tool did not exist in the registry then.

What *is* now unknown is whether the drop from 37.9% to 24.1% is caused by the
eighth tool, by the broader tool set changing agent behaviour, or purely by the
budget being spent on a broken tool. Those three explanations are not separated by
this run and a corrected re-run is required.

## Recommended next step

Re-run the same four arms with the corrected proxy. Two open decisions for the
user:

1. Keep the 4/6 call budget, or release it (the paper specifies only a maximum
   time, `t_max`; `recursion_limit` was hardcoded to 12 and has been made
   configurable as `--recursion-limit` so a released budget is not silently cut
   off by LangGraph).
2. Whether R5's 13.8% should be read at all: with grounding broken it is
   confounded, but it is also the only arm where the text retriever pushed more
   questions past the budget (16), which is itself informative about block length.
