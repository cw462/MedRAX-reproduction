# CheXagent-8B 直答基线

2026 年 11 月 14 日，使用 Stanford AIMI 随 2024 年论文发布的原版 CheXagent-8B，在冻结的三集 848 道题上单独生成答案。[论文](https://arxiv.org/abs/2401.12208) · [权重版本](https://huggingface.co/StanfordAIMI/CheXagent-8b/tree/4934e91451945c8218c267aae9c34929a7677829)

| 数据集 | 显式答案提取 | 原精确匹配 | 单题推理累计时长 |
| --- | ---: | ---: | ---: |
| CheXBench | 374/618（60.52%） | 373/618（60.36%） | 103.76 秒 |
| SLAKE | 84/114（73.68%） | 84/114（73.68%） | 12.55 秒 |
| VQA-RAD | 81/116（69.83%） | 81/116（69.83%） | 9.93 秒 |
| **合计** | **539/848（63.56%）** | **538/848（63.44%）** | **126.24 秒** |

CheXBench 的 Rad-Restruct、SLAKE 和 OpenI 子集分别答对 68/115、101/123 和 205/380。合计按题计数，准确率对应本项目使用的题目、提示和计分口径。

## 生成与计分

输入为原图和原题，选择题附完整选项。对话模板沿用 CheXagent-8B 的 User/Assistant 输入，提示要求输出选项字母或最短答案。运行使用一张 NVIDIA RTX 6000D、FP16、贪心解码和最多 64 个新增 token。共生成 848 份预测，Qwen、评审器和辅助工具调用各为 0，进程退出码为 0。[实际协议](protocol.json)

两种计分都在对应数据集答完后运行。显式答案提取将 CheXBench 的 B.no 读为 B，依据是字母和选项文本一致。这次计分变化增计 1 题、减计 0 题。[逐题计分变化](scoring_changes.json)

7 个权重分片于北京时间 16:48:55 到齐，所有题于 16:51:23 出分，间隔 2 分 28 秒。单题推理累计 126.24 秒，GPU 租赁实付金额未知。[传输事件](download.json) · [各集结果及运行退出码](summary.json)

## 逐题记录与复现

每行包含原始回答、两种计分结果、题目 ID、耗时和案例链接。题面、完整选项、已发布的图像及来源引用沿用同一冻结题目的归档。[CheXBench 618 题](chexbench.jsonl) · [SLAKE 114 题](slake.jsonl) · [VQA-RAD 116 题](vqarad.jsonl)

在保留冻结 manifest、参考文件、原图和运行环境的机器上，将入口和评分依赖置于归档对应位置。本地权重目录使用 [download.json](download.json) 记录的版本和分片布局。

    python code/baseline/run_chexagent8_direct.py <frozen_run_root> <new_output> <snapshot_dir> code/baseline

[实际入口](code/baseline/run_chexagent8_direct.py) · [显式答案评分器](code/baseline/score_direct_answer_rerun.py) · [精确匹配评分器](code/experiments/r54_author_metrics.py)

原图及题目归属见逐题归档与原始发布说明。[CheXBench](https://huggingface.co/datasets/StanfordAIMI/chexbench) · [SLAKE](https://www.med-vqa.com/slake/) · [VQA-RAD](https://doi.org/10.17605/OSF.IO/89KPS)
