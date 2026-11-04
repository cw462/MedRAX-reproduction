---
id: "t000003"
name: "Prioritize Report Generator for Structural Imaging Findings"
description: "When interpreting medical images for specific structural abnormalities (e.g., cavities, air-fluid levels) and initial classification scores are non-informative or weak."
version: "1.8"
status: "active"
branch: "task_level"
task_category:
  - "medical_imaging_interpretation"
source_trajectory_ids:
  - "10176_8353800802019"
applicable_conditions: "Tasks involving the interpretation of medical imaging where the query requires identifying specific morphological or structural features rather than general disease classification, and where automated classifiers fail to provide high-confidence detections."
required_tools:
  - "chest_xray_report_generator"
risk_level: "high"
created_at: "2026-11-04T12:46:03Z"
updated_at: "2026-11-04T12:57:30Z"
---

### Core Action
If the initial image classifier returns low confidence scores or fails to detect specific structural features (such as cavities, nodules, fluid levels, calcifications, or pleural effusion characteristics): (1) Invoke `chest_xray_report_generator` to extract detailed descriptive text findings from the image; (2) Critically evaluate the report generator's output against the clinical context and original image pixels. If the report yields a negative or 'unremarkable' finding for a feature strongly suggested by clinical context or visual cues (e.g., pericardial calcification, pleural thickening, or inhomogeneous fluid density/septations in effusions), do NOT accept the negative tool output as final. Instead, perform direct visual inspection of the original image—prioritizing lateral views where structural densities are often more distinct—to verify the presence of subtle pathologies, overriding the tool's false negative if visual evidence confirms the finding. Additionally, if there is a contradiction between the classifier (showing high scores >0.8 for Effusion/Consolidation/Edema) and the report generator (denying these findings), prioritize the classifier scores and direct visual evidence of opacities over the report generator's negative output. The report generator is prone to hallucinating normalcy in complex cases involving hardware or overlapping densities, whereas the classifier captures the presence of opacity/effusion patterns more reliably. Specifically, if bilateral perihilar opacities are present alongside cardiomegaly, prioritize the diagnosis of pulmonary edema over simple pleural effusion or atelectasis, recognizing that generic classifiers may mislabel edema patterns as effusion/consolidation. Crucially, when the report generator describes findings like 'consolidation' or 'effusion' but the clinical history suggests acute traumatic or vascular etiologies (e.g., sudden onset pain, recent trauma) and the classifier support for infectious causes is low (<0.1), treat the report's descriptive labels with skepticism. Verify if the described opacity aligns with the clinical timeline; do not allow the report generator's hallucinated temporal changes or static structural interpretations to override strong clinical contraindications for the implied diagnosis. Conversely, if visual inspection suggests specific pathologies (e.g., tumors, precise depth) but both `chest_xray_report_generator` states 'clear'/'no evidence' and `chest_xray_classifier` shows no strong findings, discard the visual hypothesis as a likely hallucination. Conclude that the imaging modality may be insufficient for the suspected distinction (e.g., breast vs. lung mass) without further views or CT, and report the negative tool findings as the primary result rather than asserting unverified visual details.
