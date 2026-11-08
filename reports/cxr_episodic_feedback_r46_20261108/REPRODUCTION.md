# R46公开离线复现与来源

本次源／开发生成、一次统一评分和一次证据导出均已完成。下面是第三方复现命令，使用新空输出目录，不需API；发布未为重复检查而再次评分。

```powershell
python -X utf8 experiments/score_cxr_episodic_feedback_r46.py `
  --source reports/cxr_episodic_feedback_r46_20261108/evidence `
  --data data/slake_episodic_r46 `
  --source-completion-exit reports/cxr_episodic_feedback_r46_20261108/evidence/source.effective.exitcode `
  --source-recovery-jobs reports/cxr_episodic_feedback_r46_20261108/evidence/job_records `
  --out reproduced_r46_scores
```

需完整仓库既有Python依赖及common answer/M4CXR纯函数，主要为Pillow/numpy。新实现为[核心与检索](../../experiments/cxr_episodic_feedback_r46.py)、[源/开发runner](../../experiments/run_cxr_episodic_feedback_r46.py)、[数据准备](../../experiments/prepare_cxr_episodic_feedback_r46.py)、[限定恢复](../../experiments/recover_cxr_episodic_feedback_r46.py)、[评分](../../experiments/score_cxr_episodic_feedback_r46.py)、[导出](../../experiments/export_cxr_episodic_feedback_r46.py)。[原3项信息流测试](../../tests/test_cxr_episodic_feedback_r46.py)与[2项真实不可覆盖恢复回归](../../tests/test_cxr_episodic_feedback_r46_recovery.py)均已完成；第二次discover因导入原fixture共执行5项，不虚构成5个全新回归。

原始数据BoKelvin/SLAKE、revision a9083ce6c34ac3ffb17671a605962924d8a8f9e9、CC-BY-4.0。沿R44固定train12／validation27及排除清单，无新数据选择；[来源manifest](../../data/slake_episodic_r46/manifest.json)、[源输入](../../data/slake_episodic_r46/source_inputs.jsonl)、[每源标签](../../data/slake_episodic_r46/source_labels)、[开发输入](../../data/slake_episodic_r46/inputs.jsonl)和事后[开发参考](../../data/slake_episodic_r46/references.jsonl)均保留。开发参考没有部署到生成服务器，不进入E；source y是源标签而非完整临床报告。

source原始退出1与effective0、recovery job0必须同时理解；不能把单个0标志当全健康原始完成。scorer验证恢复模式、2例4请求未重试声明、完整source/dev的全部四类请求文件、批准E原条目等于原始frozenE、source/approved/hash与实际完成绑定。全部显式答案先做参考无关适配，再打开开发参考，主EM沿M4CXR；没有原M JSON主门槛。技术未知发送不会自动重试。

公开evidence保留78份request/started/response/result，源预测／真值揭示事件／原稿／冻结和批准E、开发预测／检索上下文、原始失败与恢复job证据。IMAGE_MAP将content-addressed base64引用链接到精确20张原始JPEG；按记录media_type把链接字节base64编码即可重建图像URI。未发布key/config/权重。图像二进制字节保留；Git可能将新文本CRLF规范为LF，清单按待提交blob字节计数。来源术语与公共数据许可不会被本项目代码许可证重新许可。

这是一项source/dev E组件比较；开发队列已用过，不是未见测试，也没有独立患者身份保证。R44数据与R46不能合并当独立样本；R45同图无真值记忆和本轮源真值跨图E是不同实验。完整目标最强记录保持原样。
