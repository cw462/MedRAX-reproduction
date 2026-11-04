---
id: "t000001"
name: "longitudinal_imaging_synthesis"
description: "When a clinical question implies temporal progression, comparison, or change over time involving multiple images, do not rely on single-image analysis tools in isolation."
version: "1.4"
status: "active"
branch: "task_level"
task_category:
  - "medical_imaging_interpretation"
source_trajectory_ids:
  - "18680_8143559034799"
applicable_conditions: "The user query contains keywords indicating chronology (e.g., 'progression', 'change', 'improvement', 'worsening', 'compared to') or explicitly references multiple figures/timepoints, but the available tools only provide static, single-image interpretations."
required_tools:
  - "chest_xray_classifier"
  - "chest_xray_report_generator"
risk_level: "high"
created_at: "2026-11-04T12:44:54Z"
updated_at: "2026-11-04T13:04:46Z"
---

### Core Action
If the query requires assessing progression or comparing multiple timepoints: (1) Explicitly identify all referenced images/timepoints; (2) Call `chest_xray_classifier` for EACH relevant image individually to extract static findings; (3) Manually synthesize these independent outputs to identify trends (e.g., new opacities, resolving effusions) rather than relying on a single snapshot or assuming chronology from one call; (4) Cross-reference the synthesized temporal trend with clinical history (e.g., exertion, trauma) before selecting the final diagnosis. Do not infer longitudinal changes from a single image report.
