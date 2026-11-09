# R49：同图真值反馈＋在线窗口Skill，全量三清单结果

CheXbench：M43 466/618→R49 465/618（75.40%→75.24%），49纠正／50误改／净-1；聚簇95%微平均差区间[-3.3762, +3.0450]pp（含0）。

另列SLAKE：M43 108/114→R49 113/114（94.74%→99.12%），5纠正／0误改／净+5；聚簇95%微平均差区间[+0.9174, +8.4750]pp（全正）。

VQA-RAD：M42 100/116→R49 97/116（86.21%→83.62%），4纠正／7误改／净-3；聚簇95%微平均差区间[-8.2645, +2.7273]pp（含0）。

以上保留实际正负结果，无增分也不改变运行记录。三份清单分别报告：618、114、116，共848个新生成题目级记录，不合成848个独立病例的总体准确率。最终原runner的三组实际原始退出均为0，最后一次adoption_1接续controller也退出0；首次依赖故障、后续CUDA、两次元学习schema、Embedding、MAIRA及采用归因校验中断的原始退出1与日志全部保留，不能说所有尝试都退出0。冻结运行源文件未改，但下文列明操作wrapper、提示、故障闭合例外、MAIRA生成策略及采用归因接口修订；完整生成后统一答案口径评分、导出和公开语义重算，没有靠评分解析放宽或历史答案填充获得结果。

## 已完成组的离线评分与来源

用户要求每组完整结束后先报告该组结果，后续数据集照冻结方案继续。各组summary／per_question已保存后在此原样复用，没有第二次私有指标计算或据此改后续推理。CheX首次进入原生评分函数在输入路径门槛失败：公开别名`assets/...`与真实运行清单的`images/...`不一致，发生于ALL-arm适配、参考／feedback／complete正文读取之前，未产生分数。保存原始started／退出1故障元数据后，只复制一次实际canonical源inputs并显式接续同一已知前置失败；原生gate、解析和指标不改，预测不改，模型调用0。故函数进入次数与完整指标计算次数分别报告，不能把首个失败称另一套已完成成绩。

| 数据集 | 原生评分函数进入次数 | 完整指标计算次数 | 适配／标签前失败 | 已保存score receipt |
|---|---|---|---|---|
| CheXbench | 2 | 1 | 1 | [原始凭证](deployment_source/reporting_provenance/score_receipts/chexbench.json) |
| 另列SLAKE | 1 | 1 | 0 | [原始凭证](deployment_source/reporting_provenance/score_receipts/slake.json) |
| VQA-RAD | 1 | 1 | 0 | [原始凭证](deployment_source/reporting_provenance/score_receipts/vqarad.json) |

来源路径、原始失败／显式接续、逐组pull／score与最终控制拉取凭证见[离线评分来源说明](OFFLINE_SCORING_PROVENANCE.md)。CheX实际成功评分的input目录与references文件为两个独立来源，复现页从真实receipt记录读取，未由目录命名猜测。公开语义重算另列，不更改历史私有成绩。

## 信息条件与方法

唯一新方法`M43-IM-GT-S49`，所有题新生成，各数据集空Skill／空同图记忆冷启动。主与元调用qwen3.7-plus，.2／.95／2048／thinking=false；主／工具调用次数无固定上限，以合法终答、三次重复无进展、技术异常终止。窗口30、buffer20、三分支top6、每两窗口治理。过去同图原模型答案／理由／健康工具证据保持原样，预测及保存事件完成后才揭示本题标注，供后续同图题和窗口学习。没有当前／未来真值或其他数据集的Skill／病例传入。

R49为R47式在线记忆与SkeMex启发的项目适配，非官方SkeMex、Evo-MedAgent或历史M43执行器的完整复现。解除了旧预算并改变循环，没有同期无Skill对照。历史记录、信息优势、调用资源、采样／时段共同变化，差值不能单独归因Skill；同模型Analysis／Review和采用信用不证明临床正确或因果归因。[方案](PLAN.md) · [实际协议](PROTOCOL.json) · [来源与限制](METHOD_AND_LIMITS.md)。

CheX保留488图组／130后续题，五跨子集同图组十题；另列SLAKE30图组、VQA58图组。SLAKE114与CheX-SLAKE123同源共享17图、64相同图像＋措辞题，114中73题位于共享图像；没有论文精确114题号核验。VQA同图复述按图聚簇。三清单已有反复开发暴露，不称未见测试、闭卷SOTA、同预算因果收益或稳定医学泛化。原无在线反馈最好完整记录466／108／100仍按原条件单列，R47在线GT468/618也保持独立记录。

## CheXbench：完整618题

CheXbench：M43 466/618→R49 465/618（75.40%→75.24%），49纠正／50误改／净-1；聚簇95%微平均差区间[-3.3762, +3.0450]pp（含0）。

| 比较臂 | 完整分母 | 正确数 | 微平均／EM | 子集宏平均 | word recall | 纠正／误改／净增 | 微平均差95%簇区间 |
|---|---|---|---|---|---|---|---|
| M43-IM-GT-S49 | 618 | 465 | 75.24% | 77.98% | 不适用／未知 | — | — |
| M43 | 618 | 466 | 75.40% | 77.08% | 不适用／未知 | 49／50／-1 | [-3.3762, +3.0450]pp（含0） |
| R47_online_GT | 618 | 468 | 75.73% | 77.25% | 不适用／未知 | 45／48／-3 | [-3.5542, +2.5479]pp（含0） |

历史比较来自固定完整整臂；本轮所有题均新生成，原图首次题也可能受此前跨病例Skill影响。R47只作CheX的在线同图真值反馈次要参照；不以较弱参照替代原无反馈最好整臂。

| 臂 | 完整子集 | 分母 | 正确数 | 准确率 |
|---|---|---|---|---|
| M43-IM-GT-S49 | OpenI | 380 | 270 | 71.05% |
| M43-IM-GT-S49 | Rad-Restruct | 115 | 77 | 66.96% |
| M43-IM-GT-S49 | SLAKE | 123 | 118 | 95.93% |
| M43 | OpenI | 380 | 276 | 72.63% |
| M43 | Rad-Restruct | 115 | 73 | 63.48% |
| M43 | SLAKE | 123 | 117 | 95.12% |
| R47_online_GT | OpenI | 380 | 278 | 73.16% |
| R47_online_GT | Rad-Restruct | 115 | 73 | 63.48% |
| R47_online_GT | SLAKE | 123 | 117 | 95.12% |

