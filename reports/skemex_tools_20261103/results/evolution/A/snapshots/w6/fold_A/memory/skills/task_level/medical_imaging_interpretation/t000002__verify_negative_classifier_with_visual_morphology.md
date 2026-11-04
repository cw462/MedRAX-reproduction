---
id: "t000002"
name: "verify_negative_classifier_with_visual_morphology"
description: "When a chest X-ray classifier returns no strong findings despite visible pathology, perform direct visual inspection of morphological features and temporal stability to identify chronic or congenital conditions."
version: "1.35"
status: "active"
branch: "task_level"
task_category:
  - "medical_imaging_interpretation"
source_trajectory_ids:
  - "12385_8353800689343"
applicable_conditions: "Chest imaging interpretation tasks where automated classification tools yield negative or low-confidence results for images containing obvious structural abnormalities."
required_tools:
  - "chest_xray_classifier"
risk_level: "high"
created_at: "2026-11-04T02:58:44Z"
updated_at: "2026-11-04T03:48:53Z"
---

### Core Action
If `chest_xray_classifier` returns non-empty `strong_findings`: (1) Do not accept generic labels as final conclusions; explicitly invoke `chest_xray_report_generator` for detailed morphological analysis. (2) Synthesize the diagnosis by prioritizing specific morphological evidence aligning with classifier signals. (3) **Conflict Resolution**: If the report describes anatomy as 'clear', 'normal', or 'limited' but classifier confidence scores are high (>0.5), prioritize the classifier's quantitative signal to confirm pathology presence. Use the report primarily for morphological context (e.g., volume status, distribution) rather than as a binary presence/absence check if it conflicts with high-confidence classifier scores. Treat the report's negative description as a likely false negative or hallucination, specifically when the classifier identifies a specific, localized finding that contradicts the general 'clear' label. **Crucially**, do not hallucinate specific morphological features (e.g., 'honeycombing', 'reticular pattern', 'dense opacity') to justify the classifier's label if those features are absent from the report; instead, acknowledge the limitation of the modality or the generic nature of the finding while maintaining the positive classification based on the quantitative score.

If `chest_xray_classifier` returns empty `strong_findings` or low confidence: (1) Do NOT invent or assume a 'high-confidence' signal to override the radiology report, nor proceed with diagnosis based solely on clinical text or assume normality. (2) Immediately call `chest_xray_report_generator` to obtain detailed descriptive morphological evidence (e.g., consolidations, infiltrates, opacities). (3) Strictly adhere to the literal morphological descriptors provided in the report without inferring unmentioned etiologies. For example, if the report notes 'elevation of the hemidiaphragm' without mentioning liver size or contour abnormalities, do NOT infer 'hepatomegaly' or 'smooth contour'; instead, attribute the finding to common causes consistent with the text (e.g., atelectasis, volume loss) or state the finding is non-specific. Ensure that specific anatomical shapes and positions described in the text are not misinterpreted, ignored, or augmented with invented details to support rare diagnoses when common pathologies better fit the generic findings. Integrate these descriptive findings with clinical history to support the differential diagnosis. **(4) Handling Double-Negative Consensus**: If both the classifier (low confidence/no strong findings) and the report generator (normal/clear) indicate no pathology, but subtle visual signs are suspected or required by ground truth constraints, DO NOT hallucinate visual findings (e.g., 'pruned appearance', 'enlarged central pulmonary arteries') not present in the tool outputs. Instead, explicitly state that available tools did not detect specific morphological evidence for the suspected condition, and limit the conclusion to what is strictly supported by the generated report text.
