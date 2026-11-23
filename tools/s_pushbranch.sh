set -u
export GIT_SSH_COMMAND="ssh -i /root/.ssh/medrax_deploy_key -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=20"
KEY=/root/.ssh/medrax_deploy_key
chmod 600 "$KEY"
. /etc/network_turbo >/dev/null 2>&1

W=/dev/shm/rrsi_push
BR=archive/rrsi-20261119-21
rm -rf "$W"; mkdir -p "$W"; cd "$W"
git init -q
git config user.email "agent@local"
git config user.name "RRSI archiver"
git remote add origin git@github.com:cw462/MedRAX-reproduction.git

mkdir -p "artifacts/rrsi_20261119_20261121"
tar -xzf /dev/shm/rrsi_code_results_20261119_20261121.tar.gz -C artifacts/rrsi_20261119_20261121

cat > artifacts/rrsi_20261119_20261121/README.md <<'EOF'
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
EOF

git add -A
git commit -q -m "archive: RRSI 2026-11-19..21 code, configs and results

Runtime bulk (~45G: dev/, interim_validation/, validation100/, search/,
rootfs snapshots in evidence/ and process-checks/) is intentionally excluded.
See artifacts/rrsi_20261119_20261121/README.md."

echo "=== pushing $(git count-objects -vH | grep size-pack) ==="
T0=$(date +%s)
timeout 600 git push origin "HEAD:refs/heads/$BR" 2>&1 | tail -8
echo "push rc=$? elapsed=$(( $(date +%s) - T0 ))s"

echo
echo "=== verify remote ref ==="
LOCAL_SHA=$(git rev-parse HEAD)
REMOTE_SHA=$(timeout 60 git ls-remote origin "refs/heads/$BR" | awk '{print $1}')
echo "local  $LOCAL_SHA"
echo "remote $REMOTE_SHA"
[ "$LOCAL_SHA" = "$REMOTE_SHA" ] && echo "VERIFIED: branch exists on GitHub with matching sha" || echo "MISMATCH"
