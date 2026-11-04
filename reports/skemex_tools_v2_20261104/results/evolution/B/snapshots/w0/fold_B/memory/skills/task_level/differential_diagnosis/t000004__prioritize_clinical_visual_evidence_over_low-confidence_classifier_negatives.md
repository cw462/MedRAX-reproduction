---
id: "t000004"
name: "Prioritize Clinical/Visual Evidence Over Low-Confidence Classifier Negatives"
description: "When chest X-ray classifier scores are non-diagnostic but clinical symptoms and visual markers strongly suggest an acute pathology, prioritize the clinical and visual evidence over the negative tool output."
version: "1.0"
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
updated_at: "2026-11-04T13:53:04Z"
---

### Core Action
If `chest_xray_classifier` returns no strong findings (e.g., all scores < 0.8) BUT clinical history (e.g., sudden onset pain) or visual markers (e.g., arrows pointing to pleural lines) strongly suggest a specific acute pathology: (1) Do NOT conclude 'normal' or rule out the pathology based solely on the classifier output; (2) Explicitly note that the tool's lack of calibrated probabilities means 'no strong finding' is not equivalent to 'negative'; (3) Prioritize the clinical and visual evidence in the final differential diagnosis, listing the suspected acute pathology as a primary consideration despite the tool's output.
