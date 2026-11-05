# SLAKE 与 VQA-RAD 胸片问答四组比较

VQA-RAD 上，M 相对直接作答净增 15 题（+12.93 个百分点），配对图像 bootstrap 的 95% 区间为 +4.76 至 +22.12。SLAKE 上，M 与 X 各净增 1 题，C 净减 5 题。两套数据分别评分。VQA-RAD 的 M 是本轮唯一一个相对 D 的区间完全在零以上的比较。

## 样本与评分

- **SLAKE-English-CXR-Closed** 从 BoKelvin/SLAKE 的官方测试划分筛出英文、胸部 X 光、闭合式题目，保留 114 题与 30 张原图。发布版本为 `a9083ce6c34ac3ffb17671a605962924d8a8f9e9`，CC BY 4.0。原论文的独立 114 题清单未取得，本次题目 ID 以公开清单为准。 [数据清单](slake/data_manifest.json) · [原始题目与图像](slake/inputs.jsonl) · [参考答案](slake/references.jsonl)
- **VQA-RAD-CXR-Closed** 从 OSF 官方 `test_freeform` / `test_para` 测试划分筛出闭合式胸片题。107 张标为 CHEST 的图像经过模态复核，最终闭合式比较为 116 题与 58 张原图，开放式题目单列。数据源 CC0 1.0。 [数据清单](vqarad/data_manifest.json) · [原始题目与图像](vqarad/inputs.jsonl) · [参考答案](vqarad/references.jsonl)

主模型实际返回标识均为 `qwen3.7-plus`。四组共用原图、图号绑定和题目，温度 0.2、`top_p=0.95`、`enable_thinking=false`，单次输出最多 2,048 token。关闭技能、记忆、同病例多题上下文与额外病史。题目保留官方短答案形式。各数据集四组完成后才读取独立参考答案。评分接受裸 `answer` / `reason` JSON，只对 `answer` 做 NFKC、大小写、标点、空白规范化和 `true/false` 映射后的整串匹配。缺答留在完整分母。图像是可用的聚类单位，配对百分位区间使用 10,000 次重采样，种子 20261105。 [协议](../../../configs/cxr_vqa_toolsets_protocol.json) · [运行代码](../../../experiments/run_cxr_vqa_toolsets.py) · [评分代码](../../../experiments/score_cxr_vqa_toolsets.py)

| 数据集 | 组 | 正确 / 总题 | 准确率 | 缺答 | 纠正 / 误改 | 净增 | 相对 D 百分点（95% 区间） |
|---|---|---:|---:|---:|---:|---:|---:|
| SLAKE | D | 104/114 | 91.23% | 0 | 0 / 0 | 0 | 基线 |
| SLAKE | M | 105/114 | 92.11% | 1 | 6 / 5 | +1 | +0.88［−3.60, +5.66］ |
| SLAKE | C | 99/114 | 86.84% | 0 | 2 / 7 | −5 | −4.39［−9.62, 0.00］ |
| SLAKE | X | 105/114 | 92.11% | 1 | 4 / 3 | +1 | +0.88［−3.64, +5.39］ |
| VQA-RAD | D | 84/116 | 72.41% | 1 | 0 / 0 | 0 | 基线 |
| VQA-RAD | M | 99/116 | 85.34% | 0 | 16 / 1 | +15 | +12.93［+4.76, +22.12］ |
| VQA-RAD | C | 86/116 | 74.14% | 1 | 5 / 3 | +2 | +1.72［−2.91, +6.67］ |
| VQA-RAD | X | 90/116 | 77.59% | 0 | 9 / 3 | +6 | +5.17［−0.96, +11.86］ |

