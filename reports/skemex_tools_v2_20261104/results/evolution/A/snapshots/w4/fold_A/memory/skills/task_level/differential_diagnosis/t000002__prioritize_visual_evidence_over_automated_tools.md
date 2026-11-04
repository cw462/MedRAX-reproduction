---
id: "t000002"
name: "prioritize_visual_evidence_over_automated_tools"
description: "When automated radiology tools return normal or contradictory reports despite specific clinical vignette clues suggesting pathology, prioritize direct visual inspection of the original image."
version: "1.8"
status: "active"
branch: "task_level"
task_category:
  - "differential_diagnosis"
source_trajectory_ids:
  - "12385_8353800664317"
applicable_conditions: "Tasks involving differential diagnosis where automated chest X-ray classifiers or report generators fail to detect subtle signs or provide results inconsistent with the clinical presentation."
required_tools:
  - "chest_xray_classifier"
  - "chest_xray_report_generator"
risk_level: "high"
created_at: "2026-11-04T12:45:16Z"
updated_at: "2026-11-04T13:21:15Z"
---

### Core Action
If `chest_xray_classifier` and `chest_xray_report_generator` return normal or non-specific findings but the clinical vignette describes specific symptoms (e.g., localized pain, abnormal breath sounds) or suggests a condition with subtle radiographic signs: (1) Do not accept the 'normal' tool output as final; (2) Manually inspect the original chest X-ray image for subtle features (e.g., tubular opacities, hyperlucency, faint consolidations, focal densities) that automated tools may miss; (3) Base the differential diagnosis on the combination of clinical clues and direct visual evidence rather than relying solely on the generated report. CRITICAL ADDITION 1: When visual inspection reveals bilateral perihilar opacities, pleural effusions, or cardiomegaly/enlarged cardiomediastinum, prioritize Pulmonary Edema/Cardiac Failure in the differential over Pneumonia, even if fever is present. Fever can be a distractor or comorbidity; the structural radiographic pattern (symmetry, vascular congestion, cardiac silhouette) is the primary discriminator for cardiac vs. infectious etiology. CRITICAL ADDITION 2: In trauma contexts, if a 'focal density' or localized opacity is identified despite negative automated reports, do not default to common parenchymal injuries like pulmonary contusion. Instead, consider penetrating injury with retained foreign bodies (including radiolucent objects like wood causing secondary inflammation/hematoma) or localized hematoma, especially if the clinical history supports penetration or specific localized impact. CRITICAL ADDITION 3: During manual inspection, strictly verify anatomical laterality (Left vs. Right) and morphological descriptors (e.g., Sharp vs. Indistinct margins) against the image pixels before forming a conclusion. Do not allow diagnostic preference (e.g., favoring Pneumonia) to hallucinate visual features; if the image shows sharp margins and left-sided blunting, explicitly reject interpretations suggesting indistinct margins or right-sided pathology, regardless of how well they fit a preferred diagnosis.
