---
id: "t000004"
name: "Prioritize Clinical/Visual Evidence Over Low-Confidence Classifier Negatives"
description: "When chest X-ray classifier scores are non-diagnostic but clinical symptoms and visual markers strongly suggest an acute pathology, prioritize the clinical and visual evidence over the negative tool output."
version: "1.7"
status: "deprecated"
branch: "task_level"
task_category:
  - "differential_diagnosis"
source_trajectory_ids:
  - "16844_8143559672130"
applicable_conditions: "Tasks involving differential diagnosis where automated image classification tools return low-confidence or negative results despite strong contextual clues (symptoms, specific visual annotations) indicating a potential acute condition."
required_tools:
  - "chest_xray_classifier"
risk_level: "high"
created_at: "2026-11-04T13:53:04Z"
updated_at: "2026-11-04T14:22:13Z"
---

### Core Action
If `chest_xray_classifier` returns no strong findings (e.g., all scores < threshold) but clinical context (e.g., recent surgery, trauma) and visual inspection suggest structural pathology (e.g., mediastinal widening, abnormal contours):

1. **Accept Tool Limitation**: Explicitly acknowledge that the classifier did not detect strong visual evidence. Do NOT hallucinate radiological signs to match the clinical suspicion.
2. **Prioritize Clinical Timeline & Structural Markers**: Give precedence to the patient's clinical history (e.g., post-operative status) and visible gross structural anomalies over the classifier's negative output when inferring acute complications (e.g., hematoma, effusion) rather than chronic or malignant processes.
3. **Invoke Objective Reporting for Ambiguity**: If the structural anomaly is subtle or requires precise morphological description to rule out artifacts, call `chest_xray_report_generator` to obtain an objective, structured description of the region of interest. Use this report to confirm the presence of the structural marker before finalizing the differential diagnosis.
