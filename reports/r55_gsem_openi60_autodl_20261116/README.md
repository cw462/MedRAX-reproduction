# R55 M14 GSEM · AutoDL OpenI-60

| 主回答模型 | 答对 | 准确率 | 主模型调用 | 工具调用 | 工具失败 | 到最后一题落盘 |
|---|---:|---:|---:|---:|---:|---:|
| Qwen3.6-Flash | 35/60 | 58.3% | 182 | 105 | 3 | 9.8 分钟 |
| DeepSeek V4.1 Flash | 26/60 | 43.3% | 60 | 0 | 0 | 2.6 分钟 |

逐题配对中，两组共同答对 14 题、共同答错 13 题。Qwen 独对 21 题，DeepSeek 独对 12 题。两组各有 60 条预测、60 条检索和 60 条反馈更新记录，均正常退出。

两组用相同的 OpenI 60 题、原图、题序、11 个工具、18 个经验节点、41 条初始边和逐题更新规则。标注在当题预测落盘后释放。RTX 6000D 上的工具由现有常驻进程执行，胸片专家是 StanfordAIMI/CheXagent-8b，版本为 `4934e91451945c8218c267aae9c34929a7677829`。Qwen3.6-Flash 和 DeepSeek V4.1 Flash 通过同一 Token Plan 调用，后者固定到 `deepseek-v4.1-flash-1017`。模型辅助角色沿用实验室配置。初次启动缺少辅助配置链接，在付费请求前退出，补齐后重启。

工具由模型按提示自行选择。DeepSeek 60 题均在首轮给出可评分答案，未发出 `calls`。工具参与度是两组观察到的行为差异。此处的配对分差反映这批题上的整套运行表现。

请求用量、模型返回标识、工具路线和计时见摘要。记录的 token 统计可与 Token Plan 扣费对账。 [摘要](summary.json)

逐题记录包含题干、完整选项、预测、对错、工具观察和 Open-i 原图链接。完整调用记录和工具图像保存在 AutoDL，正分段同步到 H 盘。 [逐题记录](per-question.json) · [初始图](initial-graph.json) · [运行源码](source)

题目来自 Stanford AIMI CheXBench。胸片来自 Indiana University 医院网络，由美国国立卫生研究院国家医学图书馆（NLM, NIH, Bethesda, MD, USA）发布。 [CheXBench 数据卡](https://huggingface.co/datasets/StanfordAIMI/chexbench) · [Open-i 数据来源](https://openi-vip.nlm.nih.gov/faq) · [Demner-Fushman 等](https://pubmed.ncbi.nlm.nih.gov/26133894/)
