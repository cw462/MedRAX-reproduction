# Qwen3.6-Flash M5 CerebraFusionMemory 历史实验分析

三个方法的正式逐题判分来自各自的原始归档。CheXBench 内的 SLAKE 子集有 123 题，独立评测的 SLAKE 有 114 题。

## 成绩与子集

| 方法 | CheXBench | SLAKE benchmark | VQA-RAD | 合计 |
| --- | --- | --- | --- | --- |
| M5 8 tools | 451/618 | 108/114 | 99/116 | 658/848 |
| ReAct 8 tools | 431/618 | 94/114 | 87/116 | 612/848 |
| M5 11 tools | 436/618 | 106/114 | 93/116 | 635/848 |

M5 八工具整体比同批八工具 ReAct 多答对 46 题（+5.42 个百分点），比前一批十一工具 M5 多答对 23 题（+2.71 个百分点）。两组 M5 来自不同日期的运行，十一工具批次有模型服务切换记录。配对差异体现各历史运行的整体结果。

| 方法 | CheXBench 子集 | 正确 | 错误 | 总数 | 准确率 |
| --- | --- | --- | --- | --- | --- |
| M5 8 tools | Rad-ReStruct | 79 | 36 | 115 | 68.70% |
| ReAct 8 tools | Rad-ReStruct | 76 | 39 | 115 | 66.09% |
| M5 11 tools | Rad-ReStruct | 78 | 37 | 115 | 67.83% |
| M5 8 tools | SLAKE | 120 | 3 | 123 | 97.56% |
| ReAct 8 tools | SLAKE | 113 | 10 | 123 | 91.87% |
| M5 11 tools | SLAKE | 114 | 9 | 123 | 92.68% |
| M5 8 tools | OpenI | 252 | 128 | 380 | 66.32% |
| ReAct 8 tools | OpenI | 242 | 138 | 380 | 63.68% |
| M5 11 tools | OpenI | 244 | 136 | 380 | 64.21% |

## 工具调用

| 子集 | 总调用 | 成功 | 失败 | 每题平均 | 主模型调用 | 同题重复工具 | 同题完全重复 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Rad-ReStruct | 186 | 186 | 0 | 1.6174 | 344 | 2 | 0 |
| SLAKE | 123 | 123 | 0 | 1.0 | 334 | 4 | 0 |
| OpenI | 703 | 693 | 10 | 1.85 | 1129 | 66 | 0 |
| CheXBench 合计 | 1012 | 1002 | 10 | 1.6375 | 1807 | 72 | 0 |
| SLAKE benchmark | 109 | 108 | 1 | 0.9561 | 306 | 2 | 0 |
| VQA-RAD benchmark | 157 | 154 | 3 | 1.3534 | 332 | 0 | 0 |
| 全部 848 题 | 1278 | 1264 | 14 | 1.5071 | 2445 | 74 | 0 |

| 子集 | 0 次 | 1 次 | 2 次 | 3+ 次 |
| --- | --- | --- | --- | --- |
| Rad-ReStruct | 0/1 (0.00%) | 28/44 (63.64%) | 49/68 (72.06%) | 2/2 (100.00%) |
| SLAKE | 28/28 (100.00%) | 68/71 (95.77%) | 20/20 (100.00%) | 4/4 (100.00%) |
| OpenI | 7/11 (63.64%) | 79/128 (61.72%) | 106/159 (66.67%) | 60/82 (73.17%) |
| CheXBench 合计 | 35/40 (87.50%) | 175/243 (72.02%) | 175/247 (70.85%) | 66/88 (75.00%) |
| SLAKE benchmark | 19/19 (100.00%) | 78/83 (93.98%) | 9/10 (90.00%) | 2/2 (100.00%) |
| VQA-RAD benchmark | 9/10 (90.00%) | 49/55 (89.09%) | 41/51 (80.39%) | 0/0 (—) |
| 全部 848 题 | 63/69 (91.30%) | 302/381 (79.27%) | 225/308 (73.05%) | 68/90 (75.56%) |

