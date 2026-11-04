---
id: "t000003"
name: "fallback_visual_analysis_for_low_confidence_classifier"
description: "When automated image classifiers return low-confidence or negative findings for suspected acute pathologies, initiate direct visual inspection or report generation to identify subtle radiographic signs."
version: "1.15"
status: "active"
branch: "task_level"
task_category:
  - "differential_diagnosis"
source_trajectory_ids:
  - "16844_8143559672130"
applicable_conditions: "Applicable in diagnostic imaging tasks where initial automated tool outputs (e.g., classifiers) do not provide high-confidence positive results despite clinical suspicion or ambiguous presentation."
required_tools:
  - "chest_xray_report_generator"
risk_level: "high"
created_at: "2026-11-04T03:56:54Z"
updated_at: "2026-11-04T04:14:57Z"
---

### Core Action
If the `chest_xray_classifier` returns no strong findings (scores < threshold) or negative results for a suspected condition: (1) Do not accept the negative result as final; (2) Call `chest_xray_report_generator` to produce a detailed textual description of the image; (3) CRITICAL: Strictly constrain your diagnostic reasoning to the explicit findings reported by the `chest_xray_report_generator`. DO NOT hallucinate anatomical details, pathologies, or absences (e.g., missing ribs, specific opacities) that are not explicitly stated in the generated report. If the report is non-specific, negative, or states 'grossly clear', prioritize these negative/normal findings over speculative pattern matching or preconceived diagnoses. Only proceed with a positive diagnosis if distinct, verifiable anatomical anomalies are explicitly identified in the tool output.
