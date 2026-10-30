# V7 step 1: offline forensics of the 28 changed questions

No API calls. Answers come from the scored sidecars; injected text is rebuilt
from each run's retrieval log and checked against the logged length and sha256
(`log_match`); tool paths come from `semantic_trace.jsonl`.

**Mechanism level is `unknown` for every row unless stated otherwise.** What this
file establishes is what was visible and what changed, not why the model changed.

| group | n | log_match B/C | questions |
|---|---:|---|---|
| common_correct | 5 | 5/5 | 15189, 3436, 5369, 548, 7738 |
| b_only_correct | 3 | 3/3 | 11858, 13154, 3359 |
| c_only_correct | 3 | 3/3 | 11804, 18780, 3546 |
| common_harm | 6 | 6/6 | 15314, 16568, 17621, 4491, 722, 8300 |
| b_only_harm | 3 | 3/3 | 18202, 4118, 5533 |
| c_only_harm | 8 | 8/8 | 12721, 13238, 16663, 1678, 3397, 3561, 3686, 3834 |

## common_harm

### 15314_8353800558683 (detection,classification,relationship,reasoning, std C)

A/B/C = C/B/B

Plan focus: 分布属性来源与任务目标（问 PJP 支持证据）

* B's option differs from the standard on: “Bilateral ground-glass” vs “Multifocal patchy”; “peripheral” vs “central”; “” vs “and right middle lobe consolidation”
* C's option differs from the standard on: “Bilateral ground-glass” vs “Multifocal patchy”; “peripheral” vs “central”; “” vs “and right middle lobe consolidation”
* B injected 819 chars, 2 memories; attribute keywords in the injection: 1/17, in its own tool observations: 6/17
* C injected 1400 chars, skills ['S005', 'S017', 'S016']; attribute keywords in the injection: 7/17, in its own tool observations: 4/17
* first tool-path divergence B vs A: index 4, A=None vs B=xray_phrase_grounding
* first tool-path divergence C vs A: index 2, A=chest_xray_expert vs C=xray_phrase_grounding

### 16568_8353800483171 (localization,comparison,relationship,reasoning, std B)

A/B/C = B/A/A

Plan focus: 逐图逐侧核对，工具只说右侧≠左侧正常

* B's option differs from the standard on: “radiographs indicate unilateral” vs “bilateral”; “confined to” vs “are predominantly in the lower lobes and”; “'s middle lobe” vs “”
* C's option differs from the standard on: “radiographs indicate unilateral” vs “bilateral”; “confined to” vs “are predominantly in the lower lobes and”; “'s middle lobe” vs “”
* B injected 834 chars, 2 memories; attribute keywords in the injection: 0/18, in its own tool observations: 3/18
* C injected 1400 chars, skills ['S005', 'S014', 'S011']; attribute keywords in the injection: 6/18, in its own tool observations: 4/18
* first tool-path divergence B vs A: index 1, A=chest_xray_classifier vs B=chest_xray_report_generator
* first tool-path divergence C vs A: index 1, A=chest_xray_classifier vs C=chest_xray_report_generator

### 17621_8143559684844 (detection,localization,characterization,reasoning, std D)

A/B/C = D/A/A

Plan focus: 标准答案与解释冲突，单列歧义

* B's option differs from the standard on: “resolved” vs “decreased in size”; “new lesions have appeared” vs “the nodular shadows”; “lower” vs “upper”
* C's option differs from the standard on: “resolved” vs “decreased in size”; “new lesions have appeared” vs “the nodular shadows”; “lower” vs “upper”
* B injected 836 chars, 2 memories; attribute keywords in the injection: 0/13, in its own tool observations: 2/13
* C injected 1400 chars, skills ['S014', 'S005', 'S002']; attribute keywords in the injection: 3/13, in its own tool observations: 3/13
* first tool-path divergence B vs A: index 7, A=xray_phrase_grounding vs B=None
* first tool-path divergence C vs A: index 0, A=chest_xray_classifier vs C=chest_xray_expert

