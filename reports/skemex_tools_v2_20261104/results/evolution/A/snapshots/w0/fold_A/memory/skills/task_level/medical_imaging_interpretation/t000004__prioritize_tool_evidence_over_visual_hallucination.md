---
id: "t000004"
name: "prioritize_tool_evidence_over_visual_hallucination"
description: "When interpreting medical imaging, if visual inspection suggests pathology (e.g., masses, spatial relationships) that contradicts negative or neutral findings from diagnostic tools, trust the tool outputs."
version: "1.0"
status: "active"
branch: "task_level"
task_category:
  - "medical_imaging_interpretation"
source_trajectory_ids:
  - "4005_8353801527324"
applicable_conditions: "Tasks involving medical image interpretation where automated analysis tools (report generators, classifiers) are available alongside visual input."
required_tools:
  - "chest_xray_report_generator"
  - "chest_xray_classifier"
risk_level: "high"
created_at: "2026-11-04T12:46:29Z"
updated_at: "2026-11-04T12:46:29Z"
---

### Core Action
If visual inspection suggests specific pathologies (e.g., tumors, precise depth) but `chest_xray_report_generator` states 'clear' or 'no evidence' and `chest_xray_classifier` shows no strong findings: (1) Discard the visual hypothesis as a likely hallucination; (2) Conclude that the imaging modality may be insufficient for the suspected distinction (e.g., breast vs. lung mass) without further views/CT; (3) Report the negative tool findings as the primary result rather than asserting unverified visual details.
