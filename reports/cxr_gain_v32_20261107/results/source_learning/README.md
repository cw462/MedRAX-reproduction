# v3.2共享源学习与审阅证据

69份源请求/回复全部保留，原学习脚本最终化因病例/题号条件不兼容退出1，没有重发。43个结构候选经源内容审核，11张进入最终审阅库（7张未改、4张逐项记录的程序性修订），26份原回复因结构等原因拒绝，32张候选因内容/适用性/模态/工具边界剔除。这是操作方辅助的源库，不宣称完全自动或独立临床认证。

本页费用是一次共享源学习的已知返回用量估算1.439712 CNY，未知用量记录0份；不重复计入每个目标队列。没有共享账本读取或金额上限。原始源数据是既有开发轨迹，隔离范围仅为已披露的像素/可用ID检查。

[源原始输入](source_learning_inputs.json) · [最终隔离清单](source_roster.json) · [原图标签与hash/源提示](source_v2_manifest.json) · [原始源请求回复](calls/) · [候选库](candidate_bank.json) · [冻结审阅库](reviewed_bank.json) · [逐张剔除和修订](source_content_review.json) · [最终化凭证](bank_review.json) · [图像资产](image_assets.json) · [工具预检](tool_preflight.json) · [初次DICOM失败记录](tool_preflight_initial_failed.json) · [实际开发注入核验](dev_verified.json) · [发布白名单](publication_manifest.json)。

卡片的source_evidence和源正确答案仅用于追溯与源学习，目标只可注入条件化行动/避免误推文本。公开文件已脱敏，原始推理库hash仍以[上层运行说明](../../README.md)为准。病例图像与源反馈的原出处及条款沿用[原SkeMex源报告](../../../skemex_tools_v2_20261104/README.md)。源原图通过explicit Figure标签绑定，没有按文件顺序猜时点；混合模态/不合适的候选可拒绝，不将CT或内镜解释冒充CXR发现。
