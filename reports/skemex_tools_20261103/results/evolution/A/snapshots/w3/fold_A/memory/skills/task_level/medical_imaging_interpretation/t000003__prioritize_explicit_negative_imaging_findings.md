---
id: "t000003"
name: "Prioritize Explicit Negative Imaging Findings"
description: "When an imaging report generator explicitly states that anatomy is 'clear' or 'normal', the agent must accept this negative finding and suppress any internal visual assumptions of pathology."
version: "1.2"
status: "deprecated"
branch: "task_level"
task_category:
  - "medical_imaging_interpretation"
source_trajectory_ids:
  - "4005_8353801524020"
applicable_conditions: "Tasks involving the interpretation of medical imaging reports where the tool output contains explicit negative findings (e.g., 'clear lungs', 'no acute abnormalities') that contradict the agent's prior expectations or visual heuristics."
required_tools:
  - "chest_xray_report_generator"
risk_level: "high"
created_at: "2026-11-04T02:59:02Z"
updated_at: "2026-11-04T03:25:12Z"
---

### Core Action
If the `chest_xray_report_generator` returns a report stating that the relevant anatomy is 'clear', 'normal', 'unremarkable', or limited by technical factors (e.g., 'limited by habitus'): (1) Cross-reference this with quantitative scores from `chest_xray_classifier` for major structural abnormalities (e.g., Consolidation, Effusion, Cardiomegaly, Lung Opacity); (2) If classifier confidence scores are high (>0.5 or defined threshold) and contradict the text report's negative or vague finding, prioritize the classifier's quantitative evidence and visual morphology over the generated text; (3) Do NOT accept the 'normal' or 'limited' label if high-confidence classifier signals indicate pathology to avoid false negatives; (4) Formulate the final answer reflecting the severity indicated by the classifier scores.
