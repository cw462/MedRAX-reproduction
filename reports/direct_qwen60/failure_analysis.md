# D0 差异集合与失败定位

D0 原终态主成绩 17/60；同次输出的独立派生解析为 42/60，相对 V12 首答净变化 +3 题。原解析器拒绝了附带选项全文的 Answer 行，形成技术解析损失；派生结果不覆盖原成绩，不增加模型请求。

以下模型短依据是保存输出，并未被当作已确认患者事实；归因需要核对所列图像与选项，不能只凭回复定论。

| 差异集合 | 题数 |
|---|---:|
| D0_correct_initial_not | 0 |
| initial_correct_lost_A_or_B | 5 |
| D0_not_correct_agent_correct | 24 |
| D0_new_common_error_recovery | 0 |
| all_five_not_correct | 11 |
| D0_derived_correct_initial_not | 6 |
| D0_derived_not_correct_agent_correct | 3 |
| D0_derived_new_common_error_recovery | 0 |
| all_five_not_correct_using_derived | 11 |

缓存阶段的四项转换见 [transitions.json](transitions.json)，包含首答→候选、候选→求解器、候选→采用答案以及求解器→控制器回退。旧 schema 解析损失保持原成绩；V12 3436 的首读缺答及 A/B 输出解析故障详见[已发布失败分析](../v12/error-cases.md)。

## 11858_8353800664572

[原图、完整选项与V12过程](../v12/results/cases/11858_8353800664572.md) · [D0请求](requests/11858_8353800664572.json)

Based on the chest X-ray findings and the clinical history, which of the following is the most likely diagnosis for the mass observed in the right hemithorax of this 57-year-old male patient?

A. Lipoma
B. Well-differentiated liposarcoma
C. Metastatic tumor
D. Pleural effusion
E. Primary lung cancer
F. Pneumonia

D0 保存的原始短答：
```text
Answer: B. Well-differentiated liposarcoma  
Reason: The large, well-circumscribed, homogeneous mass in the right hemithorax with fat density (radiolucency) on chest X-ray—especially in a middle-aged male—is highly suggestive of a lipomatous tumor; well-differentiated liposarcoma is the most common malignant soft-tissue tumor in adults and can present as a large intrathoracic mass with fat attenuation, whereas benign lipoma is less likely to reach this size and location. The absence of air bronchograms and lack of infiltrative pattern argue against pneumonia or primary lung cancer; pleural effusion would show meniscus sign and layering, not a solid mass; metastasis is possible but less likely without known primary or multiple lesions.
```

参考 B；D0原终态 None；派生解析 B；首答 B；A采用 A；B采用 B。

## 17621_8143559684844

[原图、完整选项与V12过程](../v12/results/cases/17621_8143559684844.md) · [D0请求](requests/17621_8143559684844.json)

Based on the findings from the initial chest X-ray and the follow-up X-ray (Figures 1 and 7b), which of the following best describes the progression of the pulmonary findings in the context of Pyoderma gangrenosum with pulmonary involvement?
A) The right middle zone opacity has resolved, and new lesions have appeared in the bilateral lower zones.
B) The right middle zone opacity has increased in size, and new cavitating nodules have appeared in the bilateral upper zones.
C) The right middle zone opacity remains unchanged, and the nodular shadows have decreased in size in the bilateral upper zones.
D) The right middle zone opacity has decreased in size, and the nodular shadows in the bilateral upper zones have increased in size.
E) The right middle zone opacity has increased in size, and the nodular shadows have decreased in size in the bilateral lower zones.
F) The right middle zone opacity has decreased in size, and the nodular shadows have increased in size in the bilateral lower zones.

D0 保存的原始短答：
```text
Answer: D) The right middle zone opacity has decreased in size, and the nodular shadows in the bilateral upper zones have increased in size.

Reason: Figure 1 shows a prominent right middle zone opacity (arrow) and subtle nodular opacities in the upper zones; Figure 7b shows that the right middle zone opacity is less conspicuous (smaller), while new or enlarged nodular shadows are now evident in the bilateral upper lung zones, consistent with progression of pulmonary involvement in pyoderma gangrenosum.
```

