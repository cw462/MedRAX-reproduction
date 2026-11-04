---
id: "t000003"
name: "fallback_visual_analysis_for_low_confidence_classifier"
description: "When automated image classifiers return low-confidence or negative findings for suspected acute pathologies, initiate direct visual inspection or report generation to identify subtle radiographic signs."
version: "1.32"
status: "active"
branch: "task_level"
task_category:
  - "differential_diagnosis"
source_trajectory_ids:
  - "16844_8143559672130"
applicable_conditions: "Applicable in diagnostic imaging tasks where initial automated tool outputs (e.g., classifiers) do not provide high-confidence positive results despite clinical suspicion or ambiguous presentation."
required_tools:
  - "chest_xray_report_generator"
risk_level: "high"
created_at: "2026-11-04T03:56:54Z"
updated_at: "2026-11-04T04:39:46Z"
---

### Core Action
When interpreting medical images (e.g., Chest X-ray):

1.  **Tool Invocation**: Immediately invoke the appropriate analysis tool (e.g., `chest_xray_classifier` for screening, `chest_xray_report_generator` for detailed description) with the image input. Do not attempt to diagnose, describe findings, or claim visual verification without first calling the tool and referencing its output.
2.  **Evidence-Based Synthesis**: Base the final response STRICTLY on the tool's output text. Every anatomical landmark or morphological detail cited (e.g., 'cavitary lesion', 'necrotizing changes') must be explicitly present in the returned text string. Do not infer, extrapolate, or hallucinate details (such as heart position, fissure location, or specific patterns like 'reticulonodular' unless explicitly stated) that are not verbatim in the tool output.
3.  **Handling Negative/Weak Classifier Results**: If the `chest_xray_classifier` returns no strong findings (scores < threshold) or negative results:
    *   Do not accept the negative result as final.
    *   Call `chest_xray_report_generator` to produce a detailed textual description.
    *   Check if the generated report explicitly identifies specific findings (e.g., 'pneumothorax', 'nodule', 'chest tube') or references visual annotations (e.g., 'arrow points to...').
4.  **Precedence Rules**:
    *   **Explicit Findings Take Precedence**: If the report contains explicit positive findings or device identifications, these take precedence over the classifier's negative output, conflicting clinical priors, or external knowledge. Accept these as primary diagnostic evidence even if they contradict a preferred rare diagnosis or initial suspicion.
    *   **Explicit Negations are Definitive**: If the tool explicitly negates a finding (e.g., 'no pleural abnormalities'), treat this as definitive evidence against that finding, regardless of associated confidence scores or prior expectations.
    *   **No Hallucination for Alignment**: Do not hallucinate missing signs (e.g., 'translucent line', 'varying cardiac density') to force alignment with a preferred diagnosis if those signs are absent from the tool's report. The validity of the answer is determined by adherence to the provided tool output, not by external correctness.
5.  **Ambiguous/Generic Findings**: If the report contains only generic or non-specific findings (e.g., 'opacity', 'infiltrates') that do not definitively confirm the suspected pathology, do not infer specific morphological features (e.g., 'hyperlucency', 'mediastinal shift', 'honeycombing') unless explicitly stated. Flag the discrepancy and recommend further imaging (e.g., CT) rather than forcing a positive diagnosis based on clinical suspicion alone.
