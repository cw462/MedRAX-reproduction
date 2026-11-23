# MAIRA-2 定位实验：阴性结果（2026-11-23）

接续 `HANDOFF.md` 待办 #1 / #2。结论一句话：**MAIRA-2 的 grounding 框对 CheXBench 定位题是噪声（≈50%），
配对裁剪实验的前提不成立，不必再做。**

## 0. 环境打通（此前卡住的部分）

| 问题 | 解决 |
|---|---|
| 数据盘 50G 已 100% 满、只剩 200K | 权重放 `/dev/shm`（46G 内存盘），不占磁盘 |
| HF 不通 / ModelScope 单流 1.6 MB/s | `source /etc/network_turbo` 后 8 并发达 **74 MB/s** |
| MAIRA-2 权重缺失 | ModelScope `microsoft/maira-2` 拉到 `/dev/shm/maira2`，27.53 GB / 270 s，24 文件尺寸校验全过 |
| transformers 未装 | `transformers==4.51.3`（模型卡要求 `>=4.48,<4.52`）+ `protobuf>=7.36`（sentencepiece 的 proto 版本冲突） |
| 图片集 | 冻结输入 tar 解出 CheXBench 493 张图（OpenI 363 / Rad-Restruct 115 / SLAKE） |

模型加载 12 s，显存 13.8 GB（bf16），推理 0.49 s/题（grounding）/ 1.44 s/图（报告生成）。

## 1. 题目口径

CheXBench 618 题里有 **291 道是"同一病灶、不同侧/不同叶"的二选一**（例：`left indwelling catheter`
vs `right indwelling catheter`），选项 A/B 顺序已随机、gold 平衡（186 A / 180 B，always-A 50.8%）。
另有 29 道上下叶型、46 道严重度型。

标签自检：本口径的 gold 字母与旧实验 `p0_side_result.json` 的 `ref` **286/286 完全一致**，
与 `res_chexbench_base.json` 的 `reference` **291/291 一致**。所以下面的差异不是标签问题。

## 2. 实验一：phrase grounding 框 → 质心判左右（失败）

对每题取"去掉方位词的公共短语"（如 `base pulmonary atelectasis`）做 MAIRA-2 phrase grounding，
取最大框的质心：`cx<0.5` 判患者右侧，否则左侧。

| 口径 | n | 出框率 | 准确率 |
|---|---:|---:|---:|
| 全部定位题 | 366 | 63.7% | 43.8% |
| 左右型 | 291 | 61.5% | **49.7%** |
| 上下叶型 | 29 | 86.2% | 52.0% |

两种左右约定都试过（49.7% / 50.3%），都是随机水平。按框大小分层（w<0.15 到 0.35–0.5）
准确率 45.5%~54.5%，没有"小框更准"的趋势。

**同一批 177 题上：MAIRA 50.3%，M5 71.8%。**

进一步验证框本身有没有意义 —— 拿 MAIRA 自己的报告当参照：

| 检验 | 结果 |
|---|---|
| 框的左右 == 同一张图 MAIRA 报告里说的左右 | **55.2%**（n=67） |
| 心脏框质心位置 | 在图像右半（mean cx=0.581, 11/14），说明图像方向是**标准位**，不存在"图像翻转"问题 |

框与模型自己的文字判断都对不上，说明**框是噪声，不是方向约定或图像翻转的问题**。

## 3. 实验二：接地报告生成 → 读左右（有信号但覆盖不足）

改用受过训练的 `format_and_preprocess_reporting_input(get_grounding=True)` 生成接地报告，
在与目标病灶同句里抽 left/right。

| 口径 | 覆盖 | 覆盖内准确率 |
|---|---:|---:|
| 左右型（宽松） | 123/291 (42.3%) | 70.7% |
| 左右型（严格：同句单一侧） | 43/291 (14.8%) | 69.0% |
| 上下叶型 | 8/29 | 87.5% |

**覆盖不足的根因**：291 张图里 **207 张** MAIRA 只吐出"正常"模板（"The lungs are clear. No mass. 
No nodule. No adenopathy."），压根没提目标病灶。它对导管类还能说对（indwelling catheter 69.1%，
n=55），对 atelectasis / diaphragm 大面积报正常。

## 4. 实验三：报告信号 + M5 逐题答案混合

规则：报告明确给出目标病灶的单一侧 → 用报告；否则沿用 M5 原答案（`p0_side_result.json` 的 `predA`）。

| 方案 | 覆盖率 | 覆盖内准确率 | 混合后（286 题） | 相对 M5 |
|---|---:|---:|---:|---:|
| 仅严格 | 42/286 (14.7%) | 69.0% | 66.4% | +1.4 |
| 严格 + 双框 | 43/286 (15.0%) | 69.8% | 66.4% | +1.4 |
| 含宽松 | 98/286 (34.3%) | 72.4% | **66.8%** | **+1.7** |

M5 在这 286 题上 65.0%；按组先验（leave-one-out）只有 54.0%；纯视觉 DeepSeek 52.6%。

两者不一致时报告明显更准（报告 66.7% vs M5 33.3%，n=12），但样本太小。

## 5. 结论与影响

1. **MAIRA-2 不是定位题的决定性变量** —— 两种用法（框、报告）都不足以超过 M5。
2. **配对裁剪实验（MAIRA 框 → 裁剪 → qwen3.6-flash 判断）前提不成立**：框与模型自身判断只有 55% 一致，
   在噪声框上裁剪只会重演 47.6% 的失败，不必再花 API 预算。
