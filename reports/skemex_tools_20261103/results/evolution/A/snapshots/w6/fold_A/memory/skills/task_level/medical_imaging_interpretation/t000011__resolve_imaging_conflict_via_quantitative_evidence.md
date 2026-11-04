---
id: "t000011"
name: "resolve_imaging_conflict_via_quantitative_evidence"
description: "When a text-based report generator provides a generic 'normal' assessment that contradicts high-confidence quantitative findings from an image classifier, prioritize the objective classifier data and re-evaluate for subtle pathologies."
version: "1.0"
status: "active"
branch: "task_level"
task_category:
  - "medical_imaging_interpretation"
source_trajectory_ids:
  - "6972_8353801559179"
applicable_conditions: "Applicable in medical imaging interpretation tasks where multiple tools provide conflicting assessments: one tool offers a qualitative/narrative summary (often prone to hallucination or oversimplification) and another provides objective, high-confidence quantitative metrics or feature detections."
required_tools:
  - "chest_xray_classifier"
  - "chest_xray_report_generator"
risk_level: "high"
created_at: "2026-11-04T03:29:36Z"
updated_at: "2026-11-04T03:29:36Z"
---

### Core Action
If `chest_xray_report_generator` returns a 'clear' or 'normal' conclusion but `chest_xray_classifier` indicates high-confidence abnormalities (e.g., probability > 0.8 for specific findings): (1) Disregard the generic narrative conclusion; (2) Prioritize the classifier's quantitative evidence as the primary diagnostic signal; (3) Integrate relevant clinical context (e.g., patient history) to interpret the specific quantitative findings (such as vascular obstruction or oligemia) that the text generator may have missed; (4) Generate a final assessment that explicitly addresses the discrepancy and highlights the objective findings.
