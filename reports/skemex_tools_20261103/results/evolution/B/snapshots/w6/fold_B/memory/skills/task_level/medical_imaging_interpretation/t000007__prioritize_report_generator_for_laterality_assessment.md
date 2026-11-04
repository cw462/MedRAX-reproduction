---
id: "t000007"
name: "prioritize_report_generator_for_laterality_assessment"
description: "When diagnosing conditions involving anatomical laterality or spatial orientation (e.g., situs inversus, dextrocardia), prioritize the report generator over the classifier to capture structural landmark positions."
version: "1.0"
status: "active"
branch: "task_level"
task_category:
  - "medical_imaging_interpretation"
source_trajectory_ids:
  - "9009_8353800909239"
applicable_conditions: "Tasks requiring determination of left-right anatomical orientation, mirror-image anatomy, or spatial positioning of internal organs where normalized pathology scores are insufficient."
required_tools:
  - "chest_xray_report_generator"
risk_level: "high"
created_at: "2026-11-04T04:39:35Z"
updated_at: "2026-11-04T04:39:35Z"
---

### Core Action
If the diagnostic task involves determining anatomical laterality (e.g., heart apex position, liver/stomach side): (1) Do NOT rely solely on `chest_xray_classifier` outputs, as they lack spatial orientation data; (2) Call `chest_xray_report_generator` to obtain descriptive text regarding structural landmarks and their relative positions; (3) Extract laterality information from the generated report to confirm or rule out conditions like situs inversus.
