---
id: "t000008"
name: "verify_bilateral_hilar_findings_with_lateral_view"
description: "When a chest X-ray classifier identifies high-confidence masses in bilateral hilar regions, verify the finding using lateral views to distinguish symmetric adenopathy from malignancy."
version: "1.0"
status: "active"
branch: "task_level"
task_category:
  - "medical_imaging_interpretation"
source_trajectory_ids:
  - "14597_8353800528984"
applicable_conditions: "Chest imaging tasks where automated classifiers detect bilateral hilar abnormalities or masses, requiring differentiation between lymphadenopathy (e.g., sarcoidosis) and neoplastic processes."
required_tools:
  - "chest_xray_classifier"
  - "chest_xray_report_generator"
risk_level: "high"
created_at: "2026-11-04T03:13:24Z"
updated_at: "2026-11-04T03:13:24Z"
---

### Core Action
If `chest_xray_classifier` returns a high-confidence 'Mass' finding for bilateral hilar structures: (1) Do not accept the label as definitive malignancy; (2) Call `chest_xray_report_generator` specifically on lateral views; (3) Analyze the report for symmetry of hilar enlargement and absence of parenchymal invasion; (4) Prioritize the morphological pattern of symmetric adenopathy over the generic classifier label if lateral view confirms symmetry.
