# R47实际操作记录与公开离线复现

本次已完成一次生成、一次完整统一评分、一次证据导出和一次公开证据主比较复现。下面前两组记录本次操作者实际使用的路径，`local_assets`及`D:/...`是本地私有档案位置，不是公共下载链接，也不是第三方必须拥有的盘符。

## 本次实际评分命令

```powershell
python -X utf8 experiments/score_cxr_image_memory_gt_r47.py `
  --frozen local_assets/image_memory_gt_r47_preparation_no_byte_checks/frozen.json `
  --run D:/MedRAX_Experiment_Artifacts/image_memory_gt_r47_20261108/generation `
  --references reports/cxr_vqa_extension/results/chexbench/references.jsonl `
  --out reports/cxr_image_memory_gt_r47_20261108/results `
  --r45-frozen local_assets/image_memory_r45_preparation/frozen.private.json `
  --r45-run D:/MedRAX_Experiment_Artifacts/image_memory_r45_20261108/generation
```

可选R45参数仅打开历史冻结预测／请求档案，没有新R45生成。R47原始generation.exitcode为0，618预测／上下文／反馈及全部205套发送／回复完成后才评分；没有effective recovery。评分先对所有比较臂原始终态做共同显式答案适配，再读参考与反馈内容；M43须机械还原466/618。当前题反馈y按各自事件时间，必须晚于其自身不可覆盖预测保存；后续输入仅可含同图此前前缀。

## 本次实际导出与公开核对命令

```powershell
python -X utf8 experiments/export_cxr_image_memory_gt_r47.py `
  --frozen local_assets/image_memory_gt_r47_preparation_no_byte_checks/frozen.json `
  --run D:/MedRAX_Experiment_Artifacts/image_memory_gt_r47_20261108/generation `
  --scores reports/cxr_image_memory_gt_r47_20261108/results `
  --data reports/cxr_vqa_extension/results/chexbench `
  --reference-dir local_assets/image_memory_gt_r47_preparation_no_byte_checks/reference_vault `
  --health D:/MedRAX_Experiment_Artifacts/image_memory_gt_r47_20261108/health `
  --out reports/cxr_image_memory_gt_r47_20261108/evidence

python -X utf8 experiments/verify_public_cxr_image_memory_gt_r47.py `
  --evidence reports/cxr_image_memory_gt_r47_20261108/evidence `
  --out reports/cxr_image_memory_gt_r47_20261108/public_reproduction
```

导出只按既有publisher白名单保存题干／完整选项、618原预测、上下文、真值事件／独立标签、205套request/started/response/result、75逻辑工具结构及可用raw结果、原图／相关派生图、单次健康探针和job记录。私有路径和凭证字段沿原publisher脱敏，权重、账户秘钥和无关文件不发布。旧488个唯一原图沿仓库已有公开资产复用；来源条款不因本项目代码许可证而被重新许可。

## 第三方便携公开复现

在完整仓库根目录、现有Python依赖环境运行；保留仓库里的原图和M43→M-C41／M来源请求档案。主要使用numpy与现有共同答案适配纯函数，不需要API秘钥，不启动推理、工具或GPU。输出目录必须是新空路径，不能覆盖本次结果。

```powershell
python -X utf8 experiments/verify_public_cxr_image_memory_gt_r47.py `
  --evidence reports/cxr_image_memory_gt_r47_20261108/evidence `
  --out reproduced_r47_public_scores
```

公开验证器先从原始保存回复适配两个比较臂，再读取反馈／参考；核对618题成员与顺序、同图前缀、先预测后反馈、原模型参数、闭合请求、调用上限、原始exit0、微／宏／各子集、纠正／误改／净增及逐题提取一致。用户明确取消的原始运行与公开复现字节／哈希校验保持关闭；不要求脱敏元数据或路径逐字节一致。既有图像存储和工具缓存键未改变。这些语义核对不证明供应商解码或临床解释正确。

公开结果为[public_reproduction/summary.json](public_reproduction/summary.json)，`matches_published_primary_scores_and_extractions=true`。它覆盖M43对M43-IM-GT主比较，**不声称复现可选R45次要比较**。路径展示已被出版器转换，不应把exported evidence作为私有run传回原始scorer；便携复现使用专用public verifier。

[核心记忆／反馈](../../experiments/cxr_image_memory_gt_r47.py) · [准备](../../experiments/prepare_cxr_image_memory_gt_r47.py) · [runner](../../experiments/run_cxr_image_memory_gt_r47.py) · [原始档案评分](../../experiments/score_cxr_image_memory_gt_r47.py) · [导出](../../experiments/export_cxr_image_memory_gt_r47.py) · [公开验证器](../../experiments/verify_public_cxr_image_memory_gt_r47.py) · [离线边界测试](../../tests/test_cxr_image_memory_gt_r47.py) · [实际测试记录](TESTS.md)。

本轮仍是已曝光618题中的在线同图标注反馈设置，历史基线、复用预测、单次采样、跨子集同图和标注重叠使因果与泛化解释受限；不能作为标准闭卷独立题SOTA或临床证明。
