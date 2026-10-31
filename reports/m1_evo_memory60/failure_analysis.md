# M1：具体经验与差异分析

以下是完成后的定向阅读入口。反思文字和模型观察不是人工确认的患者事实；参考诊断不证明所有相关征象可见。

## E的纠正与误改

legal_wrong_to_correct: [13154_8353800587826](cases/13154_8353800587826.md), [7738_8353800850751](cases/7738_8353800850751.md)

correct_to_legal_wrong: [11858_8353800664572](cases/11858_8353800664572.md), [1461_8353802159822](cases/1461_8353802159822.md), [15189_8353800545058](cases/15189_8353800545058.md), [17621_8143559684844](cases/17621_8143559684844.md), [3686_8353801520174](cases/3686_8353801520174.md), [4118_8353801523564](cases/4118_8353801523564.md), [4491_8353801523228](cases/4491_8353801523228.md), [4510_8353801532552](cases/4510_8353801532552.md), [8300_8353800861859](cases/8300_8353800861859.md)

missing_to_correct: 

correct_to_missing: 

## ES的纠正与误改

legal_wrong_to_correct: [13154_8353800587826](cases/13154_8353800587826.md), [13935_8353800618951](cases/13935_8353800618951.md), [3359_8353801515597](cases/3359_8353801515597.md)

correct_to_legal_wrong: [11858_8353800664572](cases/11858_8353800664572.md), [1461_8353802159822](cases/1461_8353802159822.md), [15189_8353800545058](cases/15189_8353800545058.md), [17621_8143559684844](cases/17621_8143559684844.md), [3686_8353801520174](cases/3686_8353801520174.md), [4118_8353801523564](cases/4118_8353801523564.md), [4510_8353801532552](cases/4510_8353801532552.md)

missing_to_correct: 

correct_to_missing: 

## 非通用经验示例（归档全文，非当前患者事实）

```json
{
  "task": [
    "sequence interpretation",
    "temporal change localization"
  ],
  "modality": "CXR",
  "case_pattern": "recurrent pneumonia with surgery",
  "error_or_success": "correct selection of B over C/D/E based on lobe-specific progression and post-op pneumothorax",
  "decisive_difference": "Figure 1a/1b show right lower lobe (RLL) consolidation (posterior basal on lateral), not middle or upper; Figure 4a shows volume loss (atelectasis) in same region; Figure 4c shows apical lucency with visceral pleural line—minimal pneumothorax—not complete resolution or nodule formation",
  "inspection_action": "In sequential CXRs, correlate opacity location across PA/lateral views to confirm lobe (e.g., RLL = posterior basal on lateral, silhouetting diaphragm on PA); then assess for volume loss (shifted fissure, elevated hemidiaphragm) and new lucency with pleural line for pneumothorax",
  "evidence_basis": {
    "image": "RLL opacity in Fig 1a/1b; volume loss in Fig 4a; apical lucency with pleural line in Fig 4c",
    "question": "clinical history of recurrent pneumonia and surgery",
    "reference_only": "none provided"
  },
  "limitations": "No time stamps or clinical timeline; lateral view (Fig 1b) is low-contrast but sufficient to localize posterior basal RLL; pneumothorax size not quantified",
  "id": "seed:10026_8353800813737",
  "source_case_id": "11cc3a8595218a3523d9db72e05742b8e336ef77ef3cf7387de082ebf5b18288",
  "source_question_id": "10026_8353800813737",
  "source_phase": "seed_train",
  "available_after_step": 0,
  "previous_choice_text": "Persistent right lower lobe consolidation with progression to atelectasis, followed by resolution of consolidation and minimal pneumothorax post-surgery.",
  "correct_choice_text": "Persistent right lower lobe consolidation with progression to atelectasis, followed by resolution of consolidation and minimal pneumothorax post-surgery.",
  "modality_source": "reflection_model_reported_not_ground_truth",
  "truncated_fields": [],
  "actionable": true
}
```

