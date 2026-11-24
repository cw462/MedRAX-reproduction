# OpenI 胸片线管检测与解剖分割

线管检测覆盖 OpenI / Rad-ReStruct 侧别问题样本中的 147 张正位胸片。各阶段使用五折模型。按照运行脚本的 0.5 阈值，有 36 张胸片至少检出一种线管。每张图可以有多类检出。

| 线管 | 检出图数 |
| --- | ---: |
| 气管插管（ETT） | 3 |
| 鼻胃管（NGT） | 8 |
| 中心静脉导管（CVC） | 27 |
| Swan-Ganz 导管 | 0 |

[逐图预测](predictions.jsonl)保留线管存在分数、分类、解剖标志点、运行时间和各阶段折号。全流程在 36 张图上运行。[结构化汇总](summary.json)记录检测数及 M2F 解剖分割的文件覆盖。M2F 正位模型生成 147 个输出，侧位模型生成 126 个输出。两组按运行模型计数。

图像文件名沿用 OpenI，病例来源可在同一项目的 MAIRA-2 任务表中对照。 [OpenI 图像库](https://openi.nlm.nih.gov/) · [任务表](../../results/maira2_20261123/lat_tasks_maira.json)

## 复现入口

- [五折线管检测](source/lt_frontal.py)
- [正位分割](source/seg_frontal.py) · [侧位分割](source/seg_lateral.py)
- [解剖输出特征](source/m2f_features.py) · [几何计算](source/cvc_geom.py)

## 局限

本批数字描述模型输出分布。与人工标注的逐图对照和性能评估待完成。
