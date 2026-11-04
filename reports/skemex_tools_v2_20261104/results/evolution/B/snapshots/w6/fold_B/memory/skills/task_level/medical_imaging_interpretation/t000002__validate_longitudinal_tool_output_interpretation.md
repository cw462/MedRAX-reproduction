---
id: "t000002"
name: "validate_longitudinal_tool_output_interpretation"
description: "Prevents misinterpretation of static classifier scores as longitudinal change metrics and hallucination of specific visual features not present in tool output."
version: "1.0"
status: "active"
branch: "task_level"
task_category:
  - "medical_imaging_interpretation"
source_trajectory_ids:
  - "16812_8353800572859"
applicable_conditions: "When interpreting medical imaging results from automated tools (e.g., classifiers, detectors) across multiple timepoints or when describing findings based on tool outputs."
required_tools:
  - "chest_xray_classifier"
risk_level: "high"
created_at: "2026-11-04T13:51:51Z"
updated_at: "2026-11-04T13:51:51Z"
---

### Core Action
If comparing imaging findings across timepoints using a classifier tool: (1) Treat each score as an independent, uncalibrated snapshot; do NOT calculate deltas or infer progression/regression solely from score differences (e.g., 0.88 vs 0.89). (2) Restrict descriptive language strictly to the labels provided by the tool (e.g., 'Lung Opacity'); do NOT hallucinate specific morphological features (e.g., 'consolidation', 'nodule') unless explicitly returned by the tool. (3) If longitudinal assessment is required, acknowledge the limitation of static scores and prioritize explicit radiologist reports or visual confirmation over score trends.
