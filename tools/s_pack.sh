set -u
R=/root/autodl-tmp/medrax_m5_rrsi_acc_ttl_v4_20261119
S=/root/autodl-tmp/medrax_m5_data_rsi_8tools_300_20261118_plus
STAGE=/dev/shm/rrsi_stage
OUT=/dev/shm/rrsi_code_results_20261119_20261121.tar.gz

rm -rf "$STAGE"; mkdir -p "$STAGE"
cd "$STAGE"

copy() {  # copy() <src> <dst-rel>
  if [ -e "$1" ]; then mkdir -p "$(dirname "$2")"; cp -r "$1" "$2"; fi
}

copy "$R/configs"                        m5_rrsi_acc_ttl_v4_20261119/configs
copy "$R/source"                         m5_rrsi_acc_ttl_v4_20261119/source
copy "$R/deployment"                     m5_rrsi_acc_ttl_v4_20261119/deployment
copy "$R/deployment.json"                m5_rrsi_acc_ttl_v4_20261119/deployment.json
copy "$R/deployment.zip"                 m5_rrsi_acc_ttl_v4_20261119/deployment.zip
copy "$R/integration_inputs"             m5_rrsi_acc_ttl_v4_20261119/integration_inputs
copy "$R/prepared"                       m5_rrsi_acc_ttl_v4_20261119/prepared
copy "$R/USER_PAUSED.json"               m5_rrsi_acc_ttl_v4_20261119/USER_PAUSED.json
copy "$R/run/code"                       m5_rrsi_acc_ttl_v4_20261119/run/code
copy "$R/run/initial"                    m5_rrsi_acc_ttl_v4_20261119/run/initial
copy "$R/run/frozen.json"                m5_rrsi_acc_ttl_v4_20261119/run/frozen.json
copy "$R/run_parallel_20261120/code"     m5_rrsi_acc_ttl_v4_20261119/run_parallel_20261120/code
copy "$R/run_parallel_20261120/initial"  m5_rrsi_acc_ttl_v4_20261119/run_parallel_20261120/initial
copy "$R/run_parallel_20261120/frozen.json" m5_rrsi_acc_ttl_v4_20261119/run_parallel_20261120/frozen.json
copy "$R/v6_pilot_20261120/source"       m5_rrsi_acc_ttl_v4_20261119/v6_pilot_20261120/source
copy "$R/v6_pilot_20261120/trusted"      m5_rrsi_acc_ttl_v4_20261119/v6_pilot_20261120/trusted
copy "$R/v6_pilot_20261120/confirmation_input" m5_rrsi_acc_ttl_v4_20261119/v6_pilot_20261120/confirmation_input

T="$R/m5_rrsi_dev50_val100_test848_v5"
copy "$T/source"          test848_v5/source
copy "$T/test"            test848_v5/test
copy "$T/data"            test848_v5/data
copy "$T/upstream"        test848_v5/upstream
copy "$T/experiment.json" test848_v5/experiment.json
copy "$T/resolved_config.json" test848_v5/resolved_config.json
copy "$T/controller.log"  test848_v5/controller.log

copy "$S/configs"                    data_rsi_8tools_300_20261118_plus/configs
copy "$S/experiments"                data_rsi_8tools_300_20261118_plus/experiments
copy "$S/artifacts/native_driver"    data_rsi_8tools_300_20261118_plus/native_driver

echo "=== staged size ==="
du -sh "$STAGE"
find "$STAGE" -type f | wc -l

tar -czf "$OUT" -C "$STAGE" .
ls -lh "$OUT"
