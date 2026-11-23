set -u
R=/root/autodl-tmp/medrax_m5_rrsi_acc_ttl_v4_20261119
S=/root/autodl-tmp/medrax_m5_data_rsi_8tools_300_20261118_plus

echo "=== KEEP candidates (code / config / small results / logs) ==="
for p in \
  "$R/configs" "$R/source" "$R/deployment" "$R/deployment.json" "$R/deployment.zip" \
  "$R/evidence" "$R/integration_inputs" "$R/prepared" "$R/process-checks" \
  "$R/run/code" "$R/run/initial" "$R/run/frozen.json" \
  "$R/run_parallel_20261120/code" "$R/run_parallel_20261120/initial" "$R/run_parallel_20261120/frozen.json" \
  "$R/v6_pilot_20261120/source" "$R/v6_pilot_20261120/trusted" "$R/v6_pilot_20261120/confirmation_input" \
  "$R/m5_rrsi_dev50_val100_test848_v5/source" "$R/m5_rrsi_dev50_val100_test848_v5/test" \
  "$R/m5_rrsi_dev50_val100_test848_v5/data" "$R/m5_rrsi_dev50_val100_test848_v5/upstream" \
  "$R/m5_rrsi_dev50_val100_test848_v5/experiment.json" "$R/m5_rrsi_dev50_val100_test848_v5/resolved_config.json" \
  "$R/m5_rrsi_dev50_val100_test848_v5/controller.log" \
  "$S/configs" "$S/experiments" "$S/artifacts/native_driver" ; do
  [ -e "$p" ] && du -sh "$p"
done

echo
echo "=== DROP candidates (bulk artifacts) ==="
for p in \
  "$R/dev" "$R/interim_validation" "$R/validation100" "$R/run/search" "$R/run/runtime_audit" \
  "$R/run_parallel_20261120/search" "$R/run_parallel_20261120/runtime_audit" \
  "$R/v6_pilot_20261120/validation100" "$R/v6_pilot_20261120/events" "$R/v6_pilot_20261120/gateway_audit" \
  "$R/gateway_audit" "$R/cpu-rootfs" "$R/cpu-rootfs002" \
  "$R/m5_rrsi_dev50_val100_test848_v5/dev" "$R/m5_rrsi_dev50_val100_test848_v5/interim_validation" \
  "$S/artifacts" ; do
  [ -e "$p" ] && du -sh "$p"
done
