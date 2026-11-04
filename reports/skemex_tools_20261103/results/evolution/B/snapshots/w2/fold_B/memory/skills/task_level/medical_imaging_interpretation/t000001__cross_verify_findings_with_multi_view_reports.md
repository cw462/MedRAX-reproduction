---
id: "t000001"
name: "cross_verify_findings_with_multi_view_reports"
description: "When a specific anatomical finding or lesion visibility is ambiguous in a single view, generate reports for multiple orthogonal views to cross-verify presence or absence."
version: "1.2"
status: "active"
branch: "task_level"
task_category:
  - "medical_imaging_interpretation"
source_trajectory_ids:
  - "795_8353802159426"
applicable_conditions: "Tasks involving interpretation of multi-view medical imaging (e.g., Chest X-ray PA and Lateral) where spatial localization or visibility of a specific feature needs confirmation."
required_tools:
  - "chest_xray_report_generator"
risk_level: "medium"
created_at: "2026-11-04T03:54:53Z"
updated_at: "2026-11-04T04:04:59Z"
---

### Core Action
If the presence of a specific finding (e.g., vessel, nodule, consolidation) is unclear or requires spatial verification: (1) call `chest_xray_report_generator` for the primary view (e.g., PA); (2) call `chest_xray_report_generator` for the orthogonal view (e.g., Lateral); (3) compare the generated textual reports to check for consistent mentions or explicit exclusions of the finding. Conclude based on the concordance or discordance between the two views. IMPORTANT: Do NOT apply this skill to tasks involving multiple time points (temporal sequences). If the input involves comparing images from different dates to assess progression or resolution, use a temporal analysis strategy instead of cross-view verification.
