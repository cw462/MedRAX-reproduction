# chexbench_openi_0209 · 误改

Which finding is in this chest X-ray?

| 选项 | 内容 |
|---|---|
| A | surgical instruments in the right lung |
| B | surgical instruments in the left lung |

参考标注 **B**。B0-F **B. surgical instruments in the left lung**，L1-F **A. surgical instruments in the right lung**。

![原图](../data/images/openi/images/CXR3006_IM-1388-1001.png)

## B0-F

主模型 4 次，工具 3 次，格式修复 0 次。运行器状态 `completed`。

[完整步骤](../B0/steps/chexbench_openi_0209.json) · [锁定首答](../B0/predictions/R55-M5-11tools-CheXagent8B/chexbench_openi_0209.json) · [工具回执](../B0/services/tool_selections/R49-AGENT/chexbench_openi_0209)

| 调用 | 请求 | 响应 | 协议事件 |
|---:|---|---|---|
| 1 | [请求](../B0/services/calls/R49-AGENT/chexbench_openi_0209/1/request.json) | [响应](../B0/services/calls/R49-AGENT/chexbench_openi_0209/1/response.json) | [协议事件](../B0/services/protocol_events/chexbench_openi_0209/1.json) |
| 2 | [请求](../B0/services/calls/R49-AGENT/chexbench_openi_0209/2/request.json) | [响应](../B0/services/calls/R49-AGENT/chexbench_openi_0209/2/response.json) | [协议事件](../B0/services/protocol_events/chexbench_openi_0209/2.json) |
| 3 | [请求](../B0/services/calls/R49-AGENT/chexbench_openi_0209/3/request.json) | [响应](../B0/services/calls/R49-AGENT/chexbench_openi_0209/3/response.json) | [协议事件](../B0/services/protocol_events/chexbench_openi_0209/3.json) |
| 4 | [请求](../B0/services/calls/R49-AGENT/chexbench_openi_0209/4/request.json) | [响应](../B0/services/calls/R49-AGENT/chexbench_openi_0209/4/response.json) | [协议事件](../B0/services/protocol_events/chexbench_openi_0209/4.json) |

![maira2_grounded_report · grounded_report.png](../B0/services/tool_cache/0fc0a3c8ec9732270e3da29715abd0b63258e164799aa90dce6d686fe5821bc2/artifacts/grounded_report.png)

## L1-F

主模型 3 次，工具 2 次，格式修复 0 次。运行器状态 `completed`。

[完整步骤](../L1/steps/chexbench_openi_0209.json) · [锁定首答](../L1/predictions/R55-M5-11tools-CheXagent8B/chexbench_openi_0209.json) · [工具回执](../L1/services/tool_selections/R49-AGENT/chexbench_openi_0209)

| 调用 | 请求 | 响应 | 协议事件 |
|---:|---|---|---|
| 1 | [请求](../L1/services/calls/R49-AGENT/chexbench_openi_0209/1/request.json) | [响应](../L1/services/calls/R49-AGENT/chexbench_openi_0209/1/response.json) | [协议事件](../L1/services/protocol_events/chexbench_openi_0209/1.json) |
| 2 | [请求](../L1/services/calls/R49-AGENT/chexbench_openi_0209/2/request.json) | [响应](../L1/services/calls/R49-AGENT/chexbench_openi_0209/2/response.json) | [协议事件](../L1/services/protocol_events/chexbench_openi_0209/2.json) |
| 3 | [请求](../L1/services/calls/R49-AGENT/chexbench_openi_0209/3/request.json) | [响应](../L1/services/calls/R49-AGENT/chexbench_openi_0209/3/response.json) | [协议事件](../L1/services/protocol_events/chexbench_openi_0209/3.json) |

![xray_phrase_grounding · grounding_1e4e430d.png](../L1/services/tool_cache/0277f7f7c2969497d3fdec1665100a6f7e58b3430623fa0440ea0cce3c689ac4/artifacts/maira_runtime/overlays/grounding_1e4e430d.png)
