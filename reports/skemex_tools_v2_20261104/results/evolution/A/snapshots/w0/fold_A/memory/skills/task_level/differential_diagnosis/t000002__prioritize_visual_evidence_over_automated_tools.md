---
id: "t000002"
name: "prioritize_visual_evidence_over_automated_tools"
description: "When automated radiology tools return normal or contradictory reports despite specific clinical vignette clues suggesting pathology, prioritize direct visual inspection of the original image."
version: "1.0"
status: "active"
branch: "task_level"
task_category:
  - "differential_diagnosis"
source_trajectory_ids:
  - "12385_8353800664317"
applicable_conditions: "Tasks involving differential diagnosis where automated chest X-ray classifiers or report generators fail to detect subtle signs or provide results inconsistent with the clinical presentation."
required_tools:
  - "chest_xray_classifier"
  - "chest_xray_report_generator"
risk_level: "high"
created_at: "2026-11-04T12:45:16Z"
updated_at: "2026-11-04T12:45:16Z"
---

### Core Action
If `chest_xray_classifier` and `chest_xray_report_generator` return normal or non-specific findings but the clinical vignette describes specific symptoms (e.g., localized pain, abnormal breath sounds) or suggests a condition with subtle radiographic signs: (1) Do not accept the 'normal' tool output as final; (2) Manually inspect the original chest X-ray image for subtle features (e.g., tubular opacities, hyperlucency, faint consolidations) that automated tools may miss; (3) Base the differential diagnosis on the combination of clinical clues and direct visual evidence rather than relying solely on the generated report.