### 4491_8353801523228 (classification,characterization,diagnosis,reasoning, std B)

A/B/C = B/E/E

Plan focus: 阳性观察是否被后续报告遗漏覆盖

* B's option differs from the standard on: “shows no abnormal findings” vs “reveals pneumomediastinum and subcutaneo”; “discharge the patient without further in” vs “manage conservatively with observation”
* C's option differs from the standard on: “shows no abnormal findings” vs “reveals pneumomediastinum and subcutaneo”; “discharge the patient without further in” vs “manage conservatively with observation”
* B injected 553 chars, 1 memories; attribute keywords in the injection: 1/12, in its own tool observations: 1/12
* C injected 1400 chars, skills ['S012', 'S017', 'S002']; attribute keywords in the injection: 1/12, in its own tool observations: 1/12
* first tool-path divergence B vs A: index 3, A=chest_xray_expert vs B=xray_phrase_grounding
* first tool-path divergence C vs A: index 3, A=chest_xray_expert vs C=xray_phrase_grounding

### 722_8353802117601 (localization,comparison,relationship,reasoning, std D)

A/B/C = D/C/C

Plan focus: 对象-图像-侧别-大小关系表

* B's option differs from the standard on: “right” vs “left”; “of similar size to” vs “larger than”; “left lower” vs “right middle”
* C's option differs from the standard on: “right” vs “left”; “of similar size to” vs “larger than”; “left lower” vs “right middle”
* B injected 569 chars, 1 memories; attribute keywords in the injection: 1/10, in its own tool observations: 5/10
* C injected 1400 chars, skills ['S005', 'S016', 'S002']; attribute keywords in the injection: 7/10, in its own tool observations: 5/10
* first tool-path divergence B vs A: index 0, A=chest_xray_classifier vs B=chest_xray_expert
* first tool-path divergence C vs A: index 2, A=chest_xray_expert vs C=xray_phrase_grounding

### 8300_8353800861859 (classification,comparison,diagnosis,reasoning, std D)

A/B/C = D/B/B

Plan focus: 当前腔内征象 vs 既往结核关键词

* B's option differs from the standard on: “Tuberculous cavity” vs “Aspergilloma (fungus ball)”; “initiate anti-tuberculous therapy” vs “consider surgical resection due to risk ”
* C's option differs from the standard on: “Tuberculous cavity” vs “Aspergilloma (fungus ball)”; “initiate anti-tuberculous therapy” vs “consider surgical resection due to risk ”
* B injected 1096 chars, 3 memories; attribute keywords in the injection: 0/11, in its own tool observations: 4/11
* C injected 1400 chars, skills ['S003', 'S005', 'S014']; attribute keywords in the injection: 0/11, in its own tool observations: 4/11
* first tool-path divergence B vs A: index 4, A=xray_phrase_grounding vs B=None
* first tool-path divergence C vs A: index 5, A=None vs C=xray_phrase_grounding

## c_only_harm

### 12721_8353800681884 (classification,comparison,diagnosis,reasoning, std B)

A/B/C = B/B/None

Plan focus: 完成失败，不是判断翻转；查冗余轨迹

* B injected 553 chars, 1 memories; attribute keywords in the injection: 0/0, in its own tool observations: 0/0
* C injected 1400 chars, skills ['S014', 'S017', 'S012']; attribute keywords in the injection: 0/0, in its own tool observations: 0/0
* first tool-path divergence B vs A: index 2, A=chest_xray_expert vs B=chest_xray_report_generator
* first tool-path divergence C vs A: index 2, A=chest_xray_expert vs C=chest_xray_report_generator

### 13238_8353800603808 (localization,comparison,relationship,reasoning, std B)

A/B/C = B/B/A

Plan focus: 右/中央、胸壁关系、肋间、气管

