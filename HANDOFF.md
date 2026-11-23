# 医影 RAG 项目交接文档（2026-11-23 16:20 UTC+8）

## 0. 这份文档给谁
给"在另一台电脑上用 DeepSeek Harness 继续接手的 agent"。
读完这份 + `REPORT.md` + `results/` 下的 JSON，就能无缝继续。

---

## 1. 项目目标
在冻结的 848 道放射学 VQA 题（SLAKE 114 / VQA-RAD 116 / CheXBench 618）上，
评估"检索增强（RAG）+ 视觉工具（检测器/分割）"能给 DeepSeek-V4.1-Flash 和 Qwen3.6-Flash 带来多少准确率提升，
并定位失败原因、给出可落地的改进工具。

对应两条基线：
- Qwen3.6-Flash 8 工具 M5（AutoDL 跑）: 658/848 = **77.59%**
  - CheXBench 451/618 = 72.98%，SLAKE 108/114 = 94.74%，VQA-RAD 99/116 = 85.34%
- 纯视觉 DeepSeek V4.1 Flash（本机 API 复现）: 63.8%

---

## 2. 一句话结论
**RAG 对"概念型"题有效（SLAKE +3.5）、对"看图判断"题无效甚至有害（VQA-RAD -12 → 加门控后 -1.7）；
定位失败（占 M5 错误的 57%）必须靠"病灶级 grounding + 几何判定"，文本层增强（改提示词/RAG/检测器先验）全部实测无效。**

---

## 3. 已完成实验与结果

### 3.1 DeepSeek V4.1 Flash 上 RAG 的三数据集结果
| 配置 | SLAKE | VQA-RAD | CheXBench |
|---|---:|---:|---:|
| 纯视觉 | 66.67% | 74.1~76.7% | 60.5~60.8% |
| + RAG（教科书） | +0.00 | -10.34 | — |
| + RAG（Wikipedia） | +4.39 | -12.07 | +0.17 |
| **+ RAG（StatPearls 全量 + 门控）** | **+3.51** | **-1.72** | **+0.50** |

三套合计：基线 63.83% → RAG **64.43%（+0.60）**。
关键：语料（StatPearls）和证据门控（标题/正文匹配才给证据）是转折点。

### 3.2 五种检索方法对比（hit@5，top-5 是否覆盖题目概念）
| 方法 | Wiki 语料 | StatPearls 全量 |
|---|---:|---:|
| BM25 | 71.9% | 70.4% |
| BM25+去重 | 71.9% | **70.9%** |
| 概念查询重写 | 50.6% | 59.6% |
| PRF 伪相关反馈 | 48.1% | 65.7% |
| GraphRAG-lite（概念图扩展） | 54.9% | 53.6% |
结论：**朴素 BM25+去重最强**；38% 的题是定位题，检索再多知识也用不上。

### 3.3 M5（Qwen3.6-Flash 8 工具）190 条错误的分解
| 失败类型 | 条数 | 占比 |
|---|---:|---:|
| 定位（左/右、部位） | 109 | 57.4% |
| 存在性 yes/no | 50 | 26.3% |
| 严重度分级（mild/severe） | 16 | 8.4% |
| 整体正常/异常 | 11 | 5.8% |
| 细节存在性 | 9 | 4.7% |
| 其他 | 6 | 3.2% |

定位题内部：M5 预测 B 200 次 vs A 120 次（位置偏置），ref=A 时准确率 53.4%、ref=B 时 78.6%。
109 个定位错误里 61 个调用过 `xray_phrase_grounding`，但框没有被当坐标用。

### 3.4 P0 / P1 / P3（全部实测，均未奏效）
| 实验 | 设计 | 结果 |
|---|---|---|
| P0 去位置偏置 | 317 道定位题：字母作答 vs 先答 left/right 再映射 | 65.6% → 66.6%（+1.0，不显著） |
| P1 RAG on yes/no | 238 道 CheXBench yes/no，StatPearls+门控 | 79.7% → 75.2%（**-2.5**） |
| P3 检测器融合 | 232 道 yes/no，torchxrayvision 概率作文本先验 | 79.7% → 78.9%（**-0.8**） |
| P3 检测器单独 | 23 道具体征象 yes/no | 73.9%（与 VLM 持平，信息互补） |

### 3.5 MedSAM 测量（实验室服务器）
- 解剖先验框 → 分割 → 测量：严重度 AUC 0.29~0.57（无信号）
- Grad-CAM 框 → 分割：AUC **0.688**（弱信号，n=18）
- 结论：**MedSAM 只做分割，指标（CTR/Cobb/面积比）是几何代码；CTR 需要"心影+胸廓"两个掩膜**

### 3.6 配对裁剪（两轮）
| 方案 | 准确率 |
|---|---:|
| Qwen2.5-VL 框 + Qwen2.5-VL 判断（40 题） | 42.5% vs M5 55.0% |
| Qwen2.5-VL 框 + **qwen3.6-flash 判断**（288 题） | **47.6%** vs M5 66.0% |
| 交换顺序后 | 45.6% |
| 两次一致率 | 36.5%（一致子集准确率仅 40.4%） |
结论：劣质框 + 位置偏置 = 完全不可用。**MAIRA-2 框才是决定性变量，尚未验证。**

---

## 4. 基础设施状态

