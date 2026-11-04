---
id: "t000010"
name: "Fallback to Descriptive Imaging Report on Classifier Failure"
description: "When a structured image classifier returns empty or low-confidence findings, invoke a descriptive report generator to extract morphological evidence before finalizing the diagnosis."
version: "1.1"
status: "deprecated"
branch: "task_level"
task_category:
  - "differential_diagnosis"
source_trajectory_ids:
  - "816_8353802185068"
applicable_conditions: "Tasks requiring radiological confirmation where the primary classification tool fails to provide high-confidence specific findings (e.g., empty strong_findings), but visual data is available."
required_tools:
  - "chest_xray_classifier"
  - "chest_xray_report_generator"
risk_level: "high"
created_at: "2026-11-04T03:23:23Z"
updated_at: "2026-11-04T03:44:00Z"
---

### Core Action
If `chest_xray_classifier` returns empty `strong_findings` or low confidence scores: (1) Do NOT proceed with diagnosis based solely on clinical text or assume normality; (2) Immediately call `chest_xray_report_generator` to obtain detailed descriptive morphological evidence (e.g., consolidations, infiltrates, opacities); (3) Integrate these descriptive findings with clinical history to support the differential diagnosis.