* C's option differs from the standard on: “centrally in” vs “dorsolaterally on”; “mediastinum” vs “right side”; “causing displacement of” vs “widening”
* B injected 784 chars, 2 memories; attribute keywords in the injection: 0/0, in its own tool observations: 0/0
* C injected 1400 chars, skills ['S010', 'S006', 'S016']; attribute keywords in the injection: 5/20, in its own tool observations: 6/20
* B followed the same tool sequence as A
* first tool-path divergence C vs A: index 0, A=chest_xray_classifier vs C=xray_phrase_grounding

### 16663_8353800455763 (localization,comparison,relationship,reasoning, std C)

A/B/C = C/C/B

Plan focus: 分布与新增病因分别核对（歧义题）

* C's option differs from the standard on: “more extensive” vs “equally distributed”; “the right” vs “both”; “” vs “of both lungs”
* B injected 836 chars, 2 memories; attribute keywords in the injection: 0/0, in its own tool observations: 0/0
* C injected 1400 chars, skills ['S005', 'S002', 'S001']; attribute keywords in the injection: 3/15, in its own tool observations: 2/15
* first tool-path divergence B vs A: index 3, A=llava_med_qa vs B=xray_phrase_grounding
* first tool-path divergence C vs A: index 2, A=chest_xray_expert vs C=xray_phrase_grounding

### 1678_8353802279918 (classification,characterization,diagnosis,reasoning, std C)

A/B/C = C/C/A

Plan focus: 正侧位、投影重叠、阴性观察

* C's option differs from the standard on: “right middle lobe pneumonia” vs “the projection of anterior chest wall ti”; “confirmed by the presence of an air bron” vs “”; “” vs “shows a depressed sternum with no air br”
* B injected 936 chars, 3 memories; attribute keywords in the injection: 0/0, in its own tool observations: 0/0
* C injected 1400 chars, skills ['S006', 'S016', 'S005']; attribute keywords in the injection: 4/14, in its own tool observations: 5/14
* B followed the same tool sequence as A
* first tool-path divergence C vs A: index 0, A=chest_xray_classifier vs C=chest_xray_expert

### 3397_8353801520783 (detection,localization,characterization,reasoning, std C)

A/B/C = C/C/B

Plan focus: 空洞来自当前输出还是经验引入

* C's option differs from the standard on: “Upper lobe” vs “Bibasal interstitial”; “cavitations” vs “peripheral distribution”; “indicating possible pulmonary tuberculos” vs “consistent with interstitial lung diseas”
* B injected 774 chars, 2 memories; attribute keywords in the injection: 0/0, in its own tool observations: 0/0
* C injected 1400 chars, skills ['S017', 'S005', 'S014']; attribute keywords in the injection: 3/13, in its own tool observations: 3/13
* first tool-path divergence B vs A: index 3, A=xray_phrase_grounding vs B=None
* first tool-path divergence C vs A: index 4, A=None vs C=xray_phrase_grounding

### 3561_8353801511489 (detection,localization,characterization,reasoning, std B)

A/B/C = B/B/F

Plan focus: 正侧位同一病灶与膈肌关系

* C's option differs from the standard on: “Pseudotumor due to atelectasis” vs “Bochdalek hernia with herniated abdomina”
* B injected 1046 chars, 3 memories; attribute keywords in the injection: 0/0, in its own tool observations: 0/0
* C injected 1400 chars, skills ['S002', 'S006', 'S016']; attribute keywords in the injection: 2/6, in its own tool observations: 4/6
* first tool-path divergence B vs A: index 3, A=None vs B=xray_phrase_grounding
* first tool-path divergence C vs A: index 2, A=chest_xray_expert vs C=xray_phrase_grounding

### 3686_8353801520174 (classification,characterization,diagnosis,reasoning, std B)

A/B/C = B/B/F

Plan focus: 输入背景不足，单列

