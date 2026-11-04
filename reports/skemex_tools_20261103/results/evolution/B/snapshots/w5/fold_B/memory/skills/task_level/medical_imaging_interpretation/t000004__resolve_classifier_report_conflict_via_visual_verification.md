---
id: "t000004"
name: "resolve_classifier_report_conflict_via_visual_verification"
description: "When a generated radiology report indicates 'normal' findings but the image classifier outputs high confidence scores for specific pathologies, prioritize the quantitative classifier signal and initiate direct visual verification."
version: "1.3"
status: "deprecated"
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
updated_at: "2026-11-04T04:21:31Z"
---

### Core Action
If `chest_xray_report_generator` produces a 'normal', 'clear', or significantly incomplete report (e.g., missing obvious masses) while visual inspection or clinical context suggests pathology, OR if `chest_xray_classifier` returns high confidence scores for specific pathologies: (1) Do not accept the textual report as ground truth; (2) Prioritize direct visual verification of the image over the textual report's negative finding; (3) Specifically inspect regions highlighted by the classifier or areas of visual suspicion to confirm or refute the presence of pathology. Crucially, if visual verification confirms the absence of pathology despite high classifier confidence, explicitly trust the negative visual evidence and the normal report over the classifier's probabilistic output, avoiding hallucination of findings to fit clinical priors.
