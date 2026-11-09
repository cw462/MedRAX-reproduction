# CLAIMS_FROM_RESULTS（结果到声明）

## 允许且已核验
- 三个流全新生成：CheX 618、SLAKE 114、VQA-RAD 116，共 848 个题目级记录；不是 848 个独立病例。
- 常用显式答案口径：CheX 465/618（历史整臂 M43 466/618，纠正 49 / 误改 50 / 净 -1）；SLAKE 113/114（M43 108/114，5/0/+5）；VQA-RAD 97/116（M42 100/116，4/7/-3）。M43 无独立 VQA 臂，沿用 M42 100/116。
- CheX R47 在线 GT 468/618 为次级、不同信息条件比较器，不替换、不隐藏损失。
- Skill 命中 505/618、0/114、0/116；同图记忆命中 130/618、84/114、58/116。SLAKE 零 Skill 命中的增益不能归因 Skill。
- 逐数据集报告宏/微、子集、word recall、成对问题级变化与成对图像/病例簇 bootstrap 描述区间（描述性，非病人泛化、非因果）。
- 失败与恢复历史如实：初始依赖缺失、q41 CUDA（1 次登记生产复试＋独立诊断）、120/150 两次 META schema、Embedding 400（原 body/usage 未知＋1 次充值后生产复试＋独立欠费诊断）、168 短语 EOS 策略修订、210 重复 adoption 两代表项选择。全部中间 raw1 保留，不称所有尝试 exit0。
- 首次证据推送 628617beb 在最终结果审阅之前；最终审阅发生在全部 848 题与首次推送之后、最终报告补充推送之前；远端核验被用户豁免。
- 资源/费用：主/元/embedding/工具分账来自保存 receipts；未知用量/费用、硬件价格、controller 总墙钟如实标 unknown；CLI 审查 USD/时长与推理 CNY 分列且非发票。

## 禁止（不成立/不得主张）
- 不得主张 Skill 单独因果、同预算 Skill 收益、闭卷/未见测试 SOTA、官方 SkeMex/Evo-MedAgent 复现、临床正确性或医学能力验证。
- 不得把 848 题合并为独立病例总体准确率；不得忽略 SLAKE/CheX-SLAKE 共享图与 VQA 同图复述依赖。
- 不得把首个预适配失败（manifest_semantic_input_order_changed）称第二套已完成成绩；不得把诊断输出当生产结果。
- 不得把修复 META/embedding 子集再次加费；不得把未知用量/费用读作 0 或免费。
- 不得声称审阅发生在首次发布之前、模型权重身份已独立鉴证、或已做字节/像素哈希/临床重读。

## 实际审查限制（审阅者原述）

未重跑代码、未新评分/推理/导出、未远端核验、未核临床图像、未鉴权模型权重、未做字节/像素哈希；模型身份为 CLI 配置别名 deepseek-v4-pro 而非权重鉴证；17 共享图/64 匹配题与 save-before-reveal 时序、以及 CheX 49/50 全量逐条，按已存协议与已存分数采信，未逐事件独立重算。


## 审阅后的报告器技术修复

实际最终审阅覆盖其提交版本。随后报告器在比较首题预测与嵌套保存事件时，因公开图片链接随文档深度不同而停止；复用既有公开图片语义规范化函数后，仍执行完整对象相等及其余原门槛。该小改未另行模型审阅，原预测、分数、参考和图片均未改，且未增加评分或推理。详见 FINAL_WRITER_TECHNICAL_CONTINUATION.json。

Post-review publication-only performance delta: identical ordered public image URL replacements now cache mappings and skip a literal anchor proven absent. Three new nested synthetic path-equivalence cases passed; original source and receipt retained. No model review, metric, prediction, export or inference was repeated.

The original final-follow-up prepare native session93625 was deliberately stopped after over18 minutes in its read-only gate (actual exit1, no manifest/allowlist). A technical continuation runs the same gates with the path cache optimization; its exact internal old gate position is unknown. This does not repeat any inference/private scoring/export/model review.

A second publication-only performance correction caches resolved asset targets once per dataset. The prior optimized prepare82168 was stopped with native1 and no outputs; its exact internal gate position remains unknown. Two distinct-parent construction witnesses passed, with one asset-map read; original sources and all stops are retained. The final follow-up reuses the actual completed prepare gate for sequential content/index/base-guard phases and stages changed/new report files plus fixed source/index entries, preserving the original full allowlist. These reporting deltas were not separately model-reviewed.