3. **定位题的天花板被数据本身限制**：标签来自报告文本而非图像标注，207/291 图 MAIRA 认为"正常"；
   组先验就有 54%，说明相当一部分题靠"哪侧更常见"即可答对。
4. CheXBench 定位子集的真实提升空间，小于"57% 错误都是定位题"字面暗示的空间。

## 6. 复现

```bash
# 实例上（connect.weste.seetacloud.com:32922）
source /etc/network_turbo
python /root/maira2_dl_parallel.py /root/maira2_sizes.json /dev/shm/maira2   # 270s
python /root/mk_tasks_maira.py                    # -> /dev/shm/lat_tasks_maira.json (366)
python /root/maira_ground.py                      # -> /dev/shm/maira_boxes.json  (0.49s/题)
python /root/score_maira_side.py                  # 框 → 左右
python /root/maira_report.py                      # -> /dev/shm/maira_reports.json (1.44s/图)
python /root/score_maira_report.py                # 报告 → 左右
```

本地脚本：`code/maira2_dl_parallel.py`、`code/mk_tasks_maira.py`、`code/maira_ground.py`、
`code/maira_report.py`、`code/score_maira_side.py`、`code/score_maira_report.py`。

产物：`results/maira2_20261123/`（任务表、框、报告、两份逐题评分）。

## 7. 建议的下一步
按证据强度排序：

1. **先量化定位题的可解性上限** —— 抽 50 题人工看原图判左右，得到人类上限。
   若人类也只有 80%，那这 291 题最多再拿 15 分，不值得投自训检测器。
2. **只对"报告能说清楚"的 98 题做路由**（+1.7 已在手上），其余保持 M5 原流程，风险最低。
3. 自训 CXR 检测器（VinDr-CXR + YOLO/RT-DETR）只在第 1 步证明人类上限足够高时才值得做。
4. 真正没被验证、且更可能有大收益的方向：**yes/no 细节存在性题**（M5 错误 26.3%）、
   严重度分级（8.4%），这两个子集的标签噪声比定位题小。

## 8. 人类上限：两条无人工捷径都走不通（2026-11-23 补）

想省掉人工判读，先后试了两种统计捷径，**都无效**，记下来避免重复：

### 捷径 A：把 MAIRA 的报告当"独立读片者"

| 分层 | 覆盖 | MAIRA 报告准确率 |
|---|---:|---:|
| M5 答对的题 | 42% | **83.3%** |
| M5 答错的题 | 42% | **47.6%** |

表面上很像"标签歧义"，但这是**分层选择效应**：任何与 M5 相关的读者都会自动呈现这个
不对称（M5 答对的题，它答对的概率天然更高）。这个对比里完全没有对照组。

### 捷径 B：判别测试——"MAIRA 答错时是否正好落在 M5 的选择上"

结果是 `m5_wrong` 层 22/22 = **100%**，`m5_right` 层 0/13 = 0%。看上去干净得可疑，
实际是**结构性恒等式，不含任何信息**：

> 题目是二选一。M5 选错 ⇒ 正确项是 M5 选项的补集。
> 此时 MAIRA 若也错，只能选那个补集的补集 = M5 的选项。没有第三个可能。

同理 `m5_right` 层必然 0%。两个数字都被题目结构锁死，与标签质量无关。

**结论**：n 选二的标签，无法用另一个二选一读片者来定标。要么人工，要么找一个
准确率显著高于 65% 的独立读者（目前没有）。人工判读是唯一可行路径。

### 捷径 C：查 CheXBench 官方是否公布过人类基线

`StanfordAIMI/chexbench` 在 HF 上是 **gated（manual approval）**，要求提供 CITI 培训证书，
并逐项同意 bimcv-covid19 / mimic-cxr / padchest / candid-ptx 的 DUA。匿名读取返回
"Access to dataset ... is restricted"，`README.md` 与 `data.json` 均不可见。
因此拿不到官方人类基线数字，也没法用官方划分复核我们这 291 题的口径。

（反过来看，这条也说明：这个 benchmark 的原始图像受多个 DUA 约束，
我们自己这份 OpenI 子集已经是能合法在实例上跑的部分。）


## 9. 人工判读包的设计（`results/human_lat_packet_50.html`）

- **按 M5 对错分层抽样**：25 题 M5 答错 + 25 题 M5 答对。理由：决策关心的是
  "M5 答错的那 35% 里人类能救回多少"，随机抽样回答不了这个问题。
  （第一版随机抽样实测在 50 题上 M5 恰好 74.5%，比全量 65% 高 9.5 分，样本偏简单。）
- **层内左右各半**：13/12 × 2 格。不这么做的话 `m5_wrong` 层会偏向 M5 位置偏置的反面，
  第一版分层抽样出现 9 左 / 41 右，"看不懂就猜多数侧"能拿 82%。
- **键盘作答**：A / B / X（看不出来）直接记到当前屏顶那道题并自动跳下一题。
- 估计方式：`ceiling = 0.35 × h_wrong + 0.65 × h_right`，`h_wrong` 即可回收的错误质量。
- 精度限制：每层 25 题，95% CI 约 ±13 点。结果若落在 75% 判定边界附近，需要第二个包补到 100 题。

