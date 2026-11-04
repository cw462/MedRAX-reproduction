---
id: "t000003"
name: "fallback_visual_analysis_for_low_confidence_classifier"
description: "When automated image classifiers return low-confidence or negative findings for suspected acute pathologies, initiate direct visual inspection or report generation to identify subtle radiographic signs."
version: "1.8"
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
updated_at: "2026-11-04T04:04:36Z"
---

### Core Action
If the `chest_xray_classifier` returns no strong findings (scores < threshold) or negative results for a suspected condition: (1) Do not accept the negative result as final; (2) Call `chest_xray_report_generator` to produce a detailed textual description of the image; (3) CRITICAL: If the generated report is non-specific, negative, or states 'grossly clear', DO NOT accept this as evidence of normality. Instead, bypass the text and perform direct visual inspection of the image pixels to identify subtle signs (e.g., visceral pleural lines, fissure lines, specific opacity shapes, pneumomediastinum indicators like continuous diaphragm sign or ring-around-the-artery sign, subcutaneous streaks) that automated tools may have missed. Proceed with diagnosis based on this secondary visual evidence, prioritizing pixel-level findings over potentially hallucinated or limited textual reports.
