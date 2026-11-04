---
id: "t000005"
name: "interpret_cxr_volume_loss_patterns"
description: "When interpreting chest X-rays showing mediastinal shift and diaphragmatic elevation, prioritize volume loss as the unifying mechanism before considering primary diaphragmatic pathology or contralateral hyperinflation."
version: "1.0"
status: "active"
branch: "task_level"
task_category:
  - "medical_imaging_interpretation"
source_trajectory_ids:
  - "2847_8353801515240"
applicable_conditions: "Chest X-ray interpretation tasks involving ipsilateral structural shifts (mediastinal deviation, hemidiaphragm elevation) where the underlying etiology may be ambiguous between volume loss, mass effect, or primary diaphragmatic dysfunction."
required_tools:
  - "chest_xray_classifier"
  - "chest_xray_report_generator"
risk_level: "medium"
created_at: "2026-11-04T12:47:25Z"
updated_at: "2026-11-04T12:47:25Z"
---

### Core Action
If the chest X-ray shows ipsilateral mediastinal shift and elevated hemidiaphragm: (1) use `chest_xray_classifier` to assess for signs of lung hypoplasia or atelectasis (volume loss); (2) explicitly rule out primary diaphragmatic paralysis or eventration only after volume loss is evaluated; (3) generate the final report using `chest_xray_report_generator` attributing the structural shifts to volume loss unless contradictory evidence exists.
