---
id: "t000005"
name: "enforce_imaging_tool_invocation"
description: "When presented with a medical imaging interpretation task, the agent must invoke available analysis tools instead of generating a diagnosis from internal knowledge or hallucinating data."
version: "1.0"
status: "active"
branch: "task_level"
task_category:
  - "medical_imaging_interpretation"
source_trajectory_ids:
  - "7588_8353800871000"
applicable_conditions: "The user provides an image file (e.g., X-ray, CT, MRI) or explicitly requests an interpretation of medical imaging data, and specific analysis tools are available in the environment."
required_tools:
  - "chest_xray_classifier"
  - "chest_xray_report_generator"
risk_level: "high"
created_at: "2026-11-04T04:05:35Z"
updated_at: "2026-11-04T04:05:35Z"
---

### Core Action
If the task involves interpreting medical images: (1) Identify the modality (e.g., Chest X-ray); (2) Immediately invoke the corresponding analysis tool (e.g., `chest_xray_classifier` for classification or `chest_xray_report_generator` for detailed reporting) with the image input; (3) Base the final response strictly on the tool's output. Do NOT attempt to diagnose or describe findings without first calling the appropriate tool.
