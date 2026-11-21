# chexbench_openi_0185 · 误改

Which finding is in this chest X-ray?

| 选项 | 内容 |
|---|---|
| A | surgical instruments in the right breast |
| B | surgical instruments in the left breast |

参考标注 **B**。B0-F **B. surgical instruments in the left breast**，L1-F **A. surgical instruments in the right breast**。

![原图](../data/images/openi/images/CXR2687_IM-1158-1001.png)

## B0-F

主模型 3 次，工具 2 次，格式修复 0 次。运行器状态 `completed`。

[完整步骤](../B0/steps/chexbench_openi_0185.json) · [锁定首答](../B0/predictions/R55-M5-11tools-CheXagent8B/chexbench_openi_0185.json) · [工具回执](../B0/services/tool_selections/R49-AGENT/chexbench_openi_0185)

| 调用 | 请求 | 响应 | 协议事件 |
|---:|---|---|---|
| 1 | [请求](../B0/services/calls/R49-AGENT/chexbench_openi_0185/1/request.json) | [响应](../B0/services/calls/R49-AGENT/chexbench_openi_0185/1/response.json) | [协议事件](../B0/services/protocol_events/chexbench_openi_0185/1.json) |
| 2 | [请求](../B0/services/calls/R49-AGENT/chexbench_openi_0185/2/request.json) | [响应](../B0/services/calls/R49-AGENT/chexbench_openi_0185/2/response.json) | [协议事件](../B0/services/protocol_events/chexbench_openi_0185/2.json) |
| 3 | [请求](../B0/services/calls/R49-AGENT/chexbench_openi_0185/3/request.json) | [响应](../B0/services/calls/R49-AGENT/chexbench_openi_0185/3/response.json) | [协议事件](../B0/services/protocol_events/chexbench_openi_0185/3.json) |

![xray_phrase_grounding · grounding_83ce4f37.png](../B0/services/tool_cache/6b2a3a54d15b77bde135c65e8db4c5b45840e098ca2d0d710f6f925835aa51dd/artifacts/maira_runtime/overlays/grounding_83ce4f37.png)

## L1-F

主模型 5 次，工具 4 次，格式修复 0 次。运行器状态 `completed`。

[完整步骤](../L1/steps/chexbench_openi_0185.json) · [锁定首答](../L1/predictions/R55-M5-11tools-CheXagent8B/chexbench_openi_0185.json) · [工具回执](../L1/services/tool_selections/R49-AGENT/chexbench_openi_0185)

| 调用 | 请求 | 响应 | 协议事件 |
|---:|---|---|---|
| 1 | [请求](../L1/services/calls/R49-AGENT/chexbench_openi_0185/1/request.json) | [响应](../L1/services/calls/R49-AGENT/chexbench_openi_0185/1/response.json) | [协议事件](../L1/services/protocol_events/chexbench_openi_0185/1.json) |
| 2 | [请求](../L1/services/calls/R49-AGENT/chexbench_openi_0185/2/request.json) | [响应](../L1/services/calls/R49-AGENT/chexbench_openi_0185/2/response.json) | [协议事件](../L1/services/protocol_events/chexbench_openi_0185/2.json) |
| 3 | [请求](../L1/services/calls/R49-AGENT/chexbench_openi_0185/3/request.json) | [响应](../L1/services/calls/R49-AGENT/chexbench_openi_0185/3/response.json) | [协议事件](../L1/services/protocol_events/chexbench_openi_0185/3.json) |
| 4 | [请求](../L1/services/calls/R49-AGENT/chexbench_openi_0185/4/request.json) | [响应](../L1/services/calls/R49-AGENT/chexbench_openi_0185/4/response.json) | [协议事件](../L1/services/protocol_events/chexbench_openi_0185/4.json) |
| 5 | [请求](../L1/services/calls/R49-AGENT/chexbench_openi_0185/5/request.json) | [响应](../L1/services/calls/R49-AGENT/chexbench_openi_0185/5/response.json) | [协议事件](../L1/services/protocol_events/chexbench_openi_0185/5.json) |

![maira2_grounded_report · grounded_report.png](../L1/services/tool_cache/0e99a4414f8251e904ef3c5a9e5a10bc0b1caff463d8be373b8d9e2578fb9284/artifacts/grounded_report.png)

![xray_phrase_grounding · grounding_f3f06818.png](../L1/services/tool_cache/375dc6450b562da1b58cc9a9fd6301cec82ea8d0e0a2da030ba0dff326bd5996/artifacts/maira_runtime/overlays/grounding_f3f06818.png)

![roi_crop · original.png](../L1/services/tool_cache/c5bb1a8ed47fcc410cca248844417de1ffef6855854844a22c6fbf052ace2de3/artifacts/original.png)

![roi_crop · roi_context.png](../L1/services/tool_cache/c5bb1a8ed47fcc410cca248844417de1ffef6855854844a22c6fbf052ace2de3/artifacts/roi_context.png)

![roi_crop · roi_zoom.png](../L1/services/tool_cache/c5bb1a8ed47fcc410cca248844417de1ffef6855854844a22c6fbf052ace2de3/artifacts/roi_zoom.png)
