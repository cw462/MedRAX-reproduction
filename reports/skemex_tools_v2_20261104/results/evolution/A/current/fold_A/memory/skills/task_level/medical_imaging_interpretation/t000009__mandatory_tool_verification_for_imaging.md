---
id: "t000009"
name: "mandatory_tool_verification_for_imaging"
description: "When an image path is available in the context for a medical imaging task, do not rely on internal assumptions or hallucinations about the image content."
version: "1.0"
status: "active"
branch: "task_level"
task_category:
  - "medical_imaging_interpretation"
source_trajectory_ids:
  - "5845_8353801551879"
applicable_conditions: "The agent is tasked with interpreting medical images (e.g., X-rays, CTs) and has access to specific analysis tools, but has not yet invoked them despite having valid input data (image paths)."
required_tools:
  - "chest_xray_classifier"
  - "chest_xray_report_generator"
risk_level: "high"
created_at: "2026-11-04T13:42:36Z"
updated_at: "2026-11-04T13:42:36Z"
---

### Core Action
If the context contains a valid image path for analysis: (1) Immediately invoke `chest_xray_classifier` to obtain objective findings; (2) Use `chest_xray_report_generator` if a structured report is required. Do NOT generate diagnostic conclusions or describe image features based on internal knowledge or assumptions before these tools have been executed.
