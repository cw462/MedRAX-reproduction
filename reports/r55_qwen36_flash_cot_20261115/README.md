# Qwen3.6-Flash CoT 基线

11 月 15 日 16:09:45–16:16:25（北京时间），AutoDL 经百炼 Token Plan 完成冻结的 848 题，生成及评分退出码为 0。

| 数据集 | Qwen3.6-Flash CoT | Qwen3.7-Plus CoT 复跑 | 改对 | 改错 |
|---|---:|---:|---:|---:|
| CheXBench | 313/618（50.65%） | 421/618（68.12%） | 73 | 181 |
| SLAKE | 86/114（75.44%） | 104/114（91.23%） | 5 | 23 |
| VQA-RAD | 71/116（61.21%） | 88/116（75.86%） | 13 | 30 |
| 合计 | 470/848（55.42%） | 613/848（72.29%） | 91 | 234 |

采用与前次相同的逐步推理提示、题序、原图和评分器。温度 0.2，top_p 0.95，输出上限 2048，enable_thinking=false，每题一次 API 请求，工具调用为 0。
848 条请求除模型字段外一致，均获得独立响应，接口均返回 qwen3.6-flash。百炼 API 支持原生思考开关。
[百炼文档](https://help.aliyun.com/zh/model-studio/deep-thinking) · [Qwen3.7-Plus 对照](https://github.com/cw462/MedRAX-reproduction/blob/26d6cc1aac20ce14070e89a4744ff10796f5ba67/reports/r55_qwen_cot_repeat_20261115/README.md)

CheXBench 的 155 条回复未提取到可计分选项，均纳入完整分母。全量收到 847 条 stop 和 1 条 length。请求输入 607,487 tokens、输出 227,728 tokens。Credits 以 Token Plan 账单为准。

逐题记录含问题、完整选项、答案、正确性和已有的原图证据链接。完整请求与响应保存在 AutoDL 持久运行目录。

[CheXBench](chexbench.jsonl) · [SLAKE](slake.jsonl) · [VQA-RAD](vqarad.jsonl) · [运行配置](protocol.json) · [部署源码](source/deploy_autodl.py)
