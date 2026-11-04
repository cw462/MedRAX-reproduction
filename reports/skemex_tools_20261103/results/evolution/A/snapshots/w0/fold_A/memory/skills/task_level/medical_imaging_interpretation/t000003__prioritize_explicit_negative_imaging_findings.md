---
id: "t000003"
name: "Prioritize Explicit Negative Imaging Findings"
description: "When an imaging report generator explicitly states that anatomy is 'clear' or 'normal', the agent must accept this negative finding and suppress any internal visual assumptions of pathology."
version: "1.0"
status: "active"
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
updated_at: "2026-11-04T02:59:02Z"
---

### Core Action
If the `chest_xray_report_generator` (or equivalent imaging tool) returns a report stating that the relevant anatomy is 'clear', 'normal', or 'unremarkable': (1) Immediately accept this as the ground truth for the absence of mass/consolidation; (2) Do NOT hallucinate features like 'well-circumscribed masses' or 'nodules' based on visual artifacts or prior expectations; (3) Formulate the final answer strictly adhering to the negative finding provided by the tool.
