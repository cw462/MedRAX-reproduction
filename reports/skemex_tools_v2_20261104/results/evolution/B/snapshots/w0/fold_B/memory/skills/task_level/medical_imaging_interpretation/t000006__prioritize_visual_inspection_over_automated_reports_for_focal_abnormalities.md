---
id: "t000006"
name: "prioritize_visual_inspection_over_automated_reports_for_focal_abnormalities"
description: "When automated tools report normal findings or miss focal morphological features (e.g., cavities, air-fluid levels) despite clinical suspicion, prioritize direct visual inspection of original image pixels."
version: "1.0"
status: "active"
branch: "task_level"
task_category:
  - "medical_imaging_interpretation"
source_trajectory_ids:
  - "912_8353802160047"
applicable_conditions: "Tasks involving medical imaging interpretation where automated classifiers or report generators may overlook subtle, localized structural abnormalities or return contradictory 'normal' results."
required_tools:
  - "chest_xray_classifier"
  - "chest_xray_report_generator"
risk_level: "high"
created_at: "2026-11-04T13:54:16Z"
updated_at: "2026-11-04T13:54:16Z"
---

### Core Action
If automated tools (e.g., classifier, report generator) return 'normal' findings or fail to detect a specific focal abnormality while clinical context suggests otherwise: (1) Use tool outputs only to rule out widespread pathology (e.g., large consolidations); (2) Perform direct visual inspection of the original image pixels to identify specific morphological features (e.g., location, wall thickness, fluid levels); (3) Base the final diagnosis on pixel evidence rather than conflicting automated reports.
