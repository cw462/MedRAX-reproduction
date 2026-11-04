---
id: "t000007"
name: "resolve_ambiguous_mass_findings_with_report"
description: "When a chest X-ray classifier indicates a high probability of 'Mass' but lacks specific morphological or locational details required for differential diagnosis, invoke the report generator to obtain descriptive text."
version: "1.0"
status: "active"
branch: "task_level"
task_category:
  - "medical_imaging_interpretation"
source_trajectory_ids:
  - "11036_8353800736462"
applicable_conditions: "Tasks involving medical imaging interpretation where an initial automated classification suggests a structural abnormality (e.g., mass, nodule, opacity) but fails to provide sufficient anatomical context (such as anterior/posterior location, border characteristics, or relationship to adjacent structures) needed for accurate clinical reasoning."
required_tools:
  - "chest_xray_classifier"
  - "chest_xray_report_generator"
risk_level: "high"
created_at: "2026-11-04T14:11:25Z"
updated_at: "2026-11-04T14:11:25Z"
---

### Core Action
If `chest_xray_classifier` returns a high-probability label for 'Mass' or similar structural lesion without detailed morphological descriptors: (1) immediately invoke `chest_xray_report_generator` to extract natural language descriptions of the finding; (2) prioritize specific signs from the report (e.g., hilum-overlay sign, meniscus sign, border definition) over the categorical label to determine anatomical location and associated findings; (3) use these descriptive features to refine the differential diagnosis.
