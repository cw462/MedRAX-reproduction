---
id: "t000004"
name: "resolve_classifier_report_conflict_via_visual_verification"
description: "When a generated radiology report indicates 'normal' findings but the image classifier outputs high confidence scores for specific pathologies, prioritize the quantitative classifier signal and initiate direct visual verification."
version: "1.0"
status: "active"
branch: "task_level"
task_category:
  - "medical_imaging_interpretation"
source_trajectory_ids:
  - "13946_8353800618966"
applicable_conditions: "Applicable in medical imaging interpretation tasks where automated textual report generation conflicts with quantitative classification outputs (e.g., high probability scores for abnormalities vs. 'clear' text)."
required_tools:
  - "chest_xray_classifier"
  - "chest_xray_report_generator"
risk_level: "high"
created_at: "2026-11-04T04:03:36Z"
updated_at: "2026-11-04T04:03:36Z"
---

### Core Action
If `chest_xray_report_generator` produces a 'normal' or 'clear' report while `chest_xray_classifier` returns high confidence scores (e.g., >0.8) for specific pathologies: (1) Do not accept the textual report as ground truth; (2) Prioritize the classifier's signal as a potential false negative in the report; (3) Perform direct visual verification of the regions highlighted by the classifier to confirm or refute the presence of the pathology before finalizing the assessment.
