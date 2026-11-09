# R49 已保存离线评分、原始失败与来源路径

| 数据集 | 完整题数 | 进入原生评分函数次数 | 完整指标计算次数 | 适配／标签前失败次数 | 实际评分凭证 | 完成组拉取凭证 |
|---|---|---|---|---|---|---|
| CheXbench | 618 | 2 | 1 | 1 | [实际score receipt](deployment_source/reporting_provenance/score_receipts/chexbench.json) | [完成组pull](deployment_source/reporting_provenance/dataset_completion/chexbench/PULL_RECEIPT.json) |
| 另列SLAKE | 114 | 1 | 1 | 0 | [实际score receipt](deployment_source/reporting_provenance/score_receipts/slake.json) | [完成组pull](deployment_source/reporting_provenance/dataset_completion/slake/PULL_RECEIPT.json) |
| VQA-RAD | 116 | 1 | 1 | 0 | [实际score receipt](deployment_source/reporting_provenance/score_receipts/vqarad.json) | [完成组pull](deployment_source/reporting_provenance/dataset_completion/vqarad/PULL_RECEIPT.json) |

三组保存的summary／per_question原样复用，报告编写器没有再次评分、生成答案或调用模型。公开语义独立重算单列，不冒充第二次私有指标计算。逐数据集完整结束后先报告结果的授权和原始时点标志保持；后续组的模型、提示、顺序和规则未据这些结果调整。

CheX第一次进入原生评分函数时，既有公开输入的images路径为`assets/...`，实际运行清单使用`images/...`。原严格completed_gate以manifest_semantic_input_order_changed拒绝，在ALL-arm适配、参考／feedback／complete正文读取之前退出1，没有指标或结果目录。原始started与[故障元数据](deployment_source/reporting_provenance/score_receipts/chexbench.pre_adaptation_failure_001.json)保留；没有删除started或把第一次改写为成功。

随后从实际原数据源`/home/imss/cw/MedRAX_reproduction_20261027/code_cxr_vqa_extension/data/chexbench/inputs.jsonl`只复制一次原始inputs，题号／顺序／题干／选项／image_id等保持，618条只有images字段的路径来源不同。记录于[canonical源拉取凭证](deployment_source/reporting_provenance/dataset_completion/chexbench/SOURCE_INPUT_PULL_RECEIPT.json)。独立private wrapper只为这一个已知前置失败执行一次显式接续，保留[新attempt2 started](deployment_source/reporting_provenance/score_receipts/chexbench.pre_adaptation_resume_001.started.json)；没有放宽原生gate、适配器、答案解析或指标，也没有新推理、改预测、读真值挑答案或选择有利成绩。故CheX是两次函数进入、一次完整指标计算；SLAKE／VQA各一次。三组共4次函数进入、3次完整指标计算、1次适配前失败，不把失败算作又一套成绩。

| 数据集 | 实际成功评分的input目录 | 实际独立references文件 |
|---|---|---|
| CheXbench | D:\MedRAX_Experiment_Artifacts\online_skill_r49_20261108\dataset_completion\chexbench\source_data | C:\Users\cheng\MedRAX_v9_20261030\reports\cxr_vqa_extension\results\chexbench\references.jsonl |
| 另列SLAKE | C:\Users\cheng\MedRAX_v9_20261030\data\slake_cxr | C:\Users\cheng\MedRAX_v9_20261030\data\slake_cxr\references.jsonl |
| VQA-RAD | C:\Users\cheng\MedRAX_v9_20261030\data\vqarad_cxr | C:\Users\cheng\MedRAX_v9_20261030\data\vqarad_cxr\references.jsonl |

这些私有路径是已发生步骤的来源记录；公开复现使用各组evidence和verify_public接口，不需要本机或服务器私有目录。CheX修正后input目录只提供canonical inputs，references仍为原独立文件；不能从input目录猜测references路径。

后续最终控制拉取跳过所有已评分GEN及结果，补齐现有jobs／configs／恢复历史。实际部署源码保存249个记录；既有诊断／故障捕获补存44份、保留未覆盖2份。它们不重启任何诊断、模型或实验，不构成源码字节鉴证。所有原始控制凭证见下列明确清单，JSON语义核对未使用文件／像素摘要。

