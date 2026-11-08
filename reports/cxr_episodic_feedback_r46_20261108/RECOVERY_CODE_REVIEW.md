## 结论

**score: 8 / 10　verdict: ready**（companion 逻辑正确，可在同一冻结 run 接续余下 10 源病例/20 调用；但付费启动前须先补一处部署接线）

**review_completed: true　scope_complete: true**

## 已核实正确（companion 本体）

1. `validate_prefix` 严格限定唯一故障：`jobs/source.exitcode=='1'` 且 log 含 `FileExistsError:…source_progress.json`；`source.complete/frozen_E/source.effective.exitcode` 均不存在；SOURCE/SOURCE_REFLECT 各恰好 2 个 qid、4 文件、started 计数=2；P0/P1 零 started；`progress=={processed:1,last:r44_train_153}`。
2. prefix 重建与真实记录吻合：request 经 `restore`+`payload` 字节级比对两臂完整载荷；contexts==重算 retrieve；prediction 字段==`terminal(响应)`；feedback `y`==源标签且 `reference_revealed_at≥pred.utc`；episode 的 y/σ/γ/source_index/pixel/image_vector/phi/tau/y_hat 全比对；`accepted_structural_fields==valid`。真实 prefix 四份记录与这些断言一致。
3. 接续不重发：从 `source[2:]` 起，`paid.call(ordinal=1)`；`max_retries=0`+`unknown_sent_no_reissue`；started 计数守卫使任何已发请求直接 fail-closed；测试断言 24 次调用且每键计数=1。
4. 核心语义未变：循环体与原 runner 逐行等价，仅 `source_progress.json` 改为独立 `source_progress_events/{0003..0012}.json`；全部写新文件，无不可覆盖冲突；旧 `source_progress.json` 保持 processed=1。
5. 收尾顺序正确：12 例全部闭合→`frozen_E.json`→`source.complete.json`（completion_mode/raw1/前缀2例4请求未重试）→`source.effective.exitcode='0'`（`'x'` 独占写）；`source.exitcode=1` 留存。新异常无 try/except 吞掉，原样抛出停 job。
6. scorer 的 `--source-completion-exit` 走 effective，恢复分支验证 raw1+`jobs/source_recovery_2.exitcode==0`+completion_mode 唯一+不重试字段；`pull_source` 把 raw/effective 与 jobs 退出复制进镜像 generation，修复我上轮指出的评分路径问题。

## 需修复（付费接续前，准确位置）

- `local_assets/deploy_cxr_episodic_feedback_r46.py`：
  - `FILES` 仅 3 个文件，**缺 `recover_cxr_episodic_feedback_r46.py`**，远端不会上传 companion。
  - `modes` 无 `launch_source_recovery_2`；`launch()` 把 CMD 硬编码为原 runner，只写 `jobs/{phase}.exitcode`（仅 source/development）。没有任何路径运行 recover companion 并产生 `jobs/source_recovery_2.exitcode`，而 `score` 与 `pull_source` 都断言该文件==0。
  - 需补：上传 companion + 一个 recovery launch 分支（gate 读 `RECOVERY_REVIEW_READY.json` 且 verdict=ready、`assert not jobs/source_recovery_2.pid`、用 bash wrapper 运行 recover `--execute` 并写 `jobs/source_recovery_2.exitcode`）。

## 可接受局限

- 若 recovery 中途再故障，immutable save 会在首个已写文件上 FileExistsError 停住，需再次诊断——这与"新故障停、不自动补答/重试"一致，非缺陷。
- 真实 prefix 的 gamma 为通用"一致即确认/不一致即报"条件句，非 alwaysYes 泛化，合规。

启动顺序建议：先修 deploy 接线→0API dryrun 复验→写 `RECOVERY_REVIEW_READY.json`→再发 20 次付费调用。
