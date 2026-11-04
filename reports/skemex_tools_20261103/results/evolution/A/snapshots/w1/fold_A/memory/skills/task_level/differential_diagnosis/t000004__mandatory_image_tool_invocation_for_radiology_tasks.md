---
id: "t000004"
name: "mandatory_image_tool_invocation_for_radiology_tasks"
description: "When a differential diagnosis task involves interpreting chest imaging or requires visual evidence from radiological studies, the agent must invoke image analysis tools before forming any diagnostic conclusion."
version: "1.0"
status: "active"
branch: "task_level"
task_category:
  - "differential_diagnosis"
source_trajectory_ids:
  - "13579_8353800704700"
applicable_conditions: "Any medical task where the input includes or implies the need for chest X-ray, CT, or other radiological image interpretation to support a diagnosis or differential diagnosis."
required_tools:
  - "chest_xray_classifier"
  - "chest_xray_report_generator"
risk_level: "high"
created_at: "2026-11-04T03:05:47Z"
updated_at: "2026-11-04T03:05:47Z"
---

### Core Action
If the task requires analyzing chest imaging findings (e.g., opacities, nodules, patterns) to support a diagnosis: (1) Immediately call `chest_xray_report_generator` to obtain a structured radiological description; (2) Call `chest_xray_classifier` to identify specific pathological features if available. Do NOT generate specific radiological findings or diagnoses based on text prompts alone without first executing these tools.
