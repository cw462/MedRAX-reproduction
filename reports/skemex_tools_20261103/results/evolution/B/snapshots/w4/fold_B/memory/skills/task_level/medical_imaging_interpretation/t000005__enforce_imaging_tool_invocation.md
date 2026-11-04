---
id: "t000005"
name: "enforce_imaging_tool_invocation"
description: "When presented with a medical imaging interpretation task, the agent must invoke available analysis tools instead of generating a diagnosis from internal knowledge or hallucinating data."
version: "1.2"
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
updated_at: "2026-11-04T04:29:47Z"
---

### Core Action
If the task involves interpreting medical images: (1) Identify the modality (e.g., Chest X-ray); (2) Immediately invoke the corresponding analysis tool (e.g., `chest_xray_classifier` for classification or `chest_xray_report_generator` for detailed reporting) with the image input; (3) Base the final response STRICTLY on the tool's output text. Explicitly cite specific morphological details (e.g., 'cavitary lesion', 'necrotizing changes') found in the generated report as evidence for the diagnosis. Do NOT attempt to diagnose, describe findings, or claim visual verification without first calling the appropriate tool and referencing its output. Crucially, do NOT override or ignore the tool's output with external knowledge, visual inspection of other modalities (e.g., CT), or hallucinated findings; if the tool output contradicts other available information, prioritize the tool's explicit report for the specific modality requested.
