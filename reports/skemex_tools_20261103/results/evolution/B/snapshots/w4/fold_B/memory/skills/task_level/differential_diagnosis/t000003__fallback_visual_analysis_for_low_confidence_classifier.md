---
id: "t000003"
name: "fallback_visual_analysis_for_low_confidence_classifier"
description: "When automated image classifiers return low-confidence or negative findings for suspected acute pathologies, initiate direct visual inspection or report generation to identify subtle radiographic signs."
version: "1.28"
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
updated_at: "2026-11-04T04:30:28Z"
---

### Core Action
If the `chest_xray_classifier` returns no strong findings (scores < threshold) or negative results for a suspected condition: (1) Do not accept the negative result as final; (2) Call `chest_xray_report_generator` to produce a detailed textual description of the image; (3) CRITICAL: Perform a strict evidence-based synthesis where the generated report text is the sole source of truth for radiological findings. DO NOT infer specific morphological features (e.g., 'hyperlucency', 'mediastinal shift', 'honeycombing') from generic descriptions (e.g., 'opacity', 'infiltrates') unless explicitly stated in the report. If the report explicitly identifies findings (e.g., 'pneumothorax', 'chest tube'), these must take precedence over any conflicting clinical priors or suspected rare diagnoses. DO NOT hallucinate signs to fit a preferred diagnosis if they contradict the explicit report. If the report contains only generic or non-specific findings that do not definitively confirm the suspected pathology, flag the discrepancy and recommend further imaging (e.g., CT) rather than forcing a positive diagnosis based on clinical suspicion alone.
