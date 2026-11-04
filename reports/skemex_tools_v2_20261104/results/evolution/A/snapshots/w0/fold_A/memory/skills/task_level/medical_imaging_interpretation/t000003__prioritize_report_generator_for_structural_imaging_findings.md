---
id: "t000003"
name: "Prioritize Report Generator for Structural Imaging Findings"
description: "When interpreting medical images for specific structural abnormalities (e.g., cavities, air-fluid levels) and initial classification scores are non-informative or weak."
version: "1.0"
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
updated_at: "2026-11-04T12:46:03Z"
---

### Core Action
If the initial image classifier returns low confidence scores or fails to detect specific structural features (such as cavities, nodules, or fluid levels): (1) Do NOT attempt to describe visual findings based on raw pixel inspection or hallucinated evidence; (2) Immediately invoke `chest_xray_report_generator` to extract detailed descriptive text findings from the image; (3) Base the final clinical interpretation on the structured output of the report generator.
