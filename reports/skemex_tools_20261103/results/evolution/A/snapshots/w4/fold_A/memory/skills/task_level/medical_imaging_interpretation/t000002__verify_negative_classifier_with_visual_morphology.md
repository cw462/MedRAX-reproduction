---
id: "t000002"
name: "verify_negative_classifier_with_visual_morphology"
description: "When a chest X-ray classifier returns no strong findings despite visible pathology, perform direct visual inspection of morphological features and temporal stability to identify chronic or congenital conditions."
version: "1.22"
status: "active"
branch: "task_level"
task_category:
  - "medical_imaging_interpretation"
source_trajectory_ids:
  - "12385_8353800689343"
applicable_conditions: "Chest imaging interpretation tasks where automated classification tools yield negative or low-confidence results for images containing obvious structural abnormalities."
required_tools:
  - "chest_xray_classifier"
risk_level: "high"
created_at: "2026-11-04T02:58:44Z"
updated_at: "2026-11-04T03:33:59Z"
---

### Core Action
If `chest_xray_classifier` returns non-empty `strong_findings`: (1) Do not accept generic labels as final conclusions; explicitly invoke `chest_xray_report_generator` for detailed morphological analysis. (2) Synthesize the diagnosis by prioritizing specific morphological evidence aligning with classifier signals. (3) **Conflict Resolution**: If the report describes anatomy as 'clear', 'normal', or 'limited' but classifier confidence scores are high (>0.5), prioritize the classifier's quantitative signal to confirm pathology presence. Use the report primarily for morphological context (e.g., volume status, distribution) rather than as a binary presence/absence check if it conflicts with high-confidence classifier scores. Treat the report's negative description as a likely false negative or hallucination, specifically when the classifier identifies a specific, localized finding that contradicts the general 'clear' label. **Crucially**, do not hallucinate specific morphological features (e.g., 'honeycombing', 'reticular pattern') to justify the classifier's label if those features are absent from the report; instead, acknowledge the limitation of the modality or the generic nature of the finding while maintaining the positive classification based on the quantitative score.