* C's option differs from the standard on: “Bronchiectasis-related pulmonary changes” vs “Pulmonary metastasis from a previous ute”
* B injected 782 chars, 2 memories; attribute keywords in the injection: 0/0, in its own tool observations: 0/0
* C injected 1400 chars, skills ['S014', 'S017', 'S010']; attribute keywords in the injection: 1/6, in its own tool observations: 0/6
* first tool-path divergence B vs A: index 2, A=None vs B=chest_xray_expert
* first tool-path divergence C vs A: index 0, A=chest_xray_classifier vs C=chest_xray_expert

### 3834_8353801523222 (detection,classification,relationship,reasoning, std C)

A/B/C = C/C/A

Plan focus: 基础慢性改变 vs 本次急性叠加

* C's option differs from the standard on: “Bilateral” vs “Diffuse ground glass opacities superimpo”; “with focal honeycombing” vs “”
* B injected 819 chars, 2 memories; attribute keywords in the injection: 0/0, in its own tool observations: 0/0
* C injected 1400 chars, skills ['S005', 'S001', 'S002']; attribute keywords in the injection: 4/9, in its own tool observations: 4/9
* B followed the same tool sequence as A
* first tool-path divergence C vs A: index 2, A=chest_xray_expert vs C=xray_phrase_grounding

## b_only_harm

### 18202_8143559000122 (detection,classification,relationship,reasoning, std A)

A/B/C = A/C/A

Plan focus: “可能出现的征象”vs“本图存在的征象”

* B's option differs from the standard on: “Engorgement” vs “Wedge-shaped pleural-based opacity in th”; “and a focal peripheral hyperlucency in t” vs “”
* B injected 1044 chars, 3 memories; attribute keywords in the injection: 0/12, in its own tool observations: 11/12
* C injected 1400 chars, skills ['S011', 'S005', 'S002']; attribute keywords in the injection: 0/0, in its own tool observations: 0/0
* first tool-path divergence B vs A: index 1, A=image_visualizer vs B=chest_xray_classifier
* first tool-path divergence C vs A: index 1, A=image_visualizer vs C=chest_xray_classifier

### 4118_8353801523564 (detection,localization,characterization,reasoning, std B)

A/B/C = B/E/B

Plan focus: 左右绑定与气胸证据

* B's option differs from the standard on: “large bulla” vs “solitary cystic lesion”; “with evidence of pneumothorax” vs “and a large bulla in the right upper and”; “immediate” vs “significant dyspnoea and need for”
* B injected 908 chars, 2 memories; attribute keywords in the injection: 1/17, in its own tool observations: 7/17
* C injected 1400 chars, skills ['S017', 'S005', 'S002']; attribute keywords in the injection: 0/0, in its own tool observations: 0/0
* first tool-path divergence B vs A: index 2, A=chest_xray_expert vs B=xray_phrase_grounding
* first tool-path divergence C vs A: index 2, A=chest_xray_expert vs C=xray_phrase_grounding

### 5533_8353801540251 (detection,localization,characterization,reasoning, std B)

A/B/C = B/A/B

Plan focus: 结肠袋影存在性（否定属性）

* B injected 771 chars, 2 memories; attribute keywords in the injection: 0/0, in its own tool observations: 0/0
* C injected 1400 chars, skills ['S017', 'S009', 'S016']; attribute keywords in the injection: 0/0, in its own tool observations: 0/0
* first tool-path divergence B vs A: index 0, A=chest_xray_classifier vs B=chest_xray_expert
* first tool-path divergence C vs A: index 1, A=chest_xray_expert vs C=chest_xray_report_generator

## common_correct

### 15189_8353800545058 (classification,characterization,diagnosis,reasoning, std A)

A/B/C = E/A/A

Plan focus: 正侧位对应、气液平面是否真实存在