纠正是 D 未得分而工具组得分，误改反之。VQA-RAD `791` 的 D 回答内容与参考一致，代码围栏导致格式缺答。M、C、X 均恢复了这题的合法输出，其余纠正分别为 15、4、8 题。C 在 VQA-RAD `166` 输出不合法的首轮计划。SLAKE M 的 `12416` 是计划格式缺答，X 的 `12271` 是最终格式缺答，两题均计入各自误改。 [SLAKE 逐题变化](slake/changes.jsonl) · [VQA-RAD 逐题变化](vqarad/changes.jsonl)

## 流程、工具使用与案例

- **D** 每题一次原图直答。**M** 让同一主模型在最多四次主模型调用中自行选择最多两项工具，可提前结束。适配版提供 8 项注册工具，RoentGen 未接入。VQA-RAD 的 M 用了 70 次 CheXagent、22 次分割，LLaVA-Med 的 15 次选择均失败，MAIRA-2 另有 3 次失败。SLAKE 修复版 M 的选择以 CheXagent 72 次、分类器 32 次、分割 26 次为主。VQA-RAD `650` 中，CheXagent 给出肯定回答，分类器给出较高的心纵隔增大分数，M 最终与参考一致。VQA-RAD `185` 是 M 唯一误改，发生在未选工具的首轮。 [SLAKE M 配置](slake/runtime_m_repaired.json) · [VQA-RAD M 配置](vqarad/runtime.json) · [650 号调用](vqarad/calls/M/vqarad_650.json)
- **C** 迁移了 CXRAgent `0514b4897fd040ae2c32cf2f2cdc163a1144a06c` 的导演、原图 EDV 和按需专家复核流程，同一主模型承担这些角色。预算内配置六个已验证工具，正式题只选择 MedGemma、CheXagent、MAIRA-2，另三项 LLaVA-Rad、LLaVA-Med、MedVLM-R1 在可选菜单中。SLAKE 63 题走 EDV，其中 13 题再复核。VQA-RAD 为 40 题、11 题。MedGemma 在 SLAKE 有 4 次失败（3 次 tokenizer 读取、1 次 CUDA 非法内存访问），在 VQA-RAD 有 1 次 tokenizer 读取失败。VQA-RAD `394` 的 EDV 拒绝了与参考矛盾的 MedGemma 返回，复核后保住正确答案。`104` 中 EDV 同意 CheXagent 的结论，最终与参考不符。 [SLAKE C 配置](slake/runtime_c_ready.json) · [VQA-RAD C 配置](vqarad/runtime_c_ready.json) · [394 号调用](vqarad/calls/C/vqarad_394.json) · [104 号调用](vqarad/calls/C/vqarad_104.json)
- **X** 迁移两轮工具机制，使用 CXAS 解剖定位、保留坐标的裁剪和可选本地 Qwen 知识查询。体位门控与测量独立计数。OpenCXR 识别 PA 且旋转为零后，才用 CXAS 掩膜计算心胸比、左右肺面积对数比及气管相对胸廓中线偏移。几何规则为本地适配，策略没有经过原论文的 SFT 或 GRPO。SLAKE 有 74 次区域解析，84 次进入测量，80 次返回有效量化。VQA-RAD 有 53 次区域解析、2 次裁剪，80 次进入测量，75 次返回有效量化。SLAKE 未选择知识查询。VQA-RAD 三次正式知识查询均以 `backend_exit_-4` 退出，标准错误为空。隔离双卡验证曾用 192.46 秒生成 96 token，但两套正式成绩均无成功知识返回。VQA-RAD `1355` 的 X 纠正发生于 AP 图像，提供了解剖区域，没有返回心胸比。 [SLAKE X 配置](slake/runtime_x_ready.json) · [VQA-RAD X 配置](vqarad/runtime_x_ready.json) · [1355 号调用](vqarad/calls/X/vqarad_1355.json)

