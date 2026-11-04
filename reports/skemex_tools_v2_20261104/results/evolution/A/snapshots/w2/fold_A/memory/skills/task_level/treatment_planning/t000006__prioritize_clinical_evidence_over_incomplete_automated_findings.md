---
id: "t000006"
name: "prioritize_clinical_evidence_over_incomplete_automated_findings"
description: "When automated diagnostic tools provide non-specific or incomplete findings for a clear, large radiographic abnormality (e.g., large pleural effusion), prioritize explicit clinical presentation and visual evidence to determine standard initial management rather than waiting for specific etiologic confirmation."
version: "1.0"
status: "active"
branch: "task_level"
task_category:
  - "treatment_planning"
source_trajectory_ids:
  - "18592_8143559008899"
applicable_conditions: "Applicable when chest imaging reveals a significant structural abnormality (such as a large effusion, pneumothorax, or mass) but automated classifiers or report generators fail to provide specific etiologic details or confidence scores sufficient for definitive diagnosis."
required_tools:
  - "chest_xray_classifier"
  - "chest_xray_report_generator"
risk_level: "medium"
created_at: "2026-11-04T12:54:26Z"
updated_at: "2026-11-04T12:54:26Z"
---

### Core Action
If `chest_xray_classifier` or `chest_xray_report_generator` returns non-specific findings (e.g., 'abnormality detected' without etiology) for a visually evident large abnormality (like a large pleural effusion): (1) Do not delay management pending further automated etiologic clarification; (2) Prioritize the visual magnitude of the finding and associated clinical symptoms (e.g., dyspnea); (3) Recommend standard initial therapeutic/diagnostic intervention appropriate for the primary finding (e.g., thoracentesis for large effusion) to relieve symptoms and obtain fluid for analysis.
