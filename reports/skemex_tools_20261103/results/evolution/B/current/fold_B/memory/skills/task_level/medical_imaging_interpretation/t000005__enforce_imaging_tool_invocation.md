---
id: "t000005"
name: "enforce_imaging_tool_invocation"
description: "When presented with a medical imaging interpretation task, the agent must invoke available analysis tools instead of generating a diagnosis from internal knowledge or hallucinating data."
version: "1.11"
status: "deprecated"
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
updated_at: "2026-11-04T04:39:46Z"
---

### Core Action
If the task involves interpreting medical images: (1) Identify the modality (e.g., Chest X-ray); (2) Immediately invoke the corresponding analysis tool (e.g., `chest_xray_classifier` for classification or `chest_xray_report_generator` for detailed reporting) with the image input; (3) Base the final response STRICTLY on the tool's output text. Explicitly cite specific morphological details (e.g., 'cavitary lesion', 'necrotizing changes') found in the generated report as evidence for the diagnosis. Do NOT attempt to diagnose, describe findings, or claim visual verification without first calling the appropriate tool and referencing its output. Crucially, do NOT override or ignore the tool's output with external knowledge, visual inspection of other modalities (e.g., CT), hallucinated findings, or probabilistic scores from classifiers if they contradict the explicit textual report. Specifically, ensure that every anatomical landmark or morphological detail cited in the reasoning is explicitly present in the tool's returned text string; do not infer, extrapolate, or hallucinate details (such as heart position, fissure location, or specific patterns like 'reticulonodular' or 'basal haziness' unless explicitly stated) that are not verbatim or explicitly stated in the tool output. If the tool explicitly negates a finding (e.g., 'no pleural abnormalities'), this negation must be treated as definitive evidence against that finding, regardless of any associated confidence scores or prior expectations. Furthermore, if the tool's output identifies specific devices (e.g., catheters, lines) or pathologies (e.g., pneumothorax), these must be accepted as the primary diagnostic evidence, even if clinical context (e.g., trauma history) suggests alternative diagnoses not supported by the imaging report. **CRITICAL CONSTRAINT**: If the tool's output contains findings that differ from the expected ground truth or clinical intuition, you MUST still prioritize the tool's text. Do not hallucinate missing signs (e.g., 'translucent line', 'varying cardiac density') to force alignment with a preferred diagnosis if those signs are absent from the tool's report. The validity of the answer is determined by adherence to the provided tool output, not by external correctness.