每格为正确数/该档题数。调用计 services/tool_selections/R49-AGENT 的逐题回执，缓存命中也计一次。成功取 completed，失败取 failed，均为执行状态。正常返回空定位的调用计执行成功。主模型次数取正式判分的 main_calls，CSV 另列归档请求数和响应数。同题重复工具计某工具首调之后的每次调用。同题完全重复以工具、目标图像、原始参数识别，信息不全时使用执行缓存键。跨题缓存命中另列。调用档位由模型按题选择，各档准确率同时反映题目组成。

| 工具 | Rad-ReStruct | SLAKE | OpenI |
| --- | --- | --- | --- |
| chest_xray_expert | 0/0/0 | 3/3/0 | 155/155/0 |
| llava_med_qa | 0/0/0 | 0/0/0 | 10/10/0 |
| medgemma | 0/0/0 | 0/0/0 | 0/0/0 |
| llava_rad | 0/0/0 | 0/0/0 | 0/0/0 |
| medvlm_r1 | 0/0/0 | 0/0/0 | 0/0/0 |
| maira2_grounded_report | 113/113/0 | 92/92/0 | 238/235/3 |
| xray_phrase_grounding | 73/73/0 | 28/28/0 | 290/289/1 |
| roi_crop | 0/0/0 | 0/0/0 | 10/4/6 |

每格为总调用/成功/失败。

## 记忆检索、注入与库增长

| 数据范围 | 检索尝试 | 完成 | 命中 | 注入 | 显式提及 | top node 数 | 写入回执项数 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Rad-ReStruct | 115 | 115 | 114/115 (99.13%) | 114/115 (99.13%) | 1/114 (0.88%) | 342 | 790 |
| SLAKE | 123 | 123 | 123/123 (100.00%) | 123/123 (100.00%) | 0/123 (0.00%) | 369 | 1200 |
| OpenI | 380 | 380 | 380/380 (100.00%) | 380/380 (100.00%) | 0/380 (0.00%) | 1140 | 2520 |
| CheXBench 合计 | 618 | 618 | 617/618 (99.84%) | 617/618 (99.84%) | 1/617 (0.16%) | 1851 | 4510 |
| SLAKE benchmark | 114 | 114 | 114/114 (100.00%) | 114/114 (100.00%) | 1/114 (0.88%) | 340 | 1080 |
| VQA-RAD benchmark | 116 | 116 | 115/116 (99.14%) | 115/116 (99.14%) | 0/115 (0.00%) | 345 | 990 |
| 全部 848 题 | 848 | 848 | 846/848 (99.76%) | 846/848 (99.76%) | 2/846 (0.24%) | 2536 | 6580 |

命中指检索回执至少返回一条记忆。注入用归档主模型请求中的完整文本核实。显式提及指标匹配主模型步骤中的 Context Note 或直接指向检索记忆的短语，供定位人工复核。实际采用率留空。每题的 top node ID 去重之后按范围累加。

显式提及样本为 chexbench_rad_restruct_0210、slake_12046。

| 采集库 | 终态节点 | 终态边 | 运行前创建且留存的节点 | 运行前创建且留存的边 | 运行期间创建且留存的节点 | 运行期间创建且留存的边 | 记忆模型调用 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| chexbench | 2204 | 10307 | 7 | 0 | 2197 | 10307 | 1686 |
| slake | 728 | 1624 | 7 | 0 | 721 | 1624 | 335 |
| vqarad | 903 | 1151 | 7 | 0 | 896 | 1151 | 330 |

写入项数解析回执中的 Ingested N items，明确跳过计零。全量共有 658 道题报告写入，190 道报告跳过。节点与边按终态快照的创建时间回溯。只有终态时间和最后写入回执的 UTC 时间可按整时区偏移对齐时才计算。窗口按每个数据集的执行顺序独立切为 30 题，保留末尾不足 30 题的窗口。CSV 给出窗口准确率及截至当窗已创建且终态仍留存的节点和边，并附 CheXBench 各子集按其出现顺序划分的窗口。子集构成随运行顺序变化，窗口准确率包含这种差异。

**chexbench**　1–30 26/30（86.67%） · 31–60 27/30（90.00%） · 61–90 16/30（53.33%） · 91–120 15/30（50.00%） · 121–150 30/30（100.00%） · 151–180 28/30（93.33%） · 181–210 29/30（96.67%） · 211–240 30/30（100.00%） · 241–270 14/30（46.67%） · 271–300 23/30（76.67%） · 301–330 25/30（83.33%） · 331–360 19/30（63.33%） · 361–390 23/30（76.67%） · 391–420 19/30（63.33%） · 421–450 21/30（70.00%） · 451–480 16/30（53.33%） · 481–510 18/30（60.00%） · 511–540 17/30（56.67%） · 541–570 23/30（76.67%） · 571–600 21/30（70.00%） · 601–618 11/18（61.11%）

