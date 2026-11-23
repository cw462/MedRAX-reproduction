set -u
export GIT_SSH_COMMAND="ssh -i /root/.ssh/medrax_deploy_key -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"
chmod 600 /root/.ssh/medrax_deploy_key
. /etc/network_turbo >/dev/null 2>&1
rm -rf /dev/shm/gh1

echo "=== clone the RRSI report branch (shallow) ==="
timeout 240 git clone -q --depth 1 --single-branch \
  --branch reports/m5-rrsi-s10-val100-20261120 \
  git@github.com:cw462/MedRAX-reproduction.git /dev/shm/gh1 2>&1 | tail -5
echo "clone rc=$?"
echo
echo "=== what is in it ==="
if [ -d /dev/shm/gh1 ]; then
  find /dev/shm/gh1 -type f -not -path '*/.git/*' | wc -l
  du -sh /dev/shm/gh1
  find /dev/shm/gh1 -type f -not -path '*/.git/*' | head -40
fi