| 历史比较臂 | 微平均差95%簇区间 | 子集宏平均差95%簇区间 | 逐子集区间（pp） |
|---|---|---|---|
| M43 | [-3.3762, +3.0450]pp（含0） | [-2.1394, +3.9999]pp（含0） | {"OpenI": [-6.153940886699508, 3.092983297370732], "Rad-Restruct": [-2.5, 9.401709401709402], "SLAKE": [-4.464285714285714, 6.6115702479338845]} |
| R47_online_GT | [-3.5542, +2.5479]pp（含0） | [-2.1392, +3.5366]pp（含0） | {"OpenI": [-6.561679790026247, 2.3378145292207773], "Rad-Restruct": [-2.5, 9.401709401709402], "SLAKE": [-3.5398230088495577, 5.084745762711865]} |

区间直接引用保存评分器的10000次配对图像／可用patient-study关联簇bootstrap；不重评分。顺序依赖、在线反馈和已曝光数据使这些区间只具描述性，不证明未见患者泛化或同期因果效应。

| 保存结果的描述分组 | 完整分母 | 历史正确 | R49正确 | 纠正 | 误改 | 净增 |
|---|---|---|---|---|---|---|
| 首次图像题 | 488 | 363 | 357 | 39 | 45 | -6 |
| 此前同图记忆命中 | 130 | 103 | 108 | 10 | 5 | +5 |
| Skill命中 | 505 | 378 | 375 | 44 | 47 | -3 |
| Skill未命中 | 113 | 88 | 90 | 5 | 3 | +2 |

Skill命中505/618，此前同图记忆命中130/618；最多注入4条Skill、5条同图前缀。覆盖分组和窗口分数是事后描述，不是按正确性选用的方法。窗口内使用起始快照，末窗口进化不能改变已完成预测。

| 窗口（1起） | 题数 | 正确 | Skill命中题 | 窗口后活跃／成熟Skill | 完整证据 |
|---|---|---|---|---|---|
| 1 | 30 | 28 | 0 | 0 | [快照／轨迹／蒸馏／治理](evidence/chexbench/windows/0000) |
| 2 | 30 | 29 | 0 | 0 | [快照／轨迹／蒸馏／治理](evidence/chexbench/windows/0001) |
| 3 | 30 | 13 | 0 | 1 | [快照／轨迹／蒸馏／治理](evidence/chexbench/windows/0002) |
| 4 | 30 | 12 | 29 | 1 | [快照／轨迹／蒸馏／治理](evidence/chexbench/windows/0003) |
| 5 | 30 | 29 | 23 | 1 | [快照／轨迹／蒸馏／治理](evidence/chexbench/windows/0004) |
| 6 | 30 | 27 | 17 | 3 | [快照／轨迹／蒸馏／治理](evidence/chexbench/windows/0005) |
| 7 | 30 | 29 | 29 | 3 | [快照／轨迹／蒸馏／治理](evidence/chexbench/windows/0006) |
| 8 | 30 | 30 | 29 | 3 | [快照／轨迹／蒸馏／治理](evidence/chexbench/windows/0007) |
| 9 | 30 | 21 | 30 | 3 | [快照／轨迹／蒸馏／治理](evidence/chexbench/windows/0008) |
| 10 | 30 | 23 | 30 | 3 | [快照／轨迹／蒸馏／治理](evidence/chexbench/windows/0009) |
| 11 | 30 | 26 | 30 | 4 | [快照／轨迹／蒸馏／治理](evidence/chexbench/windows/0010) |
| 12 | 30 | 23 | 30 | 4 | [快照／轨迹／蒸馏／治理](evidence/chexbench/windows/0011) |
| 13 | 30 | 28 | 30 | 4 | [快照／轨迹／蒸馏／治理](evidence/chexbench/windows/0012) |
| 14 | 30 | 19 | 30 | 4 | [快照／轨迹／蒸馏／治理](evidence/chexbench/windows/0013) |
| 15 | 30 | 23 | 30 | 5 | [快照／轨迹／蒸馏／治理](evidence/chexbench/windows/0014) |
| 16 | 30 | 18 | 30 | 5 | [快照／轨迹／蒸馏／治理](evidence/chexbench/windows/0015) |
| 17 | 30 | 18 | 30 | 6 | [快照／轨迹／蒸馏／治理](evidence/chexbench/windows/0016) |
| 18 | 30 | 18 | 30 | 5 | [快照／轨迹／蒸馏／治理](evidence/chexbench/windows/0017) |
| 19 | 30 | 22 | 30 | 5 | [快照／轨迹／蒸馏／治理](evidence/chexbench/windows/0018) |
| 20 | 30 | 24 | 30 | 5 | [快照／轨迹／蒸馏／治理](evidence/chexbench/windows/0019) |
| 21 | 18 | 5 | 18 | 5 | [快照／轨迹／蒸馏／治理](evidence/chexbench/windows/0020) |

| Skill | 名称 | 分支 | 最终状态 | 效用 | 采用次数 | 历史版本数 | 来源题号 |
|---|---|---|---|---|---|---|---|
| s_cffc935ceb863823 | Verify Foreign Object Detection with Phrase Grounding | task_level | active | 0.6477264494927643 | 136 | 0 | chexbench_rad_restruct_0201 |
| s_e1a0642fabefb0c7 | Triangulate Location-Specific Pathology with Phrase Grounding | task_level | active | 0.588962598626994 | 11 | 0 | chexbench_slake_0046 |
| s_5a7288e7c5c11688 | Escalate Empty Grounding to Visual QA Expert | task_level | active | 0.4465890909090909 | 1 | 0 | chexbench_slake_0053 |
| s_5367798970bef205 | Resolve Ambiguous Pathology via Report-Guided Grounding | task_level | active | 0.387571228753144 | 99 | 0 | chexbench_openi_0068 |
| s_c05942bb226f0f82 | Resolve Forced-Choice Asymmetry via Phrase Grounding | task_level | merged | 0.48238541965308807 | 61 | 0 | chexbench_openi_0186 |
| s_7ac0c0d4ecc1dda3 | Resolve Forced-Choice Asymmetry via Phrase Grounding | task_level | active | 0.48643031036708095 | 77 | 1 | chexbench_openi_0186, chexbench_openi_0243 |