**slake**　1–30 27/30（90.00%） · 31–60 30/30（100.00%） · 61–90 27/30（90.00%） · 91–114 24/24（100.00%）

**vqarad**　1–30 28/30（93.33%） · 31–60 25/30（83.33%） · 61–90 25/30（83.33%） · 91–116 21/26（80.77%）

## 逐题配对

| 基线 → M5 8 tools | 范围 | 纠正 | 误改 | 共同错 | 共同对 |
| --- | --- | --- | --- | --- | --- |
| ReAct 8 tools → M5 8 tools | chexbench / Rad-ReStruct | 10 | 7 | 29 | 69 |
| ReAct 8 tools → M5 8 tools | chexbench / SLAKE | 9 | 2 | 1 | 111 |
| ReAct 8 tools → M5 8 tools | chexbench / OpenI | 64 | 54 | 74 | 188 |
| ReAct 8 tools → M5 8 tools | chexbench / ALL | 83 | 63 | 104 | 368 |
| ReAct 8 tools → M5 8 tools | slake / SLAKE benchmark | 15 | 1 | 5 | 93 |
| ReAct 8 tools → M5 8 tools | vqarad / VQA-RAD benchmark | 22 | 10 | 7 | 77 |
| ReAct 8 tools → M5 8 tools | ALL / ALL | 120 | 74 | 116 | 538 |
| M5 11 tools → M5 8 tools | chexbench / Rad-ReStruct | 6 | 5 | 31 | 73 |
| M5 11 tools → M5 8 tools | chexbench / SLAKE | 8 | 2 | 1 | 112 |
| M5 11 tools → M5 8 tools | chexbench / OpenI | 40 | 32 | 96 | 212 |
| M5 11 tools → M5 8 tools | chexbench / ALL | 54 | 39 | 128 | 397 |
| M5 11 tools → M5 8 tools | slake / SLAKE benchmark | 5 | 3 | 3 | 103 |
| M5 11 tools → M5 8 tools | vqarad / VQA-RAD benchmark | 12 | 6 | 11 | 87 |
| M5 11 tools → M5 8 tools | ALL / ALL | 71 | 48 | 142 | 587 |

配对以 question_id 为键，并核对题干、选项和参考答案。纠正和误改均以 M5 8 tools 为目标方向。逐题 CSV 保留前后终答、正式判分和原文件位置。

## 错题与可改进环节

| 主分类 | 已证实的观察 | 待人工确认 | 代表题 |
| --- | --- | --- | --- |
| 工具未调用 | 3 | 0 | chexbench_rad_restruct_0221、chexbench_openi_0295 |
| 工具选择或参数不适配 | 8 | 0 | chexbench_openi_0069、chexbench_openi_0257 |
| 工具结果与参考不一致 | 2 | 11 | chexbench_openi_0239、chexbench_openi_0274 |
| 参考一致的工具证据与终答不一致 | 1 | 0 | slake_12011 |
| 工具冲突 | 2 | 0 | vqarad_481、vqarad_791 |
| 无关记忆注入 | 0 | 1 | slake_11971 |
| 左右侧错误 | 95 | 0 | chexbench_openi_0003、slake_12447 |
| 选项绑定错误 | 1 | 0 | chexbench_openi_0309 |
| 其他已定位问题 | 2 | 2 | chexbench_rad_restruct_0210、chexbench_rad_restruct_0214 |
| 待人工确认 | 0 | 62 | chexbench_openi_0297、chexbench_openi_0322 |

正式错题 190 道，其中 114 道具有可核对的主分类观察，76 道主分类待人工确认。共 6 道错题未调用工具，若同题有优先级更高的证据，则归入该证据的类别。每题计入一个主分类。已证实表示可从档案核对的行为、标签分歧或原轨迹支持的机制。零调用题只证实调用次数。工具答案与参考一致只证明本题档案中的标签或证据一致性。主分类优先保留有直接证据的选项绑定、工具冲突、证据未进入终答和工具操作问题，再记录侧别及零调用。次要信号保留在逐题 JSON 中。可直接定位到工具操作、冲突处理、取证后终答、选项绑定或格式恢复环节的已证实错题共 14 道，按主分类去重。修补后能挽回的题数仍需实测。

