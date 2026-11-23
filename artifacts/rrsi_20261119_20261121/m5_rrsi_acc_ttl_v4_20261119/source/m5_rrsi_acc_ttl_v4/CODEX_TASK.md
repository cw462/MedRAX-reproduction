# 服务器 Codex 实施任务：M5–RRSI–Acc–TTL v4.0

请先完整读 README.md、docs/NATIVE_CONTRACT.md、docs/EXPERIMENT.md，再实施。不要在 v3.1 上继续堆四字段优化器。本包的搜索调用必须走真正的 `rrsi.loop.Run.round()`。

## 0. 不可改变的用户决策

只做固定机制 M5 与 M5-RRSI-Acc-TTL，不做 GEPA。使用现有 Qwen3.7-Plus 与医学工具，原始 848 题清单以实际文件为准。按原题序逐题运行；本题两组预测均锁定后，立即释放本题反馈并各自更新记忆；不等关联题整组完成。初始记忆为空，不导入已经看完这批题的历史库。关联关系只记录，不重排、不延迟。

准确率是唯一晋升收益；更省成本、新颖或更简短不能补偿掉分。历史回放不计入主成绩，不读取未来题标签。原始图像、选项顺序、评分口径不能改变。不能把未跑的医学性能或未完成的上游联调写成成功。

## 1. 只读定位原工程

找到真实 M5 runner/provider、成功轨迹 writer、图构建/检索、主模型客户端、工具注册与服务、图像解析及评分器。记录路径、原始 commit、模型请求/返回标识、工具版本、所有单题限额和随机设置。不要杀正在运行的 M5 进程、重启 GEPA或覆盖旧结果。

之前出现过 EvolveLab/providers 命名，但不能从旧 Windows 路径猜 Linux 路径。确认 predict 内是否自动写入反馈；若有，应在保持题内推理不变的前提下拆为 predict 和 observe。

## 2. 获取、锁定官方 RRSI

在新目录执行 `scripts/fetch_upstream.py --dest <新目录> --ref <经核对的ref>`。默认 main 只在这一步解析，脚本保存完整 commit 与核心源码校验和，正式运行不再自动拉最新。保留上游 LICENSE。

本包制作环境没有成功 clone 上游，不存在已替你验证完的 GitHub commit。必须真实下载，跑官方 tests 并另跑本包的 check_real_upstream.py。若当前上游 API 已改变，停止并适配；不要删除版本/接口检查去冒充兼容。

## 3. 移植真实 M5，而不是留下薄壳

把原始 M5 可进化的实际 prompt、控制流、上下文处理、writer、图维护、检索、工具封装与技能代码，复制并保持包结构到 `domains/med_m5/harness/`。实现 agent.py 的 initialize/predict/observe/migrate 四个固定入口；这是四个程序调用接口，不是四类文本修改字段。

所有需要进化的模块都必须在候选树内部实际导入。禁止 agent.py 只调用全局旧 provider，导致候选修改 writer.py 根本不执行。原始医学工具模型与服务保留在受保护服务层，不把工具权重或评分逻辑塞到可编辑目录。

先建立 H0 与原生 M5 的运行等价性：同原图、同模型/工具/解码/提示、同记忆读写时序；检查实际加载文件路径和哈希。模型随机性下不要求两次云端输出逐字相同，但不得因为适配器额外加入新推理规则。把映射和实证写入 integration_report.md。完成后提交 H0，填配置 initial_commit 的完整40位SHA。

开放 scope 是真实 harness 源码，不再限制四文本字段或2400字符。官方退火预算约束一次候选的独立修改数量。模型权重、外层改进器、评分器和反馈门控仍不可编辑。

## 4. 接通受保护运行环境

复制 sandbox/worker.py 和完成后的 integration/native_bridge.py 到独立 trusted_runtime 目录。native_bridge.create_services 对接现有模型与医学工具的固定服务，返回被外部网关强制限额的服务对象。细节见 NATIVE_CONTRACT。

候选容器只挂载当前候选源代码、当前单题输入和原图、隔离的可写记忆副本以及受保护 worker/bridge。不能挂载整个项目、全量题库、参考文件、其他组状态、Docker socket或用户密钥。使用带 digest 的医学运行镜像，专用 internal Docker 网络和受限 gateway。Gateway 不能充当可访问任意URL/文件的通用代理，须固定模型和工具版本，并记录真实 usage。