* B injected 793 chars, 2 memories; attribute keywords in the injection: 0/0, in its own tool observations: 0/0
* C injected 1400 chars, skills ['S011', 'S010', 'S005']; attribute keywords in the injection: 0/0, in its own tool observations: 0/0
* B followed the same tool sequence as A
* first tool-path divergence C vs A: index 4, A=xray_phrase_grounding vs C=None

### 3436_8353801521068 (detection,localization,characterization,reasoning, std B)

A/B/C = D/B/B

Plan focus: 是否有真实的肋骨/肋间定位步骤

* B injected 1083 chars, 3 memories; attribute keywords in the injection: 0/0, in its own tool observations: 0/0
* C injected 1400 chars, skills ['S015', 'S008', 'S002']; attribute keywords in the injection: 0/0, in its own tool observations: 0/0
* first tool-path divergence B vs A: index 0, A=xray_phrase_grounding vs B=chest_xray_classifier
* first tool-path divergence C vs A: index 1, A=chest_xray_classifier vs C=chest_xray_expert

### 5369_8353801533158 (classification,comparison,diagnosis,reasoning, std A)

A/B/C = F/A/A

Plan focus: 疝入内容物是否有影像支持

* B injected 1070 chars, 3 memories; attribute keywords in the injection: 0/0, in its own tool observations: 0/0
* C injected 1400 chars, skills ['S016', 'S002', 'S006']; attribute keywords in the injection: 0/0, in its own tool observations: 0/0
* first tool-path divergence B vs A: index 2, A=chest_xray_expert vs B=xray_phrase_grounding
* first tool-path divergence C vs A: index 2, A=chest_xray_expert vs C=xray_phrase_grounding

### 548_8353802023456 (detection,localization,characterization,reasoning, std D)

A/B/C = C/D/D

Plan focus: 是否检视骨性结构/相关图像

* B injected 898 chars, 2 memories; attribute keywords in the injection: 0/0, in its own tool observations: 0/0
* C injected 0 chars, skills []; attribute keywords in the injection: 0/0, in its own tool observations: 0/0
* first tool-path divergence B vs A: index 0, A=chest_xray_classifier vs B=image_visualizer
* first tool-path divergence C vs A: index 0, A=chest_xray_classifier vs C=image_visualizer

### 7738_8353800850751 (classification,comparison,diagnosis,reasoning, std C)

A/B/C = B/C/C

Plan focus: 实变变化与残余磨玻璃影是否分开记录

* B injected 819 chars, 2 memories; attribute keywords in the injection: 0/0, in its own tool observations: 0/0
* C injected 1400 chars, skills ['S005', 'S014', 'S011']; attribute keywords in the injection: 0/0, in its own tool observations: 0/0
* first tool-path divergence B vs A: index 5, A=xray_phrase_grounding vs B=None
* first tool-path divergence C vs A: index 5, A=xray_phrase_grounding vs C=None

## c_only_correct

### 11804_8353800651404 (localization,comparison,relationship,reasoning, std D)

A/B/C = F/A/D

Plan focus: 两种病征分别绑定左右，禁止互相传播

* B's option differs from the standard on: “more” vs “equally”; “the left side” vs “both sides”
* B injected 807 chars, 2 memories; attribute keywords in the injection: 0/6, in its own tool observations: 0/6
* C injected 1400 chars, skills ['S005', 'S011', 'S004']; attribute keywords in the injection: 0/0, in its own tool observations: 0/0
* first tool-path divergence B vs A: index 1, A=chest_xray_expert vs B=chest_xray_report_generator
* first tool-path divergence C vs A: index 1, A=chest_xray_expert vs C=chest_xray_report_generator

### 18780_8143559008557 (localization,comparison,relationship,reasoning, std A)

A/B/C = C/C/A

Plan focus: 完全/部分与持续/加重分别判断

