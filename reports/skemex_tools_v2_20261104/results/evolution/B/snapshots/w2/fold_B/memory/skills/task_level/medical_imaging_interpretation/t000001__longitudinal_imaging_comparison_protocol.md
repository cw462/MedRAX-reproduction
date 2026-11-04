---
id: "t000001"
name: "longitudinal_imaging_comparison_protocol"
description: "When a clinical question references historical growth, progression, or change in a lesion, and multiple time-point images are available."
version: "1.4"
status: "active"
branch: "task_level"
task_category:
  - "medical_imaging_interpretation"
source_trajectory_ids:
  - "795_8353802131057"
applicable_conditions: "Tasks involving medical imaging interpretation where the query implies a temporal dimension (e.g., 'growth pattern', 'change over time', 'progression') and the input context contains more than one image file representing different time points."
required_tools:
  - "chest_xray_classifier"
  - "chest_xray_report_generator"
risk_level: "high"
created_at: "2026-11-04T13:49:56Z"
updated_at: "2026-11-04T14:03:25Z"
---

### Core Action
If the question stem mentions 'historical growth', 'progression', or 'change' AND multiple images (e.g., prior and current) are provided: (1) Do NOT analyze only the most recent image. (2) Explicitly invoke `chest_xray_classifier` on EACH available image individually in separate tool calls to extract features for each time point; do NOT attempt to batch process multiple images in a single call or plan multiple tool executions in one step due to executor constraints. If the executor rejects multi-step plans or tool calls fail, fallback to direct visual synthesis of the image sequence to identify temporal changes. (3) Use `chest_xray_report_generator` to synthesize a comparative analysis that highlights differences in size, density, or morphology between the time points. (4) Base the final conclusion on this longitudinal comparison rather than a single static snapshot.
