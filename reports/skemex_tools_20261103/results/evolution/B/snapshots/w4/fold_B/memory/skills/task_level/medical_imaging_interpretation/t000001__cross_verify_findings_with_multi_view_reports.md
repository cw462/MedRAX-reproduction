---
id: "t000001"
name: "cross_verify_findings_with_multi_view_reports"
description: "When a specific anatomical finding or lesion visibility is ambiguous in a single view, generate reports for multiple orthogonal views to cross-verify presence or absence."
version: "1.5"
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
updated_at: "2026-11-04T04:28:55Z"
---

### Core Action
If the presence of a specific finding (e.g., vessel, nodule, consolidation) is unclear or requires spatial verification: (1) call `chest_xray_report_generator` for the primary view (e.g., PA); (2) call `chest_xray_report_generator` for the orthogonal view (e.g., Lateral); (3) compare the generated textual reports to check for consistent mentions or explicit exclusions of the finding. Conclude based on the concordance or discordance between the two views. CRITICAL PRE-CHECK: Before initiating this workflow, verify if the input images represent different time points (e.g., pre-op vs. post-op, baseline vs. follow-up). If the task involves temporal comparison to assess progression, resolution, or new onset, DO NOT apply this skill. Instead, use a temporal analysis strategy that compares findings across the timeline rather than treating them as orthogonal spatial views of a single state. Additionally, DO NOT override the textual findings from `chest_xray_report_generator` with unverified visual claims; rely strictly on the generated report outputs for clinical conclusions. STRICT CONSTRAINT: When synthesizing the final diagnostic reasoning, you MUST use the exact morphological descriptors and anatomical locations provided in the tool output (e.g., 'nodular', 'diffuse'). Do NOT introduce subjective visual adjectives (e.g., 'patchy', 'ill-defined') or specific zone localizations that are not explicitly stated in the generated reports.
