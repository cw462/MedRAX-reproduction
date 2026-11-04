---
id: "t000008"
name: "prioritize_report_generator_for_subtle_patterns"
description: "When the chest X-ray classifier returns no strong findings but clinical context suggests pathology with subtle radiographic signs, prioritize the detailed morphological description from the report generator."
version: "1.0"
status: "active"
branch: "task_level"
task_category:
  - "medical_imaging_interpretation"
source_trajectory_ids:
  - "13273_8353800689640"
applicable_conditions: "Tasks involving medical imaging interpretation where initial automated classification yields negative or low-confidence results despite high clinical suspicion of diffuse or textural abnormalities."
required_tools:
  - "chest_xray_classifier"
  - "chest_xray_report_generator"
risk_level: "medium"
created_at: "2026-11-04T14:30:33Z"
updated_at: "2026-11-04T14:30:33Z"
---

### Core Action
If `chest_xray_classifier` returns no strong findings (scores < threshold) but clinical context indicates potential pathology: (1) Call `chest_xray_report_generator` to obtain a detailed morphological description; (2) Analyze the report for diffuse patterns, texture changes, or distributional anomalies (e.g., interstitial thickening) that may not constitute discrete focal opacities; (3) Base the final diagnostic assessment on the report generator's detailed findings rather than the classifier's negative output.
