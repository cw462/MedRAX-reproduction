---
id: "t000009"
name: "temporal_severity_quantification"
description: "When evaluating the evolution of chest pathology over time, explicitly quantify severity changes using a classifier on serial images rather than relying on visual estimation."
version: "1.0"
status: "active"
branch: "task_level"
task_category:
  - "medical_imaging_interpretation"
source_trajectory_ids:
  - "17402_8143559696568"
applicable_conditions: "Tasks involving the interpretation of multiple chest imaging studies (e.g., X-rays, CTs) taken at different time points to assess disease progression, resolution, or stability."
required_tools:
  - "chest_xray_classifier"
risk_level: "medium"
created_at: "2026-11-04T03:15:15Z"
updated_at: "2026-11-04T03:15:15Z"
---

### Core Action
When analyzing temporal chest imaging sequences to distinguish transient from persistent pathology: (1) Identify key timepoints (e.g., baseline, peak severity, current/resolution); (2) Invoke `chest_xray_classifier` on each selected image to obtain objective severity scores; (3) Compare the quantitative outputs to determine the trajectory (improving, worsening, stable) rather than relying on subjective visual comparison alone.
