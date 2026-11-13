# MedRAX R55 全 848 题配对结果 · D 与 EvolveR

同一冻结题序的 848 题中，D 答对 647 题，EvolveR 答对 660 题。配对净增 13 题来自 CheXBench，SLAKE 和 VQA-RAD 的净变化相抵。

## 准确率与逐题变化

| 数据集 | D 正确率 | EvolveR 正确率 | EvolveR − D | D 错、E 对 | D 对、E 错 | 净增 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| CheXBench | 445/618（72.01%） | 458/618（74.11%） | +2.10 个百分点 | 69 | 56 | +13 |
| SLAKE | 108/114（94.74%） | 103/114（90.35%） | −4.39 个百分点 | 5 | 10 | −5 |
| VQA-RAD | 94/116（81.03%） | 99/116（85.34%） | +4.31 个百分点 | 9 | 4 | +5 |
| **全 848 题** | **647/848（76.30%）** | **660/848（77.83%）** | **+1.53 个百分点** | **83** | **70** | **+13** |

总准确率按题计数。两组均答对 577 题，均答错 118 题。SLAKE 和 VQA-RAD 合计各答对 202/230，分别有 14 题转对和 14 题转错。

## 实验协议

两组使用同一冻结题序、问题、原图、参考答案和 11 种工具。848 题的同图前序题 ID 均一致，当前题参考反馈在预测落盘后释放。主模型为 `qwen3.7-plus`，temperature 0.2、top_p 0.95，最多输出 2,048 tokens。Verify 使用 `deepseek-v4.1-flash-1017`，启用 high reasoning，最多输出 8,192 tokens。工具清单包括 CheXagent、LLaVA-Med、MedGemma、LLaVA-Rad、MedVLM-R1、MAIRA-2 报告与短语定位、ROI 裁剪、MedRet、Reflect 和 Verify。

D 关闭经验库，CheXBench 沿用已保存的前 298 题后接续。EvolveR 在三个数据集各自从空库开始，每题首答前检索，答后用 `deepseek-flash` 写卡，向量模型为 `text-embedding-v4`。EvolveR 共做 848 次首答前检查，818 题收到经验。CheXBench、SLAKE 和 VQA-RAD 分别保存 426、85 和 87 张卡，保留写卡模型返回的文本。

CheXBench 按已保存的选项判分。SLAKE 和 VQA-RAD 按归档 `r54_author_metrics` 从末次回复提取显式答案，依 `m4cxr_normalize` 对答案和参考做精确匹配。三集均以完整冻结分母报告。

## 调用、用量与时间

| 数据集 | 主模型逻辑调用 D / E | 工具调用 D / E | 失败工具 D / E | 答题累计时长 D / E |
| --- | ---: | ---: | ---: | ---: |
| CheXBench | 1,954 / 2,060 | 1,198 / 1,458 | 19 / 46 | 253.82 / 659.50 分钟 |
| SLAKE | 200 / 199 | 81 / 78 | 0 / 1 | 34.37 / 42.82 分钟 |
| VQA-RAD | 291 / 279 | 165 / 159 | 7 / 2 | 57.05 / 70.96 分钟 |
| **合计** | **2,445 / 2,538** | **1,444 / 1,695** | **26 / 49** | **5.75 / 12.89 小时** |

主模型服务请求为 D 2,445 次、EvolveR 2,539 次。SLAKE 有一次额外的失败请求，计入服务用量。主模型保存的输入 tokens 为 9,687,776 / 13,367,677，输出 tokens 为 171,877 / 162,561。Verify 工具调用 202 / 162 次，对应的服务请求为 202 / 161 次。EvolveR 写卡服务调用 598 次，嵌入调用 908 次。三集使用最多的工具为 CheXagent（544 / 634 次）和 MAIRA-2 报告（338 / 397 次）。

账本中可量化部分的成本代理合计为 D 40.845360 元、EvolveR 55.445820 元，覆盖主答和可计量的 Reflect 回执。Verify、写卡及额外失败请求中有成本未知的记录，嵌入也未并入该金额。供应商实付、Credits 和 GPU 成本未知。累计时长来自已保存的运行阶段，用于描述实验开销，两组执行可能重叠。

## 个例与恢复记录

