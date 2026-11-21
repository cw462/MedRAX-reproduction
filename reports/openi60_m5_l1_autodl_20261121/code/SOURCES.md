# 核对过的原生接口与来源

核对日期：2026-11-21。以下固定 commit 用于源码静态核对。本包未下载或运行它们的完整依赖，实际运行读取用户服务器原生产环境，并将使用的源文件记录 SHA-256。

## 用户结果聚合

- https://raw.githubusercontent.com/cw462/MedRAX-reproduction/ed1cb3ac0866670c5f16b53c0e224e59b6d965cd/reports/qwen37_full848_gepa_20261120/README.md
- https://raw.githubusercontent.com/cw462/MedRAX-reproduction/ed1cb3ac0866670c5f16b53c0e224e59b6d965cd/reports/qwen37_full848_gepa_20261120/arms/M5/summary.json
- https://raw.githubusercontent.com/cw462/MedRAX-reproduction/ed1cb3ac0866670c5f16b53c0e224e59b6d965cd/reports/qwen37_full848_gepa_20261120/sources.json

## 原 M5 生产源码快照

固定 commit：`0c299c9820356849dee017bcb0bd8fedc2cd1e75`。
前缀：`https://raw.githubusercontent.com/cw462/MedRAX-reproduction/0c299c9820356849dee017bcb0bd8fedc2cd1e75/reports/r55_lab_m5_11tools_chexagent8b_20261115/source/`

| 文件 | 核对用途 |
|---|---|
| run_r55_11tools_m5.py | run_dataset(code,out,data,references,runtime)、首答/记忆检查点、七节点初始化、stdin两行key、GPU环境约束 |
| run_r55_full848_dataset.py | ARMS、COUNTS 原始常量 |
| score_r55_full848_dataset.py | 原 aligned_correct 评分，完整分母与反馈时间校验 |
| r55_memevolve_driver003.py | 原生 M5 初始化、检索、反馈后写入、工作目录与存储 |
| r55_memory_token_plan.py | 记忆模型路由由 native_root/jobs 标记决定 |
| queue_r55_11tools_lab.py | 原生产目录布局、plan路径与环境变量 |
| experiments/run_online_skill_r54.py | 实际 run_stream、原生反馈时序、输入字段与图像view路径约束 |
| experiments/skill_services_r55.py | Services继承链与execute工具接入 |
| experiments/skill_services_r54.py | 主求解器self.call(row,'R49-AGENT',n,messages)真实入口 |
| experiments/cxr_online_primitives_r49.py | schedule、原生image_key与previous_ids |
| experiments/online_memory_r49.py | ReferenceVault、锁定预测后释放反馈、同图过去题约束 |
| experiments/toolsets_r54.py | system/action消息、原图resolve路径约束、实际请求归档 |

未将上游完整文件复制进本包；新增代码是调用这些已有接口的包装器。上游代码、模型、数据的许可与访问条件继续按原项目执行。
