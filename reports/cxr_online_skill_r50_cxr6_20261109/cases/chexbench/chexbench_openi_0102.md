# chexbench_openi_0102
Ordinal 341; source OpenI; stopped-prefix record.

Which finding is in this chest X-ray?

## Complete options

- **A**: surgical instruments in the left breast
- **B**: surgical instruments in the right breast

## Original images

![original](../../evidence/chexbench/assets/cf92ef873777950041e3ac4b25f0ecde69247a7f7fc2dac8729179c9d018cbd8.png)

Explicit answer: **B. surgical instruments in the right breast**; reference: **A**; correct: **False**.

Expert QA identified anterior surgical clips, which correspond to the right breast on a standard lateral chest X-ray.

[Prediction](../../evidence/chexbench/predictions/M43-IM-GT-S50-CXR6/chexbench_openi_0102.json) · [own post-prediction feedback](../../evidence/chexbench/feedback/chexbench_openi_0102.json) · [exact context and Skill version](../../evidence/chexbench/contexts/chexbench_openi_0102.json) · [all main requests/responses](../../evidence/chexbench/services/calls/R50-AGENT/chexbench_openi_0102)

## Tool requests and observations

- xray_phrase_grounding: status=completed; [selection](../../evidence/chexbench/services/tool_selections/R50-AGENT/chexbench_openi_0102/1.json), [full request/result/stdout/stderr artifacts](../../evidence/chexbench/services/tool_cache/da9b9ff17527858b47cd2aab0d6b8a91fb79f81689cbdfdbd32422df7094167d).
- xray_phrase_grounding: status=completed; [selection](../../evidence/chexbench/services/tool_selections/R50-AGENT/chexbench_openi_0102/2.json), [full request/result/stdout/stderr artifacts](../../evidence/chexbench/services/tool_cache/10ef7b66852d6b14764cdd8c30097fd29ada2f7815271ec0b99e60b78e8798e8).
- chest_xray_expert: status=completed; [selection](../../evidence/chexbench/services/tool_selections/R50-AGENT/chexbench_openi_0102/3.json), [full request/result/stdout/stderr artifacts](../../evidence/chexbench/services/tool_cache/cec7fca415e4c57c5c912021d3bcaaaac9cd739882e9b2411e9ed0f943a69adc).

## Skill and prior-image provenance

Selected IDs: ['s_39391f294d360026']; prior same-image IDs: [].

Phrase Grounding Verification for Conflicting Binary Choices

1. Identify the two competing options from the question.
2. For each option, construct a specific phrase describing the finding and its location (e.g., 'right lower lobe atelectasis').
3. Call xray_phrase_grounding for the first option's phrase.
4. Check the observation: if predictions list is empty or analysis_status indicates no finding, record as negative.
5. Call xray_phrase_grounding for the second option's phrase.
6. Check the observation: if predictions contain valid bounding boxes, record as positive.
7. Compare results: Select the option with valid grounding boxes. If both have boxes, prefer the one with higher confidence or more precise localization if available; if neither has boxes, re-evaluate or select based on prior probability if forced.
8. Stop when a clear distinction in grounding presence/absence is established between the two options.

Actual source cases: [chexbench_openi_0073](chexbench_openi_0073.md)

This is dataset-label scoring and model/tool narrative, not clinical adjudication or Skill causal verification.