SLAKE `12303` 的 M 和 X 都把 D 的错答改成参考答案。`12498` 三个工具组都纠正。`12046` 的 C 和 X 都把 D 的正确答案改成 `heart`。这些对照可复核每题使用的工具和返回。各组的提示、调用数、调度和可用工具共同变化，因而配对差异归属于运行的整个流程。区间按图像处理同图多题，跨数据集泛化仍需更多独立样本。 [12303 号 X 调用](slake/calls/X/slake_12303.json) · [12498 号 M 调用](slake/calls/M/slake_12498.json) · [12046 号 C 调用](slake/calls/C/slake_12046.json)

## 资源与恢复记录

| 数据集 | 组 | 主模型调用 | 输入 / 输出 token | 可选 / 自动工具 | 缓存命中 | 新后端尝试 | 逐题时间（分钟） | 费用代理（CNY） |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| SLAKE | D | 114 | 134,150 / 4,290 | 0 / 0 | 0 | 0 | 4.83 | 0.588080 |
| SLAKE | M | 257 | 766,946 / 11,011 | 143 / 0 | 13 | 130 | 38.65 | 3.199916 |
| SLAKE | C | 253 | 525,979 / 18,432 | 63 / 0 | 7 | 56 | 29.92 | 2.325100 |
| SLAKE | X | 228 | 644,368 / 9,325 | 74 / 198 | 157 | 115 | 21.43 | 2.689372 |
| VQA-RAD | D | 116 | 124,798 / 4,334 | 0 / 0 | 0 | 0 | 5.21 | 0.551200 |
| VQA-RAD | M | 240 | 643,578 / 10,198 | 122 / 0 | 9 | 113 | 31.87 | 2.696688 |
| VQA-RAD | C | 207 | 370,598 / 13,367 | 40 / 0 | 8 | 32 | 18.98 | 1.642796 |
| VQA-RAD | X | 232 | 582,208 / 8,856 | 58 / 196 | 110 | 144 | 23.87 | 2.435104 |

时间为已保存逐题耗时之和。工具 worker 的计算时间另记，SLAKE M/C/X 分别约 870、782、326 秒，VQA-RAD 分别约 696、370、551 秒，均按首次执行的记录汇总。真实生成、模型前向和 OpenCXR 推理分列在机器可读结果中。主模型费用代理按每百万输入 token 4 CNY、输出 12 CNY 核算，SLAKE 四组 8.802468 CNY，VQA-RAD 四组 7.325788 CNY。实际 Credits 与 GPU 货币成本未知。初版 SLAKE M 另有 114 次主模型调用，代理 0.715868 CNY，单列于主表之外。修复版沿用先前保存的 D。 [SLAKE 指标](slake/summary.json) · [VQA-RAD 指标](vqarad/summary.json) · [初版 M 修订](../controller_amendment.md)

SLAKE 修复版 M 与 VQA-RAD C 曾在共享账本争用时于发送前退出，随后等待锁并从原运行续跑，复用已有付费回复。SLAKE X 在 101 题后报共享账本读取错误。`12496` 的第 1 次回复已保存，第 2 次只有请求文件且未占用计数器或预留金额。锁内复查时账本可读，从原运行恢复并复用第 1 次回复，随后完成 114 题。读取异常根因尚未确定。Qwen 本地部署先修复文本输入结构，随后因 512 token 配置触发 780 秒超时而在正式运行前缩为最多 96 token，使用同一官方 FP8 revision `97f5941bf617e31c5e237364a8602ce3f03a551a`。 [SLAKE X 恢复记录](slake_x_recovery.json) · [SLAKE 12496 号调用](slake/calls/X/slake_12496.json) · [SLAKE X 完成记录](slake/complete_X.json) · [VQA-RAD X 完成记录](vqarad/complete_X.json)

每套公开证据含按组的逐题预测、调用请求与响应、工具选择及缓存、原始工具返回、失败信息和衍生图。请求中的内嵌图像以相对链接表示，保留原始字节并复用已有公开原图。发布清单列出本次新增文件。 [SLAKE 证据](slake/) · [VQA-RAD 证据](vqarad/) · [导出代码](../../../experiments/export_cxr_vqa_toolsets.py)
