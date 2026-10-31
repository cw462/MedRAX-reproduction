# 冻结的知识与经验资产

[历史总索引](../README.md) · [导出清单](manifest.json) · [早期实验](../early-experiments.md)

这里保存实际运行所引用的本地传输快照。它们用于解释“模型检索到了什么、为什么这些内容可能没有帮助”，不是新训练结果或经临床专家认证的知识库。各次调用实际注入的内容应以 V9/V10 的逐题 checkpoint 为准；完整池不等于每次都注入。

| 资产 | 保存内容 | 解释边界 |
|---|---|---|
| [experience_pool.json](experience_pool.json) | 60 条训练轨迹的冻结结构化经验池，含 steps、terminal status、task outcome、source IDs 和原已有来源摘要 | 整题正确不能证明每一步观察正确；未标注的 step credit 仍为 unknown |
| [skills.json](skills.json) | 17 张技能卡、触发条件、动作、检查点、回退、来源轨迹和拒收统计 | 同一来源池的蒸馏表示；不是独立临床知识或已验证策略 |
| [clinical_cards.jsonl](knowledge_pack/knowledge/clinical_cards.jsonl) | 59 张临床知识卡及模态、前提、证据要求、局限、来源页码 | CT 规则不能自动迁移成胸片事实；缺少当前病例证据时不能据规则断言病灶存在 |
| [source_manifest.json](knowledge_pack/knowledge/source_manifest.json) | 16 份来源的题名、链接、版本、页码范围与原有权利说明 | 来源全文与 PDF 不随本次包复制；链接和页码用于复核 |
| [retrieval/](knowledge_pack/retrieval/) | 当时的 BM25、dense、RRF 检索源代码、配置、依赖，以及 hybrid/lexical 索引的卡片和元数据 | 不含 MiniLM 权重或 dense 向量文件；不能把成功检索视为准确率提升 |

原有 `sha256` 等字段只是当时保存的来源标识；本次发布替换了私有路径，**这些旧值不能用来认证脱敏后的公开文件字节**，也没有为发布重复扫描或重算账本。需要精确了解某轮输入时，先查看该轮的 effective configuration、retrieval checkpoint 和实际 messages。

本次未复制 264 页临床来源全文（`source_pages.jsonl`），也未复制文章 PDF、权重或神经索引向量。知识卡、出处页码和各轮实际注入的短内容足以回溯本轮检索行为；若重新构建全部检索资产，需按来源条件自行取得文献和模型。原包的 `PACKAGE_INFO.json` 与索引 metadata 保留其历史文件名，**其中提到的文件不代表已全部包含在本公开包中**。

复现导出器：[export_history_assets.py](../../../experiments/export_history_assets.py)。它只读取明确列出的设计文档及本地资产，不运行推理，不读取费用账本，不重新评分。
