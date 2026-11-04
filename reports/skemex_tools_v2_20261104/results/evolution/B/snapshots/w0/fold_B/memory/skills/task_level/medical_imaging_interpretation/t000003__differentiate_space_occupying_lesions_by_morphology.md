---
id: "t000003"
name: "differentiate_space_occupying_lesions_by_morphology"
description: "When interpreting chest X-rays with contralateral mediastinal shift and white-out, do not rely solely on classifier scores to distinguish between effusion and mass."
version: "1.0"
status: "active"
branch: "task_level"
task_category:
  - "medical_imaging_interpretation"
source_trajectory_ids:
  - "17421_8143559697162"
applicable_conditions: "Cases involving unilateral lung opacity (white-out) accompanied by mediastinal shift away from the affected side (contralateral/push effect), where differential diagnosis includes large pleural effusion versus large mass/tumor."
required_tools:
  - "chest_xray_classifier"
  - "chest_xray_report_generator"
risk_level: "high"
created_at: "2026-11-04T13:52:47Z"
updated_at: "2026-11-04T13:52:47Z"
---

### Core Action
If the `chest_xray_classifier` indicates high probability for 'Effusion' or 'Mass' in the presence of contralateral mediastinal shift: (1) Do NOT select the diagnosis based solely on the highest classifier score. (2) Call `chest_xray_report_generator` to obtain detailed morphological descriptions. (3) Explicitly check the report for the 'meniscus sign' (curved upper border indicating fluid/effusion) versus 'discrete mass borders' or 'lobulated contours' (indicating solid mass/tumor). (4) Prioritize the morphological evidence from the report over the classifier's categorical label when distinguishing between these two space-occupying lesions.
