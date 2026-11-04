---
id: "t000007"
name: "enforce_tool_usage_for_image_interpretation"
description: "When a task requires interpreting medical imaging data (e.g., X-rays, CTs), the agent must invoke specific analysis tools rather than generating visual descriptions from text context alone."
version: "1.0"
status: "active"
branch: "task_level"
task_category:
  - "medical_imaging_interpretation"
source_trajectory_ids:
  - "7913_8353800870985"
applicable_conditions: "The user query explicitly references an image file, attachment, or visual finding that requires computational analysis, and no prior tool output containing the interpretation is available in the context."
required_tools:
  - "chest_xray_classifier"
  - "chest_xray_report_generator"
risk_level: "high"
created_at: "2026-11-04T03:11:56Z"
updated_at: "2026-11-04T03:11:56Z"
---

### Core Action
If the task involves analyzing a medical image: (1) Do NOT attempt to describe or diagnose the image based on textual cues or hallucinated figure references. (2) Immediately invoke `chest_xray_classifier` to obtain objective findings or `chest_xray_report_generator` to produce a structured report. (3) Base all subsequent clinical reasoning strictly on the tool's output.