对每题反馈访问、越界路径、模型替换、无限工具循环、超限、同图下一题即时读到前题记忆做探针测试。Docker不是恶意代码绝对安全证明；若现有服务不能隔离权限，不要以“提示词禁止”为唯一保障。

如果原生服务需HTTP接口或内部调用，你可以实现网关适配，但不能把原生工具变成简单大模型文字模拟。确认网关从服务端强制限额，不能只相信候选传来的 limits。

## 5. 固定评分与真实数据

将现有题清单导出为 public_cases.jsonl，每行严格为 id/dataset/question/options/images/group_keys（可选），options 是有序 [{label,text}]。不允许 public 文件中夹带 reference/correct_answer。原图使用真实文件字节。

私有 references.jsonl 每行为 {id,reference}。保持原评分器的归一化、多选处理、错误输出政策和分母；在 integration/native_score.py 实际绑定，返回 {correct:0|1,metric_id:固定标识}。不要为了方便换成另一套 exact-match 或 LLM judge。必要时保留原任务题型信息，应同时正式扩展公开schema及测试，不能私加标签字段。

本版只实现 full_label，当前题锁定后释放标签。不同反馈强度不是一个运行中的开关。初始 H0 过去接触这848题的程度要披露。

## 6. 在线搜索、选择与迁移

每题反馈结束后，若还有后续题且轮次预算未用完，执行一轮官方 Run.round()。不额外加入30题预热/每10题；也不把该事件调度称为原版离线触发机制。

默认最近最多20题作为顺序回放窗口，当前版和候选都从同一个历史窗口开始前的实验组快照出发，边回放边按已释放标签写记忆，各2次。20是回放窗口，不是触发间隔。writer/图维护的改变会在该回放后续题产生效果。仅单题历史时，writer改变可能无法观察到收益；记录而非伪造提升。

候选必须兼容当前真实记忆，或提供确定性migrate；迁移在副本中检查，接受后采用该副本。拒绝候选不撤销本题已完成的原生写入，也不采用候选回放后的记忆。

每轮面板变了就重评父版本。选择只比较同面板/同起点的准确率；停滞信号基于已接受的配对收益，不能拿跨面板绝对准确率趋势判停滞。保留官方历史、component标签、探索与剪枝建议。

## 7. 预算与验收证据

先运行 budget 命令并把输出保存。默认847轮/2候选/20题/2重复的最大正常历史预测数100500，不含角色调用与失败重试。不要告诉用户只多跑848次。允许在首次计分前锁定较小预算，但必须说明达到轮数上限后策略不再进化，不可事后挑最佳预算同流结果。

配置中的 model_calls/tool_calls/output_tokens 是 null，必须填现有M5实际上限，不猜值。模型服务不通、图缺失、评分器未绑定时停止，不生成假结果。

建立配置要求的四份真实JSON报告，每份含 status=passed、passed_checks，以及指向真实日志/断言输出的 evidence_files；只改字符串不算验收。要求键见 m5rrsi/validation.py。check_real_upstream.py 会生成第四份；其他三份由原生测试生成。

## 8. 启动流程

```bash
python -m pip install -e .
python -m unittest discover -s tests -v
# 克隆并锁定官方后，运行官方 tests（有网络的服务器执行依赖安装）
# 然后：
python scripts/check_real_upstream.py --repo <repo> --lock <lock> --report <evidence/upstream_contract.json>
python -m m5rrsi.cli prepare --inputs <public_cases.jsonl> --out <stream.json>
python -m m5rrsi.cli budget --config configs/ttl_official.json
python -m m5rrsi.cli validate --config configs/ttl_official.json
python -m m5rrsi.cli freeze --config configs/ttl_official.json
python -m m5rrsi.cli run --config configs/ttl_official.json --stop-after 5
python -m m5rrsi.cli run --config configs/ttl_official.json --resume
python -m m5rrsi.cli report --run-dir <run_dir>
```

--stop-after 是完成题数上限，不是改变正式流长度；第5题后该做的搜索仍在续跑前完成。暂停后只在代码/数据/配置不变时resume。接入测试请用另行标记的数据；禁止看了正式前5题标签后改H0还声称原首遍结果。创建STOP文件在当前题/搜索完成后停止；不要在一个流未完成时展示为848题全量。

## 交付给用户

交付实际源码diff与上游SHA/哈希、H0 transplant map、运行冻结文件、原生验收日志、两组首遍锁定答案、各轮候选diff/审查/回放面板/分数/接受记录、模型及工具用量和最终主结果CSV。说明哪些东西未完成。不得把本包51项离线测试冒充上游联调或医学评估成功。