| 臂 | 缺显式答案 | 答案域冲突 | 完整原生JSON | 旧M特定契约 | 提取机制 |
|---|---|---|---|---|---|
| M43-IM-GT-S49 | 0 | 1 | 618 | 618 | {"whole_json_answer": 618} |
| M43 | 0 | 0 | 618 | 618 | {"whole_json_answer": 618} |
| R47_online_GT | 0 | 1 | 618 | 618 | {"whole_json_answer": 618} |

JSON为单独接口诊断，主指标使用共同显式答案与作者答案口径。无答案、冲突和重复无进展记录保留，不从reason或参考猜答。实际终态计数：{"completed": 617, "repeated_invalid_output": 1}。

全部正负例见[CASE_INDEX](CASE_INDEX.md)；[实际资源](RESOURCE_SUMMARY.json)、[保存评分summary](results/chexbench/summary.json)、[公开语义重算](public_reproduction/chexbench/summary.json)、[全部原始证据](evidence/chexbench/)均保留。工具名称与次数：{"chest_xray_expert": 583, "xray_phrase_grounding": 406, "chest_xray_segmentation": 24, "chest_xray_report_generator": 108, "chest_xray_classifier": 93, "llava_med_qa": 37, "image_visualizer": 2}。有记录不等于医学解释正确；同模型Skill Review和采用归因不是独立临床核实。


## 另列SLAKE：完整114题

另列SLAKE：M43 108/114→R49 113/114（94.74%→99.12%），5纠正／0误改／净+5；聚簇95%微平均差区间[+0.9174, +8.4750]pp（全正）。

| 比较臂 | 完整分母 | 正确数 | 微平均／EM | 子集宏平均 | word recall | 纠正／误改／净增 | 微平均差95%簇区间 |
|---|---|---|---|---|---|---|---|
| M43-IM-GT-S49 | 114 | 113 | 99.12% | 99.12% | 99.12% | — | — |
| M43 | 114 | 108 | 94.74% | 94.74% | 94.74% | 5／0／+5 | [+0.9174, +8.4750]pp（全正） |

历史比较来自固定完整整臂；本轮所有题均新生成，原图首次题也可能受此前跨病例Skill影响。R47只作CheX的在线同图真值反馈次要参照；不以较弱参照替代原无反馈最好整臂。

| 臂 | 完整子集 | 分母 | 正确数 | 准确率 |
|---|---|---|---|---|
| M43-IM-GT-S49 | all | 114 | 113 | 99.12% |
| M43 | all | 114 | 108 | 94.74% |

| 历史比较臂 | 微平均差95%簇区间 | 子集宏平均差95%簇区间 | 逐子集区间（pp） |
|---|---|---|---|
| M43 | [+0.9174, +8.4750]pp（全正） | [+0.9174, +8.4750]pp（全正） | {"all": [0.9174311926605505, 8.474976015350169]} |

区间直接引用保存评分器的10000次配对图像／可用patient-study关联簇bootstrap；不重评分。顺序依赖、在线反馈和已曝光数据使这些区间只具描述性，不证明未见患者泛化或同期因果效应。

| 保存结果的描述分组 | 完整分母 | 历史正确 | R49正确 | 纠正 | 误改 | 净增 |
|---|---|---|---|---|---|---|
| 首次图像题 | 30 | 29 | 30 | 1 | 0 | +1 |
| 此前同图记忆命中 | 84 | 79 | 83 | 4 | 0 | +4 |
| Skill命中 | 0 | 0 | 0 | 0 | 0 | +0 |
| Skill未命中 | 114 | 108 | 113 | 5 | 0 | +5 |

Skill命中0/114，此前同图记忆命中84/114；最多注入0条Skill、6条同图前缀。覆盖分组和窗口分数是事后描述，不是按正确性选用的方法。窗口内使用起始快照，末窗口进化不能改变已完成预测。

| 窗口（1起） | 题数 | 正确 | Skill命中题 | 窗口后活跃／成熟Skill | 完整证据 |
|---|---|---|---|---|---|
| 1 | 30 | 29 | 0 | 0 | [快照／轨迹／蒸馏／治理](evidence/slake/windows/0000) |
| 2 | 30 | 30 | 0 | 0 | [快照／轨迹／蒸馏／治理](evidence/slake/windows/0001) |
| 3 | 30 | 30 | 0 | 0 | [快照／轨迹／蒸馏／治理](evidence/slake/windows/0002) |
| 4 | 24 | 24 | 0 | 0 | [快照／轨迹／蒸馏／治理](evidence/slake/windows/0003) |

最终Skill库为空，原样报告；没有人工补卡。

| 臂 | 缺显式答案 | 答案域冲突 | 完整原生JSON | 旧M特定契约 | 提取机制 |
|---|---|---|---|---|---|
| M43-IM-GT-S49 | 0 | 0 | 114 | 114 | {"whole_json_answer": 114} |
| M43 | 0 | 0 | 114 | 114 | {"whole_json_answer": 114} |

JSON为单独接口诊断，主指标使用共同显式答案与作者答案口径。无答案、冲突和重复无进展记录保留，不从reason或参考猜答。实际终态计数：{"completed": 114}。

全部正负例见[CASE_INDEX](CASE_INDEX.md)；[实际资源](RESOURCE_SUMMARY.json)、[保存评分summary](results/slake/summary.json)、[公开语义重算](public_reproduction/slake/summary.json)、[全部原始证据](evidence/slake/)均保留。工具名称与次数：{"chest_xray_expert": 52, "chest_xray_report_generator": 4, "chest_xray_classifier": 20, "xray_phrase_grounding": 3, "chest_xray_segmentation": 4, "llava_med_qa": 3}。有记录不等于医学解释正确；同模型Skill Review和采用归因不是独立临床核实。


