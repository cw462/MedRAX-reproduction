# 原生接入契约与文件边界

## Editable agent API

这些函数是固定程序入口，不代表只准修改四个prompt。它们的函数体及导入的整套harness代码可进化。

```python
initialize(state_dir: Path, services) -> dict | None
predict(case: dict, state_dir: Path, services) -> dict
observe(case: dict, prediction: dict, feedback: dict, state_dir: Path, services) -> dict | None
migrate(state_dir: Path, services) -> dict | None
```

predict 返回 answer 字符串及真实 trace（list/dict）。当前题 reference 不进入predict。observe 在预测锁定后接收 {correct,reference}，调用现有writer，不补改原预测。migrate 应确定性、可重入、向后兼容；不要随意清空记忆或调用未知模型重写整个库。源码只读，状态仅写 /state。

所有可持久状态必须进入 state_dir：图、向量索引、检索次数、去重表、策略相关缓存等。不得使用全局共享数据库、临时全局singleton或同时向两组写一份memory。

## Trusted services

native_bridge.create_services(gateway_url, model, limits, seed) 返回原M5需要的模型/工具客户端以及 usage_receipt()。网关必须是外部受保护服务，固定Qwen和现有医学工具；不得把全量题库、参考答案、任意文件读取能力交给候选。图片传输应绑定当前挂载原图字节，不以文件名推断另一个同名图。

usage_receipt() 至少返回：

```json
{"total_tokens": 123, "model_calls": 2, "tool_calls": 1}
```

这是示例结构不是实测用量。服务端强制预算、记录实际模型标识、token和工具调用。不能信任候选自行填报的“0 token”。强对抗设置还应加入主控侧验签或回查网关账本；本包没有宣称 Python 对象本身能抵御任意恶意猴补丁。

底层服务可重用现有模型调用与工具进程，不必重新加载工具模型。容器默认无GPU直通，计算密集的医学工具可在原有服务端运行。

## Docker boundary

使用确定镜像digest；仅暴露当前候选、当前状态副本、当前图像、当前请求和只读trusted_runtime。无原始API key环境、无整个仓库或run目录挂载。专用internal网络仅到受限gateway。容器只读根文件系统、非特权用户、无Linux capabilities、pid/memory/cpu限制和超时。

内部网络不自动保证网关不能代理互联网；需要服务端allowlist与权限验证，记录到sandbox_gateway_report。没有这一证据不得通过freeze。

## Protected scorer

native_score.py 是主控侧程序，不可被改进器编辑。stdin：{id,dataset,options,answer,reference}；stdout：单个 {correct:0|1,metric_id:...}。保持原有计分协议。stderr可记录故障但不能写凭据。没有真实绑定时必须报错。

## 预测与写入不可合并

如果旧M5的run函数内部自动获取标签并写记忆，应拆分外层接口但保持题内动作不变。预测必须持久化后才能调用评分和writer。不能把全部带标签case records一次性交给原runner再声称隐藏了当前标签。

## 初始等价性与哈希

首次生成的两份空记忆文件树必须相同；数据库中的时间戳/绝对路径等非语义字段需要规范导出，不能因此禁用一致性检查。之后每步先复制独立字节再执行，避免SQLite/WAL或向量库共享句柄。worker禁止写源码pycache，输入和候选树按SHA256核对。

每份上线验收JSON须包含status、passed_checks、evidence_files，证据可以是测试日志、源路径映射、图像哈希比对和真实工具轨迹。不能只填“passed”却没有测试。
