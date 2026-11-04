---
id: "t000006"
name: "multi_image_independent_synthesis"
description: "When interpreting multiple chest images representing different patients or distinct time points, avoid spatial cross-verification and instead generate independent reports before synthesizing findings."
version: "1.0"
status: "active"
branch: "task_level"
task_category:
  - "medical_imaging_interpretation"
source_trajectory_ids:
  - "13273_8353800587919"
applicable_conditions: "The task involves analyzing two or more medical images that are not orthogonal views of the same anatomical state (e.g., longitudinal follow-ups, different patients, or unrelated studies)."
required_tools:
  - "chest_xray_report_generator"
risk_level: "high"
created_at: "2026-11-04T04:27:29Z"
updated_at: "2026-11-04T04:27:29Z"
---

### Core Action
If the input contains multiple images from different patients or time points: (1) Do NOT apply spatial cross-verification skills (like t000001) which assume a single static state; (2) Call `chest_xray_report_generator` independently for each image to extract specific pathological features; (3) Synthesize the textual evidence from these independent reports to identify changes or distinct features (e.g., progression of interstitial thickening vs. stable nodules).
