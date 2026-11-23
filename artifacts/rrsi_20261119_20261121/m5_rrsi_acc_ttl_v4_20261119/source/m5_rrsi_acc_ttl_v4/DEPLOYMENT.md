# M5-RRSI-Acc-TTL v4 MedRAX 接线包

新增实验仅为 Qwen3.7-Plus + M5-RRSI-Acc-TTL。固定 M5 不重跑。源码准备完成，正式 H0、目标运行配置及真实医学接线证据尚未冻结。

包内包括官方 RRSI git bundle、17 个核心源码的锁文件、真实 M5 editable harness、受保护的模型/工具网关、原评分器、Dockerfile、配置模板、软件测试和源码差异。无模型权重、凭证、病例原图或私有参考答案。

## 目标服务器操作

1. 在新的独立目录解压软件包，不覆盖现有实验。
2. 用 scripts/fetch_upstream.py 获取官方提交 be50316e1db05914068a973f322770ef08ed7ba1。网络不可用时可从 evidence/rrsi-official-v4.git.bundle 还原同一官方仓库，核对已有官方锁文件，保留 LICENSE。
3. 将 native_harness 放入官方 checkout 的 domains/med_m5/harness。源文件、原生算法和初始化差异的映射见 harness_transplant_map.json。
4. 只读定位目标服务器已有的 848 题、原图、参考文件、11 工具解释器和原权重。原版 CheXagent 必须为 8B/4934e91。按实际路径填写 configs/native_gateway.binding.example.json，不把示例路径视为已经存在。
5. scripts/prepare_existing_autodl.py 读取显式指定的原生 manifests/data/references 绑定，在目标服务器内准备公开输入、私有参考和受保护当前题 metadata；原图原地复用，不复制到本机。
6. 用 integration/Dockerfile 构建候选镜像，写入其完整 sha256 image ID 或 repository digest。创建专用 internal Docker network，网关只在此网络的网桥接口监听。候选无 GPU、密钥、Docker socket、题库或参考库挂载。
7. 以目标原生环境启动 python -m integration.native_gateway --config <实际网关配置>。控制 socket 只给宿主主控，候选得到单题 session URL。sandbox/worker.py 与 integration/native_bridge.py 复制到独立 trusted_runtime。
8. 用正式 848 题以外的少量真实病例做一次最小接线检查，核对原图、实际工具观察、写入及下一题读取和原评分。生成真实证据后提交 H0，填 initial_commit。软件测试不替代真实医学调用。
9. 运行 validate、freeze、run --stop-after 5，再在配置、代码和数据不变时 --resume。第 5 题后的搜索照常完成，不把这 5 题作为调参用例。

## 本次协议

primary_arms=["rrsi_acc"]。单题主模型和工具总次数沿用原生不限次，每次主响应 2048 tokens。Verify 使用原独立 8192-token profile。每题先锁定预测，随后立即反馈并更新本组记忆，不等待同图关联题整组结束。

原生 M5 有 7 个种子节点，本次按 v4 使用空初始记忆。这一初始化差异应披露，已有 M5 分数作为历史对照，不作为新空记忆协议的配对成绩。

默认预算是 848 次首遍预测和最多 100500 次正常历史回放预测，另计 writer、角色调用及重试。正式预算在首次计分前冻结，尚未运行正式病例。

## 证据

integration_report.md 记录当前边界。evidence/upstream_contract.json 证明实际调用官方 Run.round()；其软件夹具 H0 commit 不可用作正式 H0。其余证据区分软件测试与目标服务器实际接线。正式预测数为 0。