### 代表性轨迹

- **chexbench_rad_restruct_0210 · 其他已定位问题**　格式恢复要求仅输出 JSON。两次作答间无新工具，原始正文中的选项 B 变成终答 A。 终答 A. no，参考 B。
  - 检索建议　[Context Note] Similar tasks have combined broad visual assessment with targeted grounding for common conditions, then verified against multiple anatomical criteria before concluding absence. One approach that worked treated even minor or incidental findings as positive evidence to avoid false negatives.
  - 工具回执　maira2_grounded_report（completed）、xray_phrase_grounding（completed）。
- **chexbench_rad_restruct_0214 · 其他已定位问题**　格式恢复时由参考一致的 yes 改成 A，原始轨迹显示使用的是同一钙化肉芽肿证据。 终答 A，参考 B。
  - 检索建议　[Context Note] Similar tasks have benefited from combining direct visual inspection with specialized detection tools, since subtle or incidental findings can be easy to overlook. One approach that worked involved treating any tool-flagged abnormality as positive evidence rather than dismissing it as clinically insignificant.
  - 工具回执　maira2_grounded_report（completed）、xray_phrase_grounding（completed）。
- **chexbench_rad_restruct_0221 · 工具未调用**　逐题归档的工具次数为 0，且无工具选择回执。是否加工具可纠正待验证。 终答 A，参考 B。
  - 检索建议　[Context Note] Similar tasks have combined direct visual inspection with automated detection tools, treating agreement between empty tool outputs and clean visual reads as strong evidence for a negative answer.
  - 工具回执　0 次调用。
- **chexbench_openi_0003 · 左右侧错误**　参考与终答的膈肌侧别相反。两个候选驱动短语分别返回框，无法单凭出框判定侧别。 终答 A，参考 B。
  - 检索建议　[Context Note] Similar tasks have benefited from first establishing image orientation and then comparing each hemidiaphragm independently before synthesizing a judgment. One approach that worked was corroborating a suspected elevation with secondary signs rather than relying on a single region's appearance.
  - 工具回执　maira2_grounded_report（completed）、xray_phrase_grounding（completed）、xray_phrase_grounding（completed）。
- **chexbench_openi_0069 · 工具选择或参数不适配**　ROI 调用用像素坐标传入要求归一化的框，原始回执为 invalid_box。 终答 A，参考 B。
  - 检索建议　[Context Note] Similar tasks have benefited from confirming image orientation markers before assigning laterality to findings. One approach that worked involved identifying anatomical landmarks first to distinguish left from right in ambiguous cases.
  - 工具回执　roi_crop（failed）、maira2_grounded_report（completed）。
- **chexbench_openi_0239 · 工具结果与参考不一致**　CheXagent 给出与参考相反的 B，求解器明确采用 B。影像上的正确侧别待阅读确认。 终答 B，参考 A。
  - 检索建议　[Context Note] Similar tasks have benefited from delegating specialized visual analysis to a domain-specific expert tool before validating results through independent anatomical reasoning. One approach that worked involved cross-checking an expert's conclusion against standard anatomical priors to confirm laterality.
  - 工具回执　chest_xray_expert（completed）。
- **chexbench_openi_0257 · 工具选择或参数不适配**　ROI 调用返回 invalid_box，随后未取得可判定导管侧别的局部结果。 终答 A. right indwelling catheter，参考 B。
  - 检索建议　[Context Note] Similar tasks have benefited from first confirming image orientation and anatomical landmarks before assigning laterality to any device. One approach that worked involved tracing the entry point and trajectory of radio-opaque lines to establish which side the catheter occupies.
  - 工具回执　roi_crop（failed）、maira2_grounded_report（completed）、llava_med_qa（completed）。
