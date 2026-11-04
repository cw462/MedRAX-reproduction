---
id: "t000012"
name: "Contextualize Negative Imaging in High-Risk Trauma"
description: "When interpreting chest imaging for high-energy blunt trauma, do not rule out vascular injury solely based on the absence of strong parenchymal findings in automated classifiers."
version: "1.0"
status: "active"
branch: "task_level"
task_category:
  - "medical_imaging_interpretation"
source_trajectory_ids:
  - "568_8353802196329"
applicable_conditions: "Applies to medical imaging interpretation tasks involving blunt chest trauma or high-velocity impact mechanisms where automated detection tools return negative or low-confidence results for obvious pathologies (e.g., pneumothorax, consolidation)."
required_tools:
  - "chest_xray_classifier"
  - "chest_xray_report_generator"
risk_level: "high"
created_at: "2026-11-04T03:31:38Z"
updated_at: "2026-11-04T03:31:38Z"
---

### Core Action
If the `chest_xray_classifier` returns empty 'strong_findings' (negative result) in a case with a mechanism of high-energy blunt trauma (e.g., crush injury, deceleration): (1) Do NOT conclude the absence of severe pathology; (2) Explicitly consider occult vascular injuries (e.g., aortic rupture) or mediastinal abnormalities that may not trigger high-opacity scores; (3) Instruct the `chest_xray_report_generator` to highlight mediastinal width, hilar contours, and clinical correlation needs rather than defaulting to minor parenchymal findings like contusions.