参考 D；D0原终态 None；派生解析 D；首答 D；A采用 D；B采用 B。

## 16486_8353800471802

[原图、完整选项与V12过程](../v12/results/cases/16486_8353800471802.md) · [D0请求](requests/16486_8353800471802.json)

Based on the chest X-ray findings in Figure 1 and Figure 8, what is the most likely diagnosis, and what does the progression of findings suggest about the clinical course of the condition in this patient?
A) Secondary pneumomediastinum due to oesophageal rupture, with worsening condition
B) Spontaneous pneumothorax with stable condition
C) Primary spontaneous pneumomediastinum with improvement
D) Pneumopericardium with no change in condition
E) Pneumoperitoneum with deterioration
F) Primary spontaneous pneumomediastinum with worsening condition

D0 保存的原始短答：
```text
Answer: C) Primary spontaneous pneumomediastinum with improvement  
Reason: Both Figure 1 and Figure 8 show subtle linear lucencies along the left heart border and mediastinum, consistent with pneumomediastinum; however, the second image (Figure 8) shows less prominent air, suggesting resolution. There is no evidence of pneumothorax, pneumopericardium, or pneumoperitoneum, and no signs of oesophageal rupture (e.g., pleural effusion, subcutaneous emphysema, or mediastinal shift). The absence of trauma or underlying lung disease favors primary spontaneous pneumomediastinum, and the reduced air on follow-up indicates improvement.
```

参考 C；D0原终态 None；派生解析 C；首答 B；A采用 C；B采用 F。

## 17132_8143559675802

[原图、完整选项与V12过程](../v12/results/cases/17132_8143559675802.md) · [D0请求](requests/17132_8143559675802.json)

Based on the chest radiograph findings and the clinical presentation, which of the following is the most likely diagnosis, considering the obscuration of the left heart border, significant cardio-mediastinal shift to the right, and mediastinal widening observed in the chest X-ray (Figures 1 and 2)?

A) Left lower lobe pneumonia
B) T-cell acute lymphoblastic leukemia/lymphoma
C) Pulmonary tuberculosis
D) Primary lung carcinoma
E) Left-sided pleural effusion
F) Hodgkin’s lymphoma

D0 保存的原始短答：
```text
Answer: B) T-cell acute lymphoblastic leukemia/lymphoma  
Reason: The chest X-ray shows a large mediastinal mass causing obscuration of the left heart border (loss of left cardiac silhouette), significant rightward mediastinal shift, and mediastinal widening—classic radiographic features of a bulky anterior mediastinal mass. In pediatric patients, T-cell acute lymphoblastic leukemia/lymphoma (especially lymphoblastic lymphoma) commonly presents with a rapidly enlarging thymic mass in the anterior mediastinum, leading to these findings. The age-appropriate presentation (implied by the pediatric chest X-ray appearance) and aggressive mass effect favor this over other options like Hodgkin’s lymphoma (less common in very young children and often more nodal), pneumonia, or pleural effusion (which would not cause such marked mediastinal shift and widening without fluid layering).
```

参考 B；D0原终态 None；派生解析 B；首答 E；A采用 E；B采用 E。

## 13238_8353800603808

[原图、完整选项与V12过程](../v12/results/cases/13238_8353800603808.md) · [D0请求](requests/13238_8353800603808.json)

Based on the chest X-ray findings, which of the following statements best describes the location and characteristics of the thoracic mass in relation to the patient's thoracic anatomy? 

A) The mass is located centrally in the mediastinum, causing displacement of the trachea to the left and widening of the mediastinal shadow.
B) The mass is located dorsolaterally on the right side, widening the third intercostal space, and is inseparable from the lateral thoracic wall.
C) The mass is located in the anterior chest wall, causing elevation of the right diaphragm and compression of the right lower lobe.
D) The mass is located in the apical region of the left lung, causing left-sided pleural effusion and blunting of the costophrenic angle.
E) The mass is entirely subcutaneous without involvement of the thoracic cavity, lying superficial to the ribs.
F) The mass is causing displacement of the heart and widening of the cardiac silhouette.

