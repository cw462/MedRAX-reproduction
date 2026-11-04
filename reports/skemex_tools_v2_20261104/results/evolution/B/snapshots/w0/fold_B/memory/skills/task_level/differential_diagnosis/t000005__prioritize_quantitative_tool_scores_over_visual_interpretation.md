---
id: "t000005"
name: "Prioritize Quantitative Tool Scores Over Visual Interpretation"
description: "When diagnostic tool outputs provide quantitative confidence scores that are ambiguous or below the strong positive threshold, rely on these numerical values rather than generating unsupported visual interpretations of the image."
version: "1.0"
status: "active"
branch: "task_level"
task_category:
  - "differential_diagnosis"
source_trajectory_ids:
  - "16844_8143559676460"
applicable_conditions: "Tasks involving the interpretation of diagnostic imaging where automated classification tools return probabilistic scores or confidence levels, particularly when results are negative, equivocal, or moderate."
required_tools:
  - "chest_xray_classifier"
risk_level: "high"
created_at: "2026-11-04T13:53:34Z"
updated_at: "2026-11-04T13:53:34Z"
---

### Core Action
If `chest_xray_classifier` returns scores below the 'strong' threshold (e.g., < 0.8) for a suspected condition: (1) Accept the quantitative output as the primary evidence, acknowledging the finding is not strongly supported; (2) Do NOT claim to see specific radiological signs (e.g., 'visual inspection confirms...') that contradict or exceed the tool's confidence level; (3) Broaden the differential diagnosis to include other causes consistent with the low-confidence or negative tool result, rather than forcing a diagnosis based on hallucinated visual features.
