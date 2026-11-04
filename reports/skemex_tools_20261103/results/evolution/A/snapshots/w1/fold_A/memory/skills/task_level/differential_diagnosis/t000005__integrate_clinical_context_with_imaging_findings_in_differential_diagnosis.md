---
id: "t000005"
name: "Integrate Clinical Context with Imaging Findings in Differential Diagnosis"
description: "When imaging classifiers suggest multiple competing diagnoses (e.g., edema vs. consolidation), prioritize clinical risk factors and history over visual heuristics to determine the primary etiology."
version: "1.0"
status: "active"
branch: "task_level"
task_category:
  - "differential_diagnosis"
source_trajectory_ids:
  - "794_8353802185434"
applicable_conditions: "Tasks involving differential diagnosis where radiological findings are ambiguous or overlap between conditions (e.g., infectious vs. cardiogenic causes), and specific patient history (devices, fever, labs) provides critical discriminative evidence."
required_tools:
  - "chest_xray_classifier"
  - "chest_xray_report_generator"
risk_level: "high"
created_at: "2026-11-04T03:06:46Z"
updated_at: "2026-11-04T03:06:46Z"
---

### Core Action
If `chest_xray_classifier` returns high scores for overlapping pathologies (e.g., 'Consolidation' and 'Enlarged Cardiomediastinum'): (1) Do not rely solely on visual patterns like 'bat-wing' appearance; (2) Explicitly cross-reference patient history (e.g., prosthetic valves, fever, immunosuppression) against the differential list; (3) Prioritize diagnoses that explain both the imaging and the specific clinical risk factors (e.g., septic emboli from endocarditis causing consolidations); (4) Use `chest_xray_report_generator` to synthesize a conclusion that weighs clinical context higher than non-specific radiological signs.