| 已保留公开控制记录 | 对应私有来源（历史路径） |
|---|---|
| [deployment_source/reporting_provenance/DATASET_COMPLETION_REPORTING_AUTHORIZATION.json](deployment_source/reporting_provenance/DATASET_COMPLETION_REPORTING_AUTHORIZATION.json) | C:\Users\cheng\MedRAX_v9_20261030\local_assets\online_skill_r49_preparation\DATASET_COMPLETION_REPORTING_AUTHORIZATION.json |
| [deployment_source/reporting_provenance/score_receipts/chexbench.json](deployment_source/reporting_provenance/score_receipts/chexbench.json) | C:\Users\cheng\MedRAX_v9_20261030\local_assets\r49_dataset_score_receipts\chexbench.json |
| [deployment_source/reporting_provenance/score_receipts/chexbench.started.json](deployment_source/reporting_provenance/score_receipts/chexbench.started.json) | C:\Users\cheng\MedRAX_v9_20261030\local_assets\r49_dataset_score_receipts\chexbench.started.json |
| [deployment_source/reporting_provenance/dataset_completion/chexbench/PULL_RECEIPT.json](deployment_source/reporting_provenance/dataset_completion/chexbench/PULL_RECEIPT.json) | D:\MedRAX_Experiment_Artifacts\online_skill_r49_20261108\dataset_completion\chexbench\PULL_RECEIPT.json |
| [deployment_source/reporting_provenance/score_receipts/chexbench.pre_adaptation_failure_001.json](deployment_source/reporting_provenance/score_receipts/chexbench.pre_adaptation_failure_001.json) | C:\Users\cheng\MedRAX_v9_20261030\local_assets\r49_dataset_score_receipts\chexbench.pre_adaptation_failure_001.json |
| [deployment_source/reporting_provenance/score_receipts/chexbench.pre_adaptation_resume_001.started.json](deployment_source/reporting_provenance/score_receipts/chexbench.pre_adaptation_resume_001.started.json) | C:\Users\cheng\MedRAX_v9_20261030\local_assets\r49_dataset_score_receipts\chexbench.pre_adaptation_resume_001.started.json |
| [deployment_source/reporting_provenance/dataset_completion/chexbench/SOURCE_INPUT_PULL_RECEIPT.json](deployment_source/reporting_provenance/dataset_completion/chexbench/SOURCE_INPUT_PULL_RECEIPT.json) | D:\MedRAX_Experiment_Artifacts\online_skill_r49_20261108\dataset_completion\chexbench\SOURCE_INPUT_PULL_RECEIPT.json |
| [deployment_source/reporting_provenance/score_receipts/slake.json](deployment_source/reporting_provenance/score_receipts/slake.json) | C:\Users\cheng\MedRAX_v9_20261030\local_assets\r49_dataset_score_receipts\slake.json |
| [deployment_source/reporting_provenance/score_receipts/slake.started.json](deployment_source/reporting_provenance/score_receipts/slake.started.json) | C:\Users\cheng\MedRAX_v9_20261030\local_assets\r49_dataset_score_receipts\slake.started.json |
| [deployment_source/reporting_provenance/dataset_completion/slake/PULL_RECEIPT.json](deployment_source/reporting_provenance/dataset_completion/slake/PULL_RECEIPT.json) | D:\MedRAX_Experiment_Artifacts\online_skill_r49_20261108\dataset_completion\slake\PULL_RECEIPT.json |
| [deployment_source/reporting_provenance/score_receipts/vqarad.json](deployment_source/reporting_provenance/score_receipts/vqarad.json) | C:\Users\cheng\MedRAX_v9_20261030\local_assets\r49_dataset_score_receipts\vqarad.json |
| [deployment_source/reporting_provenance/score_receipts/vqarad.started.json](deployment_source/reporting_provenance/score_receipts/vqarad.started.json) | C:\Users\cheng\MedRAX_v9_20261030\local_assets\r49_dataset_score_receipts\vqarad.started.json |
| [deployment_source/reporting_provenance/dataset_completion/vqarad/PULL_RECEIPT.json](deployment_source/reporting_provenance/dataset_completion/vqarad/PULL_RECEIPT.json) | D:\MedRAX_Experiment_Artifacts\online_skill_r49_20261108\dataset_completion\vqarad\PULL_RECEIPT.json |
| [deployment_source/reporting_provenance/dataset_completion/FINAL_CONTROL_PULL_RECEIPT.json](deployment_source/reporting_provenance/dataset_completion/FINAL_CONTROL_PULL_RECEIPT.json) | D:\MedRAX_Experiment_Artifacts\online_skill_r49_20261108\dataset_completion\FINAL_CONTROL_PULL_RECEIPT.json |
| [deployment_source/reporting_provenance/supplemental_receipts/source_completed.json](deployment_source/reporting_provenance/supplemental_receipts/source_completed.json) | D:\MedRAX_Experiment_Artifacts\online_skill_r49_20261108\actual_code_source\source_completed.json |
| [deployment_source/reporting_provenance/supplemental_receipts/local_captures_completed.json](deployment_source/reporting_provenance/supplemental_receipts/local_captures_completed.json) | D:\MedRAX_Experiment_Artifacts\online_skill_r49_20261108\supplemental_receipts\local_captures_completed.json |

本页是来源与尝试次数说明，不代替实际完整结果审阅。最终审阅仍须覆盖逐数据集报告、这次来源路径前置失败／接续、请求账以及全部正负结果，不以增分或正向结论为前提。