## VQA-RAD：完整116题

VQA-RAD：M42 100/116→R49 97/116（86.21%→83.62%），4纠正／7误改／净-3；聚簇95%微平均差区间[-8.2645, +2.7273]pp（含0）。

| 比较臂 | 完整分母 | 正确数 | 微平均／EM | 子集宏平均 | word recall | 纠正／误改／净增 | 微平均差95%簇区间 |
|---|---|---|---|---|---|---|---|
| M43-IM-GT-S49 | 116 | 97 | 83.62% | 83.62% | 83.62% | — | — |
| M42 | 116 | 100 | 86.21% | 86.21% | 87.93% | 4／7／-3 | [-8.2645, +2.7273]pp（含0） |

历史比较来自固定完整整臂；本轮所有题均新生成，原图首次题也可能受此前跨病例Skill影响。R47只作CheX的在线同图真值反馈次要参照；不以较弱参照替代原无反馈最好整臂。

| 臂 | 完整子集 | 分母 | 正确数 | 准确率 |
|---|---|---|---|---|
| M43-IM-GT-S49 | all | 116 | 97 | 83.62% |
| M42 | all | 116 | 100 | 86.21% |

| 历史比较臂 | 微平均差95%簇区间 | 子集宏平均差95%簇区间 | 逐子集区间（pp） |
|---|---|---|---|
| M42 | [-8.2645, +2.7273]pp（含0） | [-8.2645, +2.7273]pp（含0） | {"all": [-8.264462809917356, 2.727272727272727]} |

区间直接引用保存评分器的10000次配对图像／可用patient-study关联簇bootstrap；不重评分。顺序依赖、在线反馈和已曝光数据使这些区间只具描述性，不证明未见患者泛化或同期因果效应。

| 保存结果的描述分组 | 完整分母 | 历史正确 | R49正确 | 纠正 | 误改 | 净增 |
|---|---|---|---|---|---|---|
| 首次图像题 | 58 | 48 | 45 | 1 | 4 | -3 |
| 此前同图记忆命中 | 58 | 52 | 52 | 3 | 3 | +0 |
| Skill命中 | 0 | 0 | 0 | 0 | 0 | +0 |
| Skill未命中 | 116 | 100 | 97 | 4 | 7 | -3 |

Skill命中0/116，此前同图记忆命中58/116；最多注入0条Skill、4条同图前缀。覆盖分组和窗口分数是事后描述，不是按正确性选用的方法。窗口内使用起始快照，末窗口进化不能改变已完成预测。

| 窗口（1起） | 题数 | 正确 | Skill命中题 | 窗口后活跃／成熟Skill | 完整证据 |
|---|---|---|---|---|---|
| 1 | 30 | 21 | 0 | 0 | [快照／轨迹／蒸馏／治理](evidence/vqarad/windows/0000) |
| 2 | 30 | 27 | 0 | 0 | [快照／轨迹／蒸馏／治理](evidence/vqarad/windows/0001) |
| 3 | 30 | 27 | 0 | 0 | [快照／轨迹／蒸馏／治理](evidence/vqarad/windows/0002) |
| 4 | 26 | 22 | 0 | 0 | [快照／轨迹／蒸馏／治理](evidence/vqarad/windows/0003) |

最终Skill库为空，原样报告；没有人工补卡。

| 臂 | 缺显式答案 | 答案域冲突 | 完整原生JSON | 旧M特定契约 | 提取机制 |
|---|---|---|---|---|---|
| M43-IM-GT-S49 | 0 | 0 | 116 | 116 | {"whole_json_answer": 116} |
| M42 | 0 | 0 | 116 | 116 | {"whole_json_answer": 116} |

JSON为单独接口诊断，主指标使用共同显式答案与作者答案口径。无答案、冲突和重复无进展记录保留，不从reason或参考猜答。实际终态计数：{"completed": 116}。

全部正负例见[CASE_INDEX](CASE_INDEX.md)；[实际资源](RESOURCE_SUMMARY.json)、[保存评分summary](results/vqarad/summary.json)、[公开语义重算](public_reproduction/vqarad/summary.json)、[全部原始证据](evidence/vqarad/)均保留。工具名称与次数：{"chest_xray_expert": 74, "chest_xray_report_generator": 10, "llava_med_qa": 20, "xray_phrase_grounding": 16, "chest_xray_segmentation": 11, "chest_xray_classifier": 3}。有记录不等于医学解释正确；同模型Skill Review和采用归因不是独立临床核实。


## 实际费用、时间与未知项

| 数据集 | 独立资源类别 | 实际请求 | 输入／输出token或总token | 已知CNY费用代理小计 | 费用未知请求 | 已知请求秒数之和 | 耗时未知请求 |
|---|---|---|---|---|---|---|---|
| CheXbench | 主推理 | 1846 | 7425404／99398 | 30.894392 | 0 | 4218.753 | 0 |
| CheXbench | 元学习／筛选／治理 | 967 | 23707012／272819 | 98.101876 | 0 | 5982.317 | 0 |
| CheXbench | Embedding | 321 | 65528 | 0 | 321 | 95.859 | 0 |
| 另列SLAKE | 主推理 | 201 | 573980／8550 | 2.398520 | 0 | 394.847 | 0 |
| 另列SLAKE | 元学习／筛选／治理 | 29 | 128859／4114 | 0.564804 | 0 | 101.722 | 0 |
| 另列SLAKE | Embedding | 1 | 405 | 0 | 1 | 0.244 | 0 |
| VQA-RAD | 主推理 | 253 | 799846／11737 | 3.340228 | 0 | 540.913 | 0 |
| VQA-RAD | 元学习／筛选／治理 | 45 | 214612／6171 | 0.932500 | 0 | 149.132 | 0 |
| VQA-RAD | Embedding | 0 | 0 | 0 | 0 | 0.000 | 0 |

| 数据集 | 生产Embedding物理请求 | 成功向量回复 | 已登记SDK400失败 | usage未知请求 | 已知token小计 | 费用未知请求 |
|---|---|---|---|---|---|---|
| CheXbench | 321 | 320 | 1 | 1 | 65528 | 321 |
| 另列SLAKE | 1 | 1 | 0 | 0 | 405 | 1 |
| VQA-RAD | 0 | 0 | 0 | 0 | 0 | 0 |