D0 保存的原始短答：
```text
Answer: E) The mass is entirely subcutaneous without involvement of the thoracic cavity, lying superficial to the ribs.  
Reason: The chest X-ray (Figure 1) shows no evidence of intrathoracic mass, mediastinal shift, pleural effusion, or lung compression; the lung fields, heart, and diaphragms appear normal. The clinical context (not shown but implied by the question’s phrasing and standard interpretation of such images in test banks) suggests a palpable external mass—commonly a lipoma or cyst—that does not distort thoracic structures, consistent with a subcutaneous lesion.
```

参考 B；D0原终态 None；派生解析 E；首答 B；A采用 B；B采用 B。

## 13935_8353800618951

[原图、完整选项与V12过程](../v12/results/cases/13935_8353800618951.md) · [D0请求](requests/13935_8353800618951.json)

A 26-year-old male patient presents with sudden thoracic and supraclavicular pain and dyspnoea. The chest X-ray was initially misinterpreted as normal. Upon reevaluation, multiple subtle signs were observed. Which of the following findings is most indicative of a spontaneous pneumomediastinum on the chest X-ray, and what does this imply about the underlying pathophysiological mechanism?

A) Presence of a continuous diaphragmatic sign; suggests pneumopericardium due to air posterior to the pericardium.
B) Observation of subcutaneous emphysema in the supraclavicular region; indicates air leakage from the mediastinum into subcutaneous tissue.
C) Detection of a double bronchial wall sign; implies air dissecting along the bronchial walls due to alveolar rupture.
D) Identification of Naclerio's V sign; indicates an esophageal rupture with mediastinal air lateral to the aorta.
E) Visualization of the thymic sail sign; suggests pneumomediastinum in a pediatric patient due to elevated thymus.
F) Recognition of the ring around the artery sign; signifies air enclosing the pulmonary artery due to tracheobronchial injury.

D0 保存的原始短答：
```text
Answer: B) Observation of subcutaneous emphysema in the supraclavicular region; indicates air leakage from the mediastinum into subcutaneous tissue.

Reason: The arrows in Figure 3a point to lucency in the supraclavicular regions, consistent with subcutaneous emphysema—a classic sign of spontaneous pneumomediastinum. This occurs when air from ruptured alveoli dissects along bronchovascular sheaths into the mediastinum and then tracks upward into the neck, supporting a pathophysiological mechanism of alveolar rupture (e.g., due to Valsalva maneuver), not esophageal or tracheal injury.
```

参考 C；D0原终态 None；派生解析 B；首答 C；A采用 C；B采用 C。

## 11624_8353800763402

[原图、完整选项与V12过程](../v12/results/cases/11624_8353800763402.md) · [D0请求](requests/11624_8353800763402.json)

Based on the chest X-ray images provided, which of the following best describes the changes observed in the left lung from Figure 1 to Figure 3, and the underlying reasoning for these observations?

A) Figure 1 shows a large left-sided pneumothorax and a cystic structure, and Figure 3 shows complete resolution of the pneumothorax with no cystic changes, indicating successful drainage and healing without residual cyst.

B) Figure 1 shows a large left-sided pneumothorax and a cystic structure, and Figure 3 shows a re-expansion of the left lung with disappearance of the cystic structure, indicating that the structure was likely a bullae that resolved with the pneumothorax.

C) Figure 1 shows a large left-sided pneumothorax and a cystic structure, and Figure 3 shows a recurrent pneumothorax with a persistent cystic structure, suggesting a bronchogenic cyst that contributes to recurrent pneumothorax due to its rupture.

D) Figure 1 shows a large left-sided pneumothorax and a cystic structure, and Figure 3 shows a stable lung with no pneumothorax, but a new opacity in the left lower zone, indicating an infection or abscess formation in the previously cystic area.

