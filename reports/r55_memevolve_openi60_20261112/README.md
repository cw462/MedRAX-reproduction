# MemEvolve 在 OpenI 左右侧 60 题上的逐题对照

D 和 M1–M5 使用同一批 60 张图、题目与选项、顺序及 Qwen3.7-plus，沿用 R54 逐题流程和 R55 的 11 个工具。各记忆组从空库开始，保存本题预测后才释放本题标注并写入记忆。六组均正常退出且交齐 60 道答案。

| 组 | 方法 | 答对 | 较 D 改对 / 改错 | 工具调用 | 主模型请求 | 记忆模型请求 | 有记忆的题 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| D | 无外部记忆 | 37/60（61.7%） | — | 163 | 239 | 0 | — |
| M1 | DILU | 37/60（61.7%） | 9 / 9 | 193 | 259 | 0 | 59 |
| M2 | ExPeL | 43/60（71.7%） | 9 / 3 | 223 | 288 | 103 | 59 |
| M3 | Memp | 41/60（68.3%） | 10 / 6 | 260 | 286 | 100 | 58 |
| M4 | Agent-KB | 41/60（68.3%） | 7 / 3 | 209 | 249 | 217 | 58 |
| M5 | CerebraFusionMemory | 45/60（75.0%） | 10 / 2 | 220 | 270 | 163 | 58 |

M5 比 D 多答对 8 题，M2 多答对 6 题。M1 的 9 道改对题与 9 道改错题相抵，同时多调用 30 次工具。这些差值来自这一次固定顺序运行，逐题变化可在配对表中复查。

记忆适配器传入历史题目、代理回复和已释放标注。原始工具返回保存在本次证据记录，五组实际写入载荷中的原始工具消息计数均为零。M1 使用一近邻历史回复检索，不调用记忆模型。M5 运行图式与文本记忆，基础工具目录固定为 11 项。

M4 有 19 条失败轨迹按原规则跳过，另有 3 条轨迹的模型摘要失败。对应回执可在每题的 memory_write 字段找到。工具技术失败单独记录，六组含技术失败的题数分别为 1、2、3、7、3、3。

用量和耗时取自已保存的服务与记忆模型回执。主模型、辅助工具模型和记忆模型的 token 字段可分别查阅。这份导出的计费证据以请求次数与 token 为单位。

- [逐题答案与配对差异](paired-results.json)
- [逐题表 CSV](per-question.csv)
- [完整题干、选项、原图编号、工具动作与观察](case-evidence.json)
- [运行条件、退出状态、服务用量和耗时](run-condition-and-usage.json)
- [实验入口及工具适配源码](source) · [源码校验值](source-sha256.json)

题目来自 Stanford AIMI 的 CheXbench。每题保留 Indiana University Chest X-ray Collection 原图文件名及 Open-i 索引链接。Open-i 对该图集使用 CC BY-NC-ND 4.0。派生图像留存在运行证据中，报告保留生成它们的工具参数和工件索引。 [CheXbench](https://huggingface.co/datasets/StanfordAIMI/chexbench) · [Open-i 图像条款](https://openi.nlm.nih.gov/contactus) · [CC BY-NC-ND 4.0](https://creativecommons.org/licenses/by-nc-nd/4.0/)

记忆实现固定在 MemEvolve 提交 `078e18cb6153fdc5b888308349cb6771eb7bde8f`。 复现使用本项目的 R54 工具运行环境、相同冻结清单、已验证的 MiniLM 权重和对应 API 配置。 [MemEvolve 上游源码](https://github.com/dorain123/MemEvolve/tree/078e18cb6153fdc5b888308349cb6771eb7bde8f)
