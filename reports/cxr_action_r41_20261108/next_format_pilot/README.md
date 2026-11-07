# 已准备的源开发格式修复pilot数据

状态`prepared_not_launched`；12个不同源case_id，各1题/1张原图，患者独立性未核验。全部来自已暴露的源开发库，不是未见测试。尚未实现新runner、尚未部署、付费请求0。

[冻结选择、策略及计数上限](protocol.json) · [生成输入](inputs.jsonl) · [独立参考](references.jsonl) · [完整计划](../../../refine-logs/EXPERIMENT_PLAN.md) · [准备代码](../../../experiments/prepare_cxr_r42_format_pilot.py)。

输入仅含原问题、完整选项、明确Figure绑定与原图；旧答案、参考和已释放轨迹不进入生成输入。参考留在独立文件，runner集成时必须核对实际请求无泄漏。准备代码纯本地处理；启动付费前仍需实现并验证一次修复分支、6/4上限和独立run边界。

从23个合格单图源case_id按预定哈希排序取12个，一例一题。原图按已有SHA核对后原样复制，没有生成或修饰图像。源参考与选项仅做唯一文字匹配校验，不是重新临床标注。原Figure标签保留，不推断时间顺序。重建时必须使用新的输出目录：

```text
python experiments/prepare_cxr_r42_format_pilot.py --out local_assets/new_r42_pilot_copy
```
