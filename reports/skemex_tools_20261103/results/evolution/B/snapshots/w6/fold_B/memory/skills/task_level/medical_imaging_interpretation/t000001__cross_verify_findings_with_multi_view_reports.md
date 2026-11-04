---
id: "t000001"
name: "cross_verify_findings_with_multi_view_reports"
description: "When a specific anatomical finding or lesion visibility is ambiguous in a single view, generate reports for multiple orthogonal views to cross-verify presence or absence."
version: "1.12"
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
updated_at: "2026-11-04T04:43:36Z"
---

### Core Action
If the presence of a specific finding (e.g., vessel, nodule, consolidation) is unclear or requires spatial verification: (1) call `chest_xray_report_generator` for the primary view (e.g., PA); (2) call `chest_xray_report_generator` for the orthogonal view (e.g., Lateral); (3) compare the generated textual reports to check for consistent mentions or explicit exclusions of the finding. Conclude based on the concordance or discordance between the two views. CRITICAL PRE-CHECK: Before initiating this workflow, verify if the input images represent different time points (e.g., pre-op vs. post-op, baseline vs. follow-up). If the task involves temporal comparison to assess progression, resolution, or new onset, DO NOT apply this skill. Instead, use a temporal analysis strategy that compares findings across the timeline rather than treating them as orthogonal spatial views of a single state. Additionally, DO NOT blindly accept textual findings from `chest_xray_report_generator` if they contradict clear visual evidence; while relying on generated reports for standard descriptors, you MUST perform direct visual inspection to verify the existence of major pathologies (e.g., masses, large consolidations) when the tool output reports 'normal' or 'clear' but clinical context suggests otherwise. STRICT CONSTRAINT: When synthesizing the final diagnostic reasoning, you MUST use the exact morphological descriptors and anatomical locations provided in the tool output (e.g., 'nodular', 'diffuse'). Do NOT introduce subjective visual adjectives (e.g., 'patchy', 'ill-defined') or specific zone localizations that are not explicitly stated in the generated reports, UNLESS the tool output is demonstrably hallucinated (e.g., reporting 'clear lungs' despite a visible mass), in which case visual descriptors take precedence. CONFLICT RESOLUTION: If the tool output explicitly states a negative finding (e.g., 'lungs are clear', 'no nodules') but direct visual inspection confirms the presence of a finding, you MUST prioritize the visual evidence over the tool's hallucinated negative. Flag the discrepancy explicitly in the reasoning (e.g., 'Tool reported normal mediastinum, but visual inspection confirms mass; proceeding with mass evaluation'). ANTI-HALLUCINATION RULE: You are strictly prohibited from fabricating findings (e.g., inventing 'cavitary lesions' or 'upper lobe opacities') that are absent from both the tool outputs and direct visual inspection. If the tool reports 'clear lungs' and visual inspection confirms no obvious pathology, you must conclude 'no acute findings' rather than forcing a diagnosis by inventing evidence.
