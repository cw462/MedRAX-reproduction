# R50：R49流程＋CXRAgent六模型工具集＋Skill适用性门控修复

日期：2026-11-09。计划代号 R50；执行前若仓库已有同名实验，使用未占用新编号，不覆盖。唯一新臂建议命名 M43-IM-GT-S50-CXR6。本计划是待执行方案，不表示服务器已经启用或完成推理。

## 1. 依据与目标

R49完整结果：CheXbench465/618（相对M43纠正49/误改50，相对R47纠正45/误改48）；独立SLAKE113/114；VQA-RAD97/116。CheX OpenI退步至270/380。Skill共CREATE6条、最终active5条，均task_level；成功PATCH0，merge1；独立SLAKE/VQA最终库为空。

目标：在相同主模型下提高完整分母正确数，优先减少OpenI定位、侧别、严重程度题的误改，同时提高跨模型证据质量。CheX首先争取超过历史R47的468/618；长期+5pp目标相对M43至少497/618。它们是目标，不是预计收益。宏平均与微平均同时报告。

## 2. 本轮只做两项方法变更

1. 工具菜单仅保留MedGemma-4B、LLaVA-Rad、CheXagent、LLaVA-Med、MAIRA-2、MedVLM-R1六个模型。移除原classifier、report_generator、segmentation、image_visualizer、dicom_processor的可选接口；原图仍正常输入主控。模型动态选用，不固定全调用。
2. 修复skill_lifecycle_r49.retrieve内适用性筛选：`if len(candidates)>5 and prescreen:`改为`if candidates and prescreen:`。沿用现有PRESCREEN，允许返回空列表。不另加知识规则、人工答案、手工Skill库或新的强制复核阶段。

这是一组组合改进，不能把总差值单独归因工具或门控。暂不新增无Skill对照或消融，不重跑已有基线。

## 3. 工具名单

| 接口 | 模型/作用 |
|---|---|
| medgemma | google/medgemma-4b-it，医学视觉问答 |
| llava_rad | microsoft/llava-rad，胸片发现描述/报告 |
| chest_xray_expert | CheXagent，胸片问答 |
| llava_med_qa | LLaVA-Med，医学视觉问答 |
| xray_phrase_grounding | MAIRA-2，当前使用短语定位接口 |
| medvlm_r1 | JZPeterPan/MedVLM-R1，推理型视觉问答 |

MAIRA-2当前接口不等同于完整grounded report generation；六模型身份对齐，不宣称接口和CXRAgent完整实现等价。

复用现有cxr_vqa_extended_backends.py和历史C臂私人runtime中的模型路径、解释器、固定revision。不默认换成MedGemma1.5，不重新实现已有后端。历史记录显示三个工具曾部署过，但本次服务器状态仍需实际确认。

## 4. 保留设置

- 主模型qwen3.7-plus；temperature0.2、top_p0.95、max_output_tokens2048、thinking=false；META继续同主模型。部署时对照实际R49配置，不擅自改模型或采样。
- R49同图反馈机制、原图绑定、先保存预测后读取本题反馈；不读取未来题或当前未提交答案。
- 30题/学习窗口、最多20条学习轨迹、general/task/action三个分支、起始窗口快照固定、新Skill下一窗口生效；每两窗口治理。
- 每题主模型/工具调用总次数不设固定上限；保留有效终答、无进展和技术故障退出规则。
- 保留已完成R49的技术修复，包括MAIRA EOS guard和META schema修复，整轮采用一致已修复版本；记录与R49早期阶段的差异。
- 保留embedding模型text-embedding-v4/1024维及已有缓存规则。不得把缓存命中记作新模型推理，也不强制清空缓存重跑。

## 5. 实施顺序

### A. 零推理配置修改

从真实部署位置取R49 config和历史C臂PRIVATE runtime，不使用GitHub里[REDACTED]路径。运行：

```bash
python enable_r50_cxr6_tools.py --config /actual/r49/config.json --donor-runtime /actual/c/runtime_c_ready.json --out-dir /actual/new/r50_config
```

