# chexbench_openi_0108
Ordinal 347; source OpenI; stopped-prefix record.

Which finding is in this chest X-ray?

## Complete options

- **A**: left clavicle deformity
- **B**: right clavicle deformity

## Original images

![original](../../evidence/chexbench/assets/f643bae3d962d7c9b1bbf8f78c65ddd2bf13ccb9be10ad673d8d0e206bf3c6db.png)

Explicit answer: **B. right clavicle deformity**; reference: **A**; correct: **False**.

Visual inspection of the original image confirms a clear deformity and discontinuity in the right clavicle (viewer's left), while the left clavicle appears intact; the grounding tool incorrectly localized the finding to the normal side.

[Prediction](../../evidence/chexbench/predictions/M43-IM-GT-S50-CXR6/chexbench_openi_0108.json) · [own post-prediction feedback](../../evidence/chexbench/feedback/chexbench_openi_0108.json) · [exact context and Skill version](../../evidence/chexbench/contexts/chexbench_openi_0108.json) · [all main requests/responses](../../evidence/chexbench/services/calls/R50-AGENT/chexbench_openi_0108)

## Tool requests and observations

- xray_phrase_grounding: status=completed; [selection](../../evidence/chexbench/services/tool_selections/R50-AGENT/chexbench_openi_0108/1.json), [full request/result/stdout/stderr artifacts](../../evidence/chexbench/services/tool_cache/40013caedf5a951321b052133eb19fbdb4926cb88c79fac416eba580d8766d70).
![tool image](../../evidence/chexbench/assets/57bf4d0ef7285f6c7613044b3c07673f2e6fca3d4b9a8d948c24fe607bee12d1.png)
- xray_phrase_grounding: status=completed; [selection](../../evidence/chexbench/services/tool_selections/R50-AGENT/chexbench_openi_0108/2.json), [full request/result/stdout/stderr artifacts](../../evidence/chexbench/services/tool_cache/9a64b1f4408bb39489d11cf235992c8a6b5c97a26e184865de6377b11d39df8d).
![tool image](../../evidence/chexbench/assets/0d2b8fa4fc0a95a03c62eae8d6d59d7595d2ef47f1d1e865dca6d647e4ce730d.png)

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
