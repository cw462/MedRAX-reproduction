---
id: "t000002"
name: "validate_mediastinal_shift_direction"
description: "When interpreting chest imaging with significant unilateral opacity, explicitly verify the direction of mediastinal shift to distinguish between space-occupying lesions (e.g., effusion) and volume-loss conditions (e.g., atelectasis)."
version: "1.5"
status: "active"
branch: "task_level"
task_category:
  - "medical_imaging_interpretation"
source_trajectory_ids:
  - "17421_8143559669694"
applicable_conditions: "Any task involving the interpretation of chest X-rays or CT scans where a large unilateral opacity, consolidation, or pleural abnormality is detected."
required_tools:
  - "chest_xray_report_generator"
  - "chest_xray_classifier"
risk_level: "high"
created_at: "2026-11-04T03:55:52Z"
updated_at: "2026-11-04T04:21:01Z"
---

### Core Action
If a large unilateral opacity is identified: (1) Use `chest_xray_report_generator` to specifically extract descriptions of mediastinal position (trachea, heart border); (2) Cross-reference this with `chest_xray_classifier` findings for effusion vs. collapse/atelectasis probabilities; (3) Apply the rule: Contralateral shift suggests space-occupying pathology (e.g., massive effusion), while Ipsilateral shift suggests volume loss (e.g., atelectasis/collapse). CRITICAL CONSTRAINT: Do not infer or hallucinate shift direction based on visual opacity patterns or diagnostic suspicion if the report generator does not explicitly state it. If the report generator fails to describe the shift or states 'no shift'/'normal', accept this textual evidence as the absolute ground truth for shift direction, overriding any visual suspicion or expected diagnostic pattern. Only use explicit textual confirmation from the report.
