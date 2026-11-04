---
id: "t000004"
name: "mandatory_image_tool_invocation_for_radiology_tasks"
description: "When a differential diagnosis task involves interpreting chest imaging or requires visual evidence from radiological studies, the agent must invoke image analysis tools before forming any diagnostic conclusion."
version: "1.3"
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
updated_at: "2026-11-04T03:25:08Z"
---

### Core Action
If the task requires analyzing chest imaging findings (e.g., opacities, nodules, patterns) to support a diagnosis: (1) Immediately call `chest_xray_report_generator` for a structured radiological description and `chest_xray_classifier` to identify specific pathological features. Do NOT generate findings or diagnoses based on text prompts, hallucinated figure references, or internal assumptions without first executing these tools. (2) Base all subsequent clinical reasoning strictly on the tool outputs. Crucially, when synthesizing the final answer, prioritize explicit positive findings from the tools (e.g., high-confidence classifier scores) over negative textual descriptors, clinical context suggestions, or internal assumptions if they conflict. If the tools do not detect a specific finding, exclude it from the conclusion; rely solely on the positive findings reported by the tools to select the correct answer.