```json
{
  "task": [
    "diagnosis",
    "comparison"
  ],
  "modality": "CXR",
  "case_pattern": "serial CXR comparison for pulmonary lesion evolution",
  "error_or_success": "Saved response chose C (size reduction), but reference answer is E (transformation to fibrotic striae)",
  "decisive_difference": "C relies on perceived size/density decrease; E requires identification of linear, reticular, low-density opacities replacing nodules—indicating fibrosis rather than mere shrinkage",
  "inspection_action": "On follow-up CXR, inspect right upper lobe for transition from discrete nodular opacities to thin, irregular linear densities (fibrotic striae) with preserved lung volume and no cavitation",
  "evidence_basis": {
    "image": "unverified visual observation (images lack sufficient resolution to confirm fibrotic striae vs. residual nodules)",
    "question": "explicit source facts: timestamps imply Figure 2a is later (2011 Aug vs. 2010 Sep)",
    "reference_only": "E is stated as correct, but no explanation provided"
  },
  "limitations": "Image resolution too low to distinguish fibrotic striae from residual nodules; no clinical history or prior imaging context; reference explanation missing",
  "id": "seed:10071_8353800827977",
  "source_case_id": "4c13492a0c99ca3e4832fcd8ed45295841678275e1cab7f77a78520759ea7771",
  "source_question_id": "10071_8353800827977",
  "source_phase": "seed_train",
  "available_after_step": 0,
  "previous_choice_text": "The nodular lesions have decreased in size in all lobes, particularly in the right upper lobe, which indicates effective therapeutic response.",
  "correct_choice_text": "The nodular lesions have transformed into fibrotic striae in the right upper lobe, indicating healing and resolution.",
  "modality_source": "reflection_model_reported_not_ground_truth",
  "truncated_fields": [],
  "actionable": true
}
```

```json
{
  "task": [
    "comparison",
    "localization"
  ],
  "modality": "CXR",
  "case_pattern": "serial imaging for miliary pattern progression",
  "error_or_success": "correct selection of B based on increased nodule density/distribution in right lung",
  "decisive_difference": "Figure 1b shows more numerous, denser, and more widespread fine nodules in the right lung vs. Figure 1a; left lung unchanged—ruling out A, C, D, E, F",
  "inspection_action": "Compare nodule count per quadrant (upper/mid/lower) and inter-nodular spacing in contralateral lung across timepoints; assess whether new opacities are truly nodular vs. alveolar or mass-like",
  "evidence_basis": {
    "image": "unverified visual observation: right lung appears more opaque with finer granular texture in 1b than 1a",
    "question": "explicit source facts: 6-month interval, focus on contralateral lung",
    "reference_only": "diagnosis confirmed as B, but no explanation provided"
  },
  "limitations": "No timepoint labels or clinical history; pixel resolution insufficient to definitively confirm nodule size <2 mm; reference explanation unavailable",
  "id": "online:E:10569_8353800725393",
  "source_case_id": "9c225a25baf2847828f299f46f22428571a4b305ad465e130ce58ac32e854fd0",
  "source_question_id": "10569_8353800725393",
  "source_phase": "past_stream",
  "available_after_step": 1,
  "previous_choice_text": "There is an increase in the number and distribution of miliary nodules in the right lung, consistent with metastatic spread.",
  "correct_choice_text": "There is an increase in the number and distribution of miliary nodules in the right lung, consistent with metastatic spread.",
  "modality_source": "reflection_model_reported_not_ground_truth",
  "truncated_fields": [],
  "actionable": true
}
```

```json
{
  "task": [
    "diagnosis",
    "comparison"
  ],
  "modality": "CXR",
  "case_pattern": "serial CXR showing change in left lung lucency and structure",
  "error_or_success": "Chose B (cystic structure resolved with pneumothorax, likely bulla) but reference answer is C (recurrent pneumothorax with persistent cyst, suggesting bronchogenic cyst)",
  "decisive_difference": "B assumes the cystic lucency disappeared; C requires it to persist. Visual inspection of Figure 3 shows a residual well-defined lucency near the left hilum—similar in location/shape to Figure 1—suggesting persistence, not resolution. The left lung is not fully re-expanded (lateral pleural line still faintly visible, volume loss), contradicting 're-expansion' in B.",
  "inspection_action": "In serial CXRs, compare exact location, shape, and border sharpness of any lucency near hilum across images; confirm if lung volume returns to baseline (rib spacing, diaphragm position) to distinguish true re-expansion from partial re-expansion with persistent lesion.",
  "evidence_basis": {
    "image": "Figure 1: large left hyperlucency, visceral pleural line, rounded lucency near hilum. Figure 3: reduced hyperlucency but persistent rounded lucency at same site; left hemithorax still slightly smaller than right, lateral pleural line faintly visible.",
    "question": "All options agree on initial pneumothorax + cystic structure in Fig 1.",
    "reference_only": "Reference selects C, implying persistent cyst and recurrent pneumothorax—but no explanation provided."
  },
  "limitations": "No clinical history (e.g., prior episodes, trauma), no time interval between images, no lateral view or CT to confirm cyst nature; pixel resolution insufficient to assess wall thickness or fluid level.",
  "id": "online:E:11624_8353800763402",
  "source_case_id": "6023019c17d1af79c63521ce0986dbec191fd40016aa370ab6d954a35ae6c9f2",
  "source_question_id": "11624_8353800763402",
  "source_phase": "past_stream",
  "available_after_step": 2,
  "previous_choice_text": "Figure 1 shows a large left-sided pneumothorax and a cystic structure, and Figure 3 shows a re-expansion of the left lung with disappearance of the cystic structure, indicating that the structure was likely a bullae that resolved with the pneumothorax.",
  "correct_choice_text": "Figure 1 shows a large left-sided pneumothorax and a cystic structure, and Figure 3 shows a recurrent pneumothorax with a persistent cystic structure, suggesting a bronchogenic cyst that contributes to recurrent pneumothorax due to its rupture.",
  "modality_source": "reflection_model_reported_not_ground_truth",
  "truncated_fields": [],
  "actionable": true
}
```