生产Embedding保留原000063的失败和新000063_arrearage_1的健康回复，分别计一次；旧失败没有usage或已保存HTTPbody，不能把表中的已知token／CNY小计读作其用量或费用为0。新健康回复已经在生产Embedding请求和费用中，不再附加一份“恢复费用”。

| 数据集 | 逻辑工具 | cache命中 | 物理生产尝试 | 健康物理尝试 | 已登记历史失败尝试 | 已知生产后端计算秒 | 后端耗时未知尝试 | 活跃失败／未知工具 | 已记录请求时段秒 |
|---|---|---|---|---|---|---|---|---|---|
| CheXbench | 1253 | 9 | 1246 | 1244 | 2 | 15879.293 | 0 | 0 | 71987.842 |
| 另列SLAKE | 86 | 1 | 85 | 85 | 0 | 637.381 | 0 | 0 | 1406.512 |
| VQA-RAD | 134 | 3 | 131 | 131 | 0 | 1609.985 | 0 | 0 | 2712.608 |

Embedding请求未定价的条目按未知列出，已知小计0不能读作免费。另有唯一开跑前接口探针，text-embedding-v4／1024维，13tokens、1.309秒、0医学题／0主请求；仅计一次，不混入三个流的请求。该探针费用未提供，保持未知，不另估单价。医学工具用时没有币价则保持未定价，缓存命中不重复计算后端尝试。

R49_META费用／请求总量保留两次原无效schema回复及各自一次独立新澄清回复，每份实际请求各计一次；下文两次故障所列费用只是该总量的非附加子集，不能再次加费。普通MUTATE字段提示不新增普通事件调用，其提示token仍按实际用量计费。没有把无效旧回复改记免费，也没有把额外学习调用漏报为主Agent免费能力。

CheX物理工具尝试包含原始已关闭CUDA失败和本次MAIRA未闭合格式失败，各一次；两份登记的健康生产尝试已在活跃健康cache中分别计数，不能再加一次。逻辑工具仍按题目选择槽位计数，未来同身份健康cache复用只计命中。活跃失败工具为0不代表所有历史物理尝试都成功。另有一次隔离CUDA诊断，实际1次工具、10.615351秒，主／元／Embedding API均0，诊断输出没有进入生产推理，且不计入物理生产尝试；其硬件成本未知，独立披露。

本次MAIRA原失败生产尝试耗时22.626826583秒，其中保存的后端计算时间19.67407546秒，已在生产物理尝试账内一次计入。独立MAIRA格式诊断另有1次工具调用、23.471671秒，实际失败；其输出仅供故障定位，没有进入生产上下文、不计入生产尝试，主／元／Embedding API均0，硬件费用未知。诊断不是一次成功工具结果，也不与健康生产尝试合并或重复计算主模型费用。

另有一次中性Embedding欠费诊断：1次请求、HTTP400、错误码Arrearage、0.299710秒；它失败退出1，没有健康向量，usage和费用均未知，不计入生产Embedding总数，也不替代原000063的缺失HTTPbody。主Agent／META／胸片工具／本地GPU调用均0。该次诊断与早先13token健康接口探针是两次不同的调用，分别记录，不能混称健康探针。

主／元／Embedding已知CNY代理小计总和为136.232320；尚有324条未定价请求（包含早先健康接口探针与单独失败欠费诊断），所以不提供虚假的完整总费用。token表沿评分器已知字段求和；缺失usage的请求数量在RESOURCE_SUMMARY逐组另列，0不能补作已知用量。工具硬件成本、供应商发票、未记录GPU等待／controller总墙钟均未知。各类请求耗时之和不是墙钟；“已记录请求时段”只指最早发送到最晚回复，不能冒充完整生成时长。完整原字段、状态、Skill谱系、窗口事件与未知口径均见[RESOURCE_SUMMARY](RESOURCE_SUMMARY.json)。

## 审阅、故障与复现边界

首次controller2277353／CheX进程2277359在第一题`chexbench_rad_restruct_0123`的预测、保存事件及自身反馈均完成后，于已完成题的学习奖励适配处报`ModuleNotFoundError: cxr_author_alignment`，原始退出1。此时只有第一题，3次主请求全部闭合、2次工具健康，尚无元学习／Embedding请求或第二题。原因是部署只复制了推理依赖，缺少在线奖励使用的既有答案适配模块；按原样补齐该模块，未修改runner、Skill规则、模型、配置、题序、标签或已保存输出。独立窄范围DeepSeek接续审阅就绪后使用单次守卫恢复，同一输出目录读取第一题既有预测／事件／反馈，构建其轨迹再继续，不重新作答或重复读取第一题标注。该次依赖接续后来又因下面的CUDA问题退出1，作为中间失败保留；最终原始退出0来自后续登记操作恢复，不是把依赖接续本身改记成功。

[依赖故障与恢复说明](DEPENDENCY_RECOVERY.md) · [实际接续审阅原文](DEPENDENCY_REPAIR_REVIEW.md) · [接续审阅元数据](DEPENDENCY_REPAIR_METADATA.json) · [完整恢复树](evidence/recovery/dependency_1) · [首次退出1／日志／原manifest](evidence/recovery/dependency_1/original)。恢复后各组仍由原冻结runner完整运行至实际原始退出0，没有effective exit、自动技术空答或吞任意异常；首次失败不被改记成功。第一题3次主请求费用代理已知小计0.025600CNY、费用未知0条，已知主请求时间合计6.167秒、时间未知0条；它们和2次工具均已包含在CheX资源总量中一次，不能再加算。窄范围接续审阅实际342363ms、CLI估算USD=1.22049，与主模型CNY分列，不冒充发票。失败前后完整墙钟及部署修复墙钟若没有独立时间记录则保持未知；跨中断的请求时段仍按其实际跨度披露。