E) Figure 1 shows a large left-sided pneumothorax and a cystic structure, and Figure 3 shows a shrinking pneumothorax and disappearance of the cystic structure, suggesting that the cystic structure was a fluid collection that resolved spontaneously.

D0 保存的原始短答：
```text
Answer: B  
Reason: Figure 1 shows a large left-sided pneumothorax with a well-defined cystic-appearing lucency (likely a bulla) in the left upper/mid zone. In Figure 3, the left lung is re-expanded, the pneumothorax has resolved, and the cystic lucency is no longer visible—consistent with a bulla that collapsed and was no longer apparent after re-expansion, rather than a persistent or new pathology. This pattern supports resolution of a bleb/bulla-associated pneumothorax.
```

参考 C；D0原终态 B；派生解析 B；首答 B；A采用 B；B采用 B。

## 11801_8353800651620

[原图、完整选项与V12过程](../v12/results/cases/11801_8353800651620.md) · [D0请求](requests/11801_8353800651620.json)

Based on the chest radiograph findings, what is the most likely diagnosis for the patient's condition given the clinical history and imaging characteristics? Consider the patterns and changes in airspace consolidations observed in the X-ray images.

A) Chronic eosinophilic pneumonia
B) Lipoid pneumonia
C) Primary pulmonary lymphoma
D) Sarcoidosis
E) Lepidic predominant adenocarcinoma
F) Bronchiectasis

D0 保存的原始短答：
```text
Answer: A) Chronic eosinophilic pneumonia  
Reason: The chest radiograph shows bilateral, peripheral, and migratory airspace consolidations—classic for chronic eosinophilic pneumonia (CEP), which often presents with upper and mid-lung zone predominant opacities that can shift over time. The pattern is distinct from the more central or nodular distributions seen in sarcoidosis, lymphoma, or adenocarcinoma, and lacks the tram-track or cystic changes of bronchiectasis or the fat-density features of lipoid pneumonia.
```

参考 B；D0原终态 None；派生解析 A；首答 A；A采用 A；B采用 A。

## 下一轮

优先把下一版 Agent 的首读改为本轮简洁独立答案与短依据；后续仅在存在明确待判属性时规划一次针对性观察，并在独立样本验证。

正确答案并集只可作为依赖标签的候选覆盖潜力，不能报告为已实现的集成准确率。


## 十题定向对照：过程事实、问题类型与待验证原因

下表覆盖正文八题，另加入D0与Agent互补的3436及D0同样误匹配的3359。正确性来自已评分参考；描述模型说了什么，不将其解释直接当作影像真值。

