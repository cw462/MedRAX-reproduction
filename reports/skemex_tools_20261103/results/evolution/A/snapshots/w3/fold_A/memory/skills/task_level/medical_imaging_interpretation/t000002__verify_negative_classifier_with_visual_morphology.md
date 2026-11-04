---
id: "t000002"
name: "verify_negative_classifier_with_visual_morphology"
description: "When a chest X-ray classifier returns no strong findings despite visible pathology, perform direct visual inspection of morphological features and temporal stability to identify chronic or congenital conditions."
version: "1.10"
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
updated_at: "2026-11-04T03:25:12Z"
---

### Core Action
If `chest_xray_classifier` returns non-empty `strong_findings`: (1) Do not accept generic labels as final conclusions; explicitly invoke `chest_xray_report_generator` for detailed morphological analysis (e.g., convex borders, silhouette signs). (2) Synthesize the diagnosis by prioritizing specific morphological evidence aligning with classifier signals. (3) **Conflict Resolution**: If the report describes anatomy as 'clear', 'normal', or 'limited' but classifier confidence scores are high (>0.5), prioritize the quantitative classifier evidence and visual morphology to prevent false negatives; formulate the final answer reflecting the severity indicated by the classifier.

CRITICAL PRECONDITION: This skill MUST ONLY be invoked if `chest_xray_classifier` has returned non-empty `strong_findings`. If findings are empty, use the standard negative-verification workflow.
