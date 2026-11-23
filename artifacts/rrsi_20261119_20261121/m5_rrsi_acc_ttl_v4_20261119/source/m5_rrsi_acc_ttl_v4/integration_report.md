# M5-RRSI-Acc-TTL v4 接线

## 运行范围

新增运行仅为 Qwen3.7-Plus 的 M5-RRSI-Acc-TTL，`primary_arms=["rrsi_acc"]`。固定 M5 不重跑，已有成绩仅作历史对照。没有 GEPA 或新增离线训练、开发、测试划分。

每题按原题序预测并锁定，然后释放本题参考答案、评分、更新记忆。当前题写入结束后，只要仍有后续题和搜索预算就调用一轮官方 RRSI。主成绩仅计首遍锁定预测。

## 已接通的源码

- 官方仓库为 google-research/rrsi，提交 `be50316e1db05914068a973f322770ef08ed7ba1`。真实执行官方 `Run.round()` 两轮，验证提升接受、持平拒绝和版本继承。报告为 `evidence/upstream_contract.json`。该联调使用明确的脚本化响应和软件夹具，不属于医学评估。
- `native_harness/` 包含实际 M5 控制流、原生 prompt、输出解析、上下文、检索、成功轨迹 writer、图维护及 CerebraFusionMemory provider。实际模块导入来自候选树。映射为 `harness_transplant_map.json`。
- 图、向量索引、embedding cache、检索使用追踪、计数器、同图记忆和原生工具缓存均随当前状态快照保存。工具缓存由候选只读挂载，原生网关负责写入。
- `integration/native_gateway.py` 固定原模型及 11 工具版本，使用宿主控制 socket 注册当前单题。候选只得到当前 session URL，不得到 API 密钥、全量题库或参考库。实际模型 usage 在网关保存并由主控回查。
- `integration/native_score.py` 使用原 `cxr_author_alignment` 与 `r54_author_metrics.outcomes(...)[aligned_correct]`，依据锁定的 `terminal_raw` 评分。开放题、非法输出、重复答案字段和完整分母的原语义保留。

## 固定模型与资源语义

主回答为 Qwen3.7-Plus Token Plan，temperature 0.2、top_p 0.95、每响应 2048 tokens、关闭 thinking。单题主调用与工具调用次数沿用原生不限次。Verify 保留其独立 8192-token profile，不受主模型单响应额度误裁。

11 工具包括 chest_xray_expert、llava_med_qa、medgemma、llava_rad、medvlm_r1、maira2_grounded_report、xray_phrase_grounding、roi_crop、medret、reflect、verify。CheXagent 使用原版 StanfordAIMI/CheXagent-8b，revision `4934e91451945c8218c267aae9c34929a7677829`。

候选数值依赖按原环境记录为 Python 3.10.18、NumPy 1.26.0、SciPy 1.11.4、scikit-learn 1.7.1。CPU 检索 embedding 固定为原 all-MiniLM-L6-v2。Dockerfile 已提供，实际运行镜像 digest 需在目标环境构建后写入配置。

## 预算

已实际运行 budget 命令，结果保存于 `evidence/budget.json`。单组首遍 848 次病例预测，最多 847 轮、每轮 2 候选、20 题顺序回放窗口、2 次重复，最多 100500 次正常历史预测。角色请求、writer、失败重试和单题内部多次模型、工具调用另计。尚未冻结正式配置。

## AutoDL 部署

优先复用 AutoDL 已有的原题、原图、参考文件、模型权重和工具环境。`scripts/prepare_existing_autodl.py` 在目标服务器内按明确绑定的原生清单准备输入，不复制原图到本机，不生成替代病例。

AutoDL 开放后先核对现有文件和实际服务路径，填写网关绑定，构建并锁定候选镜像。用正式 848 题之外的少量真实病例做一次接线检查，确认原图、原生工具回包、记忆写入、同图下一题读取及原评分。完成所需真实证据后才提交 H0、填写其完整 commit、freeze 并启动正式流。软件夹具结果不能替代这些真实证据。

## 已知限制

原 M5 源码自动注入 7 个种子节点；本次按 v4 使用空初始记忆。它是明确的初始化协议差异，历史 M5 分数不能描述为新协议下的同起点配对对照。H0 源码此前用于这批基准，清空记忆不代表主模型或人工设计从未接触这些题。

当前尚未开放 AutoDL，目标端的原生调用、H0 接线证据、容器实际隔离和正式 H0 commit 均待完成。当前正式预测数为 0。
