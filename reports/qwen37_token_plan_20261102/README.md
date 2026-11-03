# Qwen3.7-Plus / Token Plan：完成结果与完整证据

**阶段0–2已于北京时间2026-11-03 09:19:49完成，流水线正常退出（0）。固定主结果K9为296/402（73.63%），原D单答为295/402（73.38%），净增1题（+0.25个百分点），病例bootstrap 95%区间跨0。没有明确证据表明九次投票提高了本调参集的准确率。** 同温度缓存K1为297/402，K9少对1题；不能从K曲线事后挑最高分替代预设K9。

本轮共发出 **4,484次请求，0次额外重试**。阶段2的3个请求失败和5个无法解析答案均保留，九票分母固定为9；所有402题都有最终投票答案。原始生成提交为 [`3916851`](https://github.com/cw462/MedRAX-reproduction/commit/3916851437e1177f15f358bf49641b3e34844926)，实际运行修订逐项公开，未重发已发送的失败样本，也未改写其终态。

## 完整分母结果

|阶段/配置|正确/计划题数|准确率|最终题级缺答|
|---|---:|---:|---:|
|阶段0：新模型D，历史60题重新生成|48/60|80.00%|0|
|阶段1：原D，T=0.2|295/402|73.38%|0|
|阶段1：HiRes+明确图号，T=0.2|295/402|73.38%|0|
|选中单答：D|295/402|73.38%|0|
|阶段2：K1，T=0.7|297/402|73.88%|0|
|K2|296/402|73.63%|0|
|K3|296/402|73.63%|0|
|K4|295/402|73.38%|0|
|K5|296/402|73.63%|0|
|K6|295/402|73.38%|0|
|K7|295/402|73.38%|0|
|K8|297/402|73.88%|0|
|**K9（预先固定主结果）**|**296/402**|**73.63%**|**0**|

HiRes与D净差0题，未达到至少多对7题的晋级标准，因此自动选择D。K9对原D、选中单答D、同温度缓存K1的三个对照及纠正/误改、病例bootstrap区间、McNemar检验见[结果分析](results_analysis.md)和[机器可读汇总](analysis_summary.json)。原D仅在其答案属于并列领先选项时裁决平票；其余平票按固定选项顺序解决，不无条件回退D。

343题九票全体一致，其中78题仍然错误。这提示一致性不能代替正确性；≤6/9主分歧阈值、≤5/9和≤7/9敏感性分析，以及7–8/9高一致、技术不完整分组和AUROC见[分析报告](results_analysis.md)。没有定义的AUROC保留null。

## 可逐题检查的公开证据

|内容|评分与完整证据|
|---|---|
|阶段0：60题|[结果](phase0/README.md) · [指标](phase0/metrics.json) · [题干、选项、原图、逐次请求与响应](phase0/evidence/cases.json)|
|阶段0：2题HiRes技术检查|[独立导出](phase0/smoke/evidence/README.md) · [完整2题](phase0/smoke/evidence/cases.json)|
|阶段1：D/HiRes各402题|[结果](phase1/README.md) · [指标](phase1/metrics.json) · [逐题评分](phase1/per_question.json) · [完整证据](phase1/evidence/cases.json)|
|阶段2：402题×9次|[结果](phase2/README.md) · [指标](phase2/metrics.json) · [逐题评分](phase2/per_question.json) · [完整证据](phase2/evidence/cases.json) · [投票诊断](phase2/vote_diagnostics.json)|

[公开导出方式、数据出处与文件清单](publication_notes.md)记录本次发布转换。每份evidence目录含显式文件清单、完整题干与选项、原图来源、每次实际请求参数、响应、usage、采样序号、图号绑定及错误。图像保留实际请求字节并使用相对引用；复用已有公开图片，不重复存储相同图像。阶段2的D锚以相对路径引用阶段1原预测，不重复发请求或把费用算两次。API凭据、账户账本、账户累计金额和私有绝对路径不公开。

## 用量、时间和故障

完整成本与时间分解见[执行汇总](execution_summary.md)及[JSON](execution_summary.json)。原始开始至最终自动评分结束约 **9小时35分7秒**，其中保存事件所界定的五段停止至恢复约 **6小时14分56秒**；扣除这些停机区间约 **3小时20分12秒**，后者仍含本地处理与请求间开销，不是纯API时间。

本轮保存usage按继承4/12 CNY每百万token计算为 **21.930532 CNY记账代理**；运行器记录的本轮保守占用为 **23.570644**，差 **1.640112**，包括一次无usage的媒体超时及两次已收响应后结算失败的保守预留差。逐请求已保存结算合计 **22.472916** 与运行器占用的差 **1.097728** 是另一个口径，不能混同。原新增200授权不增加，前轮占用3.163412仍计入，剩余增量记账额度173.265944。

**这些金额只是记账代理，不是Token Plan实际费率、实际实扣、收费上界或Credits换算。真实Credits用量没有证据，标为未知；运行器没有自动购买额度。** 各阶段和2题smoke单独纳入用量，阶段2复用的D不重复累计。

|记录|处理与最终影响|
|---|---|
|[01 媒体下载超时](recovery_history/01_media_download_timeout/README.md)|精确HTTP400误归全局配置错误；窄修复分类，保留原失败，无重发。|
|[02 结算checksum异常](recovery_history/02_ledger_checksum/README.md)|已保存响应与usage，失败终态保留；原接口保守pending恢复。|
|[03 未发送预留异常](recovery_history/03_unsent_reservation_checksum/README.md)|新增严格未发送恢复入口；请求尚未发送，没有新增缺答或补票。|
|[04 结算及启动阻断](recovery_history/04_ledger_settlement_checksum/README.md)|已保存响应，第三个请求失败保留；一次正常恢复被构造接口拒绝，当时无新增API。|
|[05 用户授权定位恢复](recovery_history/05_authorized_ledger_diagnosis/README.md)|恢复单个JSON结束符，当时候选匹配原摘要；保留已有ack后从下一样本继续。物理原因及此前进程内checksum原因仍未知。|
|[06 用户要求取消账本检验](recovery_history/06_disable_ledger_validation/README.md)|2901个阶段2终态后，通过请求发送前的计数锁暂停安全切换，08:45:35恢复；没有新增缺答。|

修订06明确取消V12启动/commit的checksum、schema、policy快照、全表金额一致性及继承账本checksum比较，不恢复或增加替代扫描。必要JSON/金额读取、身份anchor、锁、cap、预留结算算术、继承费用、重复请求拒绝、硬token/请求上限及pending保守恢复保留。不能称全程完整性保护未变。上述技术恢复使固定实验得以完成，不是模型、输入或投票方法带来的收益。旧事件文件保留其当时状态；最终状态见[流水线完成记录](metadata/pipeline_status.json)。

完整[运行修订元数据](metadata/runtime_amendments/)、[未发送恢复确认](metadata/unsent_recovery_acknowledgements/)、[已有确认后启动恢复](metadata/acknowledged_startup_recoveries/)和[操作者暂停回执](metadata/operator_counter_lock_pauses/)一并公开。原失败/无法解析答案从未被替换为后续成功响应。

## 协议与结论范围

使用 **99病例/402题调参集**，**241病例/1002题留出集未运行**；402题参与HiRes选择，不能宣称独立泛化。没有启动其他模型、Thinking、TextOnly、工具、集成或2500题全量实验。本轮没有工具收益的实证。旧qwen3-vl-plus的42/60仅见[历史运行](../qwen_agent_v2_20261102/README.md)，不混入本轮预测与投票。

- [预先固定协议与统计规则](protocol.md) · [实际配置快照](configuration/README.md) · [流水线冻结协议](metadata/pipeline_protocol.json)
- [公开模型配置](../../configs/qwen37_token_plan_profile.json) · [阶段配置生成器](../../experiments/configure_qwen37_token_plan.py)
- [自动流水线](../../experiments/run_qwen37_token_plan_pipeline.py) · [独立样本运行器](../../experiments/run_sampled_vlm.py) · [阶段运行器](../../experiments/run_vote_phase.py)
- [独立评分器](../../experiments/score_votes.py) · [完整证据导出器](../../experiments/export_vote_phase.py)

阶段0仅做新模型技术检查，无旧40–44准确率门槛。单答T=0.2、九采样T=0.7，top_p=0.95、max_tokens=2048、timeout=120、SDK重试0、enable_thinking=false；每次是独立上下文。HiRes比较同时改变图像参数与图号标注，不能据此拆分两者单独作用。投票实验不改变输入配置；K9对T=0.2单答仍混有采样温度差异，同T的K1对照用于限制这一归因。
