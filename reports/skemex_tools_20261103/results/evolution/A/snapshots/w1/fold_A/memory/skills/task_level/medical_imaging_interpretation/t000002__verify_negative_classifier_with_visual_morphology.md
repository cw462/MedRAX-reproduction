---
id: "t000002"
name: "verify_negative_classifier_with_visual_morphology"
description: "When a chest X-ray classifier returns no strong findings despite visible pathology, perform direct visual inspection of morphological features and temporal stability to identify chronic or congenital conditions."
version: "1.6"
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
updated_at: "2026-11-04T03:09:05Z"
---

### Core Action
If `chest_xray_classifier` returns empty `strong_findings` but clinical suspicion for structural pathology (e.g., calcification, pericardial thickening, effusion, mass) remains high: (1) Do not accept the negative classifier output as final; (2) Explicitly invoke `chest_xray_report_generator` to analyze specific views (especially lateral) for morphological details (e.g., curvilinear calcifications, silhouette abnormalities) and obtain radiologist-style interpretations; (3) Formulate diagnosis and inform treatment planning based on the generated report rather than relying on internal visual inspection or the initial classifier's strong findings. CRITICAL PRECONDITION CHECK: This skill MUST NOT be invoked if `chest_xray_classifier` has already returned non-empty `strong_findings`. In cases with positive classifier findings, prioritize those findings and use visual morphology only for refinement or confirmation, not to override explicit positive detections with negative-verification logic.
