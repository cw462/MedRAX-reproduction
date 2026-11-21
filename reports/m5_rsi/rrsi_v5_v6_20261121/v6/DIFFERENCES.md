# v6 百题验证的 8 道翻转题

按相同验证题序列出首答正确性发生变化的题目。模型理由来自保存的预测。

[全部逐题记录](validation/paired_records.json) · [正式汇总](validation/summary.json) · [R0 所选程序轨迹](validation/H0.json) · [R1 所选程序轨迹](validation/R1.json)

## 第 25 题 · slake · m5rsi_slake_10032 · 由错变对

> Does the picture contain liver?

**参考答案**

> {"answer": "Yes", "answer_text": "Yes"}

**R0 所选程序首答（错误）**

> No

R0 所选程序保存的理由

> The image is an axial CT slice at the level of the heart showing cardiac chambers and lungs, without visible liver parenchyma which lies inferior to this section.

**R1 所选程序首答（正确）**

> Yes

R1 所选程序保存的理由

> The axial CT slice shows the cardiac apex and adjacent upper abdominal structures, with a homogeneous soft-tissue density in the right subdiaphragmatic region consistent with the liver dome.

## 第 39 题 · slake · m5rsi_slake_10017 · 由错变对

> Where is/are the abnormality located?

**参考答案**

> {"answer": "Liver", "answer_text": "Liver"}

**R0 所选程序首答（错误）**

> right adrenal gland

R0 所选程序保存的理由

> Visual inspection and model analysis confirm a mass located superior to the right kidney in the right adrenal gland region.

**R1 所选程序首答（正确）**

> liver

R1 所选程序保存的理由

> Visual inspection of the abdominal CT confirms a large hypodense lesion located within the liver parenchyma in the right upper quadrant, despite conflicting automated model outputs.

## 第 40 题 · rad_restruct · m5rsi_rad_2285_0042 · 由错变对

> Are there any diseases in the cardiovascular system?

- A. yes
- B. no

**参考答案**

> {"answer": "A", "answer_text": "yes"}

**R0 所选程序首答（错误）**

> B. no

R0 所选程序保存的理由

> The verifier confirmed that no definite cardiovascular abnormality is visible on this limited portable film, supporting 'no' despite the initial conflicting tool output.

**R1 所选程序首答（正确）**

> A. yes

R1 所选程序保存的理由

> Specialized chest_xray_expert model positively identified cardiovascular disease, and the verify tool confirmed this answer as correct despite conflicting general VQA output.

## 第 48 题 · rad_restruct · m5rsi_rad_1592_0050 · 由对变错

> Are there any diseases in the mediastinum?

- A. yes
- B. no

**参考答案**

> {"answer": "B", "answer_text": "no"}

**R0 所选程序首答（正确）**

> B. no

R0 所选程序保存的理由

> Visual inspection of the mediastinum shows normal width and contours without masses or lymphadenopathy, and the verifier confirmed this assessment despite the initial expert model's positive claim.

**R1 所选程序首答（错误）**

> A. yes

R1 所选程序保存的理由

> Specialized chest_xray_expert tool identified mediastinal disease, and verifier confirmed correctness despite conflicting general VQA output.

## 第 60 题 · rad_restruct · m5rsi_rad_1072_0026 · 由对变错

> Is there anything abnormal in the cardiovascular system?

- A. yes
- B. no

**参考答案**

> {"answer": "A", "answer_text": "yes"}

**R0 所选程序首答（正确）**

> A. yes

R0 所选程序保存的理由

> The image shows an indwelling central venous catheter, which is an abnormality involving the cardiovascular system.

**R1 所选程序首答（错误）**

> B. no

R1 所选程序保存的理由

> Both the specialized chest X-ray expert and LLaVA-Med independently confirm no cardiomegaly or cardiovascular abnormalities.

## 第 67 题 · slake · m5rsi_slake_10104 · 由错变对

> Does the picture contain kidney?

**参考答案**

> {"answer": "No", "answer_text": "No"}

**R0 所选程序首答（错误）**

> Yes

R0 所选程序保存的理由

> The axial abdominal CT image shows the left kidney posterior to the spleen and adjacent to the vertebral column.

**R1 所选程序首答（正确）**

> No

R1 所选程序保存的理由

> This axial CT slice is at the upper abdominal level showing liver and spleen, which are superior to the typical location of the kidneys; no renal parenchyma is visible in this image.

## 第 76 题 · slake · m5rsi_slake_10651 · 由对变错

> How many kinds of abnormalities are there in this image?

**参考答案**

> {"answer": "3", "answer_text": "3"}

**R0 所选程序首答（正确）**

> 3

R0 所选程序保存的理由

> The image shows a large heterogeneous mass with internal hemorrhage/necrosis and surrounding edema, representing three distinct abnormality types.

**R1 所选程序首答（错误）**

> 1

R1 所选程序保存的理由

> The image shows a single dominant heterogeneous mass lesion in the left hemisphere, representing one kind of abnormality despite internal complexity.

## 第 82 题 · rad_restruct · m5rsi_rad_468_0088 · 由错变对

> Are there any signs in the thorax?

- A. yes
- B. no

**参考答案**

> {"answer": "A", "answer_text": "yes"}

**R0 所选程序首答（错误）**

> B. no

R0 所选程序保存的理由

> Two independent VLMs agree there are no abnormal thoracic signs, and direct inspection shows clear lungs with normal cardiac silhouette and diaphragms.

**R1 所选程序首答（正确）**

> A

R1 所选程序保存的理由

> The zoomed ROI clearly shows multiple small, round metallic densities scattered throughout both lung fields, confirming the presence of thoracic signs despite one model reporting normal findings.
