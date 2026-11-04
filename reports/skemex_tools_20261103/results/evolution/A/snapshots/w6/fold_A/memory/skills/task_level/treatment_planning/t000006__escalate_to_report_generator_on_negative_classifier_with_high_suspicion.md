---
id: "t000006"
name: "escalate_to_report_generator_on_negative_classifier_with_high_suspicion"
description: "When a chest X-ray classifier returns no strong findings despite high clinical suspicion of structural pathology, explicitly invoke the report generator to retrieve detailed morphological evidence."
version: "1.0"
status: "deprecated"
branch: "task_level"
task_category:
  - "treatment_planning"
source_trajectory_ids:
  - "18592_8143559008899"
applicable_conditions: "Tasks involving treatment planning or diagnostic confirmation where initial automated screening tools return negative or inconclusive results, but clinical context suggests significant underlying pathology requiring detailed visual analysis."
required_tools:
  - "chest_xray_classifier"
  - "chest_xray_report_generator"
risk_level: "high"
created_at: "2026-11-04T03:09:00Z"
updated_at: "2026-11-04T03:09:05Z"
---

### Core Action
If `chest_xray_classifier` returns empty `strong_findings` but clinical indicators suggest structural pathology (e.g., effusion, mass): (1) Do NOT accept the negative classification as final; (2) Immediately invoke `chest_xray_report_generator` to obtain detailed morphological descriptions and radiologist-style interpretations; (3) Use the generated report details to inform treatment planning decisions.
