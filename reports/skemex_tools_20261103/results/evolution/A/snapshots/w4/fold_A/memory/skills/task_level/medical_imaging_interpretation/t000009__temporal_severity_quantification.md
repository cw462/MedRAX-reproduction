---
id: "t000009"
name: "temporal_severity_quantification"
description: "When evaluating the evolution of chest pathology over time, explicitly quantify severity changes using a classifier on serial images rather than relying on visual estimation."
version: "1.3"
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
updated_at: "2026-11-04T03:24:24Z"
---

### Core Action
When analyzing temporal chest imaging sequences to distinguish transient from persistent pathology: (1) Identify key timepoints (e.g., baseline, peak severity, current/resolution); (2) Invoke `chest_xray_classifier` on each selected image to obtain objective severity scores; (3) Compare the quantitative outputs to determine the trajectory. CRITICAL: Explicitly map the direction of score change to clinical status in your reasoning (e.g., if Score_B > Score_A, then Image B represents increased severity or new pathology, NOT resolution). Do not generate a narrative that contradicts the quantitative trend (e.g., claiming 'improvement' when scores increase). Verify that the textual conclusion aligns with the mathematical difference between scores before finalizing the answer. ADDITIONAL SAFEGUARD: A reduction in generic 'Lung Opacity' score does not automatically confirm 'resolution' of inflammation; it may indicate progression to atelectasis, effusion, or fibrosis which have different radiographic signatures. If the score drops significantly but residual opacity remains or morphology changes, do not conclude 'complete resolution' without verifying the specific nature of the remaining findings via morphological analysis.
