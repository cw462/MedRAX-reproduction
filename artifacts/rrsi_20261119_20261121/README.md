# RRSI 实验归档（2026-11-19 ~ 2026-11-21）

从 AutoDL 实例 `medrax_m5_rrsi_acc_ttl_v4_20261119` 归档的代码 / 配置 / 结果，
用于释放该实例的数据盘（原 50G 已满）。

## 包含

- `m5_rrsi_acc_ttl_v4_20261119/`：configs、source、deployment、integration_inputs、
  prepared、run/{code,initial,frozen.json}、run_parallel_20261120/、
  v6_pilot_20261120/{source,trusted,confirmation_input}
- `test848_v5/`：source、test、data、upstream、experiment.json、resolved_config.json、controller.log
- `data_rsi_8tools_300_20261118_plus/`：configs、experiments、native_driver

## 未包含（已丢弃）

`evidence/`(285M) 和 `process-checks/`(493M) 是容器 rootfs 快照
（site-packages 副本，5607 个 .py / 818 个 .so / ld-linux.so），非实验结果。
`dev/`、`interim_validation/`、`validation100/`、`search/` 等共约 45G 是运行时中间产物。

胸片图集 `medrax_m5_data_rsi_8tools_300_20261118_plus/artifacts/images`
（OpenI 755 / SLAKE 159 / VQA-RAD 58）**保留在实例上，未归档、未删除**。
