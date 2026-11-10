# chexbench_openi_0050
Ordinal 289; source OpenI; stopped-prefix record.

Which finding is in this chest X-ray?

## Complete options

- **A**: right indwelling catheter
- **B**: left indwelling catheter

## Original images

![original](../../evidence/chexbench/assets/724f57ac57cac6bcb1128916aa7d2cb20568bd561a7a980919be177e94394369.png)

Explicit answer: **A. right indwelling catheter**; reference: **A**; correct: **True**.

The chest_xray_expert model identified a right indwelling catheter in the lateral chest X-ray.

[Prediction](../../evidence/chexbench/predictions/M43-IM-GT-S50-CXR6/chexbench_openi_0050.json) · [own post-prediction feedback](../../evidence/chexbench/feedback/chexbench_openi_0050.json) · [exact context and Skill version](../../evidence/chexbench/contexts/chexbench_openi_0050.json) · [all main requests/responses](../../evidence/chexbench/services/calls/R50-AGENT/chexbench_openi_0050)

## Tool requests and observations

- xray_phrase_grounding: status=completed; [selection](../../evidence/chexbench/services/tool_selections/R50-AGENT/chexbench_openi_0050/1.json), [full request/result/stdout/stderr artifacts](../../evidence/chexbench/services/tool_cache/11366014a54c47769a11aebd4d2a98f08eb6c5973b93fc45a614038596c2b3f8).
- chest_xray_expert: status=completed; [selection](../../evidence/chexbench/services/tool_selections/R50-AGENT/chexbench_openi_0050/2.json), [full request/result/stdout/stderr artifacts](../../evidence/chexbench/services/tool_cache/f8dc2728662fcb6edd8895cf1950bb927627a0d32bb419b6e1f5523a6a6597ad).

## Skill and prior-image provenance

Selected IDs: []; prior same-image IDs: [].

This is dataset-label scoring and model/tool narrative, not clinical adjudication or Skill causal verification.
