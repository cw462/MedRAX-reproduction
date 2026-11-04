---
id: "t000008"
name: "prioritize_visual_morphology_over_generic_labels"
description: "When automated tools provide generic diagnostic labels (e.g., 'Pneumonia') for consolidative lung opacities, prioritize direct visual inspection for specific morphological discriminators of malignancy."
version: "1.0"
status: "active"
branch: "task_level"
task_category:
  - "medical_imaging_interpretation"
source_trajectory_ids:
  - "18414_8143559776145"
applicable_conditions: "Tasks involving the interpretation of chest imaging where differential diagnosis includes distinguishing between infectious processes and malignancies that mimic infection (e.g., pneumonic-type adenocarcinoma)."
required_tools:
  - "chest_xray_report_generator"
  - "chest_xray_classifier"
risk_level: "high"
created_at: "2026-11-04T13:41:42Z"
updated_at: "2026-11-04T13:41:42Z"
---

### Core Action
If `chest_xray_classifier` or `chest_xray_report_generator` outputs a generic label like 'Pneumonia' for a consolidative opacity: (1) Do not accept the label as final; (2) Perform direct visual inspection of the image specifically looking for morphological features suggestive of malignancy, such as cystic lucencies, intratumoral cavitation, or necrosis within the consolidation; (3) If these features are present, escalate the suspicion for pneumonic-type adenocarcinoma regardless of the automated tool's output.
