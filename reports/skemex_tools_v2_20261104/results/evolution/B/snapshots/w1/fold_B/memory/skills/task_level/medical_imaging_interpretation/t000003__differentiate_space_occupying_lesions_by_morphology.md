---
id: "t000003"
name: "differentiate_space_occupying_lesions_by_morphology"
description: "When interpreting chest X-rays with contralateral mediastinal shift and white-out, do not rely solely on classifier scores to distinguish between effusion and mass."
version: "1.2"
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
updated_at: "2026-11-04T13:59:54Z"
---

### Core Action
If the `chest_xray_classifier` indicates high probability for 'Effusion' or 'Mass' but visual inspection reveals ambiguous features (e.g., opacity without clear meniscus) or contradictory structural signs (e.g., mediastinal shift inconsistent with simple effusion): (1) Do NOT select the diagnosis based solely on the highest classifier score. (2) MANDATORILY call `chest_xray_report_generator` to obtain detailed morphological descriptions. (3) Explicitly check the report for specific morphological markers: 'meniscus sign' (indicating fluid/effusion), 'discrete mass borders' (indicating solid tumor), or 'displacement of cardiac silhouette/mediastinal structures into pleural space' (indicating herniation). (4) Prioritize these morphological findings from the generated report over the classifier's categorical label to differentiate between effusion, mass, and herniation.
