---
id: "t000004"
name: "Prioritize Clinical/Visual Evidence Over Low-Confidence Classifier Negatives"
description: "When chest X-ray classifier scores are non-diagnostic but clinical symptoms and visual markers strongly suggest an acute pathology, prioritize the clinical and visual evidence over the negative tool output."
version: "1.5"
status: "active"
branch: "task_level"
task_category:
  - "differential_diagnosis"
source_trajectory_ids:
  - "16844_8143559672130"
applicable_conditions: "Tasks involving differential diagnosis where automated image classification tools return low-confidence or negative results despite strong contextual clues (symptoms, specific visual annotations) indicating a potential acute condition."
required_tools:
  - "chest_xray_classifier"
risk_level: "high"
created_at: "2026-11-04T13:53:04Z"
updated_at: "2026-11-04T14:14:28Z"
---

### Core Action
If `chest_xray_classifier` returns no strong findings (e.g., all scores < threshold) but visual inspection reveals distinct structural pathology (e.g., bone destruction, apical mass, obvious masses):

1. **Accept Tool Limitation**: Explicitly acknowledge that the classifier did not detect strong visual evidence. Do NOT hallucinate radiological signs (e.g., specific curvilinear opacities or pathognomonic shapes) to match the clinical suspicion.
2. **Prioritize Direct Pixel Evidence**: Rely strictly on visible, unambiguous structural markers identified through direct visual inspection, such as bone destruction, large masses, or significant anatomical distortion. Do not dismiss these visible abnormalities solely because the classifier failed to flag them as 'strong'.
3. **Differentiate Based on History**: Use the clinical context to interpret these visible structural anomalies, distinguishing between potential causes that may be outside the classifier's detection scope, rather than forcing a diagnosis based on unsupported subtle features.