```json
{
  "task": [
    "comparison",
    "localization"
  ],
  "modality": "CXR",
  "case_pattern": "serial imaging for miliary pattern progression",
  "error_or_success": "correct selection of B based on increased nodular burden in right lung",
  "decisive_difference": "Figure 1b shows new diffuse fine nodules in right lung not present (or markedly less) in Figure 1a; left lung remains relatively clear, supporting contralateral progression",
  "inspection_action": "Compare bilateral lung fields side-by-side at identical magnification; specifically assess right lung for new fine nodular opacities relative to prior study",
  "evidence_basis": {
    "image": "unverified visual observation of increased right-lung nodularity in 1b vs 1a",
    "question": "explicitly asks about change over 6 months in contralateral lung",
    "reference_only": "none provided"
  },
  "limitations": "No timepoint labels or clinical history in images; assumes 1a = baseline, 1b = follow-up per saved reasoning",
  "id": "online:ES:10569_8353800725393",
  "source_case_id": "9c225a25baf2847828f299f46f22428571a4b305ad465e130ce58ac32e854fd0",
  "source_question_id": "10569_8353800725393",
  "source_phase": "past_stream",
  "available_after_step": 1,
  "previous_choice_text": "There is an increase in the number and distribution of miliary nodules in the right lung, consistent with metastatic spread.",
  "correct_choice_text": "There is an increase in the number and distribution of miliary nodules in the right lung, consistent with metastatic spread.",
  "modality_source": "reflection_model_reported_not_ground_truth",
  "truncated_fields": [],
  "actionable": true
}
```

```json
{
  "task": [
    "diagnosis"
  ],
  "modality": "CXR",
  "case_pattern": "serial CXR comparison of pneumothorax with adjacent lucency",
  "error_or_success": "Choice B selected (cystic structure resolved with re-expansion), but reference answer is C (recurrent pneumothorax with persistent cyst)",
  "decisive_difference": "B assumes disappearance of cystic lucency implies transient bulla; C requires persistence of cystic structure and recurrent pneumothorax—yet Figure 3 shows re-expanded lung without visible pleural line or new hyperlucency, contradicting 'recurrent pneumothorax'. No image evidence supports recurrence or persistence.",
  "inspection_action": "In serial CXRs, verify presence/absence of visceral pleural line and quantify residual lucency at same anatomical coordinates (e.g., using rib count) to distinguish true recurrence from artifact or incomplete re-expansion.",
  "evidence_basis": {
    "image": "Figure 1: left hyperlucency, absent markings, visible pleural line, round lucency near hilum. Figure 3: restored lung markings, no pleural line, no obvious lucency at same site.",
    "question": "Describes changes from Fig 1 to Fig 3; all options assume cystic structure present in Fig 1.",
    "reference_only": "Reference answer C asserts persistent cyst and recurrent pneumothorax, but no supporting image description or explanation provided."
  },
  "limitations": "No time interval, clinical history, or lateral views supplied; reference explanation unavailable; pixel resolution insufficient to confirm subtle pleural line or cyst wall in Fig 3.",
  "id": "online:ES:11624_8353800763402",
  "source_case_id": "6023019c17d1af79c63521ce0986dbec191fd40016aa370ab6d954a35ae6c9f2",
  "source_question_id": "11624_8353800763402",
  "source_phase": "past_stream",
  "available_after_step": 2,
  "previous_choice_text": "Figure 1 shows a large left-sided pneumothorax and a cystic structure, and Figure 3 shows a re-expansion of the left lung with disappearance of the cystic structure, indicating that the structure was likely a bullae that resolved with the pneumothorax.",
  "correct_choice_text": "Figure 1 shows a large left-sided pneumothorax and a cystic structure, and Figure 3 shows a recurrent pneumothorax with a persistent cystic structure, suggesting a bronchogenic cyst that contributes to recurrent pneumothorax due to its rupture.",
  "modality_source": "reflection_model_reported_not_ground_truth",
  "truncated_fields": [],
  "actionable": true
}
```

## 后续人工定位

只围绕差异题核对实际检索是否找到相同混淆、具体检查动作是否适用、是否将历史参考诊断直接套到当前患者，以及当前像素/题干是否足够区分；不得仅凭一段反思或正确性关联宣称因果。未超过42时交付真实失败，不自动重跑调参。

[完成后的具体差异分析与实现缺陷](outcome_interpretation.md)
