---
id: "t000007"
name: "prioritize_mechanism_over_automated_cxr_findings"
description: "When clinical mechanism suggests high-energy blunt trauma, do not rely solely on negative or non-specific automated CXR tool outputs for mediastinal assessment."
version: "1.0"
status: "active"
branch: "task_level"
task_category:
  - "medical_imaging_interpretation"
source_trajectory_ids:
  - "568_8353802196947"
applicable_conditions: "Cases involving high-energy blunt trauma mechanisms (e.g., deceleration, crush) where automated chest X-ray interpretation tools return normal or non-specific findings regarding the mediastinum or aorta."
required_tools:
  - "chest_xray_classifier"
  - "chest_xray_report_generator"
risk_level: "high"
created_at: "2026-11-04T13:21:52Z"
updated_at: "2026-11-04T13:21:52Z"
---

### Core Action
If the clinical history indicates high-energy blunt trauma (e.g., motor vehicle collision with deceleration) and automated tools (`chest_xray_classifier`, `chest_xray_report_generator`) report 'normal mediastinum' or non-specific findings: (1) Recognize that automated tools often lack sensitivity for subtle mediastinal widening or aortic contour abnormalities; (2) Explicitly flag the case for manual expert review focusing on mediastinal width and aortic knob integrity; (3) Do not rule out blunt aortic injury based solely on these automated outputs.
