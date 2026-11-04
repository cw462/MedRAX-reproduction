---
id: "t000001"
name: "verify_temporal_resolution_for_transient_pathology"
description: "When initial imaging shows diffuse bilateral opacities, verify if findings resolve rapidly in follow-up images to distinguish transient conditions from persistent pathologies."
version: "1.0"
status: "active"
branch: "task_level"
task_category:
  - "medical_imaging_interpretation"
source_trajectory_ids:
  - "18680_8143559034217"
applicable_conditions: "Tasks involving the interpretation of serial medical imaging where the differential diagnosis includes both transient (e.g., hemorrhage, edema) and persistent (e.g., infection, fibrosis) causes of similar radiographic appearances."
required_tools:
  - "chest_xray_classifier"
risk_level: "high"
created_at: "2026-11-04T02:58:10Z"
updated_at: "2026-11-04T02:58:10Z"
---

### Core Action
If the initial image analysis reveals high-confidence diffuse bilateral opacities: (1) explicitly retrieve and analyze available follow-up imaging using `chest_xray_classifier`; (2) compare the severity and extent of findings between the initial and follow-up timepoints; (3) if findings show rapid normalization or significant improvement, prioritize transient etiologies (e.g., hemorrhage, flash pulmonary edema) over slower-resolving pathologies (e.g., pneumonia, ARDS) in the final diagnosis.