随后已完成前40题和一个窗口，第41题`chexbench_rad_restruct_0163`在原主计划回复后，expert工具产生已关闭的`CUDA error: device kernel image is invalid`失败，当前题尚未保存预测或揭示自身真值。一次隔离debug诊断健康，但结果仅用于诊断，未写入生产cache或作为推理证据。实际DeepSeek操作审阅后，针对这一确定失败进行了恰好一次原始生产参数复试，关闭debug环境标志；仅复试健康后登记`r49_registered_cuda_retry_v1`并将当前工具槽位解析到`<oldkey>_cuda_1`健康cache。原坏cache和原选择归档保持不变，未来只有同后端／revision／原图路径／参数的精确登记身份可复用该健康cache。冻结八份推理源文件未改，但一次生产复试和登记cache解析覆盖属于明确的操作协议修订，不应说执行完全没有变化。

[CUDA操作修订说明](CUDA_PRODUCTION_RECOVERY.md) · [实际操作审阅](CUDA_PRODUCTION_RECOVERY_REVIEW.md) · [元数据](CUDA_PRODUCTION_RECOVERY_METADATA.json) · [操作helper源码](deployment_source/recover_cxr_online_skill_r49_cuda.py) · [完整恢复树／原始失败与诊断](evidence/recovery/cuda_1) · [GEN登记](evidence/chexbench/failure_events/cuda_1_registration.json) · [原失败选择归档](evidence/chexbench/failure_events/cuda_1_original_selection.json)。操作审阅实际46962ms、CLI估算USD=0.272114，单独报告。前40个预测不重生成，第41题既有主计划只复用已保存的第一条回复，不重发；该主请求费用代理0.003732CNY、耗时2.102秒，若缺失则未知，均已在主模型总量中一次计入。工具失败与复试的已知计算／经过时间及未知项沿实际资源原字段保留，隔离诊断另列。debug成功或生产复试健康均不能确定根因，更不能声称CUDA问题永久修复。未知发送、其他失败和新增错误不在这一登记例外内；没有自动技术空答或未登记重试。

CUDA接续在第4个窗口、120个已保存预测与反馈之后再次停止：`mutation_chexbench_slake_0004`返回PATCH，但`patch_section="c"`表示整个内容容器，不在原六个允许的单字段集合内，冻结进化代码因此报`ValueError: invalid_patch_section`。前120题、前三个已完成窗口及此前CUDA登记仍保留，尚未产生第121题上下文或作答。此处旧回复已收到、付费凭证闭合，属于已知元学习schema失败，不是未知发送，也不是模型题目答案被判错后重答。

经实际窄范围DeepSeek审阅后，只为这一已知事件新增一次独立META请求`mutation_chexbench_slake_0004_schema_1`：使用完全相同的已完成历史payload，追加schema说明，没有新病例、当前／未来真值或额外临床信息；PATCH只能保留同一目标并选择原六个合法字段，也允许模型依据原证据真实返回NONE，不由操作方把无效响应强制改成NONE。本次实际新控制输出为{"operation": "PATCH", "patch_section": "description", "patch_target_id": "s_cffc935ceb863823"}。冻结evolve的合法性验证／质量审查不改，只有这一事件的服务路由增加明确登记的schema澄清；随后仍接受原Review，不借此跳过后续失败。

[META恢复方案与边界](META_SCHEMA_RECOVERY_PLAN.md) · [真实操作审阅](META_SCHEMA_RECOVERY_REVIEW.md) · [元数据](META_SCHEMA_RECOVERY_METADATA.json) · [helper源码](deployment_source/recover_cxr_online_skill_r49_meta_schema.py) · [完整恢复树／原始失败](evidence/recovery/meta_schema_1) · [GEN登记](evidence/chexbench/failure_events/meta_schema_1_registration.json)。实际操作审阅610145ms、CLI估算USD=2.5245559999999996，与主／元模型CNY分列。原无效回复和新回复的实际token／费用／耗时分别见RESOURCE_SUMMARY的`non_additive_META_cost_subsets`；二者都已包含在R49_META总账一次。额外主Agent／Embedding／医学工具调用均0，不重新生成120题、重复揭示其标签或重跑前三个窗口；原CUDA cache覆盖继续生效，未再次运行CUDA生产复试。该次meta_schema_1接续后来在150题后的第五窗口再次因下述schema失配退出1，也作为中间失败保留；最终完整0不来自把这一尝试改记成功。学习接口格式恢复不算医学正确率增益，不能据此声称改进稳定性或临床能力已证明。

在150个已提交预测／反馈、四个完整窗口之后，`mutation_chexbench_slake_0013`再次给出PATCH，但字段为`content`而不是原六个允许字段，冻结校验仍以`invalid_patch_section`停止。实际操作审阅通过后，仅为这一已知、已闭合事件独立新增一次同历史payload、同一目标的schema澄清请求`mutation_chexbench_slake_0013_schema_2`；实际新控制为{"operation": "PATCH", "patch_section": "name", "patch_target_id": "s_cffc935ceb863823"}，只能是合法单字段PATCH或模型真实NONE，不能操作方强行NONE。原无效回复、两份请求回复及两份费用均保留；不重生成150题、重读其标签或重跑前四个已提交窗口，不重新执行此前CUDA生产复试。

这次操作还在三个数据集的普通MUTATE边界明确原六字段，禁止把`c`／`content`整个容器当字段。仅当事件名精确等于`mutation_`＋既有payload轨迹题号且原system为MUTATE时应用；原payload、模型参数和临床规则不变。已缓存的原提示变体按冻结保护清单回放，后续未缓存普通事件只增加固定字段说明，没有额外调用。CheX在150题处激活，另列SLAKE和VQA从各自冷启动时激活；不是把CheX Skill库传给后两组。任何后续新无效输出仍然停止，没有自动修复循环。这是明确的运行中操作提示变更，不能再称整个流自始至终遵循同一原始静态提示，收益归因更受混杂限制。

| 数据集 | 实际普通MUTATE请求 | 原始system请求 | 澄清system请求 | 保护原缓存事件数 | 提示澄清额外调用 |
|---|---|---|---|---|---|
| CheXbench | 199 | 21 | 178 | 21 | 0 |
| 另列SLAKE | 1 | 0 | 1 | 0 | 0 |
| VQA-RAD | 0 | 0 | 0 | 0 | 0 |