* B's option differs from the standard on: “partially” vs “completely”; “partial response to treatment” vs “full recovery; however”; “while” vs “the presence of persistent”
* B injected 770 chars, 2 memories; attribute keywords in the injection: 1/17, in its own tool observations: 4/17
* C injected 1400 chars, skills ['S017', 'S014', 'S012']; attribute keywords in the injection: 0/0, in its own tool observations: 0/0
* first tool-path divergence B vs A: index 0, A=chest_xray_classifier vs B=image_visualizer
* first tool-path divergence C vs A: index 5, A=xray_phrase_grounding vs C=None

### 3546_8353801521080 (detection,classification,relationship,reasoning, std A)

A/B/C = B/B/A

Plan focus: 病灶存在性 + 选项否定/因果表达

* B's option differs from the standard on: “air trapping in the left upper lobe resu” vs “rounded opacity with regular borders and”; “contralateral” vs “pulmonary mass causing airway obstructio”; “which does not contribute to” vs “explaining”
* B injected 769 chars, 2 memories; attribute keywords in the injection: 1/17, in its own tool observations: 5/17
* C injected 1400 chars, skills ['S016', 'S017', 'S006']; attribute keywords in the injection: 0/0, in its own tool observations: 0/0
* first tool-path divergence B vs A: index 3, A=llava_med_qa vs B=xray_phrase_grounding
* first tool-path divergence C vs A: index 2, A=chest_xray_expert vs C=xray_phrase_grounding

## b_only_correct

### 11858_8353800664572 (classification,comparison,diagnosis,reasoning, std B)

A/B/C = E/B/E

Plan focus: 肺内/肺外与胸壁关系证据

* B injected 835 chars, 2 memories; attribute keywords in the injection: 0/0, in its own tool observations: 0/0
* C injected 1400 chars, skills ['S005', 'S006', 'S003']; attribute keywords in the injection: 0/0, in its own tool observations: 0/0
* first tool-path divergence B vs A: index 3, A=None vs B=xray_phrase_grounding
* first tool-path divergence C vs A: index 2, A=chest_xray_expert vs C=xray_phrase_grounding

### 13154_8353800587826 (detection,classification,relationship,reasoning, std C)

A/B/C = F/C/F

Plan focus: 钙化判断来源、侧位绑定

* C's option differs from the standard on: “calcified” vs “solitary”; “” vs “with smooth margins”; “which is” vs “and the lateral view (Figure 1b) confirm”
* B injected 711 chars, 2 memories; attribute keywords in the injection: 0/0, in its own tool observations: 0/0
* C injected 1400 chars, skills ['S011', 'S017', 'S010']; attribute keywords in the injection: 6/16, in its own tool observations: 2/16
* first tool-path divergence B vs A: index 1, A=chest_xray_classifier vs B=chest_xray_report_generator
* first tool-path divergence C vs A: index 1, A=chest_xray_classifier vs C=chest_xray_report_generator

### 3359_8353801515597 (detection,classification,relationship,reasoning, std B)

A/B/C = D/B/D

Plan focus: 是否遗漏前纵隔肿块

* C's option differs from the standard on: “is” vs “and the anterior mediastinal mass sugges”; “result of” vs “”; “” vs “causing tracheobronchial”
* B injected 781 chars, 2 memories; attribute keywords in the injection: 0/0, in its own tool observations: 0/0
* C injected 1400 chars, skills ['S010', 'S014', 'S008']; attribute keywords in the injection: 3/10, in its own tool observations: 6/10
* first tool-path divergence B vs A: index 2, A=xray_phrase_grounding vs B=chest_xray_expert
* first tool-path divergence C vs A: index 0, A=chest_xray_classifier vs C=xray_phrase_grounding

## What is still unknown

* Whether a changed answer came from the injected block, a tool observation, a
  summary/compression step, or the final option mapping. The per-question tool
  paths and attribute checks narrow it; they cannot identify the step.
* The plan's three flagged questions (`17621_8143559684844` answer/rationale
  conflict, `16663_8353800455763` compound-option ambiguity, `3686_8353801520174`
  missing context) keep the official scoring but are flagged in the rows.
