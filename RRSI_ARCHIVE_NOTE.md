# RRSI 旧实验归档：已完成（2026-11-23 18:31）

## 状态：**已上传并已验证，45.76 G 已释放**

## 1. 归档位置

GitHub `cw462/MedRAX-reproduction`，新分支：

```
archive/rrsi-20261119-21
commit 3c2cb1dc8613796aefcddc3202c17571fd80754c
```

推送方式：在实例上 `git init` 一个空仓库，直接推到远端**新分支**（不克隆）。
因为不需要下载历史，只上传自己的对象，10 秒完成。
（反方向克隆/拉取在这个网络下会断流：`fetch-pack: unexpected disconnect`。）

## 2. 验证证据

| 检查 | 结果 |
|---|---|
| 远端 branch sha == 本地 commit sha | `3c2cb1d…` 一致（commit sha 覆盖整棵树） |
| 只取 tree 的浅克隆（`--filter=blob:none`） | 远端 932 个文件，本地 932 个 |
| 文件清单 md5 | 两端均为 `2af32a313e07fa3929466ab3f3055b9a` |
| `test848_v5/upstream` | 147 个文件已在仓库内 |

**踩坑记录**：第一次推送时 `test848_v5/upstream` 是个嵌套 git 仓库，被 git 当成 gitlink
（`160000`）提交，内容实际没上传。已删掉内层 `.git` 后 `--amend` + 强推修复，
现在 `git ls-tree -r | grep -c '^160000'` 为 0。

## 3. 删除了什么（合计 45 760 MB）

```
8925 MB  run/search
 315 MB  run/runtime_audit
2105 MB  run_parallel_20261120/search
 323 MB  run_parallel_20261120/runtime_audit
12684 MB v6_pilot_20261120/validation100
1192 MB  v6_pilot_20261120/events
 117 MB  v6_pilot_20261120/gateway_audit
 597 MB  gateway_audit
 213 MB  cpu-rootfs
 280 MB  cpu-rootfs002
11148 MB m5_rrsi_dev50_val100_test848_v5/dev
7861 MB  m5_rrsi_dev50_val100_test848_v5/interim_validation
```

删除脚本对每个路径做了两道断言：必须在 `/root/autodl-tmp/` 下，且不得命中
`artifacts/images` 或 `data_rsi_v2`。

## 4. 保留了什么

- **胸片图集**：`medrax_m5_data_rsi_8tools_300_20261118_plus/artifacts/images`
  （OpenI 755 / SLAKE 159 / VQA-RAD 58，972 个文件，156 MB）——本项目 848 题在用
- `medrax_m5_data_rsi_v2_20261117_plus`（1.6 G，同一批图的副本，留作备份）
- `evidence/`(285 M) 与 `process-checks/`(493 M)：容器 rootfs 快照（site-packages 副本），
  **未归档但也没删**，确认无用后可再释放 778 MB

## 5. 磁盘变化

| | 之前 | 之后 |
|---|---|---|
| `/root/autodl-tmp` | 50G 用满，可用 200K | 33G 已用，**可用 18G** |

顺带把 MAIRA-2 权重从 `/dev/shm` 落到了 `/root/autodl-tmp/maira2`（27.53 GB，24 文件
尺寸校验通过），实例重启不再需要重下。

## 6. 安全

临时放到实例上的 repo 级 deploy key 用完已删除（`rm -f /root/.ssh/medrax_deploy_key`，已确认）。