[字段修订方案](MUTATION_FIELDS_RECOVERY_PLAN.md) · [实际操作审阅](MUTATION_FIELDS_RECOVERY_REVIEW.md) · [元数据](MUTATION_FIELDS_RECOVERY_METADATA.json) · [helper源码](deployment_source/recover_cxr_online_skill_r49_mutation_fields.py) · [完整恢复树／150题失败边界](evidence/recovery/mutation_fields_2) · [第二次特定事件登记](evidence/chexbench/failure_events/meta_schema_2_registration.json)。各组`failure_events/mutation_fields_2_amendment.json`保留激活点、提示全文与保护事件清单，恢复树`amendments`下保留相同声明。实际操作审阅328175ms、CLI估算USD=2.2906440000000003，单独报告。第二次旧／新META用量与费用在RESOURCE_SUMMARY的独立非附加子集中显示，已在R49_META总量一次计入。该次字段修订接续后来在同一150题边界遇到下面的Embedding失败，其controller／CheX原始退出1同样保留；最终完整0不来自改写这一尝试。提示接口恢复不证明医学能力或稳定涨点，也不意味着CUDA根因已修复。

上述字段修订实际取得第二次合法PATCH回复后，在同一150题边界的Embedding000063又因SDK `BadRequestError`停止，fields2 controller／CheX原始退出1也保留。原记录没有response.json、HTTPbody或usage；400仅来自已安装SDK异常类别的状态码约定。后来一次中性诊断返回400／Arrearage，只能证明该次诊断时账户欠费，不能把它的body冒充原000063响应或据此重建原请求的具体服务器原因。

用户明确确认DashScope充值且实际新操作审阅就绪后，仅为原000063相同input／model／端点，以安装SDK的原缺省参数新增一次生产Embedding请求000063_arrearage_1。没有修改文本、模型、encoding_format参数或临床规则；收到真实有限1024维健康向量后，只为登记的精确身份建立别名，诊断结果从未用作向量。原失败请求／started／result和缺失body保持原样；不制造旧response.json。启动及最终闭合校验也只有这一份明确登记、已封存的SDK400失败例外，其它未知发送／失败仍立即停止，不能说原来的所有闭合规则完全未变。150个预测、前四个完整repo和此前CUDA／两次META包装器均保留；生产Agent／META／医学工具没有因这次修复新增调用。

[Embedding恢复方案](EMBEDDING_ARREARAGE_RECOVERY_PLAN.md) · [实际充值后操作审阅](EMBEDDING_ARREARAGE_RECOVERY_REVIEW.md) · [元数据](EMBEDDING_ARREARAGE_RECOVERY_METADATA.json) · [helper源码](deployment_source/recover_cxr_online_skill_r49_embedding_arrearage.py) · [完整恢复树／原失败／单独诊断／充值标记](evidence/recovery/embedding_arrearage_1) · [GEN登记](evidence/chexbench/failure_events/embedding_arrearage_1_registration.json) · [原失败语义归档](evidence/chexbench/failure_events/embedding_arrearage_1_original_failure.json)。操作审阅267668ms、CLI估算USD=2.3279650000000003，仍与生产CNY分列。原失败费用未知，健康新请求已包含在生产Embedding总量一次；单独失败诊断的费用也未知。该次embedding_arrearage_1接续后来在168题／5个完整窗口处遇到MAIRA未闭合格式错误，其controller2645757／CheX2645763原始退出1同样保留。恢复可用性和接口成功不算医学正确率增益，也不证明原错误具体原因、后续资金持续充足或CUDA根因已解决。

## MAIRA未闭合格式与显式生成策略修订

第169题`chexbench_slake_0053`的原MAIRA生产调用已明确失败。独立诊断在原设置下实际生成13token即EOS，生成后缀含`<obj>`而没有`</obj>`；两者在原tokenizer中都不是special，结束标签未曾生成，不能归因于decode过滤。13token未达到原max300上限，原processor严格断言拒绝。诊断用于定位这一机制，不能补标签、补box、猜阴性，不能当作同图医学观察，也未复用其输出。

实际新操作审阅通过后，`phrase_guard_1`对CheX第168个已提交预测、5个完整窗口之后的全部**新物理MAIRA调用**统一启用EOS守卫；另列SLAKE和VQA从各自冷启动启用。只根据新生成后缀的obj／box未闭合状态屏蔽EOS，其余logit不改，原input／model／量化／主prompt／max300与严格原parser保持；不强制生成标签、box、发现或阴性，不作解析回退。若守卫后仍未闭合、未正常EOS或原parser拒绝，继续技术停止，没有自动重试循环。第169题仅一次新guarded生产尝试，旧失败cache／旧selection与其原始耗时完整保留；此前168题及五个完整窗口、该题已保存主调用均没有重做，所有先前恢复包装器继续保留。

旧健康cache和已有选择保持legacy policy，不改写为新策略产物。新策略仅覆盖激活后的新物理调用，因而全流混合旧／新生成策略；本次是**自定义generation-policy amendment**，不是官方MAIRA修复，也不是与原设置相同的重试。EOS屏蔽可能改变后续文本、坐标、调用耗时和正确性，不能声称语义不受影响、医学能力获得独立验证，或把在线反馈／Skill／预算／提示／生成策略混合变化的差值作单一因果归因。

| 数据集 | 激活前已提交题数 | 保留旧MAIRA selection | 复用legacy健康cache选择 | 新guarded选择 | 复用guarded cache选择 | guarded物理尝试 | 实际屏蔽EOS步数 |
|---|---|---|---|---|---|---|---|
| CheXbench | 168 | 15 | 1 | 387 | 3 | 387 | 5682 |
| 另列SLAKE | 0 | 0 | 0 | 3 | 0 | 3 | 42 |
| VQA-RAD | 0 | 0 | 0 | 16 | 0 | 16 | 450 |