| 题号 | 可核查的过程事实 | 问题类型与解释边界 | 下一轮具体观察动作（建议，未执行） |
|---|---|---|---|
| 11858 | D0明确选B脂肪肉瘤；V12首答/B最终同为B，A最终改成A脂肪瘤。D0原解析却记缺答。 | 诊断选项匹配及技术解析。D0正确不代表其凭胸片确认脂肪密度的理由已获验证。 | 若题目已提供CT，定位同一肿块并核对脂肪、非脂肪成分及边界；仅凭未见图像不能补造密度。 |
| 17621 | D0的Answer行明确区分右中肺阴影缩小、双上肺结节增大，选D；B新增观察和终答选B，并宣称增大/空洞。 | 同一对象的时点、方向和部位绑定。D0与A正确、B错误提示重读也会反向判断，不证明K卡导致。 | 将Figure1/7b配对，分别记录右中肺和双上肺的变化方向；空洞属性另列未知/可见，避免随进展叙述附会。 |
| 16486 | D0选C“原发自发性纵隔积气、改善”；首答选B气胸，A最终C，B最终F“恶化”。 | 气体所在腔隙与变化方向是两个属性，诊断名称相同仍可因方向错而失分。 | 同区配对标出纵隔/胸膜边界，再单独比较积气是否变化，不用诊断名代替病程判定。 |
| 17132 | D0选B，首答和A/B最终均E；历史P0已选对B，因此不是旧组共同错答首次恢复。D0理由明确推断“pediatric”外观。 | 肿块病因/类型判断，且含未经题干提供的年龄推断；得分正确不能验证该推断或证明视觉更好。 | 保留年龄未知，先对照已给影像的肿块位置和纵隔/心缘关系，再判断现有题干能否区分病因。 |
| 13238 | D0称胸内结构正常，并明确诉诸“not shown but implied…test banks”的临床背景，选皮下E；首答和A/B都选对B。 | 局灶定位漏看与虚构背景。这里可直接确认使用了未提供信息，不能将其“正常”解释当作阴性事实。 | 定位右侧背外侧肿块，核对第三肋间隙与胸壁关系；把原图与局部成对呈现。 |
| 13935 | D0根据锁骨上箭头及机制解释选B皮下气肿；其他路径选对C双支气管壁征。 | 题目询问特定征象及其机制，不能仅回答一个相关但不同的征象。 | 分别看中央支气管壁和锁骨上区域，将每项征象/机制组合逐项对应完整选项。 |
| 3359 | D0选D，理由称D把肿块与肺部变化相连；但完整B也明确写出气管支气管压迫。首答B正确，A/B最终都改D。 | 完整因果选项的语义匹配偏差也出现在直接作答中，不能将其全部归咎于新增工具或检索。 | 先对照B/D原文分别覆盖的征象、因果和确定性；若两项只差病因确定程度，明确图像实际支持到哪一级，不靠“更具体”自动选胜。 |
| 3436 | D0明确选D“第7肋间隙”，参考B为第8；形态和1.5cm措辞相同。V12首答JSON失败，A/B候选和最终均B，K/E均空。 | 肋间隙计数与技术缺答恢复分开；A/B在此有互补价值，不能归功K/E。D0凭“standard chest X-ray scale”估厘米的理由亦未被校准证明。 | 原图中从可识别的肋骨依次计数，明确计肋骨还是肋间隙；尺寸在缺乏标尺时保持未定，不凭肋间距换算厘米。 |
| 11624 | D0与首答/A/B都选B，叙述Figure3肺复张、囊性结构消失；参考C包含复发气胸和持续囊性结构。 | 时点与囊性结构变化的共同错误。参考选项与模型描述冲突，但本报告不以参考文字代替重新读图确认。 | 同时配对Figure1/3，分别核对胸膜线和囊性结构是否仍可见，禁止先用“治疗后应改善”的故事补全。 |
| 11801 | 所有路径均选A慢性嗜酸性肺炎，参考B脂质性肺炎。D0把病变称为peripheral、migratory。 | 形态模式到病因的共同泛化；短依据没有给出“migratory”的具体图号/时序对应。 | 按原图号记录分布和变化，核对题干是否提供决定病因的条件；未知暴露史或时序不能自动填入。 |

[3436完整选项与图像](../v12/results/cases/3436_8353801521068.md) · [D0实际请求](requests/3436_8353801521068.json) · [D0原回复](responses/3436_8353801521068_1.json)。该题D0派生D，参考B；原终态仍为invalid_answer。

D0相对首答的6个新增正确题依次为16486、17132、3686、4118、8300、9815；3个丢失首答正确的题为13238、13935、3359。D0相对A/B最终共同采用路径的互补题为13238、13935、3436，后者是V12首答缺答恢复。各集合的完整ID和不同口径见transitions.json。D0并没有在P0、V12首答、A、B全部失败的集合中新增正确题。

上述结果支持优先检验“简洁首读是否更稳”的一个后续改动；没有证实某种医学工具无效，也没有证实模型能力已达上限。下一轮先落实该改动、保证明确Answer行的确定性解析，再在独立同条件样本评价。本文所列观察建议不构成已经执行的新实验。

[3359完整题干与原图](../v12/results/cases/3359_8353801515597.md) · [D0原回复](responses/3359_8353801515597_1.json)。D0的短依据原文为“Option D directly links the mass to the pulmonary findings”；这不证明B没有表达因果。