- **chexbench_openi_0274 · 工具结果与参考不一致**　唯一的 CheXagent 回答右基底肺不张，终答沿用，与参考的左侧相反。影像待复核。 终答 B，参考 A。
  - 检索建议　[Context Note] Similar tasks have benefited from delegating specialized visual analysis to a domain-specific expert tool, then validating the result through independent anatomical reasoning. One approach that worked involved cross-checking the expert's localization against standard anatomical priors before finalizing the answer.
  - 工具回执　chest_xray_expert（completed）。
- **chexbench_openi_0295 · 工具未调用**　逐题归档的工具次数为 0，且无工具选择回执。是否加工具可纠正待验证。 终答 A，参考 B。
  - 检索建议　[Context Note] Similar tasks have benefited from first confirming image orientation and laterality conventions before localizing pathology to specific zones. One approach that worked involved systematically checking relevant anatomical regions to determine whether the queried region matches the abnormal findings.
  - 工具回执　0 次调用。
- **chexbench_openi_0309 · 选项绑定错误**　格式恢复后终答 A，理由仍明确描述 B 对应的左下叶肺不张。 终答 A，参考 B。
  - 检索建议　[Context Note] Similar tasks have benefited from confirming image orientation and laterality conventions before localizing described pathology to specific zones. One approach that worked involved systematically checking relevant anatomical regions to determine whether queried findings match observed abnormalities.
  - 工具回执　0 次调用。
- **slake_11971 · 无关记忆注入**　建议强调判断有无异常，题目要求在心和肺之间选出异常器官。结构化取证有用，二元有无判断这部分的相关性待人工确认。 终答 lung，参考 Heart。
  - 检索建议　[Context Note] Similar tasks have benefited from gathering structured evidence via a grounded analysis tool before committing to a binary verdict. One approach that worked was confirming the tool report explicitly stated presence or absence of abnormalities before answering.
  - 工具回执　maira2_grounded_report（completed）。
- **slake_12011 · 参考一致的工具证据与终答不一致**　MAIRA-2 明确报告右侧 PICC 并提供定位框，终答用无急性病变回答是否有任何异常。 终答 No，参考 Yes。
  - 检索建议　[Context Note] Similar tasks have benefited from invoking a grounded analysis tool to obtain structured findings before committing to a binary judgment. One approach that worked involved cross-validating tool-derived evidence with direct visual inspection to confirm any detected abnormality.
  - 工具回执　maira2_grounded_report（completed）。
- **slake_12447 · 左右侧错误**　参考选项与终答选项的差异为患者左右侧，按冻结参考核实。 终答 right，参考 Left。
  - 检索建议　[Context Note] Similar tasks have benefited from first establishing image orientation via any available markers or standard conventions, then comparing bilateral symmetric structures to spot which side deviates.
  - 工具回执　maira2_grounded_report（completed）。
- **vqarad_481 · 工具冲突**　主模型明确指出结构化报告和短语定位不一致，最终以定位术语更针对为由裁决。 终答 Yes，参考 No。
  - 检索建议　[Context Note] Similar tasks have combined a specialized expert tool's primary assessment with a grounded coordinate-level report to confirm or refute the finding. One approach that worked involved cross-referencing multiple evidence sources and grounding the conclusion in explicit tool output language.
  - 工具回执　maira2_grounded_report（completed）、xray_phrase_grounding（completed）。
- **vqarad_791 · 工具冲突**　概述报告与可疑短语指向不一致，终答采用候选定位并声称看到胸膜线。 终答 yes，参考 No。
  - 检索建议　[Context Note] Similar tasks have combined direct visual inspection with automated analysis tools and corroborated findings against prior comparable analyses before concluding. One approach that worked involved matching observed visual features against known radiological hallmarks and grounding the final answer in explicit tool output language.
  - 工具回执　maira2_grounded_report（completed）、xray_phrase_grounding（completed）。

190 道错题涉及 312 次工具调用，其中 274 次可读取工具指向的原始输出。逐题工具回执、检索返回、注入请求成员路径、主模型步骤、最终答案及参考答案见 error_cases.jsonl。服务缓存输出的具体文件类型及成员路径见 raw_output_kind 和 raw_output_source。

## 来源与版本

