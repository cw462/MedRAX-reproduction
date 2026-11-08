claim_supported：**partial（实质更接近 null/不显著）**

**支持**
- M43→M43-IM-GT：466→468/618（5纠正/3损害/net+2）；macro 77.08→77.25、micro 75.40→75.73，方向为正。
- 全部8处变化集中在130个fresh重复图像（position 2），与"仅同图前序可收到真值反馈"一致；488复用预测按设计冻结。
- 5纠正中至少2例（slake_0097、openi_0303）reason 明写"prior reference annotation…"→证实GT确被读入并改变回答；openi_0310/0315 亦与反馈答案文本一致（叠加工具定位）。

**不支持/削弱**
- 配对CI含0：micro_pp[-0.501,1.278]、macro_pp[-0.717,1.092]，不显著。
- 无同期无GT对照臂（M43/R45为历史单样本）；R45对比8纠5损net3混入R45技术性null恢复，非纯GT因果。
- 3损害中2例（openi_0309/0321）反馈文本恰为当前正确答案，模型仍选错→反馈非总能救回；slake_0061 把前序"no"文本抄成错误答案。
- "87当前ref文本匹配前序反馈"为事后描述性诊断（评分阶段读ref），非来源选择/因果；同措辞17对net+1、其余601也net+1，效应不集中于措辞重叠。
- 1例choice域无效（0231：A yes/B no、ref A，旧B.no/新A.no皆错）计错。

**缺失证据**
同期同采样无GT反馈对照；独立完整性审计（EXPERIMENT_AUDIT.json缺席→完整性provisional/no audit）；语义等价判定；独立公开复现（导出进行中）。

**建议修订**
改为"无显著改善"：618例固定在线反馈队列中macro/micro仅微升(+0.175/+0.324pp)、net+2，但CI含0且无同期对照；暴露基准的oracle反馈下效应部分来自直接标签抄写，应作null/探索性结论，不作因果、泛化或SOTA断言。

**未来假设（均未执行）**
1. 加同期无GT对照臂，分离GT记忆与工具/采样噪声。2. 消融：仅prior模型输出 vs 仅GT vs 均无，量化oracle泄漏。3. 语义等价匹配+更大重复图像集，检验是否特定于atelectasis措辞重叠。

**confidence**：低-中
**scope/identity limits**：AI研究评审（非临床放射学判定）；仅据所给记录并核验 summary.json 与 score 脚本；未做独立完整性审计。
