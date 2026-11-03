# 完成后的公开导出说明

本轮所有付费生成与自动独立评分均先完成，随后才进行本次导出、分析和GitHub发布。原始终态、答案、失败、usage与运行参数未修改；没有再次调用模型、重新运行score_votes或检查账户账本。

## 公开内容及映射

- phase0/evidence：60题；phase0/smoke/evidence：独立2题HiRes技术检查。
- phase1/evidence：402题，两组单答D与HiRes。
- phase2/evidence：同402题的9次独立采样S0；原D以相对路径引用phase1/evidence/arms/D，选中单答也是D，没有单独的重复组。
- 每份evidence含cases.json、assets.json、phase_manifest.json、cost_summary.json及publication_manifest.json。后者显式列出该份导出的所有文件；完整出站列表见[publication_files.txt](publication_files.txt)。
- Base64图片变为指向同一原图字节的相对路径；阶段0复用既有公开图片，阶段1按不同字节导出原图，阶段2复用阶段1图片；图号、源文件名、请求顺序和图像metadata继续绑定。没有重新压缩/绘制图片。
- 私有根路径、凭据、账户账本和账户累计金额被删除/脱敏。原输入/来源的相对字符串可作为溯源标识，不代表独立可启动的运行配置；公开可导航文件路径由cases.json与phase_manifest.json提供。
- metadata包含最终状态、冻结实现commit、运行修订、stop event及确认、未发请求恢复和操作者安全暂停回执。历史事件的原状态不改写，最终状态另见pipeline_status.json。

## 仅用于导出的代码修复

完成后更新export_vote_phase.py以支持public_run相对引用并核对已有公开锚的内容，删除账户累计预算字段，给公开generation_gate使用正确相对路径。另修复出站检查误把模型选项标题“F:”后换行的JSON转义当作Windows绝对路径的问题：检查真实字符串叶节点而非序列化转义文本，模型原文保持原样。这些都只发生在离线导出，不是生成过程中的第07次运行修订，不改变成绩或投票。

导出器按每阶段已完成manifest执行，未打开参考答案或账户账本。结果汇总脚本仅读取已完成的评分文件，统计量从自动评分原件复制；不会再次评分：

```powershell
python -X utf8 experiments/export_vote_phase.py --manifest <local-export-manifest> --out <phase-report>
python -X utf8 experiments/summarize_qwen37_voting.py --scored-root reports/qwen37_token_plan_20261102 --out reports/qwen37_token_plan_20261102
python -X utf8 experiments/summarize_qwen37_execution.py
```

## 数据出处

题干、选项和图像沿用本仓库所使用的ChestAgentBench材料；保存原case_id、源文件名及图号，原始数据版本与病例划分见[数据划分说明](../multimodel_vote_gain_20261102/data_split.md)。上游为[wanglab/chest-agent-bench](https://huggingface.co/datasets/wanglab/chest-agent-bench)，已记录版本为921e60440927f9893228d843c0206b755744252a；原始病例来自Eurorad。既有[数据来源与第三方材料声明](../v11/data-provenance.md)说明来源及代码许可证与数据权利的区别，本次不把第三方题目或图像重新许可为仓库代码许可证。没有增加Eurorad文章全文。图像按用户授权公开实际benchmark输入；没有进行患者身份推断，也不宣称本次完成了新的去标识认证。
