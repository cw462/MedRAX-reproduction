---
id: "t000008"
name: "prioritize_report_generator_for_subtle_patterns"
description: "When the chest X-ray classifier returns no strong findings but clinical context suggests pathology with subtle radiographic signs, prioritize the detailed morphological description from the report generator."
version: "1.1"
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
updated_at: "2026-11-04T14:41:34Z"
---

### Core Action
If `chest_xray_report_generator` returns a 'normal' or 'negative' impression but clinical context (e.g., subcutaneous emphysema, soft tissue air) suggests pathology not typically prioritized in lung-focused reports: (1) Do NOT accept the negative report as definitive; (2) Perform direct visual inspection of the original image for subtle extra-pulmonary findings (like radiolucent streaks in soft tissues) that the generator may omit; (3) Override the tool's output with pixel-level verification if non-parenchymal/soft-tissue anomalies are detected.
