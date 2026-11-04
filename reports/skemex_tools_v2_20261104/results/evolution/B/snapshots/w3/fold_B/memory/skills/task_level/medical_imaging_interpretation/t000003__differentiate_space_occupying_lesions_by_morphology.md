---
id: "t000003"
name: "differentiate_space_occupying_lesions_by_morphology"
description: "When interpreting chest X-rays with contralateral mediastinal shift and white-out, do not rely solely on classifier scores to distinguish between effusion and mass."
version: "1.4"
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
updated_at: "2026-11-04T14:22:13Z"
---

### Core Action
**Scenario 1: High Classifier Probability with Ambiguous/Contradictory Visuals**
If `chest_xray_classifier` indicates high probability for 'Effusion', 'Mass', or 'Pneumothorax' but visual inspection reveals ambiguous features (e.g., total hemithorax opacity) or contradictory signs (e.g., mediastinal shift):
1. **Do NOT** select the diagnosis based solely on the highest classifier score.
2. **MANDATORILY** call `chest_xray_report_generator` to obtain detailed morphological descriptions.
3. **Explicitly check** the report for specific markers: 'meniscus sign' (simple effusion), 'air-fluid level'/'visceral pleural line' (pyopneumothorax/hydropneumothorax), 'discrete mass borders' (solid tumor), or 'mediastinal displacement'.
4. **Integrate** clinical history (e.g., infection, trauma) with these findings to differentiate between simple effusion, complex empyema, mass, and herniation. Prioritize combined findings over the classifier’s label.

**Scenario 2: Low Classifier Probability with Suspicious Clinical/Structural Context**
If `chest_xray_classifier` returns no strong findings (scores < threshold) but clinical context (e.g., recent surgery, trauma) and visual inspection suggest structural pathology (e.g., mediastinal widening, abnormal contours):
1. **Accept Tool Limitation**: Acknowledge the lack of strong visual evidence; do NOT hallucinate radiological signs to match clinical suspicion.
2. **Prioritize Clinical Timeline**: Give precedence to patient history (e.g., post-operative status) and visible gross structural anomalies over the negative classifier output when inferring acute complications (e.g., hematoma, effusion).
3. **Invoke Objective Reporting**: If the structural anomaly is subtle or requires precise description to rule out artifacts, call `chest_xray_report_generator`. Use the objective report to confirm the presence of structural markers before finalizing the differential diagnosis.
