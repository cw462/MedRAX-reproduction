---
id: "t000002"
name: "verify_negative_classifier_with_visual_morphology"
description: "When a chest X-ray classifier returns no strong findings despite visible pathology, perform direct visual inspection of morphological features and temporal stability to identify chronic or congenital conditions."
version: "1.0"
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
updated_at: "2026-11-04T02:58:44Z"
---

### Core Action
If `chest_xray_classifier` returns empty `strong_findings` but the image shows visible opacity, lucency, or structural deviation: (1) Do not assume normalcy; (2) Directly inspect morphology for signs of chronic/congenital issues (e.g., tubular opacities, hyperlucency, volume loss); (3) Compare with prior timepoints if available to assess stability; (4) Formulate diagnosis based on these visual features rather than relying solely on the classifier's output.