### 4.1 实验室服务器（双 3090，免费，长期可用）
- 主机 `10.60.147.117:22`，用户 `imss`
- **本机 Windows 直连会因 Meta TUN 抢路由失败，必须绑定 WLAN 网卡接口**，见 `medrax_work/remote.py`
- 工作目录：`/home/imss/cw/radiology_rag_p3/`
- 已部署：
  - torchxrayvision 1.5.7（env `mineru`），已跑 567 张图 → `detector_probs.json`
  - MedSAM（wanglab/medsam-vit-base，375MB，transformers SamModel）→ `medsam_measure.json`
  - 配对裁剪全部素材：`crops/`（576 张）、`crop_boxes.json`
  - Qwen2.5-VL-7B 权重在 `/home/imss/688/python学习/Qwen_/models/`
- **无外网**（pypi/GitHub 不通），依赖和权重全靠本机上传

### 4.2 AutoDL
- 旧实例 `connect.weste.seetacloud.com:26853`（CPU，已欠费/待释放）
  - 数据盘 225G/156G，含 MAIRA-2（14G bf16）、CheXagent-8B、hf_full 等
  - MAIRA-2 路径：`/root/autodl-tmp/medrax_r55_top4_full848/models/f70-persistent-41248/maira2/`
- 新克隆实例 `connect.weste.seetacloud.com:32922`（RTX 6000D 85G）
  - **克隆不完整**：数据盘只给了 50G，`medrax_r55_top4_full848` 为空，**MAIRA 权重没有过来**
  - 系统盘有 miniconda（python3.12），外网仅国内可达（baidu 200，HF 000）
  - 需要：要么重新克隆（数据盘 ≥200G），要么在实例上从 ModelScope 重新下 MAIRA-2

### 4.3 本机 Windows
- 工作区 `C:\Users\cheng\Documents\deepseek-harness\default-workspace`
- 代理 `127.0.0.1:7897`（访问 GitHub/HF/pypi 必须走它）
- 已下 MAIRA-2 分片到 `H:/RAG_KB/maira2`（**注意：之前有截断问题，已改用 100MB 分块 Range 校验下载**）

---

## 5. 数据与权重位置
| 内容 | 位置 |
|---|---|
| 三数据集题目/图片 | 本机 `rag_eval/data/`、`H:/RAG_KB/images/` |
| 语料 | `H:/RAG_KB/corpus_full.jsonl`（47 万条，StatPearls+教科书） |
| BM25 索引 | `H:/RAG_KB/bm25_full.pkl`（541MB） |
| 检测器输出 | `results/detector_probs.json`（567 图 × 18 类） |
| M5 逐题轨迹 | `H:/RAG_KB/qwen8_m5/flash_m5_*.jsonl`（从 GitHub 拉） |
| M5 报告 | `reports/r55_autodl_qwen8_20261116/` @ commit 39c5988 |

---

## 6. 待办（优先级）
1. **让 MAIRA-2 跑起来**：重新克隆（数据盘 200G）或在 32922 实例上下载（ModelScope 国内快）
2. **293 道定位题的真实配对裁剪实验**：MAIRA 框 → 裁剪 → qwen3.6-flash 判断（脚本已写好，见 code/）
3. 若配对裁剪仍 <66%，直接上 **自训 CXR 定位检测器**（VinDr-CXR 训练 YOLOv8/RT-DETR，3090 足够）
4. MedSAM 侧：补"第二掩膜"做真 CTR/Cobb，而不是单框近似
5. 最终目标：把验证有效的 RAG 只接进"概念型"子流程，冲 M5 的 77.59%

---

## 7. 踩过的坑（务必看）
1. **Windows 上连实验室服务器必须绑定 WLAN 接口**（IP_UNICAST_IF），否则 banner 读不到
2. **Git Bash 会把绝对路径参数转换**（`/home/...` → `C:/Program Files/Git/home/...`），
   用 `MSYS2_ARG_CONV_EXCL='*' python medrax_work/remote.py put ...`
3. **ModelScope 大文件长连接会被掐断**，必须 100MB 分块 Range + 尺寸校验，否则"下载完成"其实是截断
4. **SFTP 大文件（>20MB）偶发 ENOENT**，分 20MB 片上传最稳（实测 4.18MB/s）
5. **AutoDL SSH 每条命令都可能掉线**，要"一条命令一个连接 + 重试"
6. **HF 上 microsoft/maira-2 是 gated**，ModelScope 有同款无需审批
7. **配对实验必须做顺序互换 + 一致性过滤**，否则位置偏置会污染结论

---

## 8. 复现命令
```bash
# 实验室服务器（本机执行）
MSYS2_ARG_CONV_EXCL='*' python medrax_work/remote.py put <local> /home/imss/cw/radiology_rag_p3/<name>
python medrax_work/remote.py cmd "cd /home/imss/cw/radiology_rag_p3 && nohup /home/imss/miniconda3/envs/mineru/bin/python <script>.py > <log> 2>&1 &"

# RAG 评测（本机，走 API）
RAG_INDEX=H:/RAG_KB/bm25_full.pkl RAG_RETRIEVAL=rag_eval/rank_bm25_dedup_full.json \
  RAG_PROMPT=criteria RAG_GATE=1 python rag_eval/vlm_eval.py --dataset slake --arm both --workers 6 --out res_slake.json
```
