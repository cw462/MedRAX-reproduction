# 原轮 A1：完成执行，但未形成有效的记忆实验

**402题实际技能注入为0，两折技能库均为空。本轮295/402不能证明SkeMex记忆有效或无效。**

确定的适配缺陷：正文过滤器检查整个技能草稿，连适配器刚写入的合法`source_trajectory_ids`也参与匹配，因此17次CREATE草稿被误判为题目ID泄漏而拒绝。保留的107次编码事件中，另90次为NONE。原始记录、失败草稿、预测与自动评分均保持不变；[原自动评分文本](generated_scoring_README.md)单独保存。修复仅把来源字段从正文过滤中移出，来源隔离校验保留；[修订01](../../runtime_amendments/01_provenance_guard.json)记录新`_r1`命名空间，共用原预算/请求计数，不增加对照组。两源库存在可用技能后才进入目标402题。

## 已观察到的结果

D与原轮A1均295/402（73.38%），纠正6、误改6、缺答0，净增0；病例聚类bootstrap 2000次的准确率差95% CI为−1.78至+1.54个百分点，McNemar p=1。它是未注入技能条件下的重复回答差异，不能归因于SkeMex。

对旧S1为33次纠正、17次误改，净增16题；旧HS为24/29，净减5题。这些组流程不同，而且本轮无技能，不能将这些比较表述为记忆收益或严格消融。99病例/402题已经历多轮开发，区间仅描述固定预测的病例抽样不确定性，不含训练/采样随机性，也不证明独立泛化。

## 输入字节限制

[实际请求图像变体](../request_image_variants.json)记录1次目标请求：`6374_8353801543173`，原文件与保存的实际请求字节不同；对应请求PNG的IDAT CRC校验失败，见[原样保存的异常字节](../invalid_image_bytes.json)。原生文件和保存的请求载荷字节均按各自SHA保留，未修复、替换或重新编码。差异出现的时点、供应商实际接收/解码的字节及底层机制未知，不能称硬件损坏，也不能将该请求认证为与原生文件相同的有效图像输入。主表分母仍402，不删除这题以改善得分。

## 成本、时间与完整证据

原轮实际1606次已完成请求：源预测/检索678次，编码/审查124次，目标检索/回答804次，无技术额外重试。输入1,438,347、输出112,766 tokens；7.106580 CNY仅为继承4/12费率的代理记账，实际Token Plan Credits未知。生成从20:29:57至21:39:33北京，69.59分钟。不要把402个目标episode当作全部请求数。

[402题题干、选项与原图](../cases.json) · [逐题预测及短依据](per_question.json) · [类别分层](categories.json) · [完整计量](metrics.json) · [实际请求索引](../query_to_calls.json) · [两折窗口演化](../window_records/) · [冻结库](../evolution/) · [导出资产](../assets.json)。未调用病史、医学工具、Flash、控制臂、保留集或全量。官方固定源码与本地神经嵌入适配边界见[计划](../../README.md)。

---

以下保留自动生成的数值表，解释以上述执行缺陷为准：

# Official SkeMex A1: completed crossfit evaluation

A0 is the user-confirmed direct D; no tool-agent baseline is claimed.

|View|Correct/402|Accuracy|Missing|
|---|---:|---:|---:|
|D_A0|295/402|73.38%|0|
|A1|295/402|73.38%|0|
|old_S1|279/402|69.40%|0|
|old_HS|300/402|74.63%|0|

|A1 versus|Corrections|Harms|Net|Case CI pp|
|---|---:|---:|---:|---|
|D_A0|6|6|+0|-1.78 to +1.54|
|old_S1|33|17|+16|+0.51 to +7.60|
|old_HS|24|29|-5|-4.95 to +2.26|

[Metrics/usage](metrics.json) · [Per-question predictions](per_question.json) · [Official categories](categories.json). New Skills use official modules with explicit local neural embedding/model-service adapters. No history or new tools. Source-fold supervised evolution and all meta calls count toward cost. Target utility is frozen. CNY is an inherited accounting proxy, not actual Token Plan Credits.