[EOS守卫恢复方案](PHRASE_GROUNDING_EOS_GUARD_RECOVERY_PLAN.md) · [实际操作审阅](PHRASE_GUARD_RECOVERY_REVIEW.md) · [元数据](PHRASE_GUARD_RECOVERY_METADATA.json) · [helper源码](deployment_source/recover_cxr_online_skill_r49_phrase_guard.py) · [EOS policy源码](deployment_source/r49_phrase_grounding_eos_guard_candidate.py) · [完整恢复树／168题失败边界／独立失败诊断](evidence/recovery/phrase_guard_1) · [GEN复试登记](evidence/chexbench/failure_events/phrase_guard_1_registration.json) · [旧selection归档](evidence/chexbench/failure_events/phrase_guard_1_original_selection.json)。操作审阅442754ms、CLI估算USD=3.3847，与生产CNY分列。该次phrase_guard_1继续至210个已提交预测／反馈、六个完整窗口后，因下述采用归因校验停止；controller2722301／CheX2722307原始退出1同样保留，不将此中间尝试改记0。

## 两次采用归因代表项选择与完成后审计

窗口0006的两个原ANALYZE事件`analysis_chexbench_slake_0081`／`analysis_chexbench_slake_0082`，分别为同一个已注入Skill给出了两条同为ADOPTED_POSITIVE、但step_index和evidence不同的采用项。这些不是完全相同的重复记录；原assess的唯一Skill约束以`duplicate_skill_adoption`停止，尚无第211题，也没有该窗口已提交repo／events。原回复、请求、费用、210题及前六个完整窗口保持。

只对这两个已闭合已知事件，各新增一次独立META请求。模型只能返回`selected_duplicate_index`为0或1，选择该事件原来的两个重复项之一；不是操作方择优，也不重写任何status、step或evidence。实际选择为{"analysis_chexbench_slake_0081": 0, "analysis_chexbench_slake_0082": 0}。effective adoption只留下模型选中的完整原项，其余唯一项原样保持；该有效列表仅在原assess边界使用。原ANALYZE原文及MUTATE使用的分析保持，未重跑原窗口的生成／标签揭示或已缓存普通ANALYZE／MUTATE调用。两次新请求与两份原付费回复均已在R49_META总账一次计入，RESOURCE_SUMMARY的adoption_recovery.non_additive_META_cost_subsets仅作拆分、不再相加；无额外主Agent／Embedding／工具调用。

对后续未缓存普通ANALYZE，只在原system／精确事件名边界增加“每个注入skill_id最多一个采用项”的固定说明，原payload和模型配置保留，每次普通事件仍只有一次调用。旧缓存原提示按声明保护清单回放。CheX在210题处激活，另列SLAKE／VQA各自空库冷启动时激活，记忆及Skill仍逐数据集隔离。后续新的不合法采用分析继续停止，不形成自动修复循环。此操作会改变采用证据代表项、信用分配及后续Skill效用轨迹，不能称输出语义不变，或把差值单独归因记忆／Skill的医学能力。

| 数据集 | 激活前已提交题数 | 普通ANALYZE请求 | 原system请求 | 澄清system请求 | 保护原缓存事件数 | 普通澄清额外调用 |
|---|---|---|---|---|---|---|
| CheXbench | 210 | 553 | 146 | 407 | 146 | 0 |
| 另列SLAKE | 0 | 27 | 0 | 27 | 0 | 0 |
| VQA-RAD | 0 | 45 | 0 | 45 | 0 | 0 |

用户最初明确指示“这个可以跑完再审计？”。因此初始`EXECUTION_AUTHORIZATION.json`如实保留`audit_deferred_until_full_generation`、review_completed=false、scope_complete=false、explicit_user_reply及原定完成后发布前审计要求；不将其改写为曾经预审ready。随后用户明确要求“先上传github吧”“抓紧推送”，因此先在`628617beb777d4b99aa1cb7110f50fbdfc8fde8c`公开完整已完成结果与证据，当时最终结果审阅尚未完成。本页对应后续最终报告：同一次实际DeepSeek审阅发生在全部848题及首次证据推送之后、最终报告补充推送之前，覆盖adoption_protocol、request_resource_accounting、complete_results_and_claims，scope_complete来自真实结论。不能再声称审阅发生在第一次发布之前；最新用户指示和原始历史授权分开保存。这里与下文RESULT_CLAIM审阅是同一次，不重复计费，负结果可以如实发布。[发布顺序修订](PUBLICATION_SEQUENCE_AMENDMENT.md)与[实际发布控制记录](PUBLICATION_HISTORY.json)保留这一顺序。

[采用项恢复方案](ADOPTION_RECOVERY_PLAN.md) · [实际完成后的统一审计](RESULT_CLAIM_REVIEW.md) · [审计元数据](RESULT_CLAIM_METADATA.json) · [helper源码](deployment_source/recover_cxr_online_skill_r49_adoption.py) · [完整恢复树／210题失败边界／原始后审授权](evidence/recovery/adoption_1) · [GEN两次选择登记](evidence/chexbench/failure_events/adoption_1_registration.json)。各组`failure_events/analysis_unique_adoption_amendment.json`保留实际激活点、原提示／说明及保护事件清单。只有最后adoption_1的controller与三组原runner实际原始退出0，全部历史1保持；没有技术空答或effective-exit。

实际用户指定DeepSeek原生Claude Code结果审阅已完成：[原文](RESULT_CLAIM_REVIEW.md) · [元数据](RESULT_CLAIM_METADATA.json) · [结果到声明](CLAIMS_FROM_RESULTS.md)。CLI返回别名deepseek-v4-pro，421190ms／4轮，CLI估算USD=2.341015，不是发票，也不与CNY代理相加。服务别名不构成权重身份鉴证；保留任何负向或部分支持结论，执行ready分数不代替结果审阅。不存在独立完整性／临床审计通过声明。

R48的63题后MAIRA嵌套失败和原始退出1保持独立，不把R49视为其恢复、不填失败题／清缓存／重试旧请求。[全部逐题与窗口证据](CASE_INDEX.md) · [公开复现与实际路径](REPRODUCTION.md)。公开语义重算使用保存的请求回复和统一答案适配，0新推理、无新字节／哈希／像素校验；本地复算不是第三方医学审计。图片／数据来源与适用条件见各组证据，代码许可证不重新许可数据。

本页生成不等于最终补充推送完成；以实际Git推送成功为准。用户明确表示不需要推送后的远端核验，因此没有该项核验，也不将本地commit或推送回执冒称额外远端核验结论。
