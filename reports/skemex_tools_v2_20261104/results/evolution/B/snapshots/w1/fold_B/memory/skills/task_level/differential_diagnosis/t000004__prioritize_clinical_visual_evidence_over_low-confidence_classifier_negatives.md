---
id: "t000004"
name: "Prioritize Clinical/Visual Evidence Over Low-Confidence Classifier Negatives"
description: "When chest X-ray classifier scores are non-diagnostic but clinical symptoms and visual markers strongly suggest an acute pathology, prioritize the clinical and visual evidence over the negative tool output."
version: "1.1"
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
updated_at: "2026-11-04T14:03:52Z"
---

### Core Action
If `chest_xray_classifier` returns no strong findings (e.g., all scores < 0.8):

1.  **Interpret Tool Output Correctly**: Explicitly note that 'no strong finding' is not equivalent to 'negative' due to uncalibrated probabilities. Accept the quantitative output as primary evidence, acknowledging the specific pathology is not strongly supported by the model.
2.  **Avoid Visual Hallucination**: Do NOT claim to see specific radiological signs (e.g., "visual inspection confirms...") that contradict or exceed the tool's confidence level.
3.  **Contextualize Differential Diagnosis**:
    *   **If clinical history (e.g., sudden onset pain) or visual markers (e.g., arrows pointing to pleural lines) strongly suggest acute pathology**: Prioritize this evidence. List the suspected acute pathology as a primary consideration despite the tool's output.
    *   **Otherwise**: Broaden the differential diagnosis to include other causes consistent with the low-confidence or negative tool result, rather than forcing a diagnosis based on unsupported visual features.
