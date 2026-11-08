# R45 归档、有效完成与离线复现

本轮仅执行一次生成、一次统一评分、一次公开导出。已完成结果无需再次付费生成。下面命令用于第三方新输出目录复现；此次发布没有为重复检查而重跑评分。原始预测、旧评分与失败记录保持原样。

## 来源与代码

用户原包 `MedRAX_M43_ImageMemory_Codex_Code_20261108 (1).zip`；原上游8项检查中7项字节匹配，1项仅CRLF/LF差异。未执行包安装器覆盖项目。新增文件名保留原包r44后缀，实际身份R45。

- [分组与记忆](../../experiments/cxr_image_memory_r44.py)
- [无参考准备](../../experiments/prepare_cxr_image_memory_r44.py)
- [冻结顺序runner](../../experiments/run_cxr_image_memory_r44.py)
- [限定已知工具故障恢复](../../experiments/recover_cxr_image_memory_r45.py)
- [统一评分](../../experiments/score_cxr_image_memory_r44.py)
- [公开证据导出](../../experiments/export_cxr_image_memory_r45.py)
- [15项初始离线测试](../../tests/test_cxr_image_memory_r44.py)、[2项恢复边界测试](../../tests/test_cxr_image_memory_r45_recovery.py)

复用仓库已有的作者指标／共同显式答案适配、原M/C41 episode和R43定稿decision；新工具运行目录只改变GPU绑定，不修改旧目录。工具／依赖版本见[冻结协议](PROTOCOL.json)和[run记录](evidence/run.json)。原来源归属及数据条款沿[基础数据说明](../v11/data-provenance.md)与原CheXbench公开输入来源，不由本项目代码许可证重新许可。

## 本次实际评分与完成门槛

私有完整镜像保留生成、health、jobs、recovery及frozen。主轮原始退出1始终保留。有效完成须同时具备：618预测、618memory_context、每条已发送主请求的回复与凭证、逐题6/4或4/2和总644/384预算、所有坏工具恰好对应唯一登记技术空答且其后没有该题新增调用、唯一预期末尾审计错误、恢复controller真实退出0、独立完成凭证及 `generation.effective.exitcode=0`。恢复证明在[evidence/recovery](evidence/recovery)，原始和恢复job记录在[evidence/job_records](evidence/job_records)。job文本日志／退出文件由既有publisher保存为JSON字符串，内容中的原退出码不改；顶层两个评分退出标志为纯文本。

本次实际使用额外的 `--completion-exit .../generation/generation.effective.exitcode --recovery-dir .../recovery`，而非把原始 `generation.exitcode=1` 改成0。`chexbench_slake_0046` 技术空答计0分且仍占618分母。生成完成凭证 `references_read=false`；评分先对所有终态／原样复用档案进行参考无关适配，随后才加载618参考。基线必须机械还原466，否则评分停止。

## 公开离线评分命令

从包含历史依赖证据的完整仓库根目录运行，安装现有Python依赖（本评分主要使用numpy），输出目录必须不存在：

```powershell
python -X utf8 experiments/score_cxr_image_memory_r44.py `
  --frozen reports/cxr_image_memory_r45_20261108/evidence/frozen.public.json `
  --run reports/cxr_image_memory_r45_20261108/evidence `
  --references reports/cxr_image_memory_r45_20261108/evidence/references.jsonl `
  --completion-exit reports/cxr_image_memory_r45_20261108/evidence/generation.effective.exitcode `
  --recovery-dir reports/cxr_image_memory_r45_20261108/evidence/recovery `
  --out reproduced_r45_scores
```

这是0 API的评分；历史M43终态由仓库已有registry及公开档案沿M43→M-C41／原M来源链读取，不能只下载本报告目录。公开frozen中的远端路径已脱敏，评分不依赖其加载图片。复现输出的本地 `archive_call` 路径会随根目录变化，不能据路径差异要求输出逐字节相同。

主指标采用同一共同适配得到的显式答案；字母／选项文本冲突、非终态和技术缺失不从reason或参考解释意图。原M JSON工程合规另报，不能把它当原论文统一要求。实际作者代码版本、指标及未知点见[作者指标对齐报告](../cxr_author_alignment_20261108/README.md)。

## 公开证据与字节保留范围

每题输入／选项／参考、618预测、618memory_context、203条request/started/response/result、72项工具选择及原始结构、8项独立接口探针、原图／相关派生图、失败／恢复记录均在evidence。旧488个唯一有效原图复用已有公开文件；新11个有效PNG与1个坏请求字节流各自保存。坏字节流仅作为原始证据，不补成可解码图。

部分继承的旧工具观察仍含原归档目录层级的相对图像路径。为保持完成记录不变，这些字符串不被事后改写；[历史图像路径别名索引](ARCHIVED_IMAGE_PATH_ALIASES.json)将637种原字符串全部定位到已经公开的仓库图像，没有用当前题原图替换未知来源。新调用的实际image_url以及本轮输入／CASE_INDEX链接独立核对；别名不改变模型输入、答案或评分，文件可定位也不证明供应商已正确解码。

公开元数据沿既有publisher做路径、凭证字段脱敏；这不等于私有元数据的字节相同重放。完整私有流式镜像另留存，导出未发布模型loader缓存、权重及后端数值数组。公开工具可见结构与实际派生图保留；不把未公开数组称为公开原始全量张量。首次流式下载因Windows长路径在模型loader缓存处中断，仅跳过该非实验证据缓存后续传，没有重推理或重评分。

Git可能把新写文本的CRLF规范成LF；发布清单按待提交blob字节计数。图像与坏图字节为二进制原样保留，元数据的脱敏及文本换行变化须与此区别。发布核验只检查本次白名单、必要链接／格式／敏感内容／文件体积和关键提交blob，不扩展成重复运行或额外付费测试。