脚本同时更新M与R49-AGENT（R49启动会从M重建R49-AGENT），保留主模型配置和三个已有模型接口配置；输出新config.json和runtime.json，不覆盖原配置，不自动推理。路径为占位符，Codex使用已有服务器真实路径替换。

应用附带apply_fix.py中的单条件门控修复。新实验使用独立runner/module和ARM名，或在隔离checkout中修改ARM常量；不要改已归档R49代码与预测。检查日志、评分器、导出器使用一致的新臂名；不能只改目录而所有证据仍误标R49。

### B. 最小工具可用性检查

复用原部署环境。每个新增工具只做一次原图加载与推理健康检查，保存模型revision、输入图、输出、耗时和错误；优先使用非本轮计分健康样例。探针不进入Skill库、同图记忆或计分结果。不要重新测试全部旧工具，不建立重复审计/哈希门槛。

若三个工具均有健康结果，运行唯一新臂；若失败，修复具体部署问题并保留记录，不静默将工具剔除后仍称6工具实验。不要占用用户正在训练CT任务的GPU，沿已有调度选择空闲设备。

### C. 唯一新臂正式运行

依次CheXbench618 → 独立SLAKE114 → 独立VQA-RAD116。每组独立空Skill、空同图记忆；沿原始顺序与原图，全部848题新生成。不得用历史答案填充分母，也不得跨数据集导入最终库。

沿实际部署R49启动命令，只替换新runner、新config和新输出目录；API密钥继续原stdin/环境渠道，不写入计划或公开配置。保留每组先完成生成再统一计分。技术中断续跑已保存状态，不重写已完成预测。

本计划不自动增加其他实验臂。正式付费实验仅在执行环境已有相应授权时启动；当前对话交付计划和代码不等于已启动。

## 6. 必须输出的结果

1. 完整分母正确数、微平均、CheX三个子集及等权宏平均；技术终态保留在分母。
2. 与保存的M43/R47/R49逐题对齐：纠正、误改、净增；独立VQA历史100/116臂名为M42。旧直接作答记录若同题同图同主模型则复用对齐，不重跑；缺少可比档案就明确缺失。
3. 首次/单例与同图后续分组；有无Skill注入分组只作描述，不作随机对照。
4. 三个新工具各自选择题数、调用数、新推理/缓存数、错误数；实际0调用就写0，不能仅凭菜单启用认定有效。
5. PRESCREEN请求数、筛选前后候选数、全部拒绝题数、异物Skill在不相关题的注入例子；不得以提高命中率本身为目标。
6. CREATE/PATCH/merge/deprecate/mature实际事件、三分支数量、首产/首用、采用信用及正负例；继续允许零Skill结果，不降低门槛凑产出。
7. 主模型、META、embedding、工具成本/耗时分开，未知成本明确未知。同步输出工具新增前后的重复无进展调用情况。
8. 重点检查OpenI错误、chexbench_slake_0065、openi_0092/0302/0378及VQA回答类型；这些是事后分析切片，不只重跑这些题后拼接总成绩。

## 7. 结果判断

先看完整CheX正确数是否超过468，再看OpenI是否恢复、误改是否减少；宏平均单独记录。SLAKE113/114已接近上限，重点看是否保持；VQA目标先恢复至100/116以上。若整体不升，先分析新工具实际调用与冲突处理，而非自动扩展更多实验。

本轮是R49反馈/Skill流程＋6工具＋筛选修复的项目适配，不是CXRAgent完整复现；没有新增其完整Director/EDV/MDT架构，也不能叫Skill单独因果收益或未见测试SOTA。

## 8. 当前交付状态

配置转换脚本已完成；本地公开模板中6工具已列入M/R49-AGENT；六工具配置检查通过，门控包5项离线测试已通过。服务器实际模型加载、本轮探针、848题正式运行尚未在本对话执行。公开模板含脱敏路径，仅供检查，不能直接运行。

## 本版替代关系
本CXR6版本替代上一份CXR11计划。只运行CXR6新组，不并行运行CXR11。新增和移除工具、门控修复的共同变化必须披露。原始R49 Skill库保持归档，新实验仍空库；旧依赖classifier/report/segmentation的Skill不得导入。