- SLAKE [`slake_11971`](slake/cases/slake_11971.json) 两组均未调用工具，EvolveR 当时经验库为空，D 答 `lung`，EvolveR 答 `heart`，参考为 `Heart`。这次转对发生在经验尚未可用时。
- SLAKE [`slake_12045`](slake/cases/slake_12045.json) 两组均未调用工具，EvolveR 收到三张经验卡。D 答 `No`，EvolveR 答 `Yes`，参考为 `No`。该轨迹显示收到经验与答错同现，因果方向仍需单独实验检验。
- SLAKE [`slake_12393`](slake/cases/slake_12393.json) 的 EvolveR 主模型逻辑调用 2 首次返回 HTTP 500，服务侧内层为 OSS 503/QpsLimitExceeded，后以同一已保存请求重试一次。出站轨迹保留两次回执和原归档请求的相同摘要。重试取得可用回复，该题最终仍按 `No` 对参考 `Yes` 判错。
- VQA-RAD [`vqarad_1141`](vqarad/cases/vqarad_1141.json) 的 D 组 MAIRA-2 进程曾以 SIGSEGV 退出，续跑使用已保存前缀并跳过这次失败工具调用。两组最终均答 `No`，与参考一致。

运行时段、缓存与恢复历史、工具选择和资源投入存在差异。表格描述本次配对结果。对记忆策略独立贡献的估计需要控制这些条件，在线答后参考反馈也限制结果的外推范围。

## 逐题记录与源码

| 数据集 | 逐题与分数 | 协议与恢复 |
| --- | --- | --- |
| CheXBench 618 题 | [既有提交的逐题记录与离线核验](https://github.com/cw462/MedRAX-reproduction/tree/00a38f10d203c4772b03424f8b277ee041553746/reports/r55_chexbench_de_evolver_20261113) | 同一提交中的协议、经验卡、工具记录与恢复记录 |
| SLAKE 114 题 | [题目索引](slake/case_index.json) · [CSV](slake/per_question.csv) · [JSON](slake/per_question.json) · [分数与用量](slake/summary.json) | [协议](slake/protocol.json) · [主请求恢复](slake/recovery/E/slake_main_retry001.json) |
| VQA-RAD 116 题 | [题目索引](vqarad/case_index.json) · [CSV](vqarad/per_question.csv) · [JSON](vqarad/per_question.json) · [分数与用量](vqarad/summary.json) | [协议](vqarad/protocol.json) · [工具恢复](vqarad/recovery/D/vqarad_tool_skip001.json) |

SLAKE 和 VQA-RAD 的逐题文件保留问题、参考反馈、两组预测、主模型请求与回复、经验检索与写卡以及工具记录的引用。目录还含 454 份工具记录和 12 个去重快照文件。图像请求中的内嵌数据以摘要引用呈现，可在图像索引中定位。出站副本处理了私有路径及凭证值，经验向量未随包分发。

实际运行源码补充包含 D 的 65 项和 EvolveR 的 81 项，涵盖入口、评分器、局部恢复及五份恢复前版本。外部包、模型权重和工具资源由运行环境提供。[源码清单](source_manifest.json)

## 图像与来源

本包纳入 44 张 SLAKE 图，含 13 张原图与 31 张派生图。共覆盖 59 题，其中 54 题可查看原图。SLAKE 的 533 次内嵌请求图出现中，230 次可解析到本地图像。其余 277 个资产保留引用及暂扣状态。

SLAKE 图像来自 Bo Liu、Li-Ming Zhan、Li Xu 和 Xiao-Ming Wu 的分发版，采用 CC BY 4.0。索引逐图记录来源、工具处理和父图关系。[资产索引](asset_references.json) · [作者分发页](https://huggingface.co/datasets/BoKelvin/SLAKE) · [许可](https://creativecommons.org/licenses/by/4.0/)

VQA-RAD 项目标注 CC0。已核对的四张原图与 OSF 文件记录的大小和摘要一致，逐图记录未列单独许可。此包保留 VQA-RAD 的资产引用，图像文件暂扣。MedPix 原始贡献者的逐图转载权限仍待核对。[VQA-RAD 官方项目](https://doi.org/10.17605/OSF.IO/89KPS) · [NLM 使用条款](https://openi.nlm.nih.gov/contactus)

## 离线复现

在报告目录使用 Python 3.10 或更新版本。将回执写入报告目录外的一个新文件。

```shell
python -B verify_r55_full848_open_text_public_once.py . --receipt ../r55_open_text_verification.json
```

验证器从 460 份末次回复先提取答案，再读取标签核对逐题及整集分数。它还检查图像摘要、尺寸和索引中记录的来源关系，模型调用为零。逐图视觉、转载条款与历史工具运行由各自证据记录。CheXBench 的 1,236 份末次回复在既有提交中独立复核。[本包复现回执](verification.json)
