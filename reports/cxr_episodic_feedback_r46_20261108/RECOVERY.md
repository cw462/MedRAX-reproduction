# R46源阶段真实进度记录故障与限定接续

原源阶段在第2例完成预测、真值反馈、反思和E原稿之后，第二次保存同名source_progress.json触发FileExistsError。既有save使用temp/fsync/os.link发布一次性记录，拒绝覆盖；此处误把它用于可变进度。初始mock允许覆盖，未捕获该问题。它是进度IO缺陷，不是模型答错或医疗工具失败。

原source PID2122022退出1。前2例r44_train_153、r44_train_160的4个真实请求／回复／费用凭证完整闭合，2份预测／反馈／E原稿保留；没有已发送但未知请求，没有第3例的请求。原错误日志、退出1和旧progress(processed=1)不删除、不改成成功。

独立companion recover_cxr_episodic_feedback_r46.py严格验证这一特定前缀：12源的原顺序；只存在前2例的全部请求/started/response/result；完整载荷与原图base64、检索上下文、模型终态、源y、sigma/gamma、source_index及预测早于反馈时序一致；没有开发调用或已完成标志。实际本地和远端0API验证通过。新回归用不可覆盖save重现故障，证明缺回复拒绝接续、只新增余20调用、原记录字节不变、旧progress仍为1且新10份进度事件各自独立。

DeepSeek审阅companion给8/10 ready；其要求的上传与独立恢复启动分支已补齐，付费前再次确认原core/原runner字节未变和远端0API接线。新source_recovery_2 PID2137891从第3例接续，0工具；没有重发前4个请求。新进度写入source_progress_events/0003…0012.json，每个文件只写一次。原推理、检索、真值揭示和反思规则保持不变。

恢复最终实际退出0。全部12源／24发送回复闭合后，首次写入frozen_E.json、source.complete.json，并另写source.effective.exitcode=0；原jobs/source.exitcode=1保留。completion_mode为known_progress_metadata_failure_recovery，并明确2例4请求前缀未重试。source总调用仍24，不是28。后续异常不会被吞成成功；此companion不支持自动通用恢复。

完成评分使用显式`--source-completion-exit .../source.effective.exitcode`，同时核验原source.exitcode1和实际jobs/source_recovery_2.exitcode0；完整开发仍须development.exitcode0。公开复现可通过`--source-recovery-jobs evidence/job_records`定位原job凭证。私有pull把原始phase退出复制到generation供评分，并保留jobs原件，不覆盖原失败。

另有首次SFTP readiness marker写入使用了Paramiko的x模式而缺写权限，形成空标志文件。实际DeepSeek审阅、local readiness与代码比对在源启动前已完成；随后另写verified sidecar，注明其真实写入时间晚于启动，原空文件保留。当前启动helper解析有效readiness JSON，不再以空文件存在冒充批准。该元数据问题未改变模型输入、参考访问时序或预测。

[初始代码审阅](CODE_SOURCE_REVIEW.md)、[实际恢复审阅](RECOVERY_CODE_REVIEW.md)、[实际源E审阅](SOURCE_MEMORY_REVIEW.md)均保留原文与范围。审阅不是临床判图或模型权重证明；故障修复不被计作医学准确率提升。