- MedRAX-reproduction 八工具发布 commit 39c598862713f730c0710054e4f74e842b263531。[GitHub 发布目录](https://github.com/cw462/MedRAX-reproduction/tree/39c598862713f730c0710054e4f74e842b263531/reports/r55_autodl_qwen8_20261116)
- 八工具发布回执 H:\MedRAX_Experiment_Artifacts\r55_autodl_qwen_8tools_20261116_001\publication.completed.json。M5 运行实现 R55-Qwen-eight-tools，来源实现 R55-M5-full848-choice-and-open-text。CerebraFusionMemory 固定 revision 078e18cb6153fdc5b888308349cb6771eb7bde8f。本地源码 H:\MedRAX_Experiment_Artifacts\r55_autodl_qwen_8tools_20261116_001\source\flash\code\experiments、H:\MedRAX_Experiment_Artifacts\r55_autodl_qwen_8tools_20261116_001\source\flash\flash_react\code 与 H:\MedRAX_Experiment_Artifacts\r55_autodl_qwen_8tools_20261116_001\source\bin\r55_memevolve_driver_official.py。
- 十一工具源运行 r55_autodl_four_20261115_001，实现修订为 R55-top4-full848-CheXagent8B-Flash-Tongji。八工具运行清单将其 M5 标为 donor，禁用 medret、reflect、verify。十一工具扩展工具代码来自 SkeMex commit a640474590e384669dd71b657c441264beef73d2。其余代码成员由各目录的 archive.completed.json 列出。
- 本地 MedRAX-reproduction 工作副本 C:/Users/cheng/MedRAX_github 的 HEAD 为 3f51cc6247fa5bba552aa943cbca24313c8f1aae。历史来源版本来自归档运行清单和发布回执。
- 取证对照 C:\Users\cheng\RSI_8TOOLS\RSI_E1_mechanism_validation_20261122\source\Qwen36_RSI_key_questions.csv 和 C:\Users\cheng\RSI_8TOOLS\failure_analysis\QWEN\failure_attribution.csv。前者用于对照八工具逐题判分，后者用于定位已有人工案例。

| 方法 | 数据集 | 归档路径及逐题判分成员 |
| --- | --- | --- |
| M5 8 tools | chexbench | H:\MedRAX_Experiment_Artifacts\r55_autodl_qwen_8tools_20261116_001\dataset-archives\flash\M5\chexbench\evidence.tar.gz::flash/generation/M5/chexbench/analysis/per_question.json |
| M5 8 tools | slake | H:\MedRAX_Experiment_Artifacts\r55_autodl_qwen_8tools_20261116_001\dataset-archives\flash\M5\slake\evidence.tar.gz::flash/generation/M5/slake/analysis/per_question.json |
| M5 8 tools | vqarad | H:\MedRAX_Experiment_Artifacts\r55_autodl_qwen_8tools_20261116_001\dataset-archives\flash\M5\vqarad\evidence.tar.gz::flash/generation/M5/vqarad/analysis/per_question.json |
| ReAct 8 tools | chexbench | H:\MedRAX_Experiment_Artifacts\r55_autodl_qwen_8tools_20261116_001\dataset-archives\flash\ReAct\chexbench\evidence.tar.gz::flash/flash_react/react/chexbench/per_question.json |
| ReAct 8 tools | slake | H:\MedRAX_Experiment_Artifacts\r55_autodl_qwen_8tools_20261116_001\dataset-archives\flash\ReAct\slake\evidence.tar.gz::flash/flash_react/react/slake/per_question.json |
| ReAct 8 tools | vqarad | H:\MedRAX_Experiment_Artifacts\r55_autodl_qwen_8tools_20261116_001\dataset-archives\flash\ReAct\vqarad\evidence.tar.gz::flash/flash_react/react/vqarad/per_question.json |
| M5 11 tools | chexbench | H:\MedRAX_Experiment_Artifacts\r55_autodl_four_20261115_001\dataset-archives\M5\chexbench\evidence.tar.gz::medrax_r55_top4_full848/r55_autodl_four_20261115_001/generation/M5/chexbench/analysis/per_question.json |
| M5 11 tools | slake | H:\MedRAX_Experiment_Artifacts\r55_autodl_four_20261115_001\dataset-archives\M5\slake\evidence.tar.gz::medrax_r55_top4_full848/r55_autodl_four_20261115_001/generation/M5/slake/analysis/per_question.json |
| M5 11 tools | vqarad | H:\MedRAX_Experiment_Artifacts\r55_autodl_four_20261115_001\dataset-archives\M5\vqarad\evidence.tar.gz::medrax_r55_top4_full848/r55_autodl_four_20261115_001/generation/M5/vqarad/analysis/per_question.json |

- chexbench 原执行顺序、配置及工具菜单 H:\MedRAX_Experiment_Artifacts\r55_autodl_qwen_8tools_20261116_001\dataset-archives\flash\M5\chexbench\evidence.tar.gz::flash/generation/M5/chexbench/manifest.json。记忆库 H:\MedRAX_Experiment_Artifacts\r55_autodl_qwen_8tools_20261116_001\dataset-archives\flash\M5\chexbench\evidence.tar.gz::flash/generation/M5/chexbench/storage/cerebra_fusion_memory/cf_database.json。记忆模型用量 H:\MedRAX_Experiment_Artifacts\r55_autodl_qwen_8tools_20261116_001\dataset-archives\flash\M5\chexbench\evidence.tar.gz::flash/generation/M5/chexbench/analysis/memory_usage.json。
- chexbench 十一工具运行配置 H:\MedRAX_Experiment_Artifacts\r55_autodl_four_20261115_001\dataset-archives\M5\chexbench\evidence.tar.gz::medrax_r55_top4_full848/r55_autodl_four_20261115_001/manifests/M5/chexbench.json。
- slake 原执行顺序、配置及工具菜单 H:\MedRAX_Experiment_Artifacts\r55_autodl_qwen_8tools_20261116_001\dataset-archives\flash\M5\slake\evidence.tar.gz::flash/generation/M5/slake/manifest.json。记忆库 H:\MedRAX_Experiment_Artifacts\r55_autodl_qwen_8tools_20261116_001\dataset-archives\flash\M5\slake\evidence.tar.gz::flash/generation/M5/slake/storage/cerebra_fusion_memory/cf_database.json。记忆模型用量 H:\MedRAX_Experiment_Artifacts\r55_autodl_qwen_8tools_20261116_001\dataset-archives\flash\M5\slake\evidence.tar.gz::flash/generation/M5/slake/analysis/memory_usage.json。
- slake 十一工具运行配置 H:\MedRAX_Experiment_Artifacts\r55_autodl_four_20261115_001\dataset-archives\M5\slake\evidence.tar.gz::medrax_r55_top4_full848/r55_autodl_four_20261115_001/manifests/M5/slake.json。
- vqarad 原执行顺序、配置及工具菜单 H:\MedRAX_Experiment_Artifacts\r55_autodl_qwen_8tools_20261116_001\dataset-archives\flash\M5\vqarad\evidence.tar.gz::flash/generation/M5/vqarad/manifest.json。记忆库 H:\MedRAX_Experiment_Artifacts\r55_autodl_qwen_8tools_20261116_001\dataset-archives\flash\M5\vqarad\evidence.tar.gz::flash/generation/M5/vqarad/storage/cerebra_fusion_memory/cf_database.json。记忆模型用量 H:\MedRAX_Experiment_Artifacts\r55_autodl_qwen_8tools_20261116_001\dataset-archives\flash\M5\vqarad\evidence.tar.gz::flash/generation/M5/vqarad/analysis/memory_usage.json。
- vqarad 十一工具运行配置 H:\MedRAX_Experiment_Artifacts\r55_autodl_four_20261115_001\dataset-archives\M5\vqarad\evidence.tar.gz::medrax_r55_top4_full848/r55_autodl_four_20261115_001/manifests/M5/vqarad.json。

## 已知缺失

- 检索回执保留 top node IDs，未找到逐题种子与新增邻居的明细。扩展数量留空。写入回执项数可能含更新或合并，终态创建时间只能重建仍留存的节点和边。精确净增长缺少逐时点库原件。
- 实际采用率需要可核实的策略采用标注。显式提及、返回与注入分别记录。工具技术失败、工具语义与参考分歧以及临床正确性各有独立证据要求。
- 十一工具发布 Git commit 未找到可靠回执。其归档运行 ID、代码成员、M5 donor 关系和逐题正式判分可定位。
- 工具回执未保存或未指向可读取的原始输出时，raw_output 留空，并保留可定位的服务回执或缓存结果。
- CSV 空白与 JSON null 表示缺失或该行不适用。工具计数的零表示该工具确无调用。
